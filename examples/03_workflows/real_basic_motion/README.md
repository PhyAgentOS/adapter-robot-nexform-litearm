# real_basic_motion

真机基础动作（验收清单第 8、11 项）。**2026-11-05 已真机跑通**：J7 `+0.05 rad`，
1.280 s `SUCCESS`，7 轴最终误差 ≤0.0164 rad（见 `docs/validation.md` 第 11 项）。

## 链路

```text
motion_action_client
  -> motion_server               (MoveJoints / MovePose, FK/IK, 轨迹规划)
  -> joint_trajectory_controller (20 ms 轨迹点 -> JointCommand)
  -> robot-litearm               (本仓)
  -> LiteArm / LiteGrip
```

`motion_server` 本身不输出 `JointCommand`，必须经过 `joint_trajectory_controller`；
这也是本仓驱动只支持 position 模式的原因之一。

## 需要的现场配置

| 文件 | 来源 | 说明 |
|---|---|---|
| `motion_server.yaml` | 参考 operator-motion `examples/piper_fake_plant/motion_server.yaml` | URDF、base/tip frame、速度/加速度限位 |
| `controller.yaml` | 参考 operator-controls 同名示例 | 关节组限位与跟随容差 |
| `../../../config/robot.yaml` | `config/robot.example.yaml` 复制 | `speed <= 0.2`，夹爪按现场启用 |

本目录现已有真机验证用的 `motion_server.yaml` 与 `controller.yaml`（2026-11-05）。

## 运行前置（缺一不可）

1. `examples/01_sdk_tests/read_state.py` 通过，`err` 全 0。
2. `config/robot.yaml` 中 `speed <= 0.2`，`initial_position` 与实际支撑姿态一致。
3. 现场有人守在硬件急停/断电位置（硬件急停方式见 `docs/hardware.md`）。
4. 零位/正方向已有厂商书面定义并做过 FK 对拍（`docs/vendor/litearm-docs/`）。

## 运行

```bash
# motion_server / joint_trajectory_controller 来自本地 Forge runtime
mkdir -p /tmp/forge-bin
ln -sf ~/.PhyAgentOS/forge_runtime/nodes/motion_server/versions/*/motion_server /tmp/forge-bin/
ln -sf ~/.PhyAgentOS/forge_runtime/nodes/joint_trajectory_controller/versions/*/joint_trajectory_controller /tmp/forge-bin/

cd examples/03_workflows/real_basic_motion
FORGE_RUNTIME_BIN=/tmp/forge-bin \
PATH="$PWD/../../../.venv/bin:$HOME/.dora/bin:$PATH" \
env -u PYTHONPATH dora run dataflow.real.yaml
```

默认只把 `joint7` 步进 +0.05 rad 后停住，不自动失能。结束用前台 Ctrl-C
（或 `timeout -s INT`），让节点正常 `disconnect()`；**禁止** `timeout`/`kill` 强杀。

## 验收记录

每次运行记录：目标、实际轨迹、最大跟随误差、是否触发限位/报警。
写入 `docs/validation.md` 第 8、11 项，不要只勾选。
