"""Forge RobotDriver 实现。

对外契约（forge_robot.BaseRobotDriver）：
- joint_order
- connect / disconnect
- get_state -> forge_msgs.JointState
- set_command(forge_msgs.JointCommand)

SDK 的 movej_sync 是阻塞式 PTP，因此 set_command 只更新目标，由后台 worker
合并最新目标后下发；这样 Dora 的 tick/action 循环不会被单个动作阻塞。
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Protocol

from forge_msgs import JointCommand, JointState
from forge_robot import BaseRobotDriver

from .codec import (
    ARM_JOINTS,
    GRIPPER,
    JOINT_ORDER,
    clip_arm_positions,
    split_command,
)
from .config import RobotConfig
from .gripper import GripperBackend, make_gripper

logger = logging.getLogger(__name__)


class ArmLike(Protocol):
    """litearm.Arm 的最小接口，便于注入 fake 做无硬件测试。"""

    n: int
    firmware: str

    def connect(self) -> Any: ...
    def close(self) -> None: ...
    def enable(self, attempts: int = 12) -> None: ...
    def disable(self) -> None: ...
    def get_state(self, refresh: bool = False) -> Any: ...
    def movej_sync(self, q: list[float], speed: float = 1.0) -> Any: ...
    def home(self, timeout: float | None = None) -> Any: ...


class _CommandWorker:
    """单线程 + 最新目标合并；旧目标被新目标覆盖，不排队。"""

    def __init__(self, send):
        self._send = send
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._latest: list[float] | None = None
        self.last_error: Exception | None = None
        self._thread = threading.Thread(
            target=self._run, name="litearm-command", daemon=True
        )
        self._thread.start()

    def submit(self, q: list[float]) -> None:
        with self._lock:
            self._latest = list(q)
        self._wake.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            self._wake.wait(timeout=0.1)
            if self._stop.is_set():
                return
            with self._lock:
                target = self._latest
                self._latest = None
                self._wake.clear()
            if target is None:
                continue
            try:
                self._send(target)
                self.last_error = None
            except Exception as error:  # SDK 的超时/被新命令取代都走这里
                self.last_error = error
                logger.warning("movej_sync failed: %s", error)

    def close(self) -> None:
        self._stop.set()
        self._wake.set()
        self._thread.join(timeout=2.0)


class LitearmDriver(BaseRobotDriver):
    def __init__(
        self,
        config: RobotConfig,
        *,
        arm: ArmLike | None = None,
        gripper: GripperBackend | None = None,
    ):
        self.config = config
        self._arm = arm
        self._gripper = gripper if gripper is not None else make_gripper(
            config.gripper
        )
        self._worker: _CommandWorker | None = None
        self._target: dict[str, float] = {}
        self._connected = False

    @property
    def joint_order(self) -> list[str]:
        return list(JOINT_ORDER)

    # ---------------------------------------------------------------- lifecycle

    def connect(self) -> None:
        if self._connected:
            logger.warning("robot already connected")
            return

        if self._arm is None:
            try:
                import litearm as pa
            except ImportError as error:
                raise RuntimeError(
                    "litearm SDK missing; install it from the internal "
                    "litearm-python repository"
                ) from error
            self._arm = pa.Arm(port=self.config.port).connect()

        firmware = str(getattr(self._arm, "firmware", ""))
        if self.config.firmware_prefix and not firmware.startswith(
            self.config.firmware_prefix
        ):
            raise RuntimeError(
                f"unexpected firmware {firmware!r}; expected prefix "
                f"{self.config.firmware_prefix!r}"
            )

        if self.config.enable_on_connect:
            self._arm.enable()

        self._target = dict(zip(ARM_JOINTS, self._read_arm_positions()))
        if self.config.move_to_initial and self.config.initial_position:
            self._target.update(
                clip_arm_positions(self.config.initial_position)
            )
            self._arm.movej_sync(
                self._full_target(), speed=self.config.speed
            )

        self._gripper.connect()
        self._worker = _CommandWorker(self._send_arm_target)
        self._connected = True
        logger.info(
            "litearm connected: firmware=%s joints=%s",
            firmware or "unknown",
            self._arm.n,
        )

    def disconnect(self) -> None:
        if not self._connected:
            return
        try:
            if self.config.move_to_reset_on_disconnect and self.config.reset_position:
                self._target.update(clip_arm_positions(self.config.reset_position))
                self._arm.movej_sync(
                    self._full_target(), speed=self.config.speed
                )
        finally:
            if self._worker is not None:
                self._worker.close()
                self._worker = None
            self._gripper.close()
            self._arm.close()
            self._connected = False
            logger.info("litearm disconnected")

    def stop(self) -> None:
        """停止当前运动；臂保持使能（不下坠），夹爪保持当前力。"""
        if self._worker is not None:
            self._worker.close()
            self._worker = _CommandWorker(self._send_arm_target)
        self._gripper.stop()

    def emergency_stop(self) -> None:
        """急停：先取消下发，再失能。

        注意：臂会失去保持力。若姿态无支撑，请先人工托住。
        固件急停锁存 fault 时，需在 SDK 侧 reset 后才能恢复。
        """
        self.stop()
        if self._arm is not None:
            self._arm.disable()
        logger.error("emergency stop: arm disabled")

    def home(self, timeout: float | None = None) -> None:
        """固件 `home()`（0x2A）回 URDF 零位，固件内固定 0.10 低速。"""
        if not self._connected:
            raise RuntimeError("robot is not connected")
        self._arm.home(timeout=timeout)
        self._target = dict(zip(ARM_JOINTS, self._read_arm_positions()))

    # ------------------------------------------------------------------ state

    def _read_arm_positions(self) -> list[float]:
        state = self._arm.get_state().value
        return [float(joint.q) for joint in state.joints]

    def _full_target(self) -> list[float]:
        missing = [name for name in ARM_JOINTS if name not in self._target]
        if missing:
            raise RuntimeError(f"target cache incomplete: {missing}")
        return [self._target[name] for name in ARM_JOINTS]

    def get_state(self) -> JointState:
        state = self._arm.get_state().value
        if len(state.joints) != len(ARM_JOINTS):
            raise RuntimeError(
                f"expected {len(ARM_JOINTS)} joints, got {len(state.joints)}"
            )

        positions = [float(joint.q) for joint in state.joints]
        velocities = [float(joint.dq) for joint in state.joints]
        efforts = [float(joint.tau) for joint in state.joints]
        names = list(ARM_JOINTS)

        opening = self._gripper.get_opening_m()
        if opening is not None:
            names.append(GRIPPER)
            positions.append(opening)
            velocities.append(0.0)
            efforts.append(0.0)

        return JointState(
            name=names,
            position=positions,
            velocity=velocities,
            effort=efforts,
        )

    # ---------------------------------------------------------------- command

    def set_command(self, command: JointCommand) -> None:
        if getattr(command, "mode", "position") != "position":
            raise ValueError("LiteArm adapter only supports mode='position'")

        arm_updates, gripper_m = split_command(
            list(command.name), list(command.position)
        )
        if not arm_updates and gripper_m is None:
            return

        if arm_updates:
            clipped = clip_arm_positions(arm_updates)
            for name, requested in arm_updates.items():
                if clipped[name] != requested:
                    logger.warning(
                        "clipping %s from %.4f to %.4f rad",
                        name,
                        requested,
                        clipped[name],
                    )
            self._target.update(clipped)
            if self._worker is None:
                raise RuntimeError("robot is not connected")
            self._worker.submit(self._full_target())

        if gripper_m is not None:
            self._gripper.set_opening_m(gripper_m)

        if self.config.debug:
            logger.debug("target=%s gripper=%s", self._target, gripper_m)

    def _send_arm_target(self, q: list[float]) -> None:
        self._arm.movej_sync(q, speed=self.config.speed)
