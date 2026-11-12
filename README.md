LiteArm Robot Adapter 把 NexForm LiteArm 7 轴机械臂与 LiteGrip 夹爪接入 PhyAgentOS 的 Forge / Dora 运行时，供机器人应用开发者在仿真和真机上复用同一套驱动、示例与遥操参数。

# LiteArm Robot Adapter

NexForm LiteArm 7 轴机械臂 + LiteGrip 夹爪的 Forge / Dora 接入包。

- 上游交付目标：<https://github.com/PhyAgentOS/adapter-robot-nexform-litearm>
- 接入标准：PhyAgentOS Robot 接入手册（结算清单见 `docs/validation.md`）
- 参考实现：<https://github.com/PhyAgentOS/adapter-robot-piper>

> 状态：**验收项 1–15 均已有证据**。资产、驱动、配置、示例与离线自检已完成；真机固件、
> 软限位、7 轴最小/最大/归零 sweep、零位对拍、Forge/Dora 链路、仿真与真机 workflow、
> 同构控制和 VR 遥操均已验证；夹爪 payload 与堵转阈值已记录（payload 为 CAD 估算）。
> 厂商产品/开发手册已归档到 `docs/vendor/`。逐项证据见
> [`docs/validation.md`](docs/validation.md)。

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
| `assets/mjcf/litearm7_position.xml` | 同一运动学/惯量，执行器换成 `position` 并开 `gravcomp`，对应固件行为 |
| `assets/mjcf/scene_position.xml` | 仿真 workflow 入口（include `litearm7_position.xml`） |
| `assets/mjcf/meshes/` | MJCF 使用的 9 个 OBJ（STL 抽面后转换） |
| `assets/glb/litearm.glb` | 由 MJCF 导出的自包含可视化模型，见该目录 README |
| `assets/SHA256SUMS` | 交付资产哈希台账；`sha256sum -c assets/SHA256SUMS` 可校验 |
| `assets/README.md` | 资产来源、源提交、转换方式与源/交付比对记录 |

## 3. Joint 参数

- 关节：`joint1` … `joint7`，顺序 1→7，单位 **rad**
- 范围（URDF/MJCF）：J1/J3/J5 `±2.827`；J2 `±1.745`；J4 `-3.089 .. 0.035`；
  J6/J7 `±1.571`。固件软限位为两侧内缩 1°（0.0175 rad），见
  [`docs/joint_table.md`](docs/joint_table.md) §2.1
- 零位：全 0（SDK `home()` 0x2A 回 `[0]*7`）；正方向：各关节绕 URDF 轴按右手定则
  （厂商产品手册，2026-11-05 FK 对拍一致）

完整表见 [`docs/joint_table.md`](docs/joint_table.md)。MJCF 已按 URDF 重建（2026-11-05，
同步自 `litearm-mujoco` `b901d49`），轴方向与限位逐项一致。固件侧零位/正方向在
实测位姿下与 URDF FK 吻合（位置差 <1e-5 m）。J4/J5 实测越软限位是未使能自然平衡点
所致（`POS_RECOVER_BAND`：1.10.0 为 0.05 rad，1.10.1 起 0.30 rad；参考源码 1.10.5），
非故障；使能会各带回约 0.024/0.037 rad。

## 4. 末端执行器

- 型号：LiteGrip（DM4310，CAN ID `0x08`，主站 ID `0x18`）
- 单位：Forge 侧为两指总开口 **m**；SDK 侧为 **mm**，由 `codec.py` 换算
- 标定：使用 SDK 打包的 factory calibration；本仓不写入标定文件
- 行程/力：总开口 0–80 mm；闭合稳态压力矩约 0.211 Nm（SDK 读数 2.11 N）
- 堵转判据：位置窗口增量（50 ms × 5 采样，阈值 0.034 rad ≈ 2.50 mm），非力矩阈值；
  详见 [`docs/parameters.md`](docs/parameters.md) §4.1
- payload：CAD 估算 0.5772 kg、质心 ≈`[0,0,+0.055]` m（法兰系），未动态辨识、
  未写入固件（见 §13）
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
python examples/01_sdk_tests/move_single_joint.py --joint 0 --delta 0.05 --execute
python examples/01_sdk_tests/gripper_open_close.py --execute
```

## 7. Dora 节点测试

见 [`examples/02_dora_tests/`](examples/02_dora_tests/)。

```bash
cd examples/02_dora_tests
PATH=$HOME/.dora/bin:$PATH dora run dataflow.yaml
PATH=$HOME/.dora/bin:$PATH dora run dataflow.control.yaml   # enable -> home -> disable
```

先用 `--fake` 验证端口；真机配置需人工确认后再运行。

控制面通过 `control` 输入发送 `enable` / `disable` / `reset` / `home` / `stop` /
`emergency_stop`，回执在 `control_status`；`action` 支持可选的 `speed` 扩展列
（0..1）。语义见 [`docs/parameters.md` §7](docs/parameters.md)，fake 结果见
[`docs/validation.md`](docs/validation.md)「控制面记录」。

### 7.1 forge_bridge（TCP/JSON）

`examples/04_forge_bridge/` 把同一组端口暴露成一行一个 JSON 的 TCP 服务，
供 Forge Skill Gateway 或非 Python 调用方使用：

```bash
cd examples/04_forge_bridge
PATH="$PWD/../../.venv/bin:$HOME/.dora/bin:$PATH" dora run dataflow.bridge.yaml
# 另开终端
../../.venv/bin/python bridge_client.py                 # 交互式
../../.venv/bin/python bridge_client.py movej 0 0 0 0 0 0 0 --speed 0.2
```

请求命令：`state`/`status`、`movej`、`gripper`、`home`、`stop`、`enable`、
`disable`、`reset`、`estop`、`ping`；详情与线程模型见
[`docs/bridge.md`](docs/bridge.md)。桥默认只监听 `127.0.0.1:9005`，无鉴权。

驱动发布的 `state` 恒含 `joint_order` 的全部 8 项；夹爪未启用或读回超时时，
`gripper` 的位置/速度/力矩为 `NaN`（未知），桥的 JSON 输出把该值转为 `null`。

## 8. 仿真 workflow

见 [`examples/03_workflows/sim_basic_motion/`](examples/03_workflows/sim_basic_motion/)。

```bash
cd examples/03_workflows/sim_basic_motion
python offline_sweep.py                 # 离线：第 6–7 项，只需 mujoco+numpy

# Dora 链路：21/21 航点已通过（2026-11-05）
MUJOCO_GL=egl \
PATH="$PWD/../../../.venv/bin:$HOME/.dora/bin:$HOME/.PhyAgentOS/forge_runtime/nodes/mujoco_sim/versions/mujoco_sim-1.1.1-linux-x86_64-tar-gz:$PATH" \
env -u PYTHONPATH dora run dataflow.example.yaml
```

sweep 完成后 `mujoco_sim` 不会自行退出，前台 Ctrl-C 结束。

## 9. 真机 workflow

见 [`examples/03_workflows/real_basic_motion/`](examples/03_workflows/real_basic_motion/)。
2026-11-05 真机已跑通：J7 `+0.05 rad`，1.280 s `SUCCESS`，7 轴最终误差 ≤0.0164 rad。

```bash
# motion_server / joint_trajectory_controller 来自本地 Forge runtime，先建软链目录
mkdir -p /tmp/forge-bin
ln -sf ~/.PhyAgentOS/forge_runtime/nodes/motion_server/versions/*/motion_server /tmp/forge-bin/
ln -sf ~/.PhyAgentOS/forge_runtime/nodes/joint_trajectory_controller/versions/*/joint_trajectory_controller /tmp/forge-bin/

cd examples/03_workflows/real_basic_motion
FORGE_RUNTIME_BIN=/tmp/forge-bin \
PATH="$PWD/../../../.venv/bin:$HOME/.dora/bin:$PATH" \
env -u PYTHONPATH dora run dataflow.real.yaml
```

默认只把 `joint7` 步进 +0.05 rad 后停住，不自动失能。结束时前台 Ctrl-C，
让节点正常 `disconnect()`；**禁止** `timeout`/`kill` 强杀（会失去保持力矩）。

## 10. 同构控制与 VR 遥操

同构控制（第 12 项，仿真+真机已通过）：

```bash
cd examples/03_workflows/homomorphic_control
# 仿真
MUJOCO_GL=egl PATH="$PWD/../../../.venv/bin:$HOME/.dora/bin:$HOME/.PhyAgentOS/forge_runtime/nodes/mujoco_sim/versions/mujoco_sim-1.1.1-linux-x86_64-tar-gz:$PATH" \
  env -u PYTHONPATH dora run dataflow.sim.yaml
# 真机（先 probe 存基准，详见目录 README）
PATH="$PWD/../../../.venv/bin:$HOME/.dora/bin:$PATH" env -u PYTHONPATH dora run dataflow.real.yaml
```

VR 遥操（第 13–14 项）：`examples/03_workflows/vr_teleoperation/`。头显客户端
`litearm-vr-headset`（Godot/OpenXR）与 teleop `lite-vr` 为外部仓；本仓提供
`config/vr.example.yaml`、`vr_bridge_dora.py` 和两个数据流。桥在 `:9001` 上按
lite-vr `arm_follow_server` 协议接收关节流，转成 Dora `JointCommand` 驱动
`robot-litearm` 或 `mujoco_sim`，上游 teleop 无需改动。2026-11-05 用户现场确认
VR 方向/缩放/末端姿态无问题；仿真已分别验证映射（平移 scale 1.00、旋转
40°→39.8°、无跳变）和桥端到端（IK 720/720、末端 p95 0.68 mm、持位误差 0），
见 [`docs/validation.md`](docs/validation.md) §VR 仿真记录。

```bash
cd examples/03_workflows/vr_teleoperation
# 仿真：桥 + mujoco_sim
MUJOCO_GL=egl PATH="$PWD/../../../.venv/bin:$HOME/.dora/bin:$HOME/.PhyAgentOS/forge_runtime/nodes/mujoco_sim/versions/mujoco_sim-1.1.1-linux-x86_64-tar-gz:$PATH" \
  env -u PYTHONPATH dora run dataflow.sim.yaml
# 真机：桥 + robot-litearm（先确认 config/robot.yaml 与急停）
PATH="$PWD/../../../.venv/bin:$HOME/.dora/bin:$PATH" \
  env -u PYTHONPATH dora run dataflow.example.yaml
```

## 11. VR 参数来源

见 [`config/vr.example.yaml`](config/vr.example.yaml)。参数来自
`lite-vr/litearm-vr-teleop/teleop/config/teleop.yaml`（2026-11-05 抓取）。
MDH 已由 URDF 反推，见 [`docs/mdh.md`](docs/mdh.md)；`t_ee=[-0.0071,-0.0239,0.140]` m（法兰系，2026-11-05 实测，见 [`docs/validation.md`](docs/validation.md) §t_ee 记录）。

`t_ee` 标定方法：横向 `tool_offset_xy_m` 用两指中点对准目标并读 TCP，轴向
`tool_pad_offset_m=0.140` 由指尖实测（指尖总长 0.160）；语义
`p_tool = p_ee + R_ee·xyz`。`rotation` / `scale` 直接采用 `lite-vr` 配置值，
本轮未重新标定，只做现场方向与缩放确认。

## 12. 安全注意事项

- 首次真机只做低速、小步进、单关节动作；`speed <= 0.2`。
- `emergency_stop()` = 取消下发 + `arm.disable()`，**臂会失去保持力**；
  无支撑姿态必须先人工托住。厂商 SDK 另有 `Arm.emergency_stop()`（单帧、最高优先级）。
- 夹爪 `stop`/`disable` 会掉力矩，夹住的物体会掉落。
- 硬件急停：厂商产品手册要求异常时立即按下硬件急停并切断电源；按钮位置与现场接线
  见 [`docs/hardware.md`](docs/hardware.md)。
- 零位/正方向已有厂商书面定义（`docs/vendor/litearm-docs/`）并经 FK 对拍；
  实机同步动作仍须低速、有人值守。

## 13. 已知限制

1. 第 8–12 项的真机验证在固件 `1.11.0-7J` 的样机上完成；当前台架臂为
   `Litearm1.10.1-7J`（同型号、不同板）。若验收要求同一台，需换回后复跑。
2. `set_command` 只支持 `mode="position"`；速度/力矩/MIT 未映射。
3. SDK 的 `movej_sync` 是阻塞 PTP，驱动用后台 worker 合并最新目标；
   不是 20 ms 级轨迹流，不能替代 `joint_trajectory_controller` 的高频下发。
4. 标准 `GripperCommand` 只有位置目标；`grasp` 的力/堵转判定需要自定义 Tool。
5. 没有任意构型 FK；`move_pose` 需要主机侧 URDF IK（`operator-motion`）。
6. 实机 `1.11.0-7J` 的固件源码未归档（归档的是 `1.10.5-7J`）；GLB 为 q=0 静态网格，
   不含关节层级。
7. 夹爪 payload 为 CAD 估算（0.5772 kg，未动态辨识、未写入固件）；要做实数需称重或
   拆爪采空载基线。
8. 平台登记/外部贡献尚未开放，当前只在本地开发验证。
9. VR→Dora 桥 `vr_bridge_dora.py` 已实现并在仿真端到端验证；真机
   `dataflow.example.yaml` 复用同一桥，但尚未在真机跑过（第 13 项的真机确认是
   用户直接用 lite-vr 原生链路完成的）。现场部署时 teleop 的臂侧地址要指向
   桥的 `:9001`。
10. `forge_bridge` 只在 fake 驱动上做过端到端验证；真机运动/夹爪未跑。协议
    无鉴权，默认只绑定 `127.0.0.1`；`movej`/`gripper` 的 `ok` 只表示 action
    已下发，没有 action 级回执。

## 目录结构

```text
adapter-robot-nexform-litearm/
├── assets/{urdf,meshes,mjcf,glb}/
├── config/{robot,vr}.example.yaml
├── docs/{parameters,joint_table,hardware,bridge,validation,mdh}.md
├── examples/
│   ├── 01_sdk_tests/
│   ├── 02_dora_tests/
│   ├── 03_workflows/{sim_basic_motion,real_basic_motion,
│   │                  homomorphic_control,vr_teleoperation}/
│   └── 04_forge_bridge/
├── scripts/{validate_assets.py,urdf_to_mdh.py,build_entry.py,build_pyinstaller.sh}
├── src/litearm_robot/{config,codec,driver,gripper,fake,control,node,bridge,main}.py
└── tests/
```

本仓采用适配器分发布局，交付到 PhyAgentOS/Forge 工作区时整体部署为
`robots/litearm/`（对应 `Robot接入手册.md` §2 的交付路径）：

```bash
WORKSPACE=$HOME/PhyAgentOS-workspace   # 任意工作区根，需已含 forge_runtime/
mkdir -p "$WORKSPACE/robots"
rsync -a --exclude .git --exclude .venv --exclude dist "$PWD/" "$WORKSPACE/robots/litearm/"
```

包内相对路径（如 `examples/03_workflows/*/simulator.yaml` 的
`../../../assets/...`）以包根为基准，整体部署后不需要修改。验收时在
`$WORKSPACE/robots/litearm` 运行路径校验和功能检查。

## 上游来源

| 资产 | 来源 | 备注 |
|---|---|---|
| URDF + STL | `litearm-description/SE/litearm_description` | `package://` 已改相对路径 |
| MJCF + OBJ | `litearm-mujoco/src/litearm_mujoco/assets` | `b901d49` 起由 URDF 重建 |
| VR 参数 | `lite-vr/litearm-vr-teleop/teleop/config/teleop.yaml` | 2026-11-05 |
| SDK | `nexform-tech/litearm-python` | `v1.3.0`、直连 STM32 |
| 夹爪 SDK | `nexform-tech/litegrip-python` | `v1.2.1`、factory calibration |
