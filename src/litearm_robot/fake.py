"""无硬件 FakeArm：供 CI、Dora 端口测试和 dry 演示使用。"""

from __future__ import annotations

from types import SimpleNamespace


class FakeArm:
    n = 7
    firmware = "Litearm-FAKE"

    def __init__(self) -> None:
        self.q = [0.0] * 7
        self.enabled = False
        self.connected = False
        self.move_count = 0

    def connect(self) -> "FakeArm":
        self.connected = True
        return self

    def close(self) -> None:
        self.connected = False

    def enable(self, attempts: int = 12) -> None:
        self.enabled = True

    def disable(self) -> None:
        self.enabled = False

    def get_state(self, refresh: bool = False):
        joints = [
            SimpleNamespace(q=value, dq=0.0, tau=0.0) for value in self.q
        ]
        return SimpleNamespace(value=SimpleNamespace(joints=joints))

    def movej_sync(self, q: list[float], speed: float = 1.0):
        self.q = [float(value) for value in q]
        self.move_count += 1
        return self.get_state().value
