"""`control` 扩展输入与 `control_status` 回执的消息定义。

本适配器在标准 `tick/action/master_state` 之外增加一个 `control` 输入，
承载离散控制面命令。消息是一行 Arrow RecordBatch：

- `command`：`enable` / `disable` / `reset` / `home` / `stop` / `emergency_stop`
- `request_id`：调用方自定义的回执关联 id，可为空
- `timeout_s`：`home` 的超时，可为空（缺省用 `config.home_timeout_s`）

回执 `control_status` 使用 `accepted/done/rejected/error` 四种状态。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import pyarrow as pa
from forge_msgs.arrow import ensure_record_batch

ControlCommand = Literal[
    "enable",
    "disable",
    "reset",
    "home",
    "stop",
    "emergency_stop",
]
CONTROL_COMMANDS: tuple[str, ...] = (
    "enable",
    "disable",
    "reset",
    "home",
    "stop",
    "emergency_stop",
)

ControlStatusValue = Literal["accepted", "done", "rejected", "error"]
STATUS_VALUES: tuple[str, ...] = ("accepted", "done", "rejected", "error")


def _string_column(batch: pa.RecordBatch, name: str) -> str:
    if name not in batch.schema.names:
        return ""
    value = batch[name][0].as_py()
    return "" if value is None else str(value)


@dataclass(frozen=True)
class ControlRequest:
    command: str
    request_id: str = ""
    timeout_s: float | None = None

    @classmethod
    def from_arrow(
        cls, data: pa.RecordBatch | pa.Table | pa.StructArray | bytes
    ) -> "ControlRequest":
        batch = ensure_record_batch(data)
        if batch.num_rows != 1:
            raise ValueError(
                f"control 必须恰好一行，收到 {batch.num_rows} 行"
            )
        command = _string_column(batch, "command")
        if command not in CONTROL_COMMANDS:
            raise ValueError(
                f"未知 control 命令 {command!r}；允许 {list(CONTROL_COMMANDS)}"
            )
        request_id = _string_column(batch, "request_id")

        timeout_s: float | None = None
        if "timeout_s" in batch.schema.names:
            raw = batch["timeout_s"][0].as_py()
            if raw is not None:
                timeout_s = float(raw)
                if not math.isfinite(timeout_s) or timeout_s <= 0.0:
                    raise ValueError(
                        f"timeout_s 必须是有限正数，收到 {timeout_s}"
                    )

        return cls(
            command=command,
            request_id=request_id,
            timeout_s=timeout_s,
        )

    def to_arrow(self) -> pa.RecordBatch:
        return pa.RecordBatch.from_pydict(
            {
                "command": pa.array([self.command], type=pa.string()),
                "request_id": pa.array([self.request_id], type=pa.string()),
                "timeout_s": pa.array([self.timeout_s], type=pa.float64()),
            }
        )


@dataclass(frozen=True)
class ControlStatus:
    command: str
    status: str
    message: str = ""
    request_id: str = ""

    def to_arrow(self) -> pa.RecordBatch:
        return pa.RecordBatch.from_pydict(
            {
                "command": pa.array([self.command], type=pa.string()),
                "request_id": pa.array([self.request_id], type=pa.string()),
                "status": pa.array([self.status], type=pa.string()),
                "message": pa.array([self.message], type=pa.string()),
            }
        )
