"""关节顺序、限位与单位换算。

本模块不依赖 Forge / SDK，便于在无硬件、无 3.12 环境时单测。

单位契约（Forge）：
- 旋转关节：rad、rad/s、Nm
- 夹爪：两指总开口，m（SDK 侧是 mm，必须在这里换算）
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

ARM_JOINTS: tuple[str, ...] = tuple(f"joint{i}" for i in range(1, 8))
GRIPPER = "gripper"
JOINT_ORDER: tuple[str, ...] = (*ARM_JOINTS, GRIPPER)

# 来源：assets/urdf/litearm.urdf 的 <limit>，单位 rad。
# 固件软限位可能更窄/更宽，现场以固件回读为准；本表只做第一层裁剪。
JOINT_LIMITS: Mapping[str, tuple[float, float]] = {
    "joint1": (-2.827, 2.827),
    "joint2": (-1.745, 1.745),
    "joint3": (-2.827, 2.827),
    "joint4": (-3.089, 0.035),
    "joint5": (-2.827, 2.827),
    "joint6": (-1.571, 1.571),
    "joint7": (-1.571, 1.571),
}

# LiteGrip 两指总开口：闭合 0 m，全开 0.080 m（SDK 侧 0..80 mm）。
GRIPPER_MAX_M = 0.080

#: `goto(duration=...)` 的下限，避免零行程或极高速度产生 0 秒目标。
GRIPPER_MIN_MOVE_S = 0.05


def mm_to_m(value_mm: float) -> float:
    return float(value_mm) / 1000.0


def m_to_mm(value_m: float) -> float:
    return float(value_m) * 1000.0


def clip_arm_positions(
    positions: Mapping[str, float],
) -> dict[str, float]:
    """按 URDF 限位裁剪，超出即夹到边界（调用方负责记录告警）。"""
    clipped: dict[str, float] = {}
    for name, value in positions.items():
        if name not in JOINT_LIMITS:
            raise KeyError(f"unknown arm joint: {name}")
        lower, upper = JOINT_LIMITS[name]
        clipped[name] = min(max(float(value), lower), upper)
    return clipped


def clip_gripper_opening(
    value_m: float, max_m: float = GRIPPER_MAX_M
) -> float:
    return min(max(float(value_m), 0.0), float(max_m))


def gripper_move_duration_s(travel_m: float, speed_mm_s: float) -> float:
    """按行程和配置速度计算 LiteGrip `goto()` 的 duration 秒数。"""
    if not math.isfinite(speed_mm_s) or speed_mm_s <= 0.0:
        raise ValueError(f"gripper speed_mm_s must be > 0, got {speed_mm_s}")
    speed_m_s = float(speed_mm_s) / 1000.0
    return max(abs(float(travel_m)) / speed_m_s, GRIPPER_MIN_MOVE_S)


def split_command(
    names: Sequence[str],
    positions: Sequence[float],
    *,
    gripper_max_m: float = GRIPPER_MAX_M,
) -> tuple[dict[str, float], float | None]:
    """把稀疏 JointCommand 拆成 (arm 目标, 夹爪开口 m)。

    只接受本构型声明的名字；未知关节直接报错，避免静默丢命令。
    非有限值在裁剪**之前**拒绝：否则 `inf` 会被裁成限位/最大开口，
    看起来是有限值，从而绕过调用方的校验。
    """
    if len(names) != len(positions):
        raise ValueError("JointCommand name/position length mismatch")

    arm: dict[str, float] = {}
    gripper_m: float | None = None
    for name, value in zip(names, positions, strict=True):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(f"{name} position must be finite, got {value!r}")
        if name == GRIPPER:
            gripper_m = clip_gripper_opening(number, gripper_max_m)
        elif name in JOINT_LIMITS:
            arm[name] = number
        else:
            raise KeyError(f"unknown joint: {name}")
    return arm, gripper_m
