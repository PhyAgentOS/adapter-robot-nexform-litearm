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


def test_connect_firmware_failure_closes_arm():
    arm = FakeArm().connect()
    arm.firmware = "Other-FW"
    driver = LitearmDriver(
        RobotConfig(firmware_prefix="Litearm"),
        arm=arm,
        gripper=NullGripper(),
    )

    with pytest.raises(RuntimeError):
        driver.connect()

    assert arm.connected is False
    assert driver._connected is False


class _MovejBoomArm(FakeArm):
    def movej_sync(self, q, speed=1.0):
        raise RuntimeError("movej failed mid-init")


def test_connect_initial_motion_failure_closes_arm():
    arm = _MovejBoomArm().connect()
    driver = LitearmDriver(
        RobotConfig(
            move_to_initial=True, initial_position={"joint1": 0.1}
        ),
        arm=arm,
        gripper=NullGripper(),
    )

    with pytest.raises(RuntimeError):
        driver.connect()

    assert arm.connected is False


class _BrokenGripper:
    def __init__(self):
        self.closed = False

    def connect(self):
        raise RuntimeError("gripper bus unavailable")

    def close(self):
        self.closed = True

    def get_opening_m(self):
        return None

    def set_opening_m(self, opening_m):
        raise RuntimeError("not connected")

    def stop(self):
        pass


def test_connect_gripper_failure_closes_arm():
    arm = FakeArm().connect()
    gripper = _BrokenGripper()
    driver = LitearmDriver(
        RobotConfig(move_to_initial=False),
        arm=arm,
        gripper=gripper,
    )

    with pytest.raises(RuntimeError):
        driver.connect()

    assert gripper.closed is True
    assert arm.connected is False


def test_emergency_stop_disables_arm():
    driver = _driver()
    arm = driver._arm
    try:
        driver.emergency_stop()
        assert arm.enabled is False
        assert arm.mode_name == "EMERGENCY"
        assert driver.get_status().faulted is True
    finally:
        driver.disconnect()


def test_command_speed_override():
    driver = _driver()
    arm = driver._arm
    try:
        driver.set_command(
            JointCommand(name=["joint1"], position=[0.1]), speed=0.5
        )
        assert _wait_for(lambda: arm.last_speed == pytest.approx(0.5))
    finally:
        driver.disconnect()


def test_command_uses_config_speed_by_default():
    driver = _driver()
    arm = driver._arm
    try:
        driver.set_command(JointCommand(name=["joint1"], position=[0.1]))
        assert _wait_for(lambda: arm.last_speed == pytest.approx(0.2))
    finally:
        driver.disconnect()


def test_command_speed_is_clamped_to_one():
    driver = _driver()
    arm = driver._arm
    try:
        driver.set_command(
            JointCommand(name=["joint1"], position=[0.1]), speed=2.5
        )
        assert _wait_for(lambda: arm.last_speed == pytest.approx(1.0))
    finally:
        driver.disconnect()


@pytest.mark.parametrize("bad", [-0.1, float("nan"), float("inf")])
def test_command_rejects_invalid_speed(bad):
    driver = _driver()
    try:
        with pytest.raises(ValueError):
            driver.set_command(
                JointCommand(name=["joint1"], position=[0.1]), speed=bad
            )
    finally:
        driver.disconnect()


def test_disable_stops_commands_until_enable():
    driver = _driver()
    try:
        driver.disable()
        assert driver._worker is None
        with pytest.raises(RuntimeError):
            driver.set_command(
                JointCommand(name=["joint1"], position=[0.1])
            )

        driver.enable()
        driver.set_command(JointCommand(name=["joint1"], position=[0.1]))
        assert _wait_for(
            lambda: driver.get_state().position[0] == pytest.approx(0.1)
        )
    finally:
        driver.disconnect()


def test_reset_clears_emergency_latch():
    driver = _driver()
    try:
        driver.emergency_stop()
        driver.reset()
        status = driver.get_status()
        assert status.mode == "INIT"
        assert status.faulted is False

        driver.enable()
        driver.set_command(JointCommand(name=["joint1"], position=[0.2]))
        assert _wait_for(
            lambda: driver.get_state().position[0] == pytest.approx(0.2)
        )
    finally:
        driver.disconnect()


def test_home_restores_command_path():
    driver = _driver()
    arm = driver._arm
    try:
        driver.set_command(JointCommand(name=["joint1"], position=[0.3]))
        assert _wait_for(lambda: arm.q[0] == pytest.approx(0.3))

        driver.home(timeout=5.0)
        assert arm.home_count == 1
        assert arm.last_speed == pytest.approx(0.1)
        assert driver.get_state().position[0] == pytest.approx(0.0)

        driver.set_command(JointCommand(name=["joint1"], position=[0.1]))
        assert _wait_for(
            lambda: driver.get_state().position[0] == pytest.approx(0.1)
        )
    finally:
        driver.disconnect()


def test_stop_holds_measured_pose():
    driver = _driver()
    arm = driver._arm
    try:
        driver.set_command(JointCommand(name=["joint1"], position=[0.4]))
        assert _wait_for(lambda: arm.q[0] == pytest.approx(0.4))

        driver.stop()
        assert driver._target["joint1"] == pytest.approx(0.4)
    finally:
        driver.disconnect()


def test_status_reflects_firmware_fields():
    driver = _driver()
    try:
        state, status = driver.snapshot()
        assert state.name == list(ARM_JOINTS)
        assert status.enabled is True
        assert status.mode == "INIT"
        assert status.faulted is False
        assert status.joint_fault == 0
    finally:
        driver.disconnect()
