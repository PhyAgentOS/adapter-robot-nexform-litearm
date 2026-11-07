"""forge_bridge 协议、命令编解码与 TCP 服务的无硬件测试。"""

from __future__ import annotations

import importlib.util
import json
import math
import socket
import threading
import time

import pytest

HAVE_FORGE = importlib.util.find_spec("forge_msgs") is not None
pytestmark = pytest.mark.skipif(
    not HAVE_FORGE, reason="forge_msgs not installed"
)

if HAVE_FORGE:
    from forge_msgs import JointCommand, JointState

    from litearm_robot.bridge import (
        Bridge,
        BridgeOptions,
        BridgeServer,
        handle_line,
        handle_request,
    )
    from litearm_robot.codec import ARM_JOINTS, GRIPPER, GRIPPER_MAX_M
    from litearm_robot.control import ControlRequest, ControlStatus


class FakeNode:
    def __init__(self) -> None:
        self.outputs: list[tuple[str, object]] = []

    def send_output(self, output_id, value) -> None:
        self.outputs.append((output_id, value))

    def of(self, output_id: str) -> list[object]:
        return [value for name, value in self.outputs if name == output_id]


def _q(value: float = 0.0) -> list[float]:
    return [value] * len(ARM_JOINTS)


def _set_state(bridge: Bridge, q: list[float], gripper: float | None = 0.04) -> None:
    names = list(ARM_JOINTS)
    positions = list(q)
    if gripper is not None:
        names.append(GRIPPER)
        positions.append(gripper)
    bridge.set_state(
        JointState(
            name=names,
            position=positions,
            velocity=[0.0] * len(names),
            effort=[0.0] * len(names),
        )
    )


def _start(bridge: Bridge, msg, options: BridgeOptions):
    box: dict = {}
    thread = threading.Thread(
        target=lambda: box.update(resp=handle_request(bridge, msg, options)),
        daemon=True,
    )
    thread.start()
    return thread, box


def _pump_until(bridge: Bridge, node: FakeNode, predicate, timeout: float = 2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        bridge.pump(node)
        if predicate():
            return True
        time.sleep(0.005)
    return predicate()


# ------------------------------------------------------------------ 读状态


def test_state_without_data():
    response = handle_line(Bridge(), '{"cmd":"state"}')
    assert response["ok"] is True
    assert response["valid"] is False
    assert response["q"] is None
    assert response["age_s"] is None


def test_state_with_data():
    bridge = Bridge()
    _set_state(bridge, [0.1, 0.2, 0.3, -0.4, 0.5, 0.6, 0.7], gripper=0.05)
    response = handle_line(bridge, '{"cmd":"status","id":"a"}')
    assert response["ok"] is True
    assert response["valid"] is True
    assert response["id"] == "a"
    assert response["q"] == pytest.approx([0.1, 0.2, 0.3, -0.4, 0.5, 0.6, 0.7])
    assert response["gripper_m"] == pytest.approx(0.05)
    assert response["age_s"] >= 0.0


def test_state_stale_is_flagged():
    bridge = Bridge(BridgeOptions(state_timeout=0.01))
    _set_state(bridge, _q())
    time.sleep(0.02)
    response = handle_line(bridge, '{"cmd":"state"}')
    assert response["ok"] is True
    assert response["valid"] is False
    assert response["q"] is not None


def test_robot_status_cached():
    import pyarrow as pa

    bridge = Bridge()
    bridge.set_robot_status(
        pa.RecordBatch.from_pydict(
            {
                "enabled": pa.array([True], type=pa.bool_()),
                "mode": pa.array(["POSITION"], type=pa.string()),
                "faulted": pa.array([False], type=pa.bool_()),
                "faults": pa.array([""], type=pa.string()),
                "joint_fault": pa.array([0], type=pa.int64()),
            }
        )
    )
    response = handle_line(bridge, '{"cmd":"state"}')
    assert response["enabled"] is True
    assert response["mode"] == "POSITION"
    assert response["joint_fault"] == 0


# ------------------------------------------------------------------ 协议层


def test_ping():
    assert handle_line(Bridge(), '{"cmd":"ping"}') == {
        "cmd": "ping",
        "ok": True,
        "pong": True,
    }


def test_unknown_command_rejected():
    response = handle_line(Bridge(), '{"cmd":"dance"}')
    assert response["ok"] is False
    assert "未知命令" in response["error"]


def test_bad_json_rejected():
    response = handle_line(Bridge(), "{not json")
    assert response["ok"] is False
    assert "JSON" in response["error"]


def test_non_object_rejected():
    response = handle_request(Bridge(), [1, 2, 3])
    assert response["ok"] is False


def test_oversized_line_rejected_by_server():
    options = BridgeOptions(host="127.0.0.1", port=0)
    bridge = Bridge(options)
    server = BridgeServer(bridge, options)
    server.start()
    try:
        with socket.create_connection(
            ("127.0.0.1", server.bound_port), timeout=2.0
        ) as sock:
            sock.sendall(b"x" * (64 * 1024 + 10))
            sock.settimeout(2.0)
            response = json.loads(sock.makefile("rb").readline())
        assert response["ok"] is False
        assert "行长度" in response["error"]
    finally:
        server.close()


# ----------------------------------------------------------------- action


def test_movej_dispatches_action():
    options = BridgeOptions(dispatch_timeout=1.0)
    bridge = Bridge(options)
    node = FakeNode()
    target = [0.1, -0.2, 0.3, -0.4, 0.5, -0.6, 0.7]
    thread, box = _start(
        bridge, {"cmd": "movej", "q": target, "wait": False}, options
    )
    assert _pump_until(bridge, node, lambda: bool(node.of("action")))
    thread.join(timeout=2.0)

    batch = node.of("action")[0]
    command = JointCommand.from_arrow(batch)
    assert list(command.name) == list(ARM_JOINTS)
    assert list(command.position) == pytest.approx(target)
    assert "speed" not in batch.schema.names
    assert box["resp"]["ok"] is True
    assert box["resp"]["settled"] is None
    assert box["resp"]["clipped"] is False


def test_movej_speed_column():
    options = BridgeOptions(dispatch_timeout=1.0)
    bridge = Bridge(options)
    node = FakeNode()
    thread, box = _start(
        bridge, {"cmd": "movej", "q": _q(), "speed": 0.25, "wait": False}, options
    )
    assert _pump_until(bridge, node, lambda: bool(node.of("action")))
    thread.join(timeout=2.0)

    batch = node.of("action")[0]
    assert batch.schema.names[-1] == "speed"
    assert batch["speed"][0].as_py() == pytest.approx(0.25)
    assert box["resp"]["speed"] == pytest.approx(0.25)


def test_movej_clips_to_limits():
    options = BridgeOptions(dispatch_timeout=1.0)
    bridge = Bridge(options)
    node = FakeNode()
    target = _q(10.0)
    thread, box = _start(
        bridge, {"cmd": "movej", "q": target, "wait": False}, options
    )
    assert _pump_until(bridge, node, lambda: bool(node.of("action")))
    thread.join(timeout=2.0)

    assert box["resp"]["clipped"] is True
    command = JointCommand.from_arrow(node.of("action")[0])
    assert list(command.position)[0] == pytest.approx(2.827)


@pytest.mark.parametrize(
    "q",
    [
        [0.0] * 6,
        [0.0] * 8,
        ["nan"] * 7,
        [math.nan] + [0.0] * 6,
        [math.inf] + [0.0] * 6,
    ],
)
def test_movej_rejects_bad_targets(q):
    response = handle_request(Bridge(), {"cmd": "movej", "q": q})
    assert response["ok"] is False


def test_movej_settles_on_fresh_state():
    options = BridgeOptions(
        dispatch_timeout=1.0, settle_timeout=0.5, poll_period=0.005
    )
    bridge = Bridge(options)
    node = FakeNode()
    # 取所有关节限位以内的目标（joint4 上限只有 0.035 rad）。
    target = [0.02] * len(ARM_JOINTS)
    thread, box = _start(bridge, {"cmd": "movej", "q": target}, options)
    assert _pump_until(bridge, node, lambda: bool(node.of("action")))

    # 动作发出去之后才到的新鲜状态才算数。
    while "resp" not in box:
        _set_state(bridge, target)
        time.sleep(0.005)
    thread.join(timeout=2.0)

    assert box["resp"]["ok"] is True
    assert box["resp"]["settled"] is True
    assert box["resp"]["elapsed_s"] >= 0.0


def test_movej_timeout_when_never_settles():
    options = BridgeOptions(
        dispatch_timeout=1.0, settle_timeout=0.1, poll_period=0.005
    )
    bridge = Bridge(options)
    node = FakeNode()
    thread, box = _start(bridge, {"cmd": "movej", "q": [0.5] * 7}, options)
    while "resp" not in box:
        _set_state(bridge, _q())
        bridge.pump(node)
        time.sleep(0.005)
    thread.join(timeout=2.0)

    assert box["resp"]["ok"] is False
    assert box["resp"]["settled"] is False
    assert "未到位" in box["resp"]["error"]


def test_movej_dispatch_timeout_without_loop():
    options = BridgeOptions(dispatch_timeout=0.01)
    response = handle_request(
        Bridge(options), {"cmd": "movej", "q": _q(), "wait": False}, options
    )
    assert response["ok"] is False
    assert "未取走" in response["error"]


# ---------------------------------------------------------------- gripper


def test_gripper_clips_and_dispatches():
    options = BridgeOptions(dispatch_timeout=1.0)
    bridge = Bridge(options)
    node = FakeNode()
    thread, box = _start(bridge, {"cmd": "gripper", "opening_m": 0.2}, options)
    assert _pump_until(bridge, node, lambda: bool(node.of("action")))
    thread.join(timeout=2.0)

    command = JointCommand.from_arrow(node.of("action")[0])
    assert list(command.name) == [GRIPPER]
    assert list(command.position) == pytest.approx([GRIPPER_MAX_M])
    assert box["resp"]["ok"] is True
    assert box["resp"]["clipped"] is True
    assert box["resp"]["opening_m"] == pytest.approx(GRIPPER_MAX_M)


def test_gripper_requires_opening():
    response = handle_request(Bridge(), {"cmd": "gripper"})
    assert response["ok"] is False


# ------------------------------------------------------- control receipts


def _control_request(node: FakeNode) -> ControlRequest:
    for batch in node.of("control"):
        request = ControlRequest.from_arrow(batch)
        if request.request_id:
            return request
    raise AssertionError("no control output")


def test_control_home_waits_for_final_status():
    options = BridgeOptions(dispatch_timeout=1.0, control_timeout=2.0)
    bridge = Bridge(options)
    node = FakeNode()
    thread, box = _start(bridge, {"cmd": "home", "timeout_s": 1.0}, options)
    assert _pump_until(bridge, node, lambda: bool(node.of("control")))
    request = _control_request(node)
    assert request.command == "home"
    assert request.timeout_s == pytest.approx(1.0)

    bridge.on_control_status(
        ControlStatus(
            command="home",
            request_id=request.request_id,
            status="accepted",
            message="queued",
        ).to_arrow()
    )
    time.sleep(0.02)
    assert "resp" not in box  # accepted 不是终态

    bridge.on_control_status(
        ControlStatus(
            command="home",
            request_id=request.request_id,
            status="done",
            message="home complete",
        ).to_arrow()
    )
    thread.join(timeout=2.0)
    assert box["resp"]["ok"] is True
    assert box["resp"]["status"] == "done"
    assert box["resp"]["message"] == "home complete"


def test_estop_alias_maps_to_emergency_stop():
    options = BridgeOptions(dispatch_timeout=1.0)
    bridge = Bridge(options)
    node = FakeNode()
    thread, box = _start(bridge, {"cmd": "estop", "id": "e1"}, options)
    assert _pump_until(bridge, node, lambda: bool(node.of("control")))
    request = _control_request(node)
    assert request.command == "emergency_stop"

    bridge.on_control_status(
        ControlStatus(
            command="emergency_stop",
            request_id=request.request_id,
            status="done",
            message="stopped",
        ).to_arrow()
    )
    thread.join(timeout=2.0)
    assert box["resp"]["ok"] is True
    assert box["resp"]["cmd"] == "estop"
    assert box["resp"]["command"] == "emergency_stop"
    assert box["resp"]["id"] == "e1"


def test_control_timeout():
    options = BridgeOptions(dispatch_timeout=1.0, control_timeout=0.05)
    bridge = Bridge(options)
    node = FakeNode()
    thread, box = _start(bridge, {"cmd": "enable"}, options)
    assert _pump_until(bridge, node, lambda: bool(node.of("control")))
    thread.join(timeout=2.0)

    assert box["resp"]["ok"] is False
    assert box["resp"]["status"] == "timeout"


def test_control_ignores_non_final_and_unknown_ids():
    bridge = Bridge()
    waiter = bridge.expect_status("known")
    bridge.on_control_status(
        ControlStatus(
            command="home", request_id="known", status="accepted"
        ).to_arrow()
    )
    assert not waiter.event.is_set()
    bridge.on_control_status(
        ControlStatus(
            command="home", request_id="other", status="done"
        ).to_arrow()
    )
    assert not waiter.event.is_set()


def test_bridge_close_wakes_waiters():
    bridge = Bridge()
    waiter = bridge.expect_status("pending")
    bridge.close()
    assert waiter.event.is_set()
    assert waiter.status == "closed"


# ------------------------------------------------------------------ TCP


def test_server_roundtrip():
    options = BridgeOptions(host="127.0.0.1", port=0, state_timeout=5.0)
    bridge = Bridge(options)
    _set_state(bridge, _q(0.25), gripper=0.03)
    server = BridgeServer(bridge, options)
    server.start()
    try:
        with socket.create_connection(
            ("127.0.0.1", server.bound_port), timeout=2.0
        ) as sock:
            reader = sock.makefile("rb")
            sock.sendall(b'{"cmd":"state","id":"tcp-1"}\n')
            response = json.loads(reader.readline())
            assert response["ok"] is True
            assert response["id"] == "tcp-1"
            assert response["q"][0] == pytest.approx(0.25)

            sock.sendall(b"{bad}\n")
            response = json.loads(reader.readline())
            assert response["ok"] is False
    finally:
        server.close()
