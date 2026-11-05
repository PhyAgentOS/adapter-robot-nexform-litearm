# LiteArm Robot Adapter

NexForm LiteArm 7 轴机械臂 + LiteGrip 夹爪的 Forge / Dora 接入包。

- 上游交付目标：<https://github.com/PhyAgentOS/adapter-robot-nexform-litearm>
- 接入标准：PhyAgentOS Robot 接入手册（结算清单见 `docs/validation.md`）
- 参考实现：<https://github.com/PhyAgentOS/adapter-robot-piper>

> 状态：**M1 真机只读**。资产、驱动、配置、示例与离线自检已完成；真机固件/软限位/
> 静止状态已读回，尚未做任何真机运动与验收。验收进度见 [`docs/validation.md`](docs/validation.md)。

## 1. 机器人型号与构型

| 项 | 值 |
|---|---|
| 机械臂 | LiteArm，7 轴旋转关节 |
| 关节名 | `joint1` … `joint7` |
| 末端 | `ee_link`；MJCF 中另有 `tcp` site |
| 夹爪 | LiteGrip 两指夹爪，总开口 0–0.080 m |
| 通信 | USB CDC（litearm SDK 自动发现）；夹爪走 SocketCAN |

关节限位、零位、正方向与 URDF/MJCF 差异见 [`docs/joint_table.md`](docs/joint_table.md)。

## 2. 资产文件

| 路径 | 内容 |
|---|---|
| `assets/urdf/litearm.urdf` | 7 轴 URDF（mesh 路径已改为仓内相对路径） |
| `assets/meshes/` | URDF 使用的 9 个 STL |
| `assets/mjcf/litearm7.xml` | 由 `litearm-description` URDF 重建的 MJCF |
| `assets/mjcf/scene.xml` | 仿真入口（include `litearm7.xml`） |
| `assets/mjcf/meshes/` | MJCF 使用的 9 个 OBJ（STL 抽面后转换） |
| `assets/glb/litearm.glb` | 由 MJCF 导出的自包含可视化模型，见该目录 README |

## 3. Joint 参数

见 [`docs/joint_table.md`](docs/joint_table.md)。MJCF 已按 URDF 重建（2026-11-05，
同步自 `litearm-mujoco` `b901d49`），轴方向与限位逐项一致。固件侧零位/正方向在
实测位姿下与 URDF FK 吻合（位置差 <1e-5 m）。J4/J5 实测越软限位是未使能自然平衡点
所致（固件 `POS_RECOVER_BAND=0.05 rad`），非故障；使能会各带回约 0.024/0.037 rad。

## 4. 末端执行器

- 型号：LiteGrip（DM4310，CAN ID `0x08`，主站 ID `0x18`）
- 单位：Forge 侧为两指总开口 **m**；SDK 侧为 **mm**，由 `codec.py` 换算
- 标定：使用 SDK 打包的 factory calibration；本仓不写入标定文件
- 力/堵转判定（`grasp`）暂未暴露为标准 `GripperCommand`，见 §13

## 5. SDK 安装与连接

```bash
# Python 3.12（forge-robot stable/1.x 的硬要求）
uv venv --python 3.12
uv pip install -e /path/to/litearm-python
uv pip install -e /path/to/litegrip-python
uv pip install -e ".[test]"

# 只读探针，不做运动
robot-litearm probe --config config/robot.yaml
robot-litearm probe --fake            # 无硬件自检

# 核对本仓用到的 SDK 接口（需先装钉住的 SDK）
python scripts/check_sdk_api.py
```

`config/robot.yaml` 由 `config/robot.example.yaml` 复制后按现场修改。
`port: null` 表示交给 SDK 自动发现串口。

版本锁定：litearm-python `v1.3.0`、litegrip-python `v1.2.1`，其余参数见
[`docs/parameters.md`](docs/parameters.md)。

无硬件自检（不需要 SDK 与真机）：

```bash
python scripts/validate_assets.py      # 资产/关节/网格一致性
python scripts/urdf_to_mdh.py --check  # 由 URDF 反推 MDH 并做 FK 对拍
python -m pytest -q                    # codec/config；driver 用例自动跳过
robot-litearm probe --fake             # 需先装 forge-msgs / forge-robot
cd examples/02_dora_tests && dora run dataflow.yaml   # 需 dora-cli 0.4.1
```

> 若当前 shell 已 source ROS 2（`PYTHONPATH` 含 `/opt/ros/*/lib/python3.10/site-packages`），
> 该路径会污染 Python 3.12，导致 pytest 插件加载失败。请用 `env -u PYTHONPATH` 运行上述命令。

## 6. SDK 最小测试

见 [`examples/01_sdk_tests/`](examples/01_sdk_tests/)。默认只打印计划；真正下发
需要显式 `--execute`。

```bash
python examples/01_sdk_tests/read_state.py
python examples/01_sdk_tests/move_single_joint.py --joint 0 --delta 0.02 --execute
python examples/01_sdk_tests/gripper_open_close.py --execute
```

## 7. Dora 节点测试

见 [`examples/02_dora_tests/`](examples/02_dora_tests/)。

```bash
cd examples/02_dora_tests
PATH=$HOME/.dora/bin:$PATH dora run dataflow.yaml
```

先用 `--fake` 验证端口；真机配置需人工确认后再运行。

## 8. 仿真 workflow

见 [`examples/03_workflows/sim_basic_motion/`](examples/03_workflows/sim_basic_motion/)。
当前为模板，依赖 `operator-simulator-mujoco` 与 Forge runtime。

## 9. 真机 workflow

见 [`examples/03_workflows/real_basic_motion/`](examples/03_workflows/real_basic_motion/)。
模板依赖 `operator-motion`、`operator-controls`、`adapter-forge-gateway`。

## 10. 同构控制与 VR 遥操

- 同构：`examples/03_workflows/homomorphic_control/`
- VR：`examples/03_workflows/vr_teleoperation/`
- 现有实现：`lite-vr`（teleop bridge）、`litearm-vr-headset`（Godot/OpenXR 头显客户端），均不在本仓

## 11. VR 参数来源

见 [`config/vr.example.yaml`](config/vr.example.yaml)。参数来自
`lite-vr/litearm-vr-teleop/teleop/config/teleop.yaml`（2026-11-05 抓取）。
MDH 已由 URDF 反推，见 [`docs/mdh.md`](docs/mdh.md)；t_ee 当前为 0。

## 12. 安全注意事项

- 首次真机只做低速、小步进、单关节动作；`speed <= 0.2`。
- `emergency_stop()` = 取消下发 + `arm.disable()`，**臂会失去保持力**；
  无支撑姿态必须先人工托住。
- 夹爪 `stop`/`disable` 会掉力矩，夹住的物体会掉落。
- 硬件急停方式尚未归档，见 [`docs/hardware.md`](docs/hardware.md)。
- 在固件零位/正方向书面确认前，不做 MuJoCo 与真机的同步动作。

## 13. 已知限制

1. 未验收：真机仅完成只读读取（固件 1.11.0-7J、软限位、静止状态），运动与夹爪项均待执行。
2. `set_command` 只支持 `mode="position"`；速度/力矩/MIT 未映射。
3. SDK 的 `movej_sync` 是阻塞 PTP，驱动用后台 worker 合并最新目标；
   不是 20 ms 级轨迹流，不能替代 `joint_trajectory_controller` 的高频下发。
4. 标准 `GripperCommand` 只有位置目标；`grasp` 的力/堵转判定需要自定义 Tool。
5. 没有任意构型 FK；`move_pose` 需要主机侧 URDF IK（`operator-motion`）。
6. 固件零位/正方向待书面确认；GLB 为 q=0 静态网格，不含关节层级。
7. 平台登记/外部贡献尚未开放，当前只在本地开发验证。

## 目录结构

```text
adapter-robot-nexform-litearm/
├── assets/{urdf,meshes,mjcf,glb}/
├── config/{robot,vr}.example.yaml
├── docs/{parameters,joint_table,hardware,validation,mdh}.md
├── examples/
│   ├── 01_sdk_tests/
│   ├── 02_dora_tests/
│   └── 03_workflows/{sim_basic_motion,real_basic_motion,
│                      homomorphic_control,vr_teleoperation}/
├── scripts/{validate_assets.py,urdf_to_mdh.py,build_entry.py,build_pyinstaller.sh}
├── src/litearm_robot/{config,codec,driver,gripper,fake,main}.py
└── tests/
```

## 上游来源

| 资产 | 来源 | 备注 |
|---|---|---|
| URDF + STL | `litearm-description/SE/litearm_description` | `package://` 已改相对路径 |
| MJCF + OBJ | `litearm-mujoco/src/litearm_mujoco/assets` | `b901d49` 起由 URDF 重建 |
| VR 参数 | `lite-vr/litearm-vr-teleop/teleop/config/teleop.yaml` | 2026-11-05 |
| SDK | `nexform-tech/litearm-python` | `v1.3.0`、直连 STM32 |
| 夹爪 SDK | `nexform-tech/litegrip-python` | `v1.2.1`、factory calibration |
