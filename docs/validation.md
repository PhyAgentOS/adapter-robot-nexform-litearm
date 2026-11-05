# 验收清单（接入标准 §12）

复制自 `Robot接入手册.md`，逐条记录证据。**未执行的项不要勾选。**

## 阶段规划（按接入手册 §5–§12）

| 阶段 | 对应手册 | 验收项 | 状态 |
|---|---|---|---|
| 一、资料与 SDK 最小测试 | §5、§6 | 1–5 | 已完成 |
| 二、仿真接入 | §7 | 6–7 | 已完成 |
| 三、Driver + Dora + Workflow + 遥操 | §8–§10 | 8–14 | 已完成 |
| 四、交付整理与验收 | §11、§12 | 15 | 已完成（2026-11-05 提交并开 PR #1） |

| # | 验收项 | 状态 | 证据 |
|---|---|---|---|
| 1 | 厂商资料和资产文件已归档 | 已完成 | 资产齐全（URDF/MJCF/GLB/mesh，`assets/`）；厂商产品手册与软件开发手册已归档到 `docs/vendor/litearm-docs/`（V1.0.4 / 2026-10-16，源 `nexform-tech/litearm-docs` commit `483b825`）；接口摘要见 `docs/hardware.md`；资产来源与 SHA-256 台账见 `assets/README.md` + `assets/SHA256SUMS`（24 个文件，`sha256sum -c` 与 `validate_assets.py` 均通过；STL/OBJ/MJCF 与源逐字节一致，URDF 仅 mesh 路径和 CRLF→LF 不同） |
| 2 | joint 数量/名称/顺序/单位/限位/零位/正方向已记录 | 已完成 | `docs/joint_table.md`；数量/顺序/单位/固件软限位已实测；实测 `q` 下固件 FK 与 URDF FK 吻合（§3.1）；2026-11-05 零位对拍位置差 ≤3.8e-7 m、姿态差 ≤3.7e-6 rad（§3.2）；J4/J5 越软限位已定位为未使能自然平衡点 + `POS_RECOVER_BAND`。厂商产品手册「图示」给出零位/坐标系图，并书面说明各关节绕 URDF 轴按右手定则确定正方向（`docs/vendor/litearm-docs/`） |
| 3 | SDK 最小测试可读取状态 | 已完成 | `examples/01_sdk_tests/read_state.py`：2026-11-05 真机 3 次读取，7 轴 `err=0`，`mode=INIT`，固件 `Litearm1.11.0-7J` |
| 4 | SDK 最小测试可安全下发单关节动作 | 已完成 | 2026-11-05 真机：`move_single_joint.py --joint 0 --delta 0.05 --speed 0.1 --execute`，J1 `+0.1762 → +0.2268 rad`（目标 `+0.2262`，限位 ±2.827），动作后失能 |
| 5 | 末端执行器可控制 | 已完成 | 2026-11-05：`can0`（gs_usb，1 Mbps）接 LiteGrip；SDK `gripper_open_close.py --channel can0 --execute` 1.4 → 80.1 → 0.3 mm（闭合 2.5 N）；Forge 适配层 `JointCommand(gripper, 0.080/0.000/0.080 m)` 回读 0.0801/0.0002/0.0801 m。空闲总线在 `get_opening_m()` 前用 `refresh_status()` 取新帧。payload/堵转阈值见 §夹爪 payload 与堵转阈值记录 |
| 6 | 仿真模型可加载，joint 顺序和运动方向正确 | 已完成 | 2026-11-05 离线 MuJoCo：`offline_sweep.py` 加载 `assets/mjcf/scene.xml`，`nq=nu=7`，joint 名称/顺序/轴/限位与 URDF 逐项一致；7 轴正向命令均使 `q` 正向变化（7/7） |
| 7 | 仿真中所有 joint 完成最小/最大/归零 | 已完成 | 2026-11-05 离线 MuJoCo：21 航点全部 `reached=true`（容差 0.02 rad），共 28/28 通过；记录 `examples/03_workflows/sim_basic_motion/validation_output/sim_sweep.jsonl` |
| 8 | 真机中所有 joint 完成安全范围内最小/最大/归零 | 已完成 | 2026-11-05，7 轴逐一 sweep（J2 起其余关节全程归零），`speed=0.1`，全程 `flags=[]`、`joint_fault=0`、`err=1`：J1 `-2.7544 → +2.7552 → +0.0036`（折叠姿态，流程修正前）；J2 `-1.6726 → +1.6684 → +0.0048`；J3 `-2.7529 → +2.7544 → +0.0090`；J4 `-3.0150 → -0.0437 → +0.0002`；J5 `-2.7502 → +2.7506 → +0.0055`；J6 `-1.4952 → +1.4956 → +0.0048`；J7 `-1.4956 → +1.4990 → +0.0067`（rad），均在内缩 0.05 的目标内 |
| 9 | Forge robot driver 稳定读状态并下发动作 | 已完成 | 2026-11-05：`tests/test_driver.py` 8/8（FakeArm，全仓 23 passed）；真机 `LitearmDriver` 连续 20 次读状态 `max|dev|=0`，`set_command joint1 +0.05` 后 J1 0.32 s 到 `+0.0328`，回令后稳定到 `-0.0002 rad`，全程 `flags=[]`、`err=1` |
| 10 | Dora 节点测试通过 | 已完成 | fake：`dataflow.yaml` 中 7 轴状态与 +0.05 rad 动作正常；真机（2026-11-05）：`dataflow.real.yaml` + `config/robot.yaml`（`speed=0.1`），`Litearm1.11.0-7J` 连接成功，`action_source` 发 `joint7 → +0.0502`（`sent=1`），`state_print` 从 `+0.000` 更新到 `+0.050`（`received=1455`），退出时正常 disconnect |
| 11 | 仿真 workflow 和真机 workflow 均可运行 | 已完成 | 仿真：2026-11-05 Dora 链路 21/21 航点 `reached`，记录 `validation_output/sim_sweep_dora.jsonl`。真机：2026-11-05 15:04 `dataflow.real.yaml`（`ttyACM1`/`Litearm1.10.1-7J`）J7 `-0.5381 → -0.4881 rad`，1.280 s `SUCCESS`，7 轴最终误差 ≤0.0164 rad；退出清理时误杀节点致 `FAULT`/`FB_STALE`/`EMERGENCY`（见 §真机 workflow 记录） |
| 12 | 同构控制在仿真和真机姿态一致 | 已完成 | 仿真：`homomorphic_sim.jsonl` 4 个保持段稳态误差 0、方向一致；真机：`homomorphic_real.jsonl` 稳态最大误差 0.0027 rad、方向一致、无反转；跨环境偏置差 ≤0.0011 rad（见 §同构控制记录） |
| 13 | VR 遥操方向/缩放/末端姿态符合预期 | 已完成 | 仿真（2026-11-05，lite-vr teleop pybullet + 假头显）：平移 scale 1.00、手柄 +x→末端 +x / +z→−y、末端跟踪误差 ≤0.6 mm；旋转 40° 输入→末端 39.8°、主转轴单一、每帧 ≤2.06°；IK 612/612（平移）和 566/574（旋转）、无步长限幅。**VR→Dora 桥端到端（仿真）**：lite-vr teleop → TCP :9001 → `vr_bridge_dora.py` → Dora `JointCommand` → `mujoco_sim` → state 回传；IK 720/720、末端 6.0 cm 圆 vs 目标 p95 0.68 mm、桥跟踪（70 ms 延迟对齐）p95 10.7 mrad、持位误差 0。证据 `examples/03_workflows/vr_teleoperation/validation_output/`，见 §VR 仿真记录。真机：2026-11-05 用户现场确认方向/缩放/末端姿态无问题（未经过本仓桥） |
| 14 | MDH/rotation/scale/t_ee 已记录来源/方法/结果 | 已完成 | MDH 由 URDF 反推并 FK 对拍（`docs/mdh.md`）；rotation/scale 记录自源仓 `teleop.yaml`（`config/vr.example.yaml`）；t_ee=`[-0.0071,-0.0239,0.140]` m（handeye 实测 + CAD 交叉检查 + 只读 SDK 复核，见 §t_ee 记录）。夹爪 payload/堵转阈值见 §夹爪 payload 与堵转阈值记录 |
| 15 | 所有资产/代码/配置/参数/示例已提交并记录用法 | 已完成 | 2026-11-05 已提交并推送到 `PhyAgentOS/adapter-robot-nexform-litearm`，分支 `feat/litearm-adapter-delivery`，PR #1；工作区无未提交改动。README 覆盖手册 §11 全部 13 项；`docs/README.md`（索引）与 `docs/setup.md`（安装/自检）已提交；本地自检 `pytest` 23 passed、`validate_assets.py` 0 error、`urdf_to_mdh.py --check` FK 位置误差 1.878e-11 m；交付布局验证已通过 staging `robots/litearm`（16/16，见 §交付布局验证）。用法见 `README.md`，许可与审计见 `NOTICE`/`THIRD_PARTY_NOTICES.md`/`OPEN_SOURCE_AUDIT.md` |

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

## 交付布局验证（2026-11-05）

本仓是适配器分发布局（与 `adapter-robot-piper`、`adapter-robot-so101` 等一致），
按 `Robot接入手册.md` §2 整体部署到工作区的 `robots/litearm/` 后验收。部署方式
见 `README.md` §目录结构。

- 验收实例：`<workspace>/framework/robots/litearm`（rsync 工作区快照，
  含未提交改动；排除 `.git`/`.venv`/`dist`）。
- 路径校验（`robot-acceptance-validation` 技能的 16 项必需路径，`robot_name=litearm`、
  `robot_package=litearm_robot`）：

```bash
cd <workspace>/framework
python - <<'PY'
from pathlib import Path
robot_name, robot_package = 'litearm', 'litearm_robot'
root = Path('robots') / robot_name
required = [
    'README.md', 'assets/urdf', 'assets/mjcf', 'assets/glb', 'assets/meshes',
    'config/robot.example.yaml', 'config/vr.example.yaml', 'config/calibration',
    'examples/01_sdk_tests', 'examples/02_dora_tests',
    'examples/03_workflows/sim_basic_motion', 'examples/03_workflows/real_basic_motion',
    'examples/03_workflows/homomorphic_control', 'examples/03_workflows/vr_teleoperation',
    f'src/{robot_package}', 'scripts',
]
missing = [p for p in required if not (root / p).exists()]
if missing:
    print('missing:', missing)
    raise SystemExit(1)
print('required robot path layout ok:', root.resolve())
PY
```

- 结果：`required robot path layout ok: .../robots/litearm`（16/16）。
- 同一 staging 上 `scripts/validate_assets.py`：0 error / 0 warning。
- 同一 staging 上 MuJoCo 加载 `assets/mjcf/scene_position.xml`：`nq=7 nu=7`。
- 说明：`Robot接入手册.md` 的示例命令按自身 `cd` 路径计算只需 5 级 `..` 到
  framework 根，文档里写成 6 级；验收以实际工作区布局为准，本仓 workflow 使用
  `$HOME/.PhyAgentOS/forge_runtime` 或本地软链目录。

## 仿真验证记录（2026-11-05）

- 运行：`<mujoco-venv>/bin/python offline_sweep.py`（MuJoCo 3.17.0），
  加载 `assets/mjcf/scene.xml`。
- 第 6 项：`nq=nu=7`；joint 名称/顺序/轴/限位与 URDF 逐项一致；7 轴正向命令 `q` 均正向变化。
- 第 7 项：21 航点（7 轴 × min/max/zero，其余关节保持 0）全部 `reached=true`，容差 0.02 rad；
  合计 28/28，记录 `examples/03_workflows/sim_basic_motion/validation_output/sim_sweep.jsonl`。
- 驱动器为力矩 `motor`，脚本用固件 kp/kd/tau_max 做 PD + 重力补偿；目标角与真机 sweep 一致。

## 仿真 workflow 记录（第 11 项，2026-11-05）

- 模型改用 `assets/mjcf/scene_position.xml`（同一运动学，执行器为 `position`）。
  `mujoco_sim` 直接把目标角写入 `ctrl`，原 `scene.xml` 的力矩 `motor` 会被满速驱动。
- 运行：
  `MUJOCO_GL=egl PATH="$PWD/../../../.venv/bin:$HOME/.dora/bin:$HOME/.PhyAgentOS/forge_runtime/nodes/mujoco_sim/versions/mujoco_sim-1.1.1-linux-x86_64-tar-gz:$PATH" dora run dataflow.example.yaml`
- 结果：三个节点启动正常，`joint_sweep` 21 个航点（7 轴 × min/max/zero，`margin=0.9`）全部
  `reached=true`（容差 0.02 rad），记录 `validation_output/sim_sweep_dora.jsonl`；
  `state_print` 订阅 `proprio_state` 正常（约 50 Hz）。sweep 完成后 `mujoco_sim` 继续运行，
  需要手动 Ctrl-C 结束（`dora run` 不会自行退出）。
- 注意：`joint_sweep.py` 与离线 `offline_sweep.py` 输出文件已区分（`sim_sweep_dora.jsonl`
  与 `sim_sweep.jsonl`），避免互相覆盖。
- 真机侧见下节。

## 真机 workflow 记录（第 11 项，2026-11-05）

- 设备（现场确认后用当前这台）：`/dev/ttyACM1`、by-id `..._354B35763333`、
  固件 `Litearm1.10.1-7J`；`config/robot.yaml` 端口已改为 `ttyACM1`（站点文件，不提交）。
- 运行：`env -u PYTHONPATH FORGE_RUNTIME_BIN=/tmp/forge-bin PATH="$PWD/../../../.venv/bin:$HOME/.dora/bin:$PATH" dora run dataflow.real.yaml`
- 结果：4 个节点全部启动，`robot` 连接 `Litearm1.10.1-7J`；`joint_action_client`
  于 15:04:46 发送 `joint7 -0.5381 → -0.4881 rad`（+0.05），
  15:04:48 `error_code=SUCCESS`，耗时 1.280 s。最终位置
  `[0.0044, -1.7163, -0.0013, -3.0753, 1.9301, 0.3065, -0.5045]`，
  误差 `[0.0000, -0.0004, 0.0000, 0.0046, -0.0042, -0.0099, 0.0164]` rad。
  注意：使能时 J2 从 `-1.7451` 受控回程到 `-1.7163`（越软下限 0.029 rad，在
  `POS_RECOVER_BAND` 内）。
- ⚠ **退出事故**：joint_action_client 正常结束后 `dora run` 不会退出。用 `timeout`
  结束后台 CLI 时只杀了 daemon，`robot` 节点成为孤儿并继续占用串口；随后 `kill -TERM`
  该孤儿进程，SDK 未走 `close()`，臂失去保持力并触发 `FAULT`/`FB_STALE`、
  `mode=EMERGENCY`。姿态从 `J5 +1.9301 / J6 +0.3065 / J7 -0.5045`
  变为 `J5 +0.0032 / J6 -0.2192 / J7 -0.1337`，J2 `-1.7163 → -1.7485`，
  各轴 `err=0`。
- **流程修正**：真机 workflow 结束必须让 dora 正常收尾（前台 Ctrl-C，或让所有节点
  自行退出），使驱动执行 `disconnect()`；**不要**用 `timeout` 杀 daemon 后再杀节点。
  进程被强制终止时不要在没有支撑的位姿上操作。恢复需 `reset()` 后重新 `enable()`，
  且现场确认姿态有支撑。
- **恢复记录**（2026-11-05 15:07）：`reset()` → `INIT`/`flags=[]`；`enable()` →
  `MOVE_J`/`flags=[]`、7 轴 `err=1`，J2 `-1.7485 → -1.7155`、J4 `-3.0833 → -3.0699`
  （受控回程），其余轴基本不变；`close()` 后保持使能持位。

## 同构控制记录（第 12 项，2026-11-05）

- 现场只有一台臂，没有第二台物理主臂；主臂用脚本化 `master_trajectory.py`
  产生 `JointState`，下游通路与真实主臂一致：
  - 仿真：`master_trajectory` → `mirror_command`（`JointCommand(position)`）→
    `mujoco_sim`（`scene_position.xml`）；
  - 真机：`master_trajectory` → 标准 runner 的 `master_state` →
    `node_runner._joint_state_to_command` → `driver.set_command`。
- 轨迹（零位基准，`hold=1.0 s` / `ramp=4.0 s`）：
  `A = 0` → `B = (+0.15, 0, −0.10, 0, +0.10, 0, +0.10)` →
  `C = (+0.15, 0, −0.20, 0, +0.20, 0, +0.10)` → `A`，共 16 s；
  真机链路额外 `--start-delay 3.0`，等从臂连接/使能。
- 真机前置回零：`python -m litearm_robot.main home --config config/robot.yaml`
  （固件 `home()` 0x2A，固定 0.10 低速）从折叠位回零，
  `q` 由 `[0.0021,−1.7159,0.0456,−3.0699,0.0044,−0.2333,−0.1341]` 到
  `[0.0013,−0.0048,−0.0006,0.0013,−0.0006,0.0189,0.0002]`（18 s），
  `mode=MOVE_J`、`joint_fault=0`、`err=1`。
- 运行命令：
  - 仿真：`MUJOCO_GL=egl PATH="$PWD/../../../.venv/bin:$HOME/.dora/bin:<mujoco_sim 版本目录>:$PATH" env -u PYTHONPATH dora run dataflow.sim.yaml`
  - 真机：`PATH="$PWD/../../../.venv/bin:$HOME/.dora/bin:$PATH" env -u PYTHONPATH dora run dataflow.real.yaml`
- 结果（`compare_homomorphic.py`，稳态窗口 0.5 s，阈值 0.05 rad）：
  - 仿真：4 个保持段（A/B/C/A）稳态误差全为 0，方向一致，全程最大 0.0029 rad；
  - 真机：稳态最大误差 `joint6=0.0027` rad，其余 ≤0.0015 rad，方向一致、
    无轴向反转；过渡段最大 0.0408 rad（`movej_sync` 跟踪滞后，非稳态）；
  - 跨环境：4 个保持段相对基准的偏置最大差 0.0011 rad。
- 结束：`timeout -s INT`（等同前台 Ctrl-C）让 `follower_robot` 收到 STOP 并执行
  `disconnect()`；运行后 `mode=MOVE_J`、`joint_fault=0`、`err=1`，保持在零位，
  未失能。`compare_homomorphic.py` 退出码 0。
- 证据：`validation_output/homomorphic_sim.jsonl`、`homomorphic_real.jsonl`、
  `homomorphic_summary.json`、`real_run.log`。

## 阶段一记录：真机动作（2026-11-05）

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
- Forge driver 真机（第 9 项，2026-11-05）：`LitearmDriver(RobotConfig(speed=0.1, move_to_initial=False))`，
  20 次 `get_state()` 连续采样 `max|dev|=0`；`set_command(joint1, +0.05)` 后 0.32 s 到达 `+0.0328`
  （`q_tol=0.03` 提前判到位），回令后稳定在 `-0.0002 rad`；`flags=[]`、`err=1`；
  `disconnect()` 只关连接，不 `disable()`。离线 `test_driver.py` 8/8。
- Dora 真机链路（第 10 项，2026-11-05）：`dataflow.real.yaml` + `config/robot.yaml`，命令行
  `PATH="$PWD/../../.venv/bin:$HOME/.dora/bin:$PATH" dora run dataflow.real.yaml`；三个节点全部启动，
  `action_source` 只发一次 `joint7 → +0.0502 rad`，`state_print` 收到 1455 帧、J7 稳定在 `+0.050`，
  其余轴保持零位；收到 SIGINT 后各节点正常退出，`driver.disconnect()` 未失能。
- 夹爪未连接，第 5 项阻塞；未执行任何夹爪动作。

## 阶段一记录：真机只读（2026-11-05）

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

## t_ee 记录（第 14 项，2026-11-05）

- 值：`t_ee.tcp_offset_m = [-0.0071, -0.0239, 0.140]` m，法兰系（`ee_link`），
  语义 `p_tool = p_ee + R_ee · xyz`（与 litearm SDK `set_tcp_offset` 一致）。
- 来源/方法：
  - 横向 `x, y = [-0.0071, -0.0239]` m：`handeye_grasp` 的 `tool_offset_xy_m`
    实测 —— 把两指中点摆到目标（杯子）正上方，读法兰 TCP，
    `offset = R_ee_xyᵀ · (target_xy − tcp_xy)`（2026-10-27/28，同一 LiteGrip）。
  - 轴向 `z = 0.140` m：法兰到两指夹持面中心沿夹爪进给轴（ee +Z）实测；
    指尖到 0.160 m。CAD 交叉检查（`litegrip-isaacsim/gripper2`）：法兰安装面在
    base_link 后缘 z≈−0.064 m，指段前部对应约 0.13–0.14 m，与实测一致。
- 只读复核（2026-11-05，`Litearm1.10.1-7J`，零位附近）：`set_tcp_offset(xyz=…)`
  后 `get_tool_tcp()` 与 `p_ee + R_ee·xyz` 差 0；工具点位于法兰上方 0.140 m
  （法兰 z=0.7830 → 工具点 z=0.9229），方位与 ee +Z 一致；未 `enable()`、未发运动。
- 证据：`validation_output/tee_check.json`。

## VR 仿真记录（第 13 项，2026-11-05）

验证 VR 链路（手柄位姿 → 轴映射 → IK → 关节 → 仿真末端）的方向、缩放和末端姿态。
第一节用 lite-vr 自带的 pybullet 链路（`metavr-arm` 环境）单独验证映射；
第二节把同一 teleop 的关节流接到本仓新增的 `vr_bridge_dora.py`，经 Dora
`JointCommand` 驱动 `mujoco_sim`，验证桥和 Dora 接入。两节都用假帧源替代头显。

### 映射验证（lite-vr pybullet）

命令（工作目录 `<lite-vr>/litearm-vr-teleop/teleop`）：

```bash
python3 launch/run_teleop_webxr.py --source ws --host 127.0.0.1 --port 8765 \
  --no-real --viewer gui --probe <probe.jsonl>

# 另一个终端：无头显时喂帧
python3 <lite-vr>/litearm-vr-bridge/scripts/fake_headset.py \
  --host 127.0.0.1 --port 8765 --pattern circle --radius 0.03 --period 4 --duration 12
# 旋转（本仓脚本，绕 WebXR +Y 摆 ±20°）
python3 examples/03_workflows/vr_teleoperation/fake_headset_rot.py \
  --host 127.0.0.1 --port 8765 --amp-deg 20 --period 6 --duration 12
```

| 项 | 平移（circle） | 旋转（±20° yaw） |
|---|---|---|
| 帧数 / 时长 | 612 / 10.93 s | 574 / 10.39 s |
| 输入 | 6 cm 圆（x-z） | 40° 峰峰值 |
| 末端响应 | 6.0 cm 圆（x-y） | 局部旋转 39.8° |
| 缩放 | x 1.00；手 z→末端 y 1.002 | 1:1 |
| 方向 | 手 +x→末端 +x；手 +z→末端 −y（与 `teleop.yaml` 的 `rel = Mᵀ·Δp` 一致） | 符号与 `rotation_signs[1]=−1` 一致 |
| 跟踪/平滑 | 末端 vs 目标 ≤0.6 mm；vs 指令方向 cos 0.999 | 每帧最大 2.06°，无跳变 |
| 静止姿态漂移 | ≤0.17° | — |
| IK | 612/612 ok，0 clipped | 566/574 ok，0 clipped |

证据：`examples/03_workflows/vr_teleoperation/validation_output/vr_sim_summary.json` 与两个
`*_probe.jsonl`（逐帧手位姿、指令、关节角、末端位姿）。本节只验证 lite-vr 仿真链路，
不含本仓节点；真机一致性由用户 2026-11-05 现场确认，不是本次独立测量。

### VR→Dora 桥端到端（仿真）

链路：假头显 → WS :8765 → lite-vr teleop（映射/IK）→ TCP :9001 →
`vr_bridge_dora.py` → Dora `JointCommand` → `mujoco_sim` → `proprio_state` →
桥 → teleop。桥的 TCP 协议与 lite-vr `arm_follow_server` 相同，teleop 用
`--real --real-right 127.0.0.1:9001` 连接，无需改上游代码。

工作目录 `examples/03_workflows/vr_teleoperation`：

```bash
# 终端 1：Dora 仿真链路
MUJOCO_GL=egl \
PATH="$PWD/../../../.venv/bin:$HOME/.dora/bin:$HOME/.PhyAgentOS/forge_runtime/nodes/mujoco_sim/versions/mujoco_sim-1.1.1-linux-x86_64-tar-gz:$PATH" \
env -u PYTHONPATH dora run dataflow.sim.yaml

# 终端 2：lite-vr teleop（conda metavr-arm，工作目录 lite-vr/litearm-vr-teleop/teleop）
python3 launch/run_teleop_webxr.py --source ws --host 127.0.0.1 --port 8765 \
  --real --real-right 127.0.0.1:9001 --viewer gui --probe <绝对路径>/vr_bridge_e2e_probe.jsonl

# 终端 3：假头显
python3 <lite-vr>/litearm-vr-bridge/scripts/fake_headset.py \
  --host 127.0.0.1 --port 8765 --pattern circle --radius 0.03 --period 4 --duration 14
```

测试前先用桥的 `movej` 把仿真臂摆到实测抓取姿态
`[-0.052,-0.317,-0.864,-1.393,-0.340,-1.260,0.190]`。全零位接近奇异
（`sigma_min_tcp≈7.6e-5`），同一 3 cm 圆会需要大幅关节运动并偶发 IK 超差；
换到工作姿态后 720/720 帧全部解算成功。

| 项 | 结果 |
|---|---|
| 握手 | `start` 成功（锚点=实测角），state `valid`、age ≈16 ms；松手后 `hold` 就地持位 |
| 手柄 → 末端 | 6 cm 圆 → 6.0 cm 圆（x 0.0598 / y 0.0605 m） |
| teleop IK | 720/720 ok，0 clipped |
| 末端 vs 目标 | p50 0.39 mm、p95 0.68 mm、最大 0.89 mm |
| 桥跟踪（零延迟） | `|cmd−meas|` p95 31.4 mrad、最大 33.8 mrad |
| 桥跟踪（70 ms 延迟对齐） | p50 5.2、p95 10.7、最大 16.8 mrad |
| 持位 | 最终 `|cmd−meas|` = 0 |
| 关节范围 | J1 0.512、J2 0.296、J3 0.525、J4 0.175、J5 0.363、J6 0.127、J7 0.583 rad |

零延迟差主要来自 teleop 管线 + TCP + 50 Hz Dora tick + 位置执行器的端到端延迟，
对齐 70 ms 后误差降到 ~10 mrad 量级，不是桥丢帧。证据：
`validation_output/vr_bridge_summary.json`、`vr_bridge_sim.jsonl`（10 Hz 指令/实测）
和 `vr_bridge_e2e_probe.jsonl`（teleop 逐帧映射与 IK）。本次只跑仿真，未接真机。

## 夹爪 payload 与堵转阈值记录（第 5 项，2026-11-05）

来源：`can0`、factory calibration、空载（两指之间无物），`open()` → `close()`，
20 Hz 记录 `MoveProgress`。证据 `validation_output/gripper_stall_check.json`。

### 堵转阈值（实测）

判据是**位置窗口增量**，不是力矩阈值：每 50 ms 采一次位置，5 个采样（0.25 s）的
窗口净位移小于 `max(0.0015 rad, 0.2 × 窗口内应走距离)` 即判堵转。50 mm/s 时应走
12.5 mm，阈值 0.2 × 12.5 mm = 2.50 mm = 0.034 rad。

| 项 | 实测 |
|---|---|
| 开合位置 | 开 80.03 mm；合到 0.22 mm（标定闭合零点内侧 0.22 mm） |
| 闭合用时 / 帧数 | 1.99 s / 370 帧（斜坡 + 0.3 s 保压） |
| 闭合稳态压力矩 | **0.211 Nm**（SDK `force_n` 读数 2.11 N） |
| 闭合冲击峰值 | **0.818 Nm**（压紧区单帧；该段不适用 0.7 Nm 行进段保护） |
| 堵转触发时窗口位移 | 0.0053 rad（0.39 mm）< 阈值 0.034 rad（2.50 mm） |
| `MoveResult` | `ok=True, stalled=True, reached=False, protected=False` |
| 张开端 | 静止力矩 0.01–0.03 Nm（无负载顶住） |

配置里另有三个**力矩**量，都不是堵转判据：行进段力矩保护 `stop_torque_nm=0.7`
（≈7 N，3 次采样，本次未触发）、`is_grasped()` 阈值
`grasp_torque_threshold=0.5 Nm`、脱离力矩 `breakaway_nm=0.2`（≈2 N）。

`grasp(force_n=5, hold_s=0.4)`：闭合到限位（`reached=True, stalled=False`），保力段
命令前馈 0.5 Nm；状态帧回读约 0.27 Nm（回读滞后/滤波，2 s 长保力也只升到约
0.30 Nm）。**定时 `grasp()` 返回后最后一帧纯力矩仍然生效**：紧接着 `open()` 会因残余
力矩尚未让位而在位置窗口判据下误报 `stalled=True`；先 `enable()`（重初始化）再
`open()` 即正常（实测 80.06 mm）。空载测试不要依赖 `grasp()` 自己收力。

### 末端 payload（`set_payload`，CAD 估算）

- 估算值：**质量 0.5772 kg**，质心 **≈ `[0, 0, +0.055]` m（法兰系）**（轴向 ±0.02 m，
  横向 ≈0）。来源 `litegrip-isaacsim/gripper2/gripper2.urdf` 的 inertial：base_link
  0.506299 kg + 两指各 0.035454 kg；质心按刚体质量加权，法兰安装面取 CAD 后缘
  `z ≈ -0.0641 m`。**不含**法兰转接板与螺钉。
- **未做动态辨识**：SDK 的差分法（`litearm.payload.identify`）要求先有一份**空载
  基线**，而夹爪已装在法兰上，无法再采空载；绝对法在本机不可用 —— 零位下 J1 实测
  `τ ≈ -0.85 Nm`，而该姿态重力绕 J1 的力矩恒为 0，说明静态偏置/摩擦远大于可辨识信号。
- 因此该值只作为 `set_payload` 的**工程估算**，未写入固件（当前固件 `payload_mass=0`）。
  要做实数：称重得质量；或拆下夹爪采空载基线后跑差分辨识。
- 证据 `validation_output/payload_check.json`。

## 已知限制与差距

1. 实机 `Litearm1.11.0-7J` 的固件源码未归档（已归档参考源码 `Litearm1.10.5-7J`，
   `6d4dd27`）；`following_error` 阈值只能引用该源码值。
2. 夹爪 payload（`set_payload`）为 CAD 估算（质量 0.5772 kg，质心 ≈`[0,0,+0.055]` m，
   法兰系），**未做动态辨识、未写入固件**——夹爪已装机，缺空载基线；见
   §夹爪 payload 与堵转阈值记录。要做实数需称重或拆爪采基线。
3. 仿真 workflow 的 `mujoco_sim` 节点未进 PATH：运行时需显式把
   `~/.PhyAgentOS/forge_runtime/nodes/mujoco_sim/versions/...` 加进 PATH（见 §仿真 workflow 记录）。
4. 真机 workflow 的启动会使能（`enable_on_connect: true`）并让 J2/J4/J5 受控回程；
   结束必须让 dora 正常收尾，禁止 `timeout`/`kill` 强杀 robot 节点（见 §真机 workflow 记录）。
5. 第 8–12 项的真机验证在 `3857336E3134` / `1.11.0-7J` 样机上完成；当前台架臂为
   `354B35763333` / `1.10.1-7J`（2026-11-05 15:44 重新枚举为 `/dev/ttyACM0`，by-id 不变，
   `config/robot.yaml` 已改用 by-id 路径）。若验收要求同一台，需换回复跑第 8–12 项。
6. `speed` 归一化到实际角速度未实测（验收不要求该映射）；`set_command` 仅 position 模式。
7. VR→Dora 桥（`vr_bridge_dora.py`）已实现并在仿真端到端验证（`mujoco_sim`），
   协议与 lite-vr `arm_follow_server` 一致；**尚未在本仓真机 `dataflow.example.yaml`
   上跑过**，第 13 项的真机确认是用户直接使用 lite-vr 原生链路完成的。现场部署时
   注意 lite-vr teleop 的臂侧地址要指向桥的 `:9001`。
