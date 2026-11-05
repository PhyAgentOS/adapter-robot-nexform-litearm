#!/usr/bin/env python3
"""LiteGrip 开合测试。默认只打印计划，必须显式 --execute 才动作。

注意：
- 开口单位 mm（SDK 口径），Forge 侧是两指总开口 m。
- 夹爪 stop/disconnect 会掉力矩，夹住的物体会掉落。
- 默认使用 SDK 打包的 factory calibration，不写用户标定文件。

用法：
    python gripper_open_close.py                       # dry-run
    python gripper_open_close.py --execute             # open -> close
    python gripper_open_close.py --execute --cycles 3
    python gripper_open_close.py --execute --channel can1
"""

from __future__ import annotations

import argparse
import sys
import time

MAX_OPEN_MM = 80.0


def _state_line(tag: str, state) -> str:
    age = getattr(state, "data_age_s", None)
    fresh = getattr(state, "fresh", None)
    return (
        f"{tag}: position={state.position_mm:6.1f} mm "
        f"force={state.force_n:5.1f} N freshest={fresh} age={age}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--channel", default="can0")
    parser.add_argument("--can-id", type=lambda s: int(s, 0), default=0x08)
    parser.add_argument("--mst-id", type=lambda s: int(s, 0), default=0x18)
    parser.add_argument("--open-mm", type=float, default=MAX_OPEN_MM)
    parser.add_argument("--close-mm", type=float, default=0.0)
    parser.add_argument("--speed", type=float, default=20.0, help="mm/s")
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)

    if not 0.0 <= args.close_mm < args.open_mm <= MAX_OPEN_MM:
        parser.error("要求 0 <= --close-mm < --open-mm <= 80")

    print(
        f"plan: {args.open_mm:.1f} mm <-> {args.close_mm:.1f} mm, "
        f"speed={args.speed} mm/s, cycles={args.cycles}"
    )
    if not args.execute:
        print("dry-run：未动作。确认夹爪路径无障碍后加 --execute。")
        return 0

    try:
        from litegrip import LiteGrip
    except ImportError:
        print("litegrip SDK 未安装，见 README §5", file=sys.stderr)
        return 1

    gripper = LiteGrip(
        args.channel,
        can_id=args.can_id,
        mst_id=args.mst_id,
        # 保持使能，避免脚本退出时带载松开。
        disable_on_disconnect=False,
    )
    try:
        if not gripper.connect():
            print(f"failed to connect on {args.channel}", file=sys.stderr)
            return 1
        gripper.load_calibration()
        gripper.enable()
        print(_state_line("initial", gripper.get_state(wait=True)))

        for cycle in range(args.cycles):
            print(f"--- cycle {cycle + 1}/{args.cycles}")
            gripper.goto(args.open_mm, duration=1.0)
            print(_state_line("open", gripper.get_state(wait=True)))
            time.sleep(0.2)
            gripper.goto(args.close_mm, duration=1.0)
            print(_state_line("close", gripper.get_state(wait=True)))
            time.sleep(0.2)
    finally:
        # 不调用 stop()：会掉力矩。仅断开通信。
        gripper.disconnect()
    return 0


if __name__ == "__main__":
    sys.exit(main())
