"""node.py 与标准 runner 的语义对齐测试（无 Dora 运行时）。"""

from __future__ import annotations

import importlib.util
import logging
import queue

import pytest

HAVE_DEPS = all(
    importlib.util.find_spec(module) is not None
    for module in ("dora", "forge_msgs", "forge_robot")
)
pytestmark = pytest.mark.skipif(
    not HAVE_DEPS, reason="dora / forge_msgs / forge_robot not installed"
)

if HAVE_DEPS:
    import pyarrow as pa
    from forge_msgs import JointCommand, JointState

    from litearm_robot.codec import ARM_JOINTS
    from litearm_robot.control import ControlStatus
    from litearm_robot.driver import RobotStatus
    from litearm_robot.node import (
        _handle_action,
        _handle_master_state,
        _handle_tick,
        _has_joint_order,
        _status_to_arrow,
    )


class FakeDriver:
    def __init__(self, joint_order=None, error: Exception | None = None):
        self.joint_order = (
            list(ARM_JOINTS) if joint_order is None else list(joint_order)
        )
        self.commands: list[JointCommand] = []
        self.error = error
        self.consume_error_calls: list[bool] = []

    def set_command(self, command, **_kwargs) -> None:
        if self.error is not None:
            raise self.error
        self.commands.append(command)

    def snapshot(self, *, consume_error=True):
        self.consume_error_calls.append(consume_error)
        state = JointState(
            name=list(ARM_JOINTS),
            position=[0.0] * len(ARM_JOINTS),
            velocity=[0.0] * len(ARM_JOINTS),
            effort=[0.0] * len(ARM_JOINTS),
        )
        status = RobotStatus(
            enabled=True,
            mode="INIT",
            faulted=False,
            faults="",
            joint_fault=0,
        )
        return state, status


def _action(names=("joint7",), positions=(0.05,), extra_speed=None):
    batch = JointCommand(
        name=list(names), position=list(positions)
    ).to_arrow()
    if extra_speed is not None:
        batch = batch.append_column(
            "speed", pa.array([extra_speed], type=pa.float64())
        )
    return batch


def _receipts(results):
    items = []
    while not results.empty():
        items.append(results.get_nowait())
    return items


def test_has_joint_order_empty_logs(caplog):
    with caplog.at_level(logging.ERROR):
        assert _has_joint_order("action", []) is False
    assert "joint_order" in caplog.text


def test_action_dispatches_to_driver():
    driver = FakeDriver()
    results: queue.Queue[ControlStatus] = queue.Queue()
    _handle_action(driver, _action(), results, driver.joint_order, False)
    assert len(driver.commands) == 1
    assert list(driver.commands[0].name) == ["joint7"]
    assert _receipts(results) == []


def test_action_without_joint_order_is_ignored():
    driver = FakeDriver(joint_order=[])
    results: queue.Queue[ControlStatus] = queue.Queue()
    _handle_action(driver, _action(), results, [], False)
    assert driver.commands == []
    assert _receipts(results) == []


def test_rejected_action_emits_control_status():
    driver = FakeDriver()
    results: queue.Queue[ControlStatus] = queue.Queue()
    # joint9 不在 joint_order 中，strict 校验应拒绝。
    _handle_action(
        driver,
        _action(names=("joint9",), positions=(0.0,)),
        results,
        driver.joint_order,
        False,
        strict_extra_arrow_columns=True,
    )
    assert driver.commands == []
    receipts = _receipts(results)
    assert len(receipts) == 1
    assert receipts[0].command == "action"
    assert receipts[0].status == "rejected"


def test_set_command_failure_emits_control_status():
    driver = FakeDriver(error=ValueError("rejected by driver"))
    results: queue.Queue[ControlStatus] = queue.Queue()
    _handle_action(driver, _action(), results, driver.joint_order, False)
    receipts = _receipts(results)
    assert len(receipts) == 1
    assert "rejected by driver" in receipts[0].message


def test_speed_column_is_not_an_extra_column():
    """strict 校验只管关节名，扩展的 speed 列始终允许。"""
    driver = FakeDriver()
    results: queue.Queue[ControlStatus] = queue.Queue()
    _handle_action(
        driver,
        _action(extra_speed=0.5),
        results,
        driver.joint_order,
        False,
        strict_extra_arrow_columns=True,
    )
    assert len(driver.commands) == 1


def test_speed_column_allowed_by_default():
    driver = FakeDriver()
    results: queue.Queue[ControlStatus] = queue.Queue()
    _handle_action(
        driver, _action(extra_speed=0.5), results, driver.joint_order, False
    )
    assert len(driver.commands) == 1
    assert _receipts(results) == []


def test_master_state_dispatches_and_reports_failure():
    driver = FakeDriver()
    results: queue.Queue[ControlStatus] = queue.Queue()
    state = JointState(
        name=list(ARM_JOINTS),
        position=[0.1] * len(ARM_JOINTS),
        velocity=[0.0] * len(ARM_JOINTS),
        effort=[0.0] * len(ARM_JOINTS),
    ).to_arrow()
    _handle_master_state(driver, state, results, driver.joint_order, False)
    assert len(driver.commands) == 1

    failing = FakeDriver(error=RuntimeError("boom"))
    results = queue.Queue()
    _handle_master_state(
        failing, state, results, failing.joint_order, False
    )
    receipts = _receipts(results)
    assert len(receipts) == 1
    assert receipts[0].command == "master_state"
    assert "boom" in receipts[0].message


class FakeNode:
    def __init__(self) -> None:
        self.outputs: list[tuple[str, object]] = []

    def send_output(self, output_id, value) -> None:
        self.outputs.append((output_id, value))

    def of(self, output_id):
        return [value for name, value in self.outputs if name == output_id]


def test_tick_calls_on_tick_after_state():
    node = FakeNode()
    driver = FakeDriver()
    calls: list[object] = []
    _handle_tick(
        node,
        driver,
        {"robot_status"},
        driver.joint_order,
        False,
        lambda n, d: calls.append((n, d)),
    )
    assert node.of("state")
    assert node.of("robot_status")
    assert calls == [(node, driver)]
    assert driver.consume_error_calls == [True]


def test_tick_without_robot_status_does_not_consume_command_error():
    node = FakeNode()
    driver = FakeDriver()
    _handle_tick(node, driver, set(), driver.joint_order, False)
    assert node.of("state")
    assert node.of("robot_status") == []
    assert driver.consume_error_calls == [False]


def test_status_arrow_fields():
    batch = _status_to_arrow(
        RobotStatus(
            enabled=True,
            mode="MOVE_J",
            faulted=False,
            faults="",
            joint_fault=0,
        )
    )
    assert batch.schema.names == [
        "enabled",
        "mode",
        "faulted",
        "faults",
        "joint_fault",
        "command_error",
    ]
    assert batch["command_error"][0].as_py() == ""
