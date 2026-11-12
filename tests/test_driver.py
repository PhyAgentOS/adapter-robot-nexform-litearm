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
    from types import SimpleNamespace

    from forge_msgs import JointCommand

    from litearm_robot.config import GripperConfig
    from litearm_robot.driver import LitearmDriver
    from litearm_robot.fake import FakeArm
    from litearm_robot.gripper import LiteGripGripper, NullGripper


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


class _RecordingGripper:
    def __init__(self):
        self.openings = []

    def connect(self):
        pass

    def close(self):
        pass

    def get_opening_m(self):
        return None

    def set_opening_m(self, opening_m):
        self.openings.append(opening_m)

    def stop(self):
        pass


def test_gripper_command_clipped_to_configured_max():
    gripper = _RecordingGripper()
    driver = LitearmDriver(
        RobotConfig(
            move_to_initial=False,
            gripper=GripperConfig(enabled=True, max_opening_m=0.05),
        ),
        arm=FakeArm(),
        gripper=gripper,
    )
    driver.connect()
    try:
        driver.set_command(
            JointCommand(name=["gripper"], position=[0.07])
        )
        assert gripper.openings == pytest.approx([0.05])
    finally:
        driver.disconnect()


class _FakeLiteGrip:
    def __init__(self, position_mm=20.0):
        self.position_mm = position_mm
        self.calls = []

    def get_state(self, wait=False):
        return SimpleNamespace(
            position_mm=self.position_mm, data_age_s=0.0
        )

    def goto(self, position_mm, *, duration):
        self.calls.append((position_mm, duration))


def test_litegrip_goto_duration_uses_configured_speed():
    gripper = LiteGripGripper(GripperConfig(speed_mm_s=20.0))
    fake = _FakeLiteGrip(position_mm=20.0)
    gripper._gripper = fake

    gripper.set_opening_m(0.06)

    assert len(fake.calls) == 1
    position_mm, duration = fake.calls[0]
    assert position_mm == pytest.approx(60.0)
    assert duration == pytest.approx(2.0)


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
