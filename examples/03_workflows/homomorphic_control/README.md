# homomorphic_control

同构控制（验收清单第 12 项）。仿真与真机均已跑通（2026-11-05），证据见
`docs/validation.md` §同构控制记录。

## 原理

Forge 标准 runner 已内建镜像通路：

```text
master_state (JointState)
  -> node_runner._joint_state_to_command
  -> JointCommand(mode="position")
  -> driver.set_command
```

从臂只需订阅 `master_state`，`is_follower=True`（本仓 `main.py` 默认）。
仿真侧没有 runner，用 `mirror_command.py` 做同样的转换后驱动 `mujoco_sim`。

现场只有一台臂，没有第二台物理主臂，因此主臂由 `master_trajectory.py`
脚本化产生 `JointState`；进入从臂的通路与真实主臂完全相同。

## 组成

| 文件 | 说明 |
|---|---|
| `master_trajectory.py` | 确定性主臂轨迹：A(零位) → B → C → A，`hold=1 s` / `ramp=4 s`；输出 `JointState` |
| `mirror_command.py` | `JointState` → `JointCommand(position)`，供仿真链路 |
| `state_recorder.py` | 按 20 Hz 记录主/从 `JointState` 到 JSONL |
| `compare_homomorphic.py` | 离线判据：稳态误差、方向一致性、跨环境偏置差 |
| `simulator.yaml` | `mujoco_sim` 配置，加载 `assets/mjcf/scene_position.xml` |
| `dataflow.sim.yaml` | 仿真链路 |
| `dataflow.real.yaml` | 真机链路 |

轨迹相对基准的偏置（避开真机贴近下限的 J2/J4）：

```text
B = (+0.15, 0, -0.10, 0, +0.10, 0, +0.10)
C = (+0.15, 0, -0.20, 0, +0.20, 0, +0.10)
```

## 运行

### 1. 仿真

```bash
cd examples/03_workflows/homomorphic_control
MUJOCO_GL=egl \
PATH="$PWD/../../../.venv/bin:$HOME/.dora/bin:$HOME/.PhyAgentOS/forge_runtime/nodes/mujoco_sim/versions/mujoco_sim-1.1.1-linux-x86_64-tar-gz:$PATH" \
env -u PYTHONPATH dora run dataflow.sim.yaml
```

轨迹约 16 s；结束后前台 Ctrl-C（`dora run` 不会自行退出）。

### 2. 真机

前置：

1. `config/robot.yaml` 中 `speed <= 0.2`、`enable_on_connect: true`；
2. 臂在零位（或任意已知位姿）。从折叠位回零用固件 `home()`（0x2A，固定 0.10 低速）：
   ```bash
   .venv/bin/python -m litearm_robot.main home --config config/robot.yaml
   ```
3. 只读采样当前位姿作为主臂基准（避免把臂拉向零位以外的大幅动作）：
   ```bash
   PATH="$PWD/../../../.venv/bin:$PATH" \
     python -m litearm_robot.main probe --config ../../../config/robot.yaml \
     > validation_output/real_base.json
   ```
4. 现场有人守在硬件急停位置，工作空间内无人员和障碍。

运行：

```bash
cd examples/03_workflows/homomorphic_control
PATH="$PWD/../../../.venv/bin:$HOME/.dora/bin:$PATH" \
  env -u PYTHONPATH dora run dataflow.real.yaml
```

结束必须前台 Ctrl-C（或 `timeout -s INT`，等同 Ctrl-C），让 robot 节点走
STOP → `disconnect()` → `close()` 保持使能持位；**禁止** `timeout`/`kill` 强杀，
否则会失去保持力矩（见 `docs/validation.md` 第 11 项事故记录）。

### 3. 分析

```bash
../../../.venv/bin/python compare_homomorphic.py \
  validation_output/homomorphic_real.jsonl \
  --compare validation_output/homomorphic_sim.jsonl \
  --json-out validation_output/homomorphic_summary.json
```

## 验收判据与结果（2026-11-05）

- 主臂缓慢走 3 个姿态（初始、中位、偏转），从臂方向一致：通过；
- 主从角度差：仿真稳态 0，真机稳态最大 0.0027 rad（`joint6`）；
- 跨环境（仿真 vs 真机）相对基准偏置最大差 0.0011 rad；
- 无轴向反转、无奇异跳变：通过。

## 相关

本地已有 `lite-vr` / `litearm-vr-headset` 遥操实现（不在本仓）。本目录只负责
把同构链路映射到 Forge/Dora 端口，不重复实现头显侧。
