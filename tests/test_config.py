from __future__ import annotations

from pathlib import Path

import pytest

from litearm_robot.codec import JOINT_ORDER
from litearm_robot.config import load_config

ROOT = Path(__file__).resolve().parents[1]


def test_load_example_config():
    config = load_config(ROOT / "config/robot.example.yaml")
    assert config.joint_order == JOINT_ORDER
    assert 0.0 < config.speed <= 0.2
    assert config.home_timeout_s == 180.0
    assert config.gripper.can_id == 0x08
    assert config.gripper.mst_id == 0x18


def test_defaults_without_file():
    config = load_config(None)
    assert config.joint_order == JOINT_ORDER
    assert config.gripper.enabled is False


def test_rejects_wrong_joint_order(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("joint_order: [joint1, joint2]\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(path)


def test_rejects_out_of_range_speed(tmp_path):
    path = tmp_path / "fast.yaml"
    path.write_text("speed: 1.5\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(path)


def test_rejects_non_positive_home_timeout(tmp_path):
    path = tmp_path / "home.yaml"
    path.write_text("home_timeout_s: 0\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(path)


@pytest.mark.parametrize(
    "gripper_yaml",
    [
        "max_opening_m: 0\n",
        "max_opening_m: 0.2\n",
        "max_opening_m: .nan\n",
        "speed_mm_s: 0\n",
        "speed_mm_s: -1\n",
    ],
)
def test_rejects_invalid_gripper_limits(tmp_path, gripper_yaml):
    path = tmp_path / "gripper.yaml"
    path.write_text("gripper:\n  " + gripper_yaml, encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(path)


def test_rejects_unknown_initial_joint(tmp_path):
    path = tmp_path / "pose.yaml"
    path.write_text(
        "initial_position:\n  joint9: 0.0\n", encoding="utf-8"
    )
    with pytest.raises(ValueError):
        load_config(path)
