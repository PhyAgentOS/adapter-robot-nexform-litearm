#!/usr/bin/env python3
"""Dora 状态消费者：慢速打印 robot/state，验证发布订阅链路。"""

from __future__ import annotations

import argparse
import logging
import sys
import time

from dora import Node
from forge_msgs import JointState

logger = logging.getLogger("state_print")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--every", type=float, default=1.0, help="打印间隔秒")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    node = Node()
    last_print = 0.0
    count = 0

    for event in node:
        if event["type"] in ("STOP", "ERROR"):
            break
        if event["type"] != "INPUT" or event["id"] != "state":
            continue

        state = JointState.from_arrow(event["value"])
        count += 1
        now = time.monotonic()
        if now - last_print < args.every:
            continue
        last_print = now
        summary = " ".join(
            f"{name}={value:+.3f}"
            for name, value in zip(state.name, state.position)
        )
        logger.info("state#%d %s", count, summary)

    logger.info("state_print exit, received=%d", count)
    return 0


if __name__ == "__main__":
    sys.exit(main())
