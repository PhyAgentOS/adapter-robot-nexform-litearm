#!/usr/bin/env python3
"""急停路径测试：验证 disable() 能从 SDK 侧切断电机使能。

默认只打印状态，不做任何动作。加 --execute 才会失能。

警告：litearm SDK 没有独立的“取消当前运动”接口。这里的安全动作是
arm.disable()——臂会立刻失去保持力，无支撑姿态会下坠。执行前必须人工托住
或确认姿态自锁。

硬件急停按钮/断电方式尚未归档，见 docs/hardware.md。

用法：
    python safety_stop.py              # 只读
    python safety_stop.py --execute    # 失能（需要输入确认）
    python safety_stop.py --execute --yes
    python safety_stop.py --execute --enable-after   # 失能后重新使能
"""

from __future__ import annotations

import argparse
import sys
import time


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default=None)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--yes", action="store_true", help="跳过交互确认")
    parser.add_argument(
        "--enable-after",
        action="store_true",
        help="失能后重新使能，确认可以恢复",
    )
    args = parser.parse_args(argv)

    try:
        import litearm as pa
    except ImportError:
        print("litearm SDK 未安装，见 README §5", file=sys.stderr)
        return 1

    arm = pa.Arm(port=args.port).connect()
    try:
        state = arm.get_state().value
        print(f"firmware={getattr(arm, 'firmware', 'unknown')} "
              f"mode={getattr(state, 'mode_name', 'unknown')}")
        print("current:", " ".join(f"{j.q:+.3f}" for j in state.joints))

        if not args.execute:
            print("dry-run：未失能。确认姿态有支撑后加 --execute。")
            return 0

        if not args.yes:
            print("即将失能：臂会失去保持力。")
            if input("确认已托住？输入 DISABLE 继续：").strip() != "DISABLE":
                print("已取消。")
                return 1

        arm.disable()
        time.sleep(0.3)
        after = arm.get_state().value
        print(
            f"disabled: mode={getattr(after, 'mode_name', 'unknown')} "
            f"flags={list(getattr(after, 'flag_names', []) or [])}"
        )

        if args.enable_after:
            arm.enable()
            time.sleep(0.3)
            print(
                f"re-enabled: mode="
                f"{getattr(arm.get_state().value, 'mode_name', 'unknown')}"
            )
    finally:
        arm.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
