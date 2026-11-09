"""LiteGrip 夹爪后端。

Forge 侧只认“两指总开口（m）”；LiteGrip SDK 用 mm，换算在 codec 里。
"""

from __future__ import annotations

import logging
from typing import Protocol

from .codec import m_to_mm, mm_to_m
from .config import GripperConfig

logger = logging.getLogger(__name__)


class GripperBackend(Protocol):
    def connect(self) -> None: ...
    def close(self) -> None: ...
    def get_opening_m(self) -> float | None: ...
    def set_opening_m(self, opening_m: float) -> None: ...
    def stop(self) -> None: ...


class NullGripper:
    """未安装/未启用夹爪时的占位实现；开口读回 None。"""

    def connect(self) -> None:
        return None

    def close(self) -> None:
        return None

    def get_opening_m(self) -> float | None:
        return None

    def set_opening_m(self, opening_m: float) -> None:
        raise RuntimeError("gripper is disabled in config")

    def stop(self) -> None:
        return None


class LiteGripGripper:
    """LiteGrip SDK 的薄包装，惰性导入，避免无 SDK 时 import 失败。"""

    def __init__(self, config: GripperConfig):
        self.config = config
        self._gripper = None

    def connect(self) -> None:
        try:
            from litegrip import LiteGrip
        except ImportError as error:
            raise RuntimeError(
                "litegrip SDK missing; install it from the internal "
                "litegrip-python repository"
            ) from error

        self._gripper = LiteGrip(
            self.config.channel,
            can_id=self.config.can_id,
            mst_id=self.config.mst_id,
            # 断开时保持使能，避免带载松开；生命周期由调用方管理。
            disable_on_disconnect=False,
        )
        if not self._gripper.connect():
            raise RuntimeError(
                f"failed to connect LiteGrip on {self.config.channel}"
            )
        self._gripper.load_calibration()
        self._gripper.enable()
        logger.info(
            "LiteGrip connected on %s (can_id=0x%02X)",
            self.config.channel,
            self.config.can_id,
        )

    def close(self) -> None:
        if self._gripper is not None:
            self._gripper.disconnect()
            self._gripper = None

    def get_opening_m(self) -> float | None:
        if self._gripper is None:
            return None
        state = self._gripper.get_state(wait=False)
        if state.data_age_s is None or state.data_age_s > 1.0:
            # 夹爪保持姿态时总线静默，缓存会过期；主动要一帧再读。
            self._gripper.refresh_status()
            state = self._gripper.get_state(wait=True)
        if state.data_age_s is None or state.data_age_s > 1.0:
            return None
        return mm_to_m(state.position_mm)

    def set_opening_m(self, opening_m: float) -> None:
        if self._gripper is None:
            raise RuntimeError("gripper is not connected")
        self._gripper.goto(
            m_to_mm(opening_m),
            duration=0.3,
        )

    def stop(self) -> None:
        if self._gripper is not None:
            self._gripper.stop()


def make_gripper(config: GripperConfig) -> GripperBackend:
    return LiteGripGripper(config) if config.enabled else NullGripper()
