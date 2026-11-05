"""URDF -> MDH 反推的 FK 对拍（仅标准库）。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_mdh_matches_urdf_fk() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/urdf_to_mdh.py"), "--check", "200"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "位置最大误差" in result.stdout
