#!/usr/bin/env python3
"""单关节小步进测试。默认只打印计划，必须显式 --execute 才运动。

安全约定：
- 步进上限 0.05 rad，速度上限 0.2；超出直接拒绝。
- 其余关节保持当前实测位置不动。
- 动作结束后默认 disable（台架经验：静止保持会持续发热），
  失能前请确认姿态有支撑。用 --keep-enabled 可保持使能。

用法：
    python move_single_joint.py --joint 0 --delta 0.02           # dry-run
    python move_single_joint.py --joint 0 --delta 0.02 --execute # 真机
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from litearm_robot.codec import (  # noqa: E402
    ARM_JOINTS,
    JOINT_LIMITS,
    clip_arm_positions,
)

MAX_STEP_RAD = 0.05
MAX_SPEED = 0.2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--joint", type=int, required=True, help="0..6，对应 joint1..joint7")
    parser.add_argument("--delta", type=float, required=True, help="增量，单位 rad")
    parser.add_argument("--speed", type=float, default=0.1)
    parser.add_argument("--port", default=None)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument(
        "--keep-enabled",
        action="store_true",
        help="动作后保持使能（默认动作完失能）",
    )
    args = parser.parse_args(argv)

    if not 0 <= args.joint < len(ARM_JOINTS):
        parser.error(f"--joint 必须在 0..{len(ARM_JOINTS) - 1}")
    if abs(args.delta) > MAX_STEP_RAD:
        parser.error(f"单次步进不得超过 {MAX_STEP_RAD} rad")
    if not 0.0 < args.speed <= MAX_SPEED:
        parser.error(f"--speed 必须在 (0, {MAX_SPEED}]")

    try:
        import litearm as pa
    except ImportError:
        print("litearm SDK 未安装，见 README §5", file=sys.stderr)
        return 1

    name = ARM_JOINTS[args.joint]
    lower, upper = JOINT_LIMITS[name]

    arm = pa.Arm(port=args.port).connect()
    try:
        current = [float(j.q) for j in arm.get_state().value.joints]
        target = list(current)
        target[args.joint] = current[args.joint] + args.delta

        clipped = clip_arm_positions(
            {joint: target[i] for i, joint in enumerate(ARM_JOINTS)}
        )
        target = [clipped[joint] for joint in ARM_JOINTS]

        print(f"{name}: {current[args.joint]:+.4f} -> {target[args.joint]:+.4f} rad")
        print(f"limit: [{lower:+.3f}, {upper:+.3f}] rad, speed={args.speed}")
        if target[args.joint] != current[args.joint] + args.delta:
            print("注意：目标已被限位裁剪")

        if not args.execute:
            print("dry-run：未下发运动。确认环境与支撑后加 --execute。")
            return 0

        print("警告：即将运动，请确认周围无人、姿态有支撑。")
        arm.enable()
        arm.movej_sync(target, speed=args.speed)
        after = [float(j.q) for j in arm.get_state().value.joints]
        print(f"完成：{name} 实测 {after[args.joint]:+.4f} rad")

        if not args.keep_enabled:
            time.sleep(0.2)
            print("失能：臂将失去保持力，请确认已托住。")
            arm.disable()
    finally:
        arm.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
