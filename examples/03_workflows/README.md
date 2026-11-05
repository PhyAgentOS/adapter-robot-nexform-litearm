# 03 Workflows

端到端示例。**除 `sim_basic_motion` 外均为结构模板**，依赖外部 Forge runtime
与 operator 节点，未在本仓验证。

| 目录 | 目标 | 状态 | 依赖 |
|---|---|---|---|
| `sim_basic_motion/` | 仿真加载 + 全关节 sweep | 可运行（需 operator-simulator-mujoco） | mujoco_sim |
| `real_basic_motion/` | 真机 MoveJoints / MovePose | 模板 | operator-motion、operator-controls |
| `homomorphic_control/` | 主从同构 | 模板 | 主臂适配器 |
| `vr_teleoperation/` | VR 遥操 | 模板 | litearm-vr-headset、lite-vr |

## 通用约定

- 控制周期：`dora/timer/millis/20`（50 Hz）。
- dora-cli 0.4.1 要求 `args` 为字符串；写成 YAML 列表会解析失败。
- `action` 为 sparse `JointCommand`；未列出的关节保持上一目标。
- 真机速度通过 `config/robot.yaml` 的 `speed`（0..1）限制，验收期 ≤ 0.2。
- 真机动作前必须完成 `examples/01_sdk_tests` 的只读检查，并有人在硬件急停位置。

## 尚缺

- `motion_server.yaml` / `controller.yaml`：需按现场 URDF 标定后生成；
- t_ee：VR 遥操待实测，见 `docs/validation.md` 第 14 项（MDH 已由 URDF 反推）；
- 仿真/真机 workflow 尚未在本仓独立跑通。
