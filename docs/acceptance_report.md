# litearm 验收报告

验收日期：2026-11-05
验收对象：NexForm LiteArm 7-DOF + LiteGrip
源码仓：`adapter-robot-nexform-litearm`
验收实例：`<workspace>/framework/robots/litearm`（本仓分发布局整体部署为
`robots/litearm/`，含当前工作区改动）

## 结论

总体状态：pass

说明：16 项必需路径全部存在，逐项验收 15 项全部为 `✓`。第 15 项于 2026-11-05 完成：
全部改动已提交并推送到 `PhyAgentOS/adapter-robot-nexform-litearm`（分支
`feat/litearm-adapter-delivery`，PR #1），工作区无未提交改动。

## 路径结构验证

目标路径：`<workspace>/framework/robots/litearm`
（本仓采用适配器分发布局，与 `adapter-robot-piper`、`adapter-robot-so101` 等一致；
部署映射见 `README.md` §目录结构）

- [✓] `README.md`：仓库首页，覆盖接入手册 §11 全部 13 项，并记录部署方式和已知限制。
- [✓] `assets/urdf`：`litearm.urdf`，7 个 revolute joint。
- [✓] `assets/mjcf`：`litearm7.xml`（力矩 `motor`）、`scene.xml`、`litearm7_position.xml` +
  `scene_position.xml`（position 执行器，供 `mujoco_sim`）和 `meshes/`。
- [✓] `assets/glb`：`litearm.glb`（9 nodes / 9 meshes / 1 scene）和 `README.md`
  （生成命令 + SHA-256 `e51a45ad…5408f1b`，实测哈希一致）。
- [✓] `assets/meshes`：`base_link.STL`、`ee_link.STL`、`joint1..6.STL` 等。
- [✓] `config/robot.example.yaml`：真机驱动配置示例（端口、速度、使能策略）。
- [✓] `config/vr.example.yaml`：VR 的 rotation / scale / `t_ee` 参数。
- [✓] `config/calibration`：标定归档约定（`README.md`），当前不含现场标定结果。
- [✓] `examples/01_sdk_tests`：`read_state.py`、`move_single_joint.py`、
  `gripper_open_close.py`、`safety_stop.py`、`camera_read.py` 及 README。
- [✓] `examples/02_dora_tests`：`action_source.py`、`state_print.py`、`dataflow.yaml`、
  `dataflow.real.yaml`。
- [✓] `examples/03_workflows/sim_basic_motion`：`joint_sweep.py`、`simulator.yaml`、
  `dataflow.example.yaml`、`validation_output/`。
- [✓] `examples/03_workflows/real_basic_motion`：`joint_action_client.py`、
  `motion_server.yaml`、`controller.yaml`、`dataflow.real.yaml`。
- [✓] `examples/03_workflows/homomorphic_control`：`master_trajectory.py`、
  `mirror_command.py`、`state_recorder.py`、`compare_homomorphic.py`、两套 dataflow 和
  `validation_output/`。
- [✓] `examples/03_workflows/vr_teleoperation`：`vr_bridge_dora.py`、`dataflow.sim.yaml`、
  `dataflow.example.yaml`、`simulator.yaml` 和 `validation_output/`。
- [✓] `src/litearm_robot`：`config.py`、`codec.py`、`driver.py`、`gripper.py`、`fake.py`、
  `main.py`。
- [✓] `scripts`：`validate_assets.py`、`urdf_to_mdh.py`、`mjcf_to_glb.py`、
  `check_sdk_api.py`、`build_entry.py`、`build_pyinstaller.sh`。

结论：pass（16/16；`required robot path layout ok`）

## 逐项验收

1. [✓] 厂商资料和资产文件已归档。原因/证据：URDF/MJCF/GLB/mesh 齐备，`validate_assets.py`
   0 error；厂商产品手册与软件开发手册归档在 `docs/vendor/litearm-docs/`
   （V1.0.4 / 2026-10-16，源 `nexform-tech/litearm-docs` commit `483b825`）；接口摘要见
   `docs/hardware.md`。所有交付资产已建立 SHA-256 台账（`assets/SHA256SUMS`，24 个文件），
   来源、源提交与转换见 `assets/README.md`；STL/OBJ/MJCF 与源文件逐字节一致，
   URDF 仅 mesh 路径（`package://` → 相对路径）和 CRLF→LF 不同。
2. [✓] joint 数量、名称、顺序、单位、限位、零位、正方向已记录。原因/证据：
   `docs/joint_table.md` §2.1/§3.1；数量、顺序、单位、固件软限位已实测；厂商产品手册
   给出零位/坐标系图并书面说明各关节绕 URDF 轴按右手定则定正方向；实测 `q` 下固件 FK
   与 URDF FK 位置差 <1e-5 m；2026-11-05 零位对拍位置差 ≤3.8e-7 m、姿态差 ≤3.7e-6 rad。
3. [✓] SDK 最小测试可读取状态。原因/证据：`examples/01_sdk_tests/read_state.py` 在
   `Litearm1.11.0-7J` 上连续 3 次读取，7 轴 `err=0`、`mode=INIT`。
4. [✓] SDK 最小测试可安全下发单关节动作。原因/证据：`move_single_joint.py --joint 0
   --delta 0.05 --speed 0.1 --execute`，J1 `+0.1762 → +0.2268 rad`（目标 `+0.2262`，
   到位误差 0.0006 rad，软限位 ±2.827），动作后失能。
5. [✓] 末端执行器可控制。原因/证据：LiteGrip 经 `can0`（gs_usb，1 Mbps）连接；SDK 开合
   1.4 → 80.1 → 0.3 mm（闭合 2.5 N）；Forge 层 `gripper` 指令 0.080/0.000/0.080 m，
   回读 0.0801/0.0002/0.0801 m。堵转判据与阈值已实测
   （`validation_output/gripper_stall_check.json`）；payload 仅为 CAD 估算。
6. [✓] 仿真模型可加载，joint 顺序和运动方向正确。原因/证据：MuJoCo 加载
   `assets/mjcf/scene.xml` 与 `scene_position.xml` 均为 `nq=7 nu=7`；joint 名称/顺序/轴/
   限位与 URDF 逐项一致；7 轴正向命令均使 `q` 正向变化（7/7）。
7. [✓] 仿真中所有 joint 可完成最小角度、最大角度、归零测试。原因/证据：离线
   `offline_sweep.py` 21 航点（7 轴 × min/max/zero，其余关节保持 0）全部 `reached=true`
   （容差 0.02 rad），合计 28/28；Dora 链路 `joint_sweep.py` 同样 21/21。
   记录 `sim_sweep.jsonl` / `sim_sweep_dora.jsonl`。
8. [✓] 真机中所有 joint 可完成安全范围内的最小角度、最大角度、归零测试。原因/证据：
   2026-11-05 在 `1.11.0-7J` 样机上逐轴 sweep（其余关节全程归零，`speed=0.1`），
   全程 `flags=[]`、`joint_fault=0`、`err=1`：J1 `-2.7544 → +2.7552 → +0.0036`；
   J2 `-1.6726 → +1.6684 → +0.0048`；J3 `-2.7529 → +2.7544 → +0.0090`；
   J4 `-3.0150 → -0.0437 → +0.0002`；J5 `-2.7502 → +2.7506 → +0.0055`；
   J6 `-1.4952 → +1.4956 → +0.0048`；J7 `-1.4956 → +1.4990 → +0.0067` rad。
   详见 `docs/validation.md` §阶段一记录：真机动作。
9. [✓] Forge robot driver 可稳定读取状态并下发动作。原因/证据：离线
   `tests/test_driver.py` 8/8、全仓 23 passed；真机 `LitearmDriver` 连续 20 次
   `get_state()` 的 `max|dev|=0`，`set_command(joint1, +0.05)` 后 0.32 s 到 `+0.0328`，
   回令后稳定在 `-0.0002 rad`，全程 `flags=[]`、`err=1`。
10. [✓] Dora 节点测试通过。原因/证据：fake `dataflow.yaml` 中 7 轴状态与 +0.05 rad 动作
    正常；真机 `dataflow.real.yaml` 三节点全部启动，`action_source` 发
    `joint7 → +0.0502 rad`，`state_print` 收到 1455 帧、J7 稳定在 `+0.050`，
   退出时正常 `disconnect()`。
11. [✓] 仿真 workflow 和真机 workflow 均可运行。原因/证据：仿真 Dora 链路
    21/21 航点 `reached`（`sim_sweep_dora.jsonl`）；真机 2026-11-05 15:04
    `dataflow.real.yaml` 执行 J7 `-0.5381 → -0.4881 rad`，1.280 s `SUCCESS`，
    7 轴最终误差 ≤0.0164 rad。真机退出事故与流程修正见 `docs/validation.md`
    §真机 workflow 记录。
12. [✓] 同构控制在仿真和真机中姿态一致。原因/证据：现场只有一台臂，主臂用
    `master_trajectory.py` 脚本化产生 `JointState`；零位基准 A→B→C→A，
    仿真 4 个保持段稳态误差为 0、真机稳态最大 0.0027 rad、跨环境偏置差 ≤0.0011 rad，
    方向一致无反转。证据 `examples/03_workflows/homomorphic_control/validation_output/`。
13. [✓] VR 遥操作在仿真和真机中方向、缩放、末端姿态符合预期。原因/证据：lite-vr
    pybullet 链路 6 cm 手柄圆 → 6.0 cm 末端圆（scale 1.00，手 +x→+x、+z→−y），
    旋转 40° → 末端 39.8°，IK 612/612 与 566/574。VR→Dora 桥端到端（仿真）：
    lite-vr → TCP :9001 → `vr_bridge_dora.py` → Dora `JointCommand` → `mujoco_sim`，
    IK 720/720、末端 vs 目标 p95 0.68 mm、桥跟踪（70 ms 对齐）p95 10.7 mrad、
    持位误差 0。真机由用户 2026-11-05 现场确认方向/缩放/末端姿态无问题
    （通过 lite-vr 原生链路，未经过本仓桥）。
14. [✓] MDH、rotation、scale、tee 已记录来源、标定方法和验证结果。原因/证据：
    MDH 由 URDF 反推并 FK 对拍，500 组随机 `q` 位置最大误差 1.878e-11 m
    （`docs/mdh.md`、`urdf_to_mdh.py --check`）；rotation/scale 记录自源仓
    `teleop.yaml`（`config/vr.example.yaml`）；`tee` 即本仓 `t_ee`，
    值为 `[-0.0071, -0.0239, 0.140]` m（法兰系 `ee_link`，`p_tool = p_ee + R_ee·xyz`），
    横向来自 handeye 实测 `tool_offset_xy_m`，轴向 0.140 m 由实测 + CAD 交叉检查，
    只读 SDK 复核差 0（`validation_output/tee_check.json`）。
15. [✓] 所有资产、代码、配置、参数和示例均已提交并记录使用方式。原因/证据：
    2026-11-05 全部改动已提交并推送到 `PhyAgentOS/adapter-robot-nexform-litearm`
    （分支 `feat/litearm-adapter-delivery`，PR #1），工作区无未提交改动；
    使用方式已记录（`README.md`、`docs/README.md`、`docs/setup.md`、
    各 `examples/*/README.md`），交付布局验证已通过（staging `robots/litearm`，16/16）。

## 失败 / 阻塞项

- 无失败项。
- 需知悉（用户已确认不作为问题）：第 8–12 项真机数据采自 `1.11.0-7J` 样机，
  当前台架为 `1.10.1-7J`；VR→Dora 桥尚未在本仓真机 dataflow 上跑过；
  夹爪 payload 为 CAD 估算、未写固件；`1.11.0-7J` 固件源码未归档。

## 已执行验证

- 路径结构验证：在 `<workspace>/framework` 运行技能提供的 16 项检查，
  结果 `required robot path layout ok: .../robots/litearm`。
- MuJoCo load：staging 上 `assets/mjcf/scene_position.xml` 加载成功，`nq=7 nu=7`；
  `scene.xml` 早前同样验证。
- GLB check：SHA-256 与 `assets/glb/README.md` 记录一致
  （`e51a45ad760d6f13bcc2ebe6ff820df540d1acb3e1b4bab518451c76d5408f1b`）；
  `nodes=9 meshes=9 scenes=1`。
- 资产台账：`sha256sum -c assets/SHA256SUMS` 24/24 通过；
  `validate_assets.py` 的 SHA-256 检查 24 个文件、0 error / 0 warning。
- Stability check：本仓无 `scripts/<robot_name>_stability_check.py`；等价验证为
  `offline_sweep.py` 21/21 → 28/28 与 Dora 链路 21/21，无 NaN/Inf/QACC 异常。
- Dora build/run：`dora build` 对 `sim_basic_motion/dataflow.example.yaml` 与
  `vr_teleoperation/dataflow.sim.yaml` 通过；run 记录为仿真 21/21、真机 1.280 s
  `SUCCESS`、同构 `/` VR 仿真记录见 `docs/validation.md`。
- SDK / 真机：三台设备记录——`1.11.0-7J`（`ttyACM0`，第 3/4/8/9/10 项）、
  `1.10.1-7J`（`ttyACM1`，第 11 项）、`1.10.1-7J`（零位对拍与 `t_ee` 只读复核）。
- 本地自检：`pytest` 23 passed；`scripts/validate_assets.py` 0 error / 0 warning；
  `urdf_to_mdh.py --check` FK 位置误差 1.878e-11 m。

## 风险与后续

1. 等待 PR #1 审核并合并；合并后重新录制 staging 快照。
2. 录制 MuJoCo 仿真视频和真机视频，作为交付附件。
3. 把本报告的终端结果截图填入飞书 Robots 清单。
4. `Robot接入手册.md` 的示例命令按自身 `cd` 路径只需 5 级 `..` 到 framework 根，
   文档写成了 6 级；验收以实际工作区布局为准。
