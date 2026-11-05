#!/usr/bin/env python3
"""只读状态测试：直连 litearm SDK，不进入 Dora，不发射任何运动命令。

用法：
    python read_state.py                 # 读一次
    python read_state.py --repeat 5 --interval 0.5
    python read_state.py --port /dev/ttyACM0
    python read_state.py --json          # 机器可读
"""

from __future__ import annotations

import argparse
import json
import sys
import time

JOINT_NAMES = [f"joint{i}" for i in range(1, 8)]


def _read(arm) -> dict:
    state = arm.get_state().value
    return {
        "firmware": getattr(arm, "firmware", "unknown"),
        "mode": getattr(state, "mode_name", "unknown"),
        "flags": list(getattr(state, "flag_names", []) or []),
        "seq": getattr(state, "seq", None),
        "joints": [
            {
                "name": name,
                "q": joint.q,
                "dq": joint.dq,
                "tau": joint.tau,
                "t_mos": getattr(joint, "t_mos", None),
                "t_coil": getattr(joint, "t_coil", None),
                "err": getattr(joint, "err", None),
            }
            for name, joint in zip(JOINT_NAMES, state.joints)
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default=None, help="默认交给 SDK 自动发现")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        import litearm as pa
    except ImportError:
        print("litearm SDK 未安装，见 README §5", file=sys.stderr)
        return 1

    arm = pa.Arm(port=args.port).connect()
    try:
        print(f"connected: firmware={getattr(arm, 'firmware', 'unknown')}")
        for index in range(args.repeat):
            payload = _read(arm)
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print(
                    f"[{index}] mode={payload['mode']} "
                    f"flags={payload['flags']} seq={payload['seq']}"
                )
                for joint in payload["joints"]:
                    print(
                        f"  {joint['name']}: q={joint['q']:+.4f} rad "
                        f"dq={joint['dq']:+.4f} tau={joint['tau']:+.3f} Nm "
                        f"err={joint['err']}"
                    )
            if index + 1 < args.repeat:
                time.sleep(args.interval)
    finally:
        arm.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
