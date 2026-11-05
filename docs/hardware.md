# 硬件资料清单（接入标准 §5）

所有条目必须能指向本仓内文件或明确的外部路径，不允许只有口头信息。
具体数值统一记在 [`parameters.md`](parameters.md)。

| 资料 | 状态 | 位置 / 备注 |
|---|---|---|
| 厂商连接方式 | 部分 | litearm SDK 走 USB CDC（`1d50:606f`）；自动发现 |
| 控制接口 | 有 | `litearm.Arm`：`movej` / `movej_sync` / `move_l` / `move_p` / `ik` |
| 状态读取接口 | 有 | `get_state()`、`get_tcp()`、`get_status_now()` |
| 安全限制 | 部分 | 固件限位 + SDK speed 0..1；急停方式见下 |
| 急停方式 | 部分 | 本仓 `emergency_stop()` = 取消下发 + `disable()`；硬件急停需现场确认 |
| URDF | 有 | `assets/urdf/litearm.urdf` |
| MJCF | 有 | `assets/mjcf/litearm7.xml` + `scene.xml` |
| GLB | 有 | `assets/glb/litearm.glb`（q=0 静态网格，来源见同目录 README） |
| mesh + texture | 有 | `assets/meshes/`、`assets/mjcf/meshes/` |
| joint 数量/名称/顺序/单位 | 有 | `docs/joint_table.md` |
| 活动范围 / 零位 / 正方向 | 部分 | 范围有；零位/正方向待固件确认 |
| 夹爪型号/单位/限位 | 有 | LiteGrip，0–0.080 m 总开口 |
| 工具法兰 / TCP | 部分 | SDK `v1.3.0` 提供 `set_tcp_offset`；当前 VR t_ee=0，待实测 |
| 外参/手眼标定 | 外部 | 由独立标定工程提供，不在本仓；结果写入 `config/calibration/` |
| VR 参数（MDH/rotation/scale/t_ee） | 部分 | `config/vr.example.yaml`；MDH 已由 URDF 反推（`docs/mdh.md`），t_ee 待实测 |
| SDK/固件/系统版本 | 有 | SDK 版本与固件最低版本见 `docs/parameters.md`；实机 `Litearm1.11.0-7J`（2026-11-05 读回） |
| 夹爪总线 | 有 | `can0`，1 Mbit/s，`can_id=0x08`，`mst_id=0x18` |

## 急停

- 软件：`LitearmDriver.emergency_stop()` 先停 worker，再 `arm.disable()`；
  **臂会失去保持力**，无支撑姿态下坠风险。
- 硬件：现场需确认厂商急停按钮或断电方式，并写入本文件。
