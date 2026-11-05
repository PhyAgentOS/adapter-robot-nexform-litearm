# sim_basic_motion

仿真基础动作与全关节 sweep（验收清单第 6–7 项）。

## 组成

| 文件 | 说明 |
|---|---|
| `simulator.yaml` | `operator-simulator-mujoco` 配置，加载 `assets/mjcf/scene_position.xml`（position 执行器） |
| `dataflow.example.yaml` | mujoco + joint_sweep + state_print |
| `joint_sweep.py` | Dora 链路：逐关节 下限 → 上限 → 0，写 JSONL 证据（`sim_sweep_dora.jsonl`） |
| `offline_sweep.py` | 离线链路：直接加载 MJCF，做第 6–7 项检查与 sweep，不依赖 Dora |

## 依赖

Dora 链路：

- Python 3.12 + `operator-simulator-mujoco`（`mujoco_sim` 可执行，本机在
  `~/.PhyAgentOS/forge_runtime/nodes/mujoco_sim/versions/mujoco_sim-1.1.1-linux-x86_64-tar-gz/`，
  未进 PATH，运行时要显式加入）
- 本仓：`forge-msgs==1.0.1`、`dora-rs==0.4.1`
- 环境变量 `FORGE_RUNTIME_ROOT`（仅 state viewer 需要；本示例未使用）

离线链路：只需 `mujoco` + `numpy`。本机可用
`<mujoco-venv>/bin/python`（MuJoCo 3.17.0）或系统 Python（3.9.0）。

## 运行

```bash
# 离线：第 6–7 项，已验证可用
cd examples/03_workflows/sim_basic_motion
python offline_sweep.py

# Dora 链路（已跑通）：必须让 `python` 指向本仓 .venv，否则缺 forge_msgs
MUJOCO_GL=egl \
PATH="$PWD/../../../.venv/bin:$HOME/.dora/bin:$HOME/.PhyAgentOS/forge_runtime/nodes/mujoco_sim/versions/mujoco_sim-1.1.1-linux-x86_64-tar-gz:$PATH" \
env -u PYTHONPATH dora run dataflow.example.yaml
```

Dora 结果写入 `validation_output/sim_sweep_dora.jsonl`，每行：
`{joint, target_rad, actual_rad, tolerance_rad, reached}`。
离线结果写入 `validation_output/sim_sweep.jsonl`，每行另含 `check` 字段。
两者文件名不同，互不覆盖。

## 验收判据

- 第 6 项：`nq=nu=7`，joint 名称/顺序/轴/限位与 URDF 一致，7 轴正向命令均使 `q` 正向变化；
- 第 7 项：21 个航点（7 关节 × 3）全部 `reached=true`（容差 0.02 rad）；
- 离线脚本 28/28 通过（7 方向 + 21 航点），记录归档到 `docs/validation.md`。

## 已知阻塞

- 离线第 6–7 项已通过（2026-11-05）。
- Dora workflow（第 11 项仿真半边）已跑通（2026-11-05）：21/21 航点 `reached=true`。
  注意 sweep 完成后 `mujoco_sim` 仍在运行，需要手动 Ctrl-C；`dora run` 不会自行退出。
- MJCF 已按 URDF 重建（`litearm-mujoco` `b901d49`），关节轴和限位逐项一致，
  `q` 可直接共用，见 `docs/joint_table.md`。
