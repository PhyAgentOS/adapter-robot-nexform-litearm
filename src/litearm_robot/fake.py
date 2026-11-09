"""无硬件 FakeArm：供 CI、Dora 端口测试和 dry 演示使用。"""

from __future__ import annotations

from types import SimpleNamespace


class _FakeJoint:
    def __init__(self, q: float) -> None:
        self.q = q
        self.dq = 0.0
        self.tau = 0.0


class _FakeState:
    """模拟 litearm.RobotState 的字段与派生属性。"""

    def __init__(self, arm: "FakeArm") -> None:
        self.joints = [_FakeJoint(value) for value in arm.q]
        self.mode_name = arm.mode_name
        self.flags = arm.flags
        self.joint_fault = arm.joint_fault

    @property
    def enabled(self) -> bool:
        return bool(self.flags & (1 << 9))

    @property
    def faulted(self) -> bool:
        return bool(self.flags & 1) or self.mode_name == "EMERGENCY"

    @property
    def fault_detail(self) -> str:
        if self.mode_name == "EMERGENCY":
            return "EMERGENCY"
        return "FAULT" if self.flags & 1 else ""


class FakeArm:
    n = 7
    firmware = "Litearm-FAKE"

    def __init__(self) -> None:
        self.q = [0.0] * 7
        self.enabled = False
        self.connected = False
        self.move_count = 0
        self.home_count = 0
        self.reset_count = 0
        self.last_speed: float | None = None
        self.mode_name = "INIT"
        self.flags = 0
        self.joint_fault = 0

    def connect(self) -> "FakeArm":
        self.connected = True
        return self

    def close(self) -> None:
        self.connected = False

    def enable(self, attempts: int = 12) -> None:
        self.enabled = True
        self.flags |= 1 << 9

    def disable(self) -> None:
        self.enabled = False
        self.flags &= ~(1 << 9)

    def emergency_stop(self) -> None:
        self.enabled = False
        self.flags = (self.flags & ~(1 << 9)) | 1
        self.mode_name = "EMERGENCY"

    def reset(self) -> None:
        self.reset_count += 1
        self.flags = 0
        self.mode_name = "INIT"
        self.joint_fault = 0

    def get_state(self, refresh: bool = False):
        return SimpleNamespace(value=_FakeState(self))

    def movej_sync(self, q: list[float], speed: float = 1.0):
        self.q = [float(value) for value in q]
        self.move_count += 1
        self.last_speed = float(speed)
        return self.get_state().value

    def home(self, timeout: float | None = None):
        self.home_count += 1
        return self.movej_sync([0.0] * 7, speed=0.1)
