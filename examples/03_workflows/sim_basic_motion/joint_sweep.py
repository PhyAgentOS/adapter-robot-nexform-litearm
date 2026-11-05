#!/usr/bin/env python3
"""仿真关节 sweep：逐个关节走 下限 -> 上限 -> 0，写 JSONL 证据。

对应验收清单第 7 项（仿真中所有 joint 完成最小/最大/归零）。
仅用于仿真或 fake；真机 sweep 必须按第 8 项单独批准并用更低速度。

输出：--output 指定的 JSONL，每行一个航点实测结果。
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from dora import Node  # noqa: E402
from forge_msgs import JointCommand, JointState  # noqa: E402

from litearm_robot.codec import (  # noqa: E402
    ARM_JOINTS,
    JOINT_LIMITS,
    clip_arm_positions,
)

logger = logging.getLogger("joint_sweep")


def _waypoints(margin: float) -> list[tuple[str, float]]:
    points: list[tuple[str, float]] = []
    for name in ARM_JOINTS:
        lower, upper = JOINT_LIMITS[name]
        points.append((name, lower * margin))
        points.append((name, upper * margin))
        points.append((name, 0.0))
    return points


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hold", type=float, default=0.5, help="每个航点保持秒数")
    parser.add_argument("--margin", type=float, default=0.9, help="限位缩放，0..1")
    parser.add_argument("--tolerance", type=float, default=0.02, help="判定到位阈值 rad")
    parser.add_argument("--output", default="validation_output/sim_sweep.jsonl")
    args = parser.parse_args(argv)

    if not 0.0 < args.margin <= 1.0:
        parser.error("--margin 必须在 (0, 1]")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    waypoints = _waypoints(args.margin)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    handle = output.open("w", encoding="utf-8")

    node = Node()
    latest: JointState | None = None
    index = 0
    entered_at: float | None = None
    passed = 0

    try:
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
            if index >= len(waypoints):
                break

            name, target = waypoints[index]
            target = clip_arm_positions({name: target})[name]

            if entered_at is None:
                node.send_output(
                    "action",
                    JointCommand(
                        name=[name], mode="position", position=[target]
                    ).to_arrow(),
                )
                entered_at = now
                logger.info(
                    "[%d/%d] %s -> %+.3f rad",
                    index + 1,
                    len(waypoints),
                    name,
                    target,
                )
                continue

            if now - entered_at < args.hold:
                continue

            if name not in latest.name:
                logger.error("state 缺少 %s，终止", name)
                break
            actual = latest.position[latest.name.index(name)]
            reached = abs(actual - target) <= args.tolerance
            passed += int(reached)
            record = {
                "joint": name,
                "target_rad": round(target, 6),
                "actual_rad": round(float(actual), 6),
                "tolerance_rad": args.tolerance,
                "reached": reached,
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            handle.flush()
            logger.info(
                "  actual=%+.3f reached=%s", actual, reached
            )
            index += 1
            entered_at = None
    finally:
        handle.close()

    logger.info(
        "sweep 结束：%d/%d 航点到位，记录 %s",
        passed,
        len(waypoints),
        output,
    )
    return 0 if passed == len(waypoints) else 1


if __name__ == "__main__":
    sys.exit(main())
