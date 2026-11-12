"""Forge RobotDriver 实现。

对外契约（forge_robot.BaseRobotDriver）：
- joint_order
- connect / disconnect
- get_state -> forge_msgs.JointState
- set_command(forge_msgs.JointCommand)

SDK 的 movej_sync 是阻塞式 PTP，因此 set_command 只更新目标，由后台 worker
合并最新目标后下发；这样 Dora 的 tick/action 循环不会被单个动作阻塞。

控制面方法（enable、disable、reset、home、stop、emergency_stop）由节点循环的
`control` 扩展输入调用，见 node.py。home 会阻塞十几秒，调用方必须放到工作线程。
"""

from __future__ import annotations

import logging
import math
import threading
from collections.abc import Sequence
from dataclasses import dataclass
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
    def emergency_stop(self) -> None: ...
    def reset(self) -> None: ...


@dataclass(frozen=True)
class RobotStatus:
    """Forge `JointState` 之外的固件状态摘要（用于 `robot_status` 输出）。"""

    enabled: bool
    mode: str
    faulted: bool
    faults: str
    joint_fault: int


def normalize_speed(value: float | None, default: float) -> float:
    """把可选的 0..1 速度倍率规范化；超出上限夹到 1.0。"""
    if value is None:
        return default
    speed = float(value)
    if not math.isfinite(speed):
        raise ValueError(f"speed must be finite, got {value!r}")
    if speed < 0.0:
        raise ValueError(f"speed must be >= 0, got {speed}")
    if speed > 1.0:
        logger.warning("clamping speed from %.3f to 1.0", speed)
        return 1.0
    return speed


class _CommandWorker:
    """单线程 + 最新目标合并；旧目标被新目标覆盖，不排队。"""

    def __init__(self, send):
        self._send = send
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._latest: tuple[list[float], float] | None = None
        self.last_error: Exception | None = None
        self._thread = threading.Thread(
            target=self._run, name="litearm-command", daemon=True
        )
        self._thread.start()

    def submit(self, q: list[float], speed: float) -> None:
        with self._lock:
            self._latest = (list(q), float(speed))
        self._wake.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            self._wake.wait(timeout=0.1)
            if self._stop.is_set():
                return
            with self._lock:
                latest = self._latest
                self._latest = None
                self._wake.clear()
            if latest is None:
                continue
            target, speed = latest
            try:
                self._send(target, speed)
                self.last_error = None
            except Exception as error:  # SDK 的超时/被新命令取代都走这里
                self.last_error = error
                logger.warning("movej_sync failed: %s", error)

    def close(self) -> None:
        """请求退出并等待在途的 `movej_sync` 返回。

        SDK 的单段 PTP 不可中断，只能等它自然返回；返回后线程在循环顶端
        看到 `_stop` 并退出。调用方据此确认没有 SDK 调用在并发执行。
        """
        self._stop.set()
        self._wake.set()
        self._thread.join()

    def abandon(self) -> None:
        """请求退出但不等待，用于急停/失能等必须立刻下发固件命令的路径。

        线程本身是 daemon；在途的 `movej_sync` 返回后自行退出，但此时不再
        允许创建新 worker，直到调用方重新 enable/connect。
        """
        self._stop.set()
        self._wake.set()


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
        self._owns_arm = arm is None
        self._gripper = gripper if gripper is not None else make_gripper(
            config.gripper
        )
        self._worker: _CommandWorker | None = None
        #: 已放弃但可能在途的旧 worker，等 `_ensure_worker`/`_cancel_worker` 回收。
        self._retired: list[_CommandWorker] = []
        self._worker_lock = threading.RLock()
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

        try:
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
            self._ensure_worker()
        except BaseException:
            # connect 失败时必须关闭已经打开的 SDK 会话；否则 disconnect()
            # 因 _connected=False 直接返回，串口会话会泄漏。
            self._cleanup_failed_connect()
            raise

        self._connected = True
        logger.info(
            "litearm connected: firmware=%s joints=%s",
            firmware or "unknown",
            self._arm.n,
        )

    def _cleanup_failed_connect(self) -> None:
        self._cancel_worker()
        try:
            self._gripper.close()
        except Exception:
            logger.exception("failed to close gripper after connect error")
        if self._arm is not None:
            try:
                self._arm.close()
            except Exception:
                logger.exception("failed to close arm after connect error")
            finally:
                if self._owns_arm:
                    self._arm = None
        self._target = {}
        self._connected = False

    def disconnect(self) -> None:
        if not self._connected:
            return
        try:
            # 先等在途 movej_sync 返回，再直接调用 SDK / 关闭串口；
            # 否则 arm.close() 之后仍可能有运动线程在写。
            self._cancel_worker()
            if self.config.move_to_reset_on_disconnect and self.config.reset_position:
                self._target.update(clip_arm_positions(self.config.reset_position))
                self._arm.movej_sync(
                    self._full_target(), speed=self.config.speed
                )
        finally:
            self._gripper.close()
            self._arm.close()
            self._connected = False
            logger.info("litearm disconnected")

    def stop(self) -> None:
        """取消排队目标并把当前实测位姿作为新目标；臂保持使能。

        SDK 没有独立的 stop 命令：worker 里正在执行的 movej_sync 无法中断。
        这里不销毁 worker，而是把实测位姿投进同一个合并队列；在途调用返回后
        由同一线程执行，保证任何时刻只有一个 movej_sync 在跑。
        """
        if self._arm is None:
            self._gripper.stop()
            return
        self._target = dict(zip(ARM_JOINTS, self._read_arm_positions()))
        with self._worker_lock:
            worker = self._worker
        if worker is not None:
            worker.submit(self._full_target(), self.config.speed)
        self._gripper.stop()

    def emergency_stop(self) -> None:
        """急停：取消下发并发送固件 EMERGENCY_STOP（0x12）。

        固件会立即断力并锁存 EMERGENCY/FAULT；恢复必须先 `reset()` 再 `enable()`。
        注意：臂失去保持力；若姿态无支撑，请先人工托住。

        这里不等待在途 movej_sync：急停命令优先。旧线程在调用返回后自行退出，
        并在下一次 `enable()` 前被回收。
        """
        self._cancel_worker(wait=False)
        if self._arm is not None:
            self._arm.emergency_stop()
        self._gripper.stop()
        logger.error("emergency stop latched; reset() required before enable()")

    def enable(self) -> None:
        if not self._connected:
            raise RuntimeError("robot is not connected")
        self._arm.enable()
        self._target = dict(zip(ARM_JOINTS, self._read_arm_positions()))
        self._ensure_worker()

    def disable(self) -> None:
        if not self._connected:
            raise RuntimeError("robot is not connected")
        self._cancel_worker(wait=False)
        self._arm.disable()

    def reset(self) -> None:
        """清除固件故障/急停锁存；不会自动使能。"""
        if not self._connected:
            raise RuntimeError("robot is not connected")
        self._arm.reset()
        self._target = dict(zip(ARM_JOINTS, self._read_arm_positions()))

    def home(self, timeout: float | None = None) -> None:
        """固件 `home()`（0x2A）回 URDF 零位，固件内固定 0.10 低速。"""
        if not self._connected:
            raise RuntimeError("robot is not connected")
        timeout = self.config.home_timeout_s if timeout is None else timeout
        self._cancel_worker()
        try:
            self._arm.home(timeout=timeout)
        finally:
            self._target = dict(zip(ARM_JOINTS, self._read_arm_positions()))
            self._ensure_worker()

    # --------------------------------------------------------------- lifecycle

    def _ensure_worker(self) -> None:
        # 先回收被放弃的旧线程（例如急停/失能时留在在途调用里的那个），
        # 再创建新 worker，避免两个线程同时调用 SDK。
        with self._worker_lock:
            retired, self._retired = self._retired, []
        for worker in retired:
            worker.close()
        with self._worker_lock:
            if self._worker is None:
                self._worker = _CommandWorker(self._send_arm_target)

    def _cancel_worker(self, *, wait: bool = True) -> None:
        """停掉当前 worker。

        `wait=True` 等待在途 movej_sync 返回（stop/home/disconnect 路径）；
        `wait=False` 只发退出信号并登记到 `_retired`，供急停/失能立即下发
        固件命令，后续 `_ensure_worker` 或 `_cancel_worker` 再回收。
        """
        with self._worker_lock:
            workers = self._retired
            self._retired = []
            if self._worker is not None:
                workers.append(self._worker)
                self._worker = None
        for worker in workers:
            if wait:
                worker.close()
            else:
                worker.abandon()
        if not wait:
            with self._worker_lock:
                self._retired.extend(workers)

    def _submit_target(self, speed: float) -> None:
        q = self._full_target()
        with self._worker_lock:
            worker = self._worker
            if worker is None:
                raise RuntimeError(
                    "robot is not ready for commands (connect/enable first)"
                )
            worker.submit(q, speed)

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
        return self._state_to_joint_state(self._arm.get_state().value)

    def get_status(self) -> RobotStatus:
        return self._state_to_status(self._arm.get_state().value)

    def snapshot(self) -> tuple[JointState, RobotStatus]:
        """一次 SDK 读取同时得到 JointState 和固件状态摘要。"""
        state = self._arm.get_state().value
        return self._state_to_joint_state(state), self._state_to_status(state)

    def _state_to_joint_state(self, state: Any) -> JointState:
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

    @staticmethod
    def _state_to_status(state: Any) -> RobotStatus:
        return RobotStatus(
            enabled=bool(getattr(state, "enabled", False)),
            mode=str(getattr(state, "mode_name", "")),
            faulted=bool(getattr(state, "faulted", False)),
            faults=str(getattr(state, "fault_detail", "") or ""),
            joint_fault=int(getattr(state, "joint_fault", 0)),
        )

    # ---------------------------------------------------------------- command

    def set_command(
        self, command: JointCommand, *, speed: float | None = None
    ) -> None:
        """下发稀疏位置命令。

        `speed` 是本适配器的扩展（0..1 的 SDK 速度倍率），来自 action 载荷的
        可选 `speed` 列；缺省时使用 `config.speed`。
        """
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
            self._submit_target(normalize_speed(speed, self.config.speed))

        if gripper_m is not None:
            self._gripper.set_opening_m(gripper_m)

        if self.config.debug:
            logger.debug(
                "target=%s gripper=%s speed=%s",
                self._target,
                gripper_m,
                speed,
            )

    def _send_arm_target(self, q: Sequence[float], speed: float) -> None:
        self._arm.movej_sync(list(q), speed=speed)
