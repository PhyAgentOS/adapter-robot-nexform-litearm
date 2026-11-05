# vr_teleoperation

VR 遥操（验收清单第 13–14 项）。**模板。**

## 参数

全部源自 `config/vr.example.yaml`：

| 参数 | 值 / 状态 |
|---|---|
| 参数来源 | `lite-vr/litearm-vr-teleop/teleop/config/teleop.yaml`，2026-11-05 |
| translation_remap | `[[1,0,0],[0,0,1],[0,-1,0]]` |
| rotation_signs | `[1,-1,-1]` |
| base_link signs | `[-1,-1,1]` |
| scale | `1.0` |
| t_ee.tcp_offset_m | `[0,0,0]`（未标定） |
| MDH | 已由 URDF 反推，见 `docs/mdh.md`（源仓运行时不消费） |

## 依赖

- 头显客户端：`litearm-vr-headset`（Godot/OpenXR）
- teleop bridge：`lite-vr/litearm-vr-teleop`
- 本仓 `robot-litearm`

## 前置

1. 仿真中完成方向/缩放验证（验收第 13 项）；
2. 真机 `speed <= 0.2`，有人在急停位置；
3. 补齐 `t_ee` 并写回 `config/vr.example.yaml`（第 14 项；MDH 已记录）；
4. 未用上位机「关节方向检测」在真机确认机械方向前，不做仿真与真机同步。

## 验收判据

- 手柄前后/左右/上下 → 末端运动方向符合直觉；
- 姿态旋转无轴向反转、无奇异跳变；
- 缩放不过敏也不过慢；
- 真机动作满足安全速度、空间边界与急停要求。

## 记录

把每次验证的 rotation/scale/t_ee 与视频/日志路径写入 `docs/validation.md`
第 13、14 项。
