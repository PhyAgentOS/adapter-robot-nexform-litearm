#!/usr/bin/env python3
"""Dora 动作源：收到 state 后发一次 sparse JointCommand（绝对值）。

参考当前实测位置 + delta 作为目标，所以同一份 dataflow 在 fake 和真机上
语义一致。默认只发一次，避免持续运动。

输入：tick（定时器）、state（robot/state）
输出：action
"""

from __future__ import annotations

import argparse
import logging
import sys
import time

from dora import Node
from forge_msgs import JointCommand, JointState

logger = logging.getLogger("action_source")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--joint", default="joint7", help="要动的关节名")
    parser.add_argument("--delta", type=float, default=0.05, help="相对当前角度的增量 rad")
    parser.add_argument("--delay", type=float, default=2.0, help="等待多少秒再下发")
    parser.add_argument("--count", type=int, default=1)
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    node = Node()
    started = None
    latest: JointState | None = None
    sent = 0
    last_target: float | None = None

    for event in node:
        if event["type"] in ("STOP", "ERROR"):
            break
        if event["type"] != "INPUT":
            continue

        if event["id"] == "state":
            latest = JointState.from_arrow(event["value"])
            continue

        if event["id"] != "tick" or latest is None:
            continue

        now = time.monotonic()
        if started is None:
            started = now
        if now - started < args.delay or sent >= args.count:
            continue

        if args.joint not in latest.name:
            logger.error("%s not in state names %s", args.joint, latest.name)
            break
        index = latest.name.index(args.joint)
        if last_target is None:
            last_target = latest.position[index]
        target = last_target + args.delta
        last_target = target

        command = JointCommand(
            name=[args.joint],
            mode="position",
            position=[target],
        )
        node.send_output("action", command.to_arrow())
        sent += 1
        logger.info(
            "sent %s -> %.4f rad (current %.4f, delta %+.4f)",
            args.joint,
            target,
            latest.position[index],
            args.delta,
        )

    logger.info("action_source exit, sent=%d", sent)
    return 0


if __name__ == "__main__":
    sys.exit(main())
