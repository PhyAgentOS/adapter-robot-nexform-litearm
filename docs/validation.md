# 验收清单（接入标准 §12）

复制自 `Robot接入手册.md`，逐条记录证据。**未执行的项不要勾选。**

| # | 验收项 | 状态 | 证据 |
|---|---|---|---|
| 1 | 厂商资料和资产文件已归档 | 部分 | 资产齐全（URDF/MJCF/GLB/mesh，`assets/`）；厂商原始手册未归档，接口摘要见 `docs/hardware.md` |
| 2 | joint 数量/名称/顺序/单位/限位/零位/正方向已记录 | 部分 | `docs/joint_table.md`；零位/方向待确认 |
| 3 | SDK 最小测试可读取状态 | 待执行 | `examples/01_sdk_tests/read_state.py` |
| 4 | SDK 最小测试可安全下发单关节动作 | 待执行 | `examples/01_sdk_tests/move_single_joint.py` |
| 5 | 末端执行器可控制 | 待执行 | `examples/01_sdk_tests/gripper_open_close.py` |
| 6 | 仿真模型可加载，joint 顺序和运动方向正确 | 待执行 | `examples/03_workflows/sim_basic_motion/` |
| 7 | 仿真中所有 joint 完成最小/最大/归零 | 待执行 | 需 sweep 记录 |
| 8 | 真机中所有 joint 完成安全范围内最小/最大/归零 | 待执行 | 需用户逐次批准，记录 CSV/JSONL |
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

## 已知阻塞项

1. 固件零位/正方向/软限位未书面确认（阶段 1/2）。
2. `t_ee`、夹爪 payload/堵转阈值未实测（阶段 3）。
3. 真机 sweep 需要单独的安全窗口与批准。
