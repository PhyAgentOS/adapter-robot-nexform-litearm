# 验收清单（接入标准 §12）

复制自 `Robot接入手册.md`，逐条记录证据。**未执行的项不要勾选。**

| # | 验收项 | 状态 | 证据 |
|---|---|---|---|
| 1 | 厂商资料和资产文件已归档 | 部分 | 资产齐全（URDF/MJCF/GLB/mesh，`assets/`）；厂商原始手册未归档，接口摘要见 `docs/hardware.md` |
| 2 | joint 数量/名称/顺序/单位/限位/零位/正方向已记录 | 已完成 | `docs/joint_table.md`；数量/顺序/单位/固件软限位已实测；实测 `q` 下固件 FK 与 URDF FK 吻合；J4/J5 越软限位已定位为未使能自然平衡点 + `POS_RECOVER_BAND`（见 §3.1）。零位/正方向仍缺厂商书面确认（记入第 1 项） |
| 3 | SDK 最小测试可读取状态 | 已完成 | `examples/01_sdk_tests/read_state.py`：2026-11-05 真机 3 次读取，7 轴 `err=0`，`mode=INIT`，固件 `Litearm1.11.0-7J` |
| 4 | SDK 最小测试可安全下发单关节动作 | 已完成 | 2026-11-05 真机：`move_single_joint.py --joint 0 --delta 0.05 --speed 0.1 --execute`，J1 `+0.1762 → +0.2268 rad`（目标 `+0.2262`，限位 ±2.827），动作后失能 |
| 5 | 末端执行器可控制 | 阻塞 | 夹爪未连接：`gripper_open_close.py --execute` 在 `enable()` 处报“电机无反馈（超时 2.0s）”；被动 `get_state()` 恒 `fresh=False` |
| 6 | 仿真模型可加载，joint 顺序和运动方向正确 | 已完成 | 2026-11-05 离线 MuJoCo：`offline_sweep.py` 加载 `assets/mjcf/scene.xml`，`nq=nu=7`，joint 名称/顺序/轴/限位与 URDF 逐项一致；7 轴正向命令均使 `q` 正向变化（7/7） |
| 7 | 仿真中所有 joint 完成最小/最大/归零 | 已完成 | 2026-11-05 离线 MuJoCo：21 航点全部 `reached=true`（容差 0.02 rad），共 28/28 通过；记录 `examples/03_workflows/sim_basic_motion/validation_output/sim_sweep.jsonl` |
| 8 | 真机中所有 joint 完成安全范围内最小/最大/归零 | 已完成 | 2026-11-05，7 轴逐一 sweep（J2 起其余关节全程归零），`speed=0.1`，全程 `flags=[]`、`joint_fault=0`、`err=1`：J1 `-2.7544 → +2.7552 → +0.0036`（折叠姿态，流程修正前）；J2 `-1.6726 → +1.6684 → +0.0048`；J3 `-2.7529 → +2.7544 → +0.0090`；J4 `-3.0150 → -0.0437 → +0.0002`；J5 `-2.7502 → +2.7506 → +0.0055`；J6 `-1.4952 → +1.4956 → +0.0048`；J7 `-1.4956 → +1.4990 → +0.0067`（rad），均在内缩 0.05 的目标内 |
| 9 | Forge robot driver 稳定读状态并下发动作 | 待执行 | `tests/test_driver.py` + 真机 |
| 10 | Dora 节点测试通过 | 部分 | fake 链路已验证：Python 3.12.13 + dora-cli 0.4.1，`dora run dataflow.yaml` 中 `state_print` 收到 7 轴状态，`action_source` 向 `joint7` 发 +0.05 rad 后状态更新；真机链路待阶段 2 |
| 11 | 仿真 workflow 和真机 workflow 均可运行 | 待执行 | `examples/03_workflows/` |
| 12 | 同构控制在仿真和真机姿态一致 | 待执行 | `homomorphic_control/` |
| 13 | VR 遥操方向/缩放/末端姿态符合预期 | 部分 | 源仓有真机记录；本仓待复验 |
| 14 | MDH/rotation/scale/t_ee 已记录来源/方法/结果 | 部分 | `config/vr.example.yaml`、`docs/parameters.md`、`docs/mdh.md`；t_ee 待实测 |
| 15 | 所有资产/代码/配置/参数/示例已提交并记录用法 | 已完成 | 初始提交；用法见 `README.md`，许可与审计见 `NOTICE`/`THIRD_PARTY_NOTICES.md`/`OPEN_SOURCE_AUDIT.md` |

## 环境自检记录（2026-11-05）

| 组件 | 版本 | 结果 |
|---|---|---|
| Python | 3.12.13 | ✅ `.venv` |
| dora-cli / dora-rs | 0.4.1 / 0.4.1 | ✅ |
| forge-msgs / forge-robot | 1.3.0 / 1.0.1 | ✅ |
| litearm-python | `v1.3.0`（`__version__` 2.1.0） | ✅ `set_tcp_offset` / `set_payload` 存在 |
| litegrip-python | `v1.2.1` | ✅ factory calibration md5 `1a9beb55…` |
| pytest | 9.2.0 | ✅ 23 passed |
| MuJoCo / trimesh | 3.9.0 / 5.0.0 | ✅ MJCF `nq=7 nu=7`；GLB 9 个网格 |
| dora build | dora-cli 0.4.1 | ✅ 5 个 dataflow 描述均通过 |
| SDK API 核对 | litearm 2.1.0 / litegrip v1.2.1 | ✅ `scripts/check_sdk_api.py` |

命令（须 `env -u PYTHONPATH`，避免 ROS 2 的 Python 3.10 包污染）：

```bash
env -u PYTHONPATH .venv/bin/python -m pytest -q
env -u PYTHONPATH .venv/bin/robot-litearm probe --fake
cd examples/02_dora_tests && env -u PYTHONPATH PATH="$HOME/.dora/bin:$PATH" dora run dataflow.yaml
```

## 仿真验证记录（2026-11-05）

- 运行：`/home/qql/sl/litearm-mujoco/.venv/bin/python offline_sweep.py`（MuJoCo 3.17.0），
  加载 `assets/mjcf/scene.xml`。
- 第 6 项：`nq=nu=7`；joint 名称/顺序/轴/限位与 URDF 逐项一致；7 轴正向命令 `q` 均正向变化。
- 第 7 项：21 航点（7 轴 × min/max/zero，其余关节保持 0）全部 `reached=true`，容差 0.02 rad；
  合计 28/28，记录 `examples/03_workflows/sim_basic_motion/validation_output/sim_sweep.jsonl`。
- 驱动器为力矩 `motor`，脚本用固件 kp/kd/tau_max 做 PD + 重力补偿；目标角与真机 sweep 一致。

## 阶段 2 真机动作记录（2026-11-05）

- 使能保持：`arm.enable()` 后 J4 `-3.0905 → -3.0615`、J5 `2.8098 → 2.8002`（受控回程），
  `mode=MOVE_J`、`err=1`（DM 使能态）；`disable()` 后 J4 自然回落 `-3.0905`。
- 单关节：J1 `+0.1762 → +0.2268 rad`，命令 `+0.05 rad`、`speed=0.1`，到位误差 0.0006 rad。
- 已知脚本陷阱：SDK `q_tol=0.03 rad`。步长 ≤0.03 时 `movej_sync` 会立即判到位并返回，
  脚本随即失能，表现为“命令成功但关节没动”（本次 0.02 rad 首次尝试即如此）。
  真机步长应 >0.03，示例统一用 0.05。
- J1 全范围 sweep：目标软限位内缩 0.05，`-2.7595 → +2.7595 → 0.0 rad`，speed 0.1；
  实测 `-2.7544 → +2.7552 → +0.0036`，全程 `flags=[]`、使能态 `err=1`。
- ⚠ **失能事故**：J1 sweep 结束时按脚本默认在 J1≈0、其余关节折叠的位姿 `disable()`，
  臂在重力下坠落（J2 `-0.404 → +0.622`，J4 `-3.09 → -2.64`），下坠触发
  `FB_STALE`/`POS_VIOL`，`joint_fault=127`，进入 `EMERGENCY`。
  `reset()` 后恢复 `INIT`，`enable()` 成功，J5 回程 `2.8506 → 2.7987`；当前保持使能。
- 流程修正：sweep/大幅动作期间**保持使能**；结束只关闭连接（固件 watchdog fail-soft 持位），
  不在无支撑位姿调用 `disable()`。确需失能时先人工托住。
- 流程修正 2（用户要求）：跑某关节极限限位时**其余关节必须先回零**，避免构型干涉。
- J2 全范围 sweep（改正流程后，其余关节全程归零）：先 `-1.6726`、后 `+1.6684`、再回 `+0.0048`，
  `speed=0.1`，全程 `flags=[]`、`joint_fault=0`、使能态 `err=1`；结束只 `close()`，保持使能持位。
  起点 `+0.6184` → 归零 `+0.0010` 后再扫限位。
- J3 全范围 sweep（其余关节全程归零）：目标 `-2.7595 → +2.7595 → 0`，实测 `-2.7529 → +2.7544 → +0.0090`，
  `speed=0.1`；全程 `flags=[]`、`joint_fault=0`、`err=1`，其余关节偏差 ≤0.001 rad；结束只 `close()`，保持使能持位。
- J4 全范围 sweep（其余关节全程归零）：目标 `-3.0215 → -0.0325 → 0`，实测 `-3.0150 → -0.0437 → +0.0002`，
  `speed=0.1`；全程 `flags=[]`、`joint_fault=0`、`err=1`，其余关节偏差 ≤0.001 rad；结束只 `close()`，保持使能持位。
  J4 上限实测比目标低 0.0112 rad（重力下垂），在 `q_tol=0.03` 内。
- J5 全范围 sweep（其余关节全程归零）：目标 `-2.7595 → +2.7595 → 0`，实测 `-2.7502 → +2.7506 → +0.0055`，
  `speed=0.1`；全程 `flags=[]`、`joint_fault=0`、`err=1`，其余关节偏差 ≤0.001 rad；结束只 `close()`，保持使能持位。
- J6 全范围 sweep（其余关节全程归零）：目标 `-1.5035 → +1.5035 → 0`，实测 `-1.4952 → +1.4956 → +0.0048`，
  `speed=0.1`；全程 `flags=[]`、`joint_fault=0`、`err=1`，其余关节偏差 ≤0.001 rad；结束只 `close()`，保持使能持位。
- J7 全范围 sweep（其余关节全程归零）：目标 `-1.5035 → +1.5035 → 0`，实测 `-1.4956 → +1.4990 → +0.0067`，
  `speed=0.1`；全程 `flags=[]`、`joint_fault=0`、`err=1`，其余关节偏差 ≤0.001 rad；结束只 `close()`，保持使能持位。
  至此 7 轴最小/最大/归零全部完成（第 8 项）。
- `home()` 零位对照（2026-11-05）：臂已在全零位附近，`enable()` 后执行 `home()`（0x2A），
  前后 `q` 逐轴一致（`max|Δ|=0`），`flags=[]`、`joint_fault=0`、`err=1`；结束只 `close()`，保持使能持位。
- 夹爪未连接，第 5 项阻塞；未执行任何夹爪动作。

## 阶段 1 真机只读记录（2026-11-05）

- 设备：`/dev/ttyACM0`（`1d50:606f`，by-id `STM32_Virtual_ComPort_3857336E3134`）；`can0` 1 Mbit/s。
- 固件：`Litearm1.11.0-7J`，`n=7`；SDK `min_firmware=(1,5,0)`。
- 状态：`mode=INIT`、无 flags、7 轴 `err=0`；静止 `q` 见 `docs/joint_table.md` §3.1。
- 参数：逐关节软限位与 `kp/kd/tau_max` 已读回，见 `docs/joint_table.md` §2.1。
- FK 对拍：`arm.get_tcp()` 与按实测 `q` 计算的 URDF FK 位置差 <1e-5 m、rpy 差 <1e-5 rad
  ⇒ 零位与正方向换算与 URDF 一致。
- J4/J5 越软限位：已定位为**未使能自然平衡点**。软限位只钳 `q_ref`；固件
  `POS_RECOVER_BAND`（1.10.0 为 0.05 rad，1.10.1 起为 0.30 rad；本机归档 1.10.5）
  允许未使能态越界 ≤带宽，使能时受控回程。实测越界 0.0236 / 0.0369 rad 在两种版本的带内，
  `flags=[]`、`joint_fault=0`，非故障。
  注意：使能会让两轴各回约 0.024 / 0.037 rad，需支撑与批准。
- 夹爪：`LiteGrip.connect()` 被动连接成功（不使能、不发运动）；未使能时 `get_state()` 恒
  `fresh=False`，`candump can0` 3 s 无报文。使能读回需单独批准。
- 未执行：`enable()`、`movej_sync`、`home()`、任何夹爪使能/动作。

## 已知阻塞项

1. 固件零位/正方向仅有 FK 对拍证据、缺书面确认；已归档 `Litearm1.10.5-7J` 源码（`6d4dd27`），实机 `1.11.0-7J` 对应源码仍未归档。
2. `t_ee`、夹爪 payload/堵转阈值未实测（阶段 3）。
3. 夹爪未连接，末端执行器验收阻塞。
4. 仿真 workflow 依赖 `operator-simulator-mujoco` 等外部节点，本机未安装。
