#!/usr/bin/env python3
"""确定性主臂轨迹：验收清单第 12 项的同构控制输入。

现场只有一台 LiteArm，没有第二台物理主臂，因此用脚本化 `JointState` 模拟
leader。下游通路与真实主臂完全一致：

- 仿真：`mirror_command.py` 转成 `JointCommand(position)` 驱动 `mujoco_sim`
- 真机：标准 runner 的 `master_state` 输入镜像成 `JointCommand(position)`

轨迹为三个姿态（初始 / 中间 / 偏转）再回到初始，每段用 smoothstep 慢速过渡：

    A -> B -> C -> A

姿态以 `--base`（或 `--base-file` 读取的当前实测位姿）为基准加固定偏置，
因此仿真的基准取全零，真机的基准取当前位姿，两边的**偏置相同**，可直接对比
从臂的跟踪误差与方向一致性。

输出 `state`：`forge_msgs.JointState`，50 Hz。
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

logger = logging.getLogger("master_trajectory")

JOINTS = tuple(f"joint{i}" for i in range(1, 8))

# 相对基准的偏置。避开真机当前贴近下限的 J2/J4，只用 J1/J3/J5/J7。
# 量级 0.10–0.20 rad，慢速下对真机安全，也足以观察方向与跟踪误差。
OFFSET_B = (0.15, 0.0, -0.10, 0.0, 0.10, 0.0, 0.10)
OFFSET_C = (0.15, 0.0, -0.20, 0.0, 0.20, 0.0, 0.10)


def _parse_base(text: str) -> list[float]:
    values = [float(v) for v in text.split(",")]
    if len(values) != len(JOINTS):
        raise SystemExit(f"--base 需要 {len(JOINTS)} 个逗号分隔的数")
    return values


def _load_base(path: str) -> list[float]:
    """读取 `python -m litearm_robot.main probe` 的输出。"""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    names = payload["name"]
    values = payload["position"]
    by_name = dict(zip(names, values, strict=True))
    return [float(by_name[name]) for name in JOINTS]


def _smoothstep(u: float) -> float:
    u = min(max(u, 0.0), 1.0)
    return u * u * (3.0 - 2.0 * u)


def _pose_at(elapsed: float, base: list[float], hold: float, ramp: float) -> tuple[list[float], int]:
    poses = [
        base,
        [b + o for b, o in zip(base, OFFSET_B, strict=True)],
        [b + o for b, o in zip(base, OFFSET_C, strict=True)],
        base,
    ]
    if elapsed < hold:
        return poses[0], 0
    elapsed -= hold
    for leg in range(3):
        start, end = poses[leg], poses[leg + 1]
        if elapsed < ramp:
            s = _smoothstep(elapsed / ramp)
            return [a + (b - a) * s for a, b in zip(start, end, strict=True)], leg + 1
        elapsed -= ramp
        if elapsed < hold:
            return end, leg + 1
        elapsed -= hold
    return poses[-1], 3


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--base", help="基准位姿，7 个逗号分隔的 rad，默认全零")
    group.add_argument("--base-file", help="litearm_robot probe 输出的 JSON")
    parser.add_argument("--hold", type=float, default=1.0, help="每段保持秒数")
    parser.add_argument("--ramp", type=float, default=4.0, help="每段过渡秒数")
    parser.add_argument(
        "--start-delay",
        type=float,
        default=0.5,
        help="启动后先保持基准位姿的秒数（等从臂连接/使能）",
    )
    args = parser.parse_args(argv)

    if args.base_file:
        base = _load_base(args.base_file)
    elif args.base:
        base = _parse_base(args.base)
    else:
        base = [0.0] * len(JOINTS)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger.info("base=%s", [round(v, 4) for v in base])

    node = Node()
    started: float | None = None
    last_leg = -1

    for event in node:
        if event["type"] in ("STOP", "ERROR"):
            break
        if event["type"] != "INPUT" or event["id"] != "tick":
            continue

        now = time.monotonic()
        if started is None:
            started = now
        elapsed = now - started - args.start_delay
        if elapsed < 0.0:
            position, leg = base, 0
        else:
            position, leg = _pose_at(elapsed, base, args.hold, args.ramp)
        if leg != last_leg:
            logger.info("leg %d -> %s", leg, [round(v, 4) for v in position])
            last_leg = leg

        node.send_output(
            "state",
            JointState(
                name=list(JOINTS), position=position, velocity=[], effort=[]
            ).to_arrow(),
        )

    logger.info("master_trajectory exit")
    return 0


if __name__ == "__main__":
    sys.exit(main())
