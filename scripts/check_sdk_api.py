"""核对本仓用到的厂商 SDK 接口。

需要先安装钉住版本的 litearm-python / litegrip-python；不在 CI 中运行。
接口缺失或签名不兼容时返回非零。

    python scripts/check_sdk_api.py
"""

from __future__ import annotations

import inspect
import sys

# 名称 -> 必需参数（None 表示只检查存在性）
ARM_METHODS: dict[str, tuple[str, ...] | None] = {
    "connect": (),
    "close": (),
    "enable": ("attempts",),
    "disable": (),
    "get_state": ("refresh",),
    "movej_sync": ("q", "speed"),
    "movej": ("q", "speed"),
    "move_l": ("pose", "speed", "wait"),
    "move_p": ("pose", "speed", "pos_tol", "rpy_tol"),
    "ik": ("pose", "q_seed", "timeout"),
    "get_tcp": ("timeout",),
    "get_status_now": ("timeout",),
    "set_tcp_offset": ("xyz", "rpy", "payload_mass", "payload_com"),
    "set_payload": ("mass", "com"),
    "home": ("timeout",),
}

LITEGRIP_METHODS: dict[str, tuple[str, ...] | None] = {
    "connect": (),
    "disconnect": (),
    "load_calibration": ("path", "template"),
    "enable": ("retries",),
    "get_state": ("wait",),
    "goto": ("position_mm", "duration"),
    "stop": (),
}

ARM_ATTRS = ("firmware", "n")
GRIPPER_INIT_PARAMS = ("channel", "can_id", "mst_id", "disable_on_disconnect")


def _check(cls, label: str, methods: dict[str, tuple[str, ...] | None]) -> list[str]:
    problems: list[str] = []
    for name, params in methods.items():
        member = getattr(cls, name, None)
        if member is None:
            problems.append(f"{label}.{name} 不存在")
            continue
        if params is None:
            continue
        available = inspect.signature(member).parameters
        missing = [param for param in params if param not in available]
        if missing:
            problems.append(f"{label}.{name} 缺少参数 {missing}")
    return problems


def main() -> int:
    try:
        import litearm
        from litearm import Arm
        import litegrip
        from litegrip import LiteGrip
    except ImportError as error:
        print(f"SDK 未安装，跳过: {error}", file=sys.stderr)
        return 0

    problems = _check(Arm, "Arm", ARM_METHODS)
    problems.extend(_check(LiteGrip, "LiteGrip", LITEGRIP_METHODS))

    arm_probe = Arm()  # 只构造，不连接
    for attr in ARM_ATTRS:
        if not hasattr(arm_probe, attr):
            problems.append(f"Arm.{attr} 不存在")

    init_params = inspect.signature(LiteGrip.__init__).parameters
    missing = [p for p in GRIPPER_INIT_PARAMS if p not in init_params]
    if missing:
        problems.append(f"LiteGrip.__init__ 缺少参数 {missing}")

    print(
        f"litearm {getattr(litearm, '__version__', '?')}, "
        f"litegrip {getattr(litegrip, '__version__', '?')}"
    )
    if problems:
        for problem in problems:
            print(f"FAIL: {problem}", file=sys.stderr)
        return 1
    print(f"OK: {len(ARM_METHODS)} Arm 接口 + {len(LITEGRIP_METHODS)} LiteGrip 接口")
    return 0


if __name__ == "__main__":
    sys.exit(main())
