"""YAML 配置加载。字段与 config/robot.example.yaml 一一对应。"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .codec import ARM_JOINTS, GRIPPER_MAX_M, JOINT_ORDER


@dataclass(frozen=True)
class GripperConfig:
    enabled: bool = False
    channel: str = "can0"
    can_id: int = 0x08
    mst_id: int | None = 0x18
    max_opening_m: float = 0.080
    speed_mm_s: float = 20.0


@dataclass(frozen=True)
class RobotConfig:
    # None = 让 SDK 自动发现 USB CDC 串口
    port: str | None = None
    firmware_prefix: str = "Litearm"
    joint_order: tuple[str, ...] = JOINT_ORDER
    speed: float = 0.2
    home_timeout_s: float = 180.0
    enable_on_connect: bool = True
    move_to_initial: bool = True
    move_to_reset_on_disconnect: bool = False
    initial_position: dict[str, float] = field(default_factory=dict)
    reset_position: dict[str, float] = field(default_factory=dict)
    debug: bool = False
    gripper: GripperConfig = field(default_factory=GripperConfig)

    def validate(self) -> None:
        if tuple(self.joint_order) != JOINT_ORDER:
            raise ValueError(
                "joint_order must be "
                f"{list(JOINT_ORDER)}, got {list(self.joint_order)}"
            )
        for label, pose in (
            ("initial_position", self.initial_position),
            ("reset_position", self.reset_position),
        ):
            unknown = set(pose) - set(ARM_JOINTS)
            if unknown:
                raise ValueError(f"{label} has unknown joints: {sorted(unknown)}")
        if not 0.0 <= self.speed <= 1.0:
            raise ValueError(f"speed must be in 0..1, got {self.speed}")
        if self.home_timeout_s <= 0.0:
            raise ValueError(
                f"home_timeout_s must be > 0, got {self.home_timeout_s}"
            )
        gripper = self.gripper
        if not math.isfinite(gripper.max_opening_m) or not (
            0.0 < gripper.max_opening_m <= GRIPPER_MAX_M
        ):
            raise ValueError(
                "gripper.max_opening_m must be in "
                f"(0, {GRIPPER_MAX_M}], got {gripper.max_opening_m}"
            )
        if not math.isfinite(gripper.speed_mm_s) or gripper.speed_mm_s <= 0.0:
            raise ValueError(
                "gripper.speed_mm_s must be > 0, "
                f"got {gripper.speed_mm_s}"
            )


def _section(data: Any, key: str) -> dict[str, Any]:
    value = data.get(key) if isinstance(data, dict) else None
    return value if isinstance(value, dict) else {}


def load_config(path: str | Path | None = None) -> RobotConfig:
    data: dict[str, Any] = {}
    if path is not None:
        with open(path, "r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle) or {}
        if not isinstance(loaded, dict):
            raise ValueError(f"{path}: top-level YAML must be a mapping")
        data = loaded

    gripper_data = _section(data, "gripper")
    mst_raw = gripper_data.get("mst_id", 0x18)
    gripper = GripperConfig(
        enabled=bool(gripper_data.get("enabled", False)),
        channel=str(gripper_data.get("channel", "can0")),
        can_id=int(gripper_data.get("can_id", 0x08)),
        mst_id=None if mst_raw is None else int(mst_raw),
        max_opening_m=float(gripper_data.get("max_opening_m", 0.080)),
        speed_mm_s=float(gripper_data.get("speed_mm_s", 20.0)),
    )

    order = data.get("joint_order", JOINT_ORDER)
    config = RobotConfig(
        port=data.get("port"),
        firmware_prefix=str(data.get("firmware_prefix", "Litearm")),
        joint_order=tuple(order),
        speed=float(data.get("speed", 0.2)),
        home_timeout_s=float(data.get("home_timeout_s", 180.0)),
        enable_on_connect=bool(data.get("enable_on_connect", True)),
        move_to_initial=bool(data.get("move_to_initial", True)),
        move_to_reset_on_disconnect=bool(
            data.get("move_to_reset_on_disconnect", False)
        ),
        initial_position=dict(_section(data, "initial_position")),
        reset_position=dict(_section(data, "reset_position")),
        debug=bool(data.get("debug", False)),
        gripper=gripper,
    )
    config.validate()
    return config
