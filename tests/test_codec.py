from __future__ import annotations

import pytest

from litearm_robot.codec import (
    ARM_JOINTS,
    GRIPPER,
    GRIPPER_MAX_M,
    GRIPPER_MIN_MOVE_S,
    JOINT_LIMITS,
    JOINT_ORDER,
    clip_arm_positions,
    clip_gripper_opening,
    gripper_move_duration_s,
    m_to_mm,
    mm_to_m,
    split_command,
)


def test_joint_order_is_seven_arm_joints_plus_gripper():
    assert ARM_JOINTS == tuple(f"joint{i}" for i in range(1, 8))
    assert JOINT_ORDER == (*ARM_JOINTS, GRIPPER)
    assert set(JOINT_LIMITS) == set(ARM_JOINTS)


def test_mm_m_round_trip():
    assert mm_to_m(80.0) == pytest.approx(0.080)
    assert m_to_mm(0.080) == pytest.approx(80.0)
    assert mm_to_m(m_to_mm(12.3)) == pytest.approx(12.3)


def test_clip_arm_positions_clamps_both_sides():
    result = clip_arm_positions(
        {"joint1": 10.0, "joint4": 10.0, "joint5": -10.0}
    )
    assert result["joint1"] == JOINT_LIMITS["joint1"][1]
    assert result["joint4"] == JOINT_LIMITS["joint4"][1]
    assert result["joint5"] == JOINT_LIMITS["joint5"][0]


def test_clip_arm_positions_rejects_unknown_joint():
    with pytest.raises(KeyError):
        clip_arm_positions({"joint8": 0.0})


def test_clip_gripper_opening():
    assert clip_gripper_opening(-0.1) == 0.0
    assert clip_gripper_opening(GRIPPER_MAX_M + 1) == GRIPPER_MAX_M
    assert clip_gripper_opening(0.02) == pytest.approx(0.02)


def test_clip_gripper_opening_respects_configured_max():
    assert clip_gripper_opening(0.07, 0.05) == pytest.approx(0.05)
    assert clip_gripper_opening(0.04, 0.05) == pytest.approx(0.04)


def test_gripper_move_duration_uses_speed():
    assert gripper_move_duration_s(0.02, 20.0) == pytest.approx(1.0)
    assert gripper_move_duration_s(0.0, 20.0) == GRIPPER_MIN_MOVE_S
    with pytest.raises(ValueError):
        gripper_move_duration_s(0.01, 0.0)


def test_split_command_separates_arm_and_gripper():
    arm, gripper_m = split_command(
        ["joint3", "gripper", "joint1"], [0.1, 0.04, -0.2]
    )
    assert arm == {"joint3": 0.1, "joint1": -0.2}
    assert gripper_m == pytest.approx(0.04)


def test_split_command_clips_gripper():
    _, gripper_m = split_command(["gripper"], [1.0])
    assert gripper_m == GRIPPER_MAX_M


def test_split_command_respects_configured_max():
    _, gripper_m = split_command(
        ["gripper"], [0.07], gripper_max_m=0.05
    )
    assert gripper_m == pytest.approx(0.05)


def test_split_command_length_mismatch():
    with pytest.raises(ValueError):
        split_command(["joint1", "joint2"], [0.0])


def test_split_command_unknown_name_raises():
    with pytest.raises(KeyError):
        split_command(["wrist"], [0.0])
