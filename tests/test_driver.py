"""驱动层无硬件测试。forge_* 未安装时整组跳过。"""

from __future__ import annotations

import importlib.util
import time

import pytest

from litearm_robot.codec import ARM_JOINTS, JOINT_LIMITS
from litearm_robot.config import RobotConfig

HAVE_FORGE = all(
    importlib.util.find_spec(module) is not None
    for module in ("forge_msgs", "forge_robot")
)
pytestmark = pytest.mark.skipif(
    not HAVE_FORGE, reason="forge_msgs / forge_robot not installed"
)

if HAVE_FORGE:
    from forge_msgs import JointCommand

    from litearm_robot.driver import LitearmDriver
    from litearm_robot.fake import FakeArm
    from litearm_robot.gripper import NullGripper


def _driver(**overrides) -> LitearmDriver:
    config = RobotConfig(
        enable_on_connect=True,
        move_to_initial=False,
        speed=0.2,
        **overrides,
    )
    driver = LitearmDriver(
        config, arm=FakeArm(), gripper=NullGripper()
    )
    driver.connect()
    return driver


def _wait_for(predicate, timeout: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_joint_order_and_state():
    driver = _driver()
    try:
        assert driver.joint_order == list(ARM_JOINTS) + ["gripper"]
        state = driver.get_state()
        assert state.name == list(ARM_JOINTS)
        assert state.position == pytest.approx([0.0] * 7)
    finally:
        driver.disconnect()


def test_sparse_command_moves_only_named_joint():
    driver = _driver()
    try:
        driver.set_command(
            JointCommand(name=["joint3"], position=[0.25])
        )
        assert _wait_for(
            lambda: driver.get_state().position[2] == pytest.approx(0.25)
        )
        assert driver.get_state().position[:2] == pytest.approx([0.0, 0.0])
    finally:
        driver.disconnect()


def test_command_is_clipped():
    driver = _driver()
    try:
        driver.set_command(
            JointCommand(name=["joint4"], position=[10.0])
        )
        assert _wait_for(
            lambda: driver.get_state().position[3]
            == pytest.approx(JOINT_LIMITS["joint4"][1])
        )
    finally:
        driver.disconnect()


def test_rejects_non_position_mode():
    driver = _driver()
    try:
        with pytest.raises(ValueError):
            driver.set_command(
                JointCommand(
                    name=["joint1"], mode="velocity", velocity=[0.1]
                )
            )
    finally:
        driver.disconnect()


def test_unknown_joint_rejected():
    driver = _driver()
    try:
        with pytest.raises(KeyError):
            driver.set_command(
                JointCommand(name=["joint9"], position=[0.0])
            )
    finally:
        driver.disconnect()


def test_gripper_command_without_gripper_raises():
    driver = _driver()
    try:
        with pytest.raises(RuntimeError):
            driver.set_command(
                JointCommand(name=["gripper"], position=[0.02])
            )
    finally:
        driver.disconnect()


def test_firmware_prefix_mismatch_raises():
    driver = LitearmDriver(
        RobotConfig(firmware_prefix="Other"),
        arm=FakeArm(),
        gripper=NullGripper(),
    )
    with pytest.raises(RuntimeError):
        driver.connect()


def test_emergency_stop_disables_arm():
    driver = _driver()
    arm = driver._arm
    try:
        driver.emergency_stop()
        assert arm.enabled is False
    finally:
        driver.disconnect()
