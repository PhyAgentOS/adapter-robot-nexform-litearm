#!/usr/bin/env python3
"""同构控制记录器：按固定节拍把主臂/从臂的 JointState 写成 JSONL。

每行：`{"t": 秒, "master": [...], "follower": [...]}`，关节顺序均为
`joint1..joint7`。由 `compare_homomorphic.py` 离线分析。
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from dora import Node
from forge_msgs import JointState

logger = logging.getLogger("state_recorder")

JOINTS = tuple(f"joint{i}" for i in range(1, 8))


class _Latest:
    def __init__(self) -> None:
        self.by_name: dict[str, float] = {}

    def update(self, state: JointState) -> None:
        self.by_name = {
            str(name): float(value) for name, value in zip(state.name, state.position)
        }

    def arm(self) -> list[float] | None:
        if not all(name in self.by_name for name in JOINTS):
            return None
        return [self.by_name[name] for name in JOINTS]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--every", type=float, default=0.05, help="采样间隔秒")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    node = Node()
    master = _Latest()
    follower = _Latest()
    started: float | None = None
    last_write = 0.0
    count = 0

    with output.open("w", encoding="utf-8") as handle:
        for event in node:
            if event["type"] in ("STOP", "ERROR"):
                break
            if event["type"] != "INPUT":
                continue

            if event["id"] == "master":
                master.update(JointState.from_arrow(event["value"]))
                continue
            if event["id"] == "follower":
                follower.update(JointState.from_arrow(event["value"]))
                continue
            if event["id"] != "tick":
                continue

            now = time.monotonic()
            if started is None:
                started = now
            if now - last_write < args.every:
                continue
            master_arm = master.arm()
            follower_arm = follower.arm()
            if master_arm is None or follower_arm is None:
                continue

            last_write = now
            handle.write(
                json.dumps(
                    {
                        "t": round(now - started, 4),
                        "master": [round(v, 6) for v in master_arm],
                        "follower": [round(v, 6) for v in follower_arm],
                    }
                )
                + "\n"
            )
            count += 1

    logger.info("state_recorder exit, samples=%d, output=%s", count, output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
