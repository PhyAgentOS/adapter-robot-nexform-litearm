#!/usr/bin/env python3
"""Dora 控制命令源：按顺序发送 control 命令并打印回执。

输入：tick（定时器）、control_status（robot/control_status）
输出：control

示例：
    python3 control_source.py --command enable --command home --delay 1.0
"""

from __future__ import annotations

import argparse
import logging
import sys
import time

from dora import Node
from forge_msgs.arrow import ensure_record_batch

from litearm_robot.control import ControlRequest, ControlStatus

logger = logging.getLogger("control_source")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--command",
        action="append",
        dest="commands",
        choices=[
            "enable",
            "disable",
            "reset",
            "home",
            "stop",
            "emergency_stop",
        ],
        help="可重复；按给定顺序各发一次",
    )
    parser.add_argument("--delay", type=float, default=1.0, help="发下一条的间隔秒")
    parser.add_argument("--timeout-s", type=float, default=None, help="home 超时")
    parser.add_argument(
        "--exit-after", type=float, default=0.0,
        help="最后一条完成后多少秒退出；0 = 常驻",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    commands = args.commands or ["enable"]
    node = Node()
    started = None
    pending = list(commands)
    sent_at = 0.0
    done_at: float | None = None

    for event in node:
        if event["type"] in ("STOP", "ERROR"):
            break
        if event["type"] != "INPUT":
            continue

        if event["id"] == "control_status":
            value = ensure_record_batch(event["value"])
            status = ControlStatus(
                command=_column(value, "command"),
                request_id=_column(value, "request_id"),
                status=_column(value, "status"),
                message=_column(value, "message"),
            )
            logger.info(
                "status %s %s: %s",
                status.command,
                status.status,
                status.message,
            )
            if status.status in ("done", "error") and not pending:
                done_at = time.monotonic()
            continue

        if event["id"] != "tick":
            continue
        now = time.monotonic()
        if started is None:
            started = now
            sent_at = now - args.delay
        if not pending:
            if args.exit_after and done_at is not None:
                if now - done_at >= args.exit_after:
                    break
            continue
        if now - sent_at < args.delay:
            continue

        index = len(commands) - len(pending)
        request = ControlRequest(
            command=pending.pop(0),
            request_id=f"demo-{index}",
            timeout_s=args.timeout_s,
        )
        node.send_output("control", request.to_arrow())
        sent_at = now
        logger.info("sent control %s (request_id=%s)", request.command, request.request_id)

    logger.info("control_source exit, sent=%d", len(commands) - len(pending))
    return 0


def _column(value, name: str) -> str:
    if name not in value.schema.names:
        return ""
    raw = value[name][0].as_py()
    return "" if raw is None else str(raw)


if __name__ == "__main__":
    sys.exit(main())
