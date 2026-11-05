# sim_basic_motion

仿真基础动作与全关节 sweep（验收清单第 6–7 项）。

## 组成

| 文件 | 说明 |
|---|---|
| `simulator.yaml` | `operator-simulator-mujoco` 配置，直接加载 `assets/mjcf/scene.xml` |
| `dataflow.example.yaml` | mujoco + joint_sweep + state_print |
| `joint_sweep.py` | 逐关节 下限 → 上限 → 0，写 JSONL 证据 |

## 依赖

- Python 3.12 + `operator-simulator-mujoco`（`mujoco_sim` 可执行）
- 本仓：`forge-msgs==1.0.1`、`dora-rs==0.4.1`
- 环境变量 `FORGE_RUNTIME_ROOT`（仅 state viewer 需要；本示例未使用）

## 运行

```bash
cd examples/03_workflows/sim_basic_motion
MUJOCO_GL=egl dora run dataflow.example.yaml
```

结果写入 `validation_output/sim_sweep.jsonl`，每行：
`{joint, target_rad, actual_rad, tolerance_rad, reached}`。

## 验收判据

- 21 个航点（7 关节 × 3）全部 `reached=true`；
- 无关节逆向跳变、无奇异报错；
- 记录文件归档到 `docs/validation.md` 的“证据”列。

## 已知阻塞

无。MJCF 已按 URDF 重建（`litearm-mujoco` `b901d49`），关节轴和限位逐项一致，
`q` 可直接共用，见 `docs/joint_table.md`。
