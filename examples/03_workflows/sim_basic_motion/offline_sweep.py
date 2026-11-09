#!/usr/bin/env python3
"""离线 MuJoCo 验证：验收清单第 6–7 项，不依赖 Dora / operator-simulator-mujoco。

第 6 项：模型可加载，joint 数量/名称/顺序/轴/限位一致，正向命令使 q 正向变化。
第 7 项：逐关节 下限 → 上限 → 归零（其余关节保持 0），写 JSONL 证据。

驱动器为力矩电机，脚本用固件同款 kp/kd/tau_max 做 PD + 重力补偿，
目标角与真机 sweep 一致（固件软限位再内缩 0.05 rad）。

用法：
    python offline_sweep.py
    python offline_sweep.py --output validation_output/sim_sweep.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import mujoco
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from litearm_robot.codec import ARM_JOINTS, JOINT_LIMITS  # noqa: E402

DEFAULT_XML = ROOT / "assets" / "mjcf" / "scene.xml"
EXPECTED_AXES = np.array(
    [[0, 0, 1], [0, 0, 1], [0, 0, 1], [0, 0, 1], [0, 0, 1], [0, 0, -1], [0, 0, 1]],
    dtype=float,
)
# joint_table.md §2.1 固件 kp/kd/tau_max
KP = np.array([400, 400, 300, 300, 50, 50, 50.0])
KD = np.array([5.0, 5.0, 4.0, 5.0, 2.5, 2.5, 2.5])
TAU_MAX = np.array([78, 78, 21, 21, 10, 10, 10.0])
FIRMWARE_INSET = np.deg2rad(1.0)  # 固件软限位 = URDF 硬限位内缩 1°
SWEEP_INSET = 0.05  # 与真机 sweep 相同


def check_model(model: mujoco.MjModel) -> list[str]:
    """第 6 项静态检查，返回错误列表。"""
    errors: list[str] = []
    if model.nq != len(ARM_JOINTS) or model.nu != len(ARM_JOINTS):
        errors.append(f"nq/nu={model.nq}/{model.nu}，期望 {len(ARM_JOINTS)}")

    for index, name in enumerate(ARM_JOINTS):
        if index >= model.njnt:
            errors.append(f"缺少 {name}")
            continue
        joint = model.joint(index)
        if joint.name != name:
            errors.append(f"joint[{index}]={joint.name}，期望 {name}")
        if not np.allclose(model.jnt_axis[index], EXPECTED_AXES[index]):
            errors.append(f"{name} axis={model.jnt_axis[index]}，期望 {EXPECTED_AXES[index]}")
        expected = JOINT_LIMITS[name]
        if not np.allclose(model.jnt_range[index], expected, atol=1e-6):
            errors.append(f"{name} range={model.jnt_range[index]}，期望 {expected}")

    for index in range(min(model.nu, len(ARM_JOINTS))):
        joint_id = int(model.actuator_trnid[index, 0])
        if model.joint(joint_id).name != ARM_JOINTS[index]:
            errors.append(
                f"actuator[{index}] -> {model.joint(joint_id).name}，期望 {ARM_JOINTS[index]}"
            )
    return errors


def servo(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    target: np.ndarray,
    max_time: float,
) -> tuple[bool, float]:
    target = np.asarray(target, dtype=float)
    dt = model.opt.timestep
    settled = 0
    for step in range(int(max_time / dt)):
        err = target - data.qpos
        mujoco.mj_forward(model, data)
        torque = KP * err - KD * data.qvel + data.qfrc_bias
        data.ctrl[:] = np.clip(torque, -TAU_MAX, TAU_MAX)
        mujoco.mj_step(model, data)
        if np.max(np.abs(err)) < 0.005 and np.max(np.abs(data.qvel)) < 0.05:
            settled += 1
            if settled >= 200:
                return True, step * dt
        else:
            settled = 0
    return False, max_time


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xml", type=Path, default=DEFAULT_XML)
    parser.add_argument("--output", type=Path, default=Path("validation_output/sim_sweep.jsonl"))
    parser.add_argument("--tolerance", type=float, default=0.02, help="到位阈值 rad")
    parser.add_argument("--max-time", type=float, default=10.0, help="单航点最长仿真秒数")
    args = parser.parse_args(argv)

    model = mujoco.MjModel.from_xml_path(str(args.xml))
    # 2000 Hz 显式积分，保证固件增益下数值稳定
    model.opt.timestep = 0.0005
    data = mujoco.MjData(model)
    mujoco.mj_resetData(model, data)
    mujoco.mj_forward(model, data)

    errors = check_model(model)
    for message in errors:
        print(f"FAIL: {message}", file=sys.stderr)
    if errors:
        return 1
    print(f"模型加载 OK：nq={model.nq} nu={model.nu}，joint 顺序/轴/限位与 URDF 一致")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    passed = 0
    total = len(ARM_JOINTS) * 4  # direction + min/max/zero

    with args.output.open("w", encoding="utf-8") as handle:
        def emit(record: dict) -> None:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            handle.flush()

        # 第 6 项：方向检查，正向目标应使 q 正向变化
        for index, name in enumerate(ARM_JOINTS):
            mujoco.mj_resetData(model, data)
            mujoco.mj_forward(model, data)
            target = np.zeros(len(ARM_JOINTS))
            target[index] = min(0.1, 0.8 * JOINT_LIMITS[name][1])
            settled, _ = servo(model, data, target, args.max_time)
            actual = float(data.qpos[index])
            reached = bool(settled and abs(actual - target[index]) <= args.tolerance)
            passed += int(reached)
            emit(
                {
                    "check": "direction",
                    "joint": name,
                    "target_rad": round(float(target[index]), 6),
                    "actual_rad": round(actual, 6),
                    "tolerance_rad": args.tolerance,
                    "reached": reached,
                }
            )
            print(f"{name} {target[index]:+.4f} -> {actual:+.4f} {'OK' if reached else 'FAIL'}")

        # 第 7 项：下限 -> 上限 -> 归零，其余关节保持 0
        for index, name in enumerate(ARM_JOINTS):
            lower, upper = JOINT_LIMITS[name]
            q_min = lower + FIRMWARE_INSET + SWEEP_INSET
            q_max = upper - FIRMWARE_INSET - SWEEP_INSET
            for waypoint, q_target in (("min", q_min), ("max", q_max), ("zero", 0.0)):
                target = np.zeros(len(ARM_JOINTS))
                target[index] = q_target
                settled, _ = servo(model, data, target, args.max_time)
                actual = float(data.qpos[index])
                reached = bool(settled and abs(actual - q_target) <= args.tolerance)
                passed += int(reached)
                emit(
                    {
                        "check": "sweep",
                        "joint": name,
                        "waypoint": waypoint,
                        "target_rad": round(float(q_target), 6),
                        "actual_rad": round(actual, 6),
                        "tolerance_rad": args.tolerance,
                        "reached": reached,
                    }
                )
                print(
                    f"{name} {waypoint:4s} {q_target:+.4f} -> {actual:+.4f} "
                    f"{'OK' if reached else 'FAIL'}"
                )

    print(f"结果：{passed}/{total} 通过，记录 {args.output}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
