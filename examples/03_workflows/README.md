# 03 Workflows

端到端示例。`sim_basic_motion`、`real_basic_motion`、`homomorphic_control`
已在本仓跑通；`vr_teleoperation` 的桥已在仿真端到端跑通，真机由用户现场确认。

| 目录 | 目标 | 状态 | 依赖 |
|---|---|---|---|
| `sim_basic_motion/` | 仿真加载 + 全关节 sweep | 可运行（需 operator-simulator-mujoco） | mujoco_sim |
| `real_basic_motion/` | 真机 MoveJoints / MovePose | 真机已跑通（2026-11-05） | Forge runtime（motion_server、joint_trajectory_controller） |
| `homomorphic_control/` | 主从同构 | 可运行（仿真+真机已跑通） | scripts + mujoco_sim |
| `vr_teleoperation/` | VR 遥操 + VR→Dora 桥 | 映射与桥端到端已在仿真验证；真机现场确认通过 | litearm-vr-headset、lite-vr、mujoco_sim |

## 通用约定

- 控制周期：`dora/timer/millis/20`（50 Hz）。
- dora-cli 0.4.1 要求 `args` 为字符串；写成 YAML 列表会解析失败。
- `action` 为 sparse `JointCommand`；未列出的关节保持上一目标。
- 真机速度通过 `config/robot.yaml` 的 `speed`（0..1）限制，验收期 ≤ 0.2。
- 真机动作前必须完成 `examples/01_sdk_tests` 的只读检查，并有人在硬件急停位置。

## 状态

- `motion_server.yaml` / `controller.yaml` 已随 `real_basic_motion/` 提供，第 11 项真机已跑通；
- VR 的 `t_ee` 已实测并写入 `config/vr.example.yaml`（见 `docs/validation.md` 第 14 项）；
  夹爪堵转阈值已实测，payload 仅为 CAD 估算（见 `docs/validation.md` §夹爪 payload 与堵转阈值记录）；
- 第 11、12 项的仿真/真机 workflow 已在本仓跑通，见 `docs/validation.md`。
