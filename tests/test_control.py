"""control 扩展消息的无硬件测试。"""

from __future__ import annotations

import importlib.util

import pytest

HAVE_FORGE = importlib.util.find_spec("forge_msgs") is not None
pytestmark = pytest.mark.skipif(
    not HAVE_FORGE, reason="forge_msgs not installed"
)

if HAVE_FORGE:
    import pyarrow as pa

    from litearm_robot.control import (
        CONTROL_COMMANDS,
        ControlRequest,
        ControlStatus,
    )


def test_request_roundtrip():
    request = ControlRequest(
        command="home", request_id="req-1", timeout_s=30.0
    )
    parsed = ControlRequest.from_arrow(request.to_arrow())
    assert parsed == request


def test_request_defaults():
    batch = pa.RecordBatch.from_pydict(
        {"command": pa.array(["enable"], type=pa.string())}
    )
    parsed = ControlRequest.from_arrow(batch)
    assert parsed.command == "enable"
    assert parsed.request_id == ""
    assert parsed.timeout_s is None


def test_every_command_accepted():
    for command in CONTROL_COMMANDS:
        parsed = ControlRequest.from_arrow(
            pa.RecordBatch.from_pydict(
                {"command": pa.array([command], type=pa.string())}
            )
        )
        assert parsed.command == command


def test_unknown_command_rejected():
    batch = pa.RecordBatch.from_pydict(
        {"command": pa.array(["reboot"], type=pa.string())}
    )
    with pytest.raises(ValueError):
        ControlRequest.from_arrow(batch)


def test_missing_command_rejected():
    batch = pa.RecordBatch.from_pydict(
        {"request_id": pa.array([""], type=pa.string())}
    )
    with pytest.raises(ValueError):
        ControlRequest.from_arrow(batch)


@pytest.mark.parametrize("bad", [0.0, -1.0, float("nan"), float("inf")])
def test_invalid_timeout_rejected(bad):
    batch = pa.RecordBatch.from_pydict(
        {
            "command": pa.array(["home"], type=pa.string()),
            "timeout_s": pa.array([bad], type=pa.float64()),
        }
    )
    with pytest.raises(ValueError):
        ControlRequest.from_arrow(batch)


def test_multiple_rows_rejected():
    batch = pa.RecordBatch.from_pydict(
        {"command": pa.array(["enable", "disable"], type=pa.string())}
    )
    with pytest.raises(ValueError):
        ControlRequest.from_arrow(batch)


def test_status_arrow_fields():
    status = ControlStatus(
        command="home",
        request_id="req-2",
        status="done",
        message="home complete",
    )
    batch = status.to_arrow()
    assert batch.schema.names == [
        "command",
        "request_id",
        "status",
        "message",
    ]
    assert batch["status"][0].as_py() == "done"
