# 01 SDK Tests

不经过 Dora，直接调用厂商 SDK，用于验收清单第 3–5 项。

| 脚本 | 作用 | 会运动吗 |
|---|---|---|
| `read_state.py` | 读 7 轴位置/速度/力矩/温度/err | 否 |
| `move_single_joint.py` | 单关节小步进 | 仅 `--execute` |
| `gripper_open_close.py` | LiteGrip 开合 | 仅 `--execute` |
| `camera_read.py` | 外接相机取一帧（可选） | 否 |
| `safety_stop.py` | 验证 `disable()` 失能路径 | 仅 `--execute`，且需确认 |

## 前置

```bash
uv venv --python 3.12
uv pip install -e /path/to/litearm-python
uv pip install -e /path/to/litegrip-python
uv pip install -e ".[test]"     # 仓库根目录，脚本会用到 codec 里的限位
```

## 顺序

1. `read_state.py` —— 确认固件、关节数、err 全为 0。
2. `move_single_joint.py --joint N --delta 0.02` 先 dry-run，核对计划。
3. 确认环境无人、姿态有支撑后加 `--execute`。
4. `gripper_open_close.py` 同理，先 dry-run。
5. `safety_stop.py --execute` 验证失能；**执行前必须托住**。

## 安全底线

- 单次步进 ≤ 0.05 rad，速度 ≤ 0.2（脚本会拒绝超限）。
- 动作后默认失能，避免静止保持发热（台架经验：J6 长时保持会过温）。
- `disable()` 会失去保持力；`gripper.stop()` 会掉力矩。
- 未有支撑时不要执行任何失能动作。

## 真机证据记录

把每次验收的命令、输出和结论写进 `docs/validation.md` 对应的行，不要只勾选。
