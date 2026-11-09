# 硬件资料清单（接入标准 §5）

所有条目必须能指向本仓内文件或明确的外部路径，不允许只有口头信息。
具体数值统一记在 [`parameters.md`](parameters.md)。

| 资料 | 状态 | 位置 / 备注 |
|---|---|---|
| 厂商资料（产品/开发手册） | 有 | `docs/vendor/litearm-docs/`（V1.0.4 / 2026-10-16，源 commit `483b825`） |
| 厂商连接方式 | 有 | 开发手册「附录二 机械臂连接」：USB CDC `1d50:606f`、`921600 8N1`、自动发现；`docs/vendor/litearm-docs/` |
| 控制接口 | 有 | `litearm.Arm`：`movej` / `movej_sync` / `move_l` / `move_p` / `ik`；开发手册第 2 章 |
| 状态读取接口 | 有 | `get_state()`、`get_tcp()`、`get_status_now()`；开发手册「附录一 机器人状态与报错」 |
| 安全限制 | 有 | 产品手册「安全须知」+「关节参数」软限位表；开发手册「安全注意事项（软件侧）」；本仓另限 `speed` 0..1 |
| 急停方式 | 有 | 产品手册要求硬件急停并切断电源；软件侧 `emergency_stop()` 见下 |
| URDF | 有 | `assets/urdf/litearm.urdf` |
| MJCF | 有 | `assets/mjcf/litearm7.xml` + `scene.xml` |
| GLB | 有 | `assets/glb/litearm.glb`（q=0 静态网格，来源见同目录 README） |
| mesh + texture | 有 | `assets/meshes/`、`assets/mjcf/meshes/` |
| joint 数量/名称/顺序/单位 | 有 | `docs/joint_table.md`；产品手册「关节参数」 |
| 活动范围 / 零位 / 正方向 | 有 | 产品手册「关节参数」（软限位表与固件读回一致）、「图示」（零位/坐标系、**各关节绕 URDF 轴按右手定则确定正方向**）；实测 FK 对拍见 `docs/joint_table.md` §3 |
| 夹爪型号/单位/限位 | 有 | LiteGrip，0–0.080 m 总开口 |
| 工具法兰 / TCP | 有 | SDK `v1.3.0` 提供 `set_tcp_offset`；VR `t_ee=[-0.0071,-0.0239,0.140]` m（法兰系，2026-11-05 实测，见 `docs/validation.md` §t_ee 记录） |
| 外参/手眼标定 | 外部 | 由独立标定工程提供，不在本仓；结果写入 `config/calibration/` |
| VR 参数（MDH/rotation/scale/t_ee） | 有 | `config/vr.example.yaml`；MDH 已由 URDF 反推（`docs/mdh.md`），t_ee 已实测（§t_ee 记录） |
| SDK/固件/系统版本 | 有 | SDK 版本与固件最低版本见 `docs/parameters.md`；实机 `Litearm1.11.0-7J`（2026-11-05 读回） |
| 夹爪总线 | 有 | `can0`，1 Mbit/s，`can_id=0x08`，`mst_id=0x18` |

## 急停

- 软件：`LitearmDriver.emergency_stop()` 先停 worker，再 `arm.disable()`；
  **臂会失去保持力**，无支撑姿态下坠风险。厂商手册另有 `Arm.emergency_stop()`
  （单帧、单向、最高优先级通道）。
- 硬件：厂商产品手册「安全注意事项」要求发生异常时**立即按下硬件急停并切断电源**；
  按钮的具体位置与实验室现有接线仍以现场为准。
