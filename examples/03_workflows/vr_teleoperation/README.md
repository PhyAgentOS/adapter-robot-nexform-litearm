# vr_teleoperation

VR 遥操（验收清单第 13–14 项）。本目录保存 VR 参数，并提供 `vr_bridge_dora.py`：
把 lite-vr teleop 的 TCP 关节流转成 Forge `JointCommand`，让 VR 可以直接驱动本仓
的 `robot-litearm` 节点或 `mujoco_sim`。头显客户端与 teleop/IK 仍在外部仓 `lite-vr`。

## 1. 参数

全部源自 `config/vr.example.yaml`：

| 参数 | 值 / 状态 |
|---|---|
| 参数来源 | `lite-vr/litearm-vr-teleop/teleop/config/teleop.yaml`，2026-11-05 |
| translation_remap | `[[1,0,0],[0,0,1],[0,-1,0]]` |
| rotation_signs | `[1,-1,-1]` |
| base_link signs | `[-1,-1,1]` |
| scale | `1.0` |
| t_ee.tcp_offset_m | `[-0.0071,-0.0239,0.140]` m（法兰系，2026-11-05 实测） |
| MDH | 已由 URDF 反推，见 `docs/mdh.md`（源仓运行时不消费） |

## 2. VR→Dora 桥

`vr_bridge_dora.py` 监听 `127.0.0.1:9001`，协议与 lite-vr 的
`arm_follow_server` 一致（每行一条 JSON，每条命令回一行）：

| 命令 | 行为 |
|---|---|
| `{"cmd":"start"}` | 开始跟随，以当前实测角为锚点 |
| `{"cmd":"q","q":[7]}` | 一帧 7 关节目标，按 URDF 限位裁剪后转发 |
| `{"cmd":"movej","q":[7]}` | 直接跳到目标构型 |
| `{"cmd":"latch"}` / `{"cmd":"hold"}` | 停止跟随，就地持位 |
| `{"cmd":"stop"}` | 停止跟随并持位（仿真里不做失能） |
| `{"cmd":"state","request_id":N}` | 返回 `q`/`cmd_q`/`age_s`/`valid` |
| `{"cmd":"ping"}` | 返回当前状态摘要 |

Dora 侧：`state` 输入（`mujoco/proprio_state` 或 `robot/state`）→ `action`
输出（7 轴 `JointCommand(name, mode="position", position)`），每个 `tick` 下发一次。
lite-vr 的 `real_arm_client` 不需要改动，把右臂地址指向 `:9001` 即可。

| 文件 | 用途 |
|---|---|
| `vr_bridge_dora.py` | 桥节点 |
| `dataflow.sim.yaml` + `simulator.yaml` | 仿真：桥 → `mujoco_sim` |
| `dataflow.example.yaml` | 真机：桥 → `robot-litearm` |

## 3. 仿真端到端验证（2026-11-05）

链路：假头显 → WS :8765 → lite-vr teleop（映射/IK）→ TCP :9001 → 桥 →
Dora `JointCommand` → `mujoco_sim` → `proprio_state` → 桥 → teleop。

工作目录 `examples/03_workflows/vr_teleoperation`，先起 Dora：

```bash
MUJOCO_GL=egl \
PATH="$PWD/../../../.venv/bin:$HOME/.dora/bin:$HOME/.PhyAgentOS/forge_runtime/nodes/mujoco_sim/versions/mujoco_sim-1.1.1-linux-x86_64-tar-gz:$PATH" \
env -u PYTHONPATH dora run dataflow.sim.yaml
```

另两个终端（`lite-vr/litearm-vr-teleop/teleop`，conda `metavr-arm`）：

```bash
python3 launch/run_teleop_webxr.py --source ws --host 127.0.0.1 --port 8765 \
  --real --real-right 127.0.0.1:9001 --viewer gui \
  --probe <repo>/examples/03_workflows/vr_teleoperation/validation_output/vr_bridge_e2e_probe.jsonl

python3 <lite-vr>/litearm-vr-bridge/scripts/fake_headset.py \
  --host 127.0.0.1 --port 8765 --pattern circle --radius 0.03 --period 4 --duration 14
```

测试前先用桥的 `movej` 把仿真臂摆到实测抓取姿态
`[-0.052,-0.317,-0.864,-1.393,-0.340,-1.260,0.190]`；全零位的
`sigma_min_tcp≈7.6e-5` 接近奇异，3 cm 的圆需要大幅关节运动，IK 会偶尔超差。

结果（证据 `validation_output/vr_bridge_summary.json`、`vr_bridge_sim.jsonl`、
`vr_bridge_e2e_probe.jsonl`）：

| 项 | 结果 |
|---|---|
| 握手 | `start` 成功，state `valid`，age ≈16 ms；松手后 `hold` 就地持位 |
| 手柄 → 末端 | 6 cm 圆 → 6.0 cm 圆（J1/J3 等关节范围见表） |
| teleop IK | 720/720 ok，无限幅 |
| 末端 vs 目标 | p50 0.39 mm、p95 0.68 mm、最大 0.89 mm |
| 桥跟踪 | 延迟对齐 70 ms 后 p95 10.7 mrad，最大 16.8 mrad；持位误差 0 |
| 关节范围 | J1 0.512、J2 0.296、J3 0.525、J4 0.175、J5 0.363、J6 0.127、J7 0.583 rad |

零延迟比较的 p95 为 31.4 mrad，主要来自 teleop + TCP + 50 Hz Dora tick +
位置执行器的端到端延迟，不是桥丢帧。

**范围**：本次只跑仿真，未接真机；真机 `dataflow.example.yaml` 复用同一桥和协议。

## 4. lite-vr 映射验证（2026-11-05）

用 lite-vr 自带 pybullet 链路（无头显时用假帧源）单独验证映射方向与缩放，
不含本仓节点。工作目录 `<lite-vr>/litearm-vr-teleop/teleop`：

```bash
python3 launch/run_teleop_webxr.py --source ws --host 127.0.0.1 --port 8765 \
  --no-real --viewer gui --probe <probe.jsonl>

# 另一个终端：平移
python3 <lite-vr>/litearm-vr-bridge/scripts/fake_headset.py \
  --host 127.0.0.1 --port 8765 --pattern circle --radius 0.03 --period 4 --duration 12

# 旋转（本目录脚本，绕 WebXR +Y 摆 ±20°，周期 6 s）
python3 fake_headset_rot.py --host 127.0.0.1 --port 8765 --amp-deg 20 --period 6 --duration 12
```

结果（证据 `validation_output/vr_sim_summary.json` 与两个 probe）：

| 项 | 平移 | 旋转 |
|---|---|---|
| 输入 | 6 cm 圆 | ±20° yaw（40° 峰峰值） |
| 末端 | 6.0 cm 圆，scale 1.00；手 +x→+x、+z→−y | 39.8°，主转轴单一，符号符合 `rotation_signs[1]=−1` |
| 误差 | 末端 vs 目标 ≤0.6 mm | 每帧 ≤2.06°，无跳变 |
| IK | 612/612 ok | 566/574 ok，无限幅 |

## 5. 依赖与前置

- 头显客户端：`litearm-vr-headset`（Godot/OpenXR）
- teleop bridge：`lite-vr/litearm-vr-teleop`
- 本仓 `robot-litearm` 或 `mujoco_sim`
- 真机运行前：只读 probe 通过、`speed <= 0.2`、急停在手边；
  `t_ee` 已写入 `config/vr.example.yaml`；零位/正方向已有厂商书面定义并做过 FK 对拍。

## 6. 运行

仿真按第 3 节。真机把 Dora 数据流换成模板并确认现场地址：

```bash
cd examples/03_workflows/vr_teleoperation
PATH="$PWD/../../../.venv/bin:$HOME/.dora/bin:$PATH" \
  env -u PYTHONPATH dora run dataflow.example.yaml
```

真机结束一律前台 Ctrl-C，让节点正常 `disconnect()` 并保持使能持位；**禁止**
`timeout`/`kill` 强杀。夹爪在 lite-vr 里走独立 TCP `:9003`，不经过本桥。

## 7. 验收判据

- 手柄前后/左右/上下 → 末端运动方向符合直觉；
- 姿态旋转无轴向反转、无奇异跳变；
- 缩放不过敏也不过慢；
- 真机动作满足安全速度、空间边界与急停要求。

## 8. 记录

把每次验证的 rotation/scale/t_ee 与视频/日志路径写入 `docs/validation.md`
第 13、14 项。
