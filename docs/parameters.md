# LiteArm 参数总表（单一真源）

本文件记录接入所需的全部参数。新增/修改参数先改这里，再同步到
`config/*.example.yaml`、`docs/joint_table.md` 和 `docs/hardware.md`。

状态标记：

- ✅ 已确认（有可核实的来源）
- 📌 已记录（来源明确，本仓尚未复验）
- ⬜ 待真机读取/确认
- ❌ 缺失

## 1. 软件版本

| 组件 | 版本 | 日期 | 备注 |
|---|---|---|---|
| litearm-python | `v1.3.0` = `5f75768`，`__version__` 2.1.0 | 2026-10-28 | `nexform-tech/litearm-python`；含 `set_tcp_offset` / `set_payload` |
| litegrip-python | `v1.2.1` = `4ce8482` | 2026-10-30 | `nexform-tech/litegrip-python` |
| Forge | stable/1.x：`dora-rs==0.4.1`、`forge-msgs>=1.0,<2`、`forge-robot>=1.0,<2` | — | Python >= 3.12 |

> 本机存在同版本号的旧拷贝（gitee `master` `db30a9e`、`main` `ca6aa1e`），
> 不含 `set_tcp_offset`。安装时必须以 §1 的 tag 为准，不要混用。

## 2. 机械臂

| 参数 | 值 | 状态 | 来源 |
|---|---|---|---|
| 关节数/名称/顺序 | 7 轴，`joint1` … `joint7` | ✅ | URDF / MJCF / SDK |
| 单位 | rad | ✅ | URDF / MJCF `angle="radian"` |
| 限位 | 见 `docs/joint_table.md` | ✅ | URDF = MJCF（2026-11-05 起） |
| 速度上限（标称） | 1 rad/s（全关节） | 📌 | URDF `velocity="1"` |
| 零位 | URDF/MJCF `q=0`；SDK `home()` 0x2A 回 `[0]*7` | 📌 | SDK 文档 |
| 正方向 | 逐关节 `+1`（待真机逐关节确认） | ⬜ | 阶段 2：上位机方向检测 |
| 固件软限位 | 固件实际 clamp 值 | ⬜ | 阶段 1：参数读回 |
| `following_error` 阈值 | — | ⬜ | 阶段 1：参数读回 |
| `speed` 归一化 → 实际角速度 | SDK 侧 0..1 | ⬜ | 阶段 2：实测 |

连接：USB CDC `1d50:606f`，`port: null` 时由 SDK 自动发现串口。

## 3. 固件

| 参数 | 值 | 状态 |
|---|---|---|
| 版本前缀 | `Litearm` | ✅ |
| 最低版本 | `1.5.0`（SDK 常量 `MIN_FW`） | ✅ |
| 实机版本 | — | ⬜ 阶段 1（`Arm.firmware`） |

## 4. 夹爪（LiteGrip）

| 参数 | 值 | 状态 | 来源 |
|---|---|---|---|
| 电机 | DM4310 | ✅ | factory calibration |
| 总线 | `can0`，**1 Mbit/s** | ✅ | litegrip-python README |
| `can_id` / `mst_id` | `0x08` / `0x18` | ✅ | factory calibration |
| 开口语义 | `position_mm` 0 = 闭合，+80 = 张开 | ✅ | SDK `get_state()` |
| 安装方向 | 由 `close_sign` + `calibration_normal/reverse` 处理 | ✅ | SDK `load_calibration()` |
| 工作行程 | 80.0 mm | ✅ | factory calibration |
| `rad_to_mm` | 73.45731105242119 | ✅ | factory calibration |
| 零点 / 最大位置 | 0.029564 / -1.141184 rad | ✅ | factory calibration |
| 行程范围 | 1.170748 rad | ✅ | factory calibration |
| `kp` / `kd` | 100.0 / 2.0 | ✅ | factory calibration |
| `grasp_torque_threshold` | 0.5 Nm | 📌 | factory calibration；适配器尚未暴露 |
| 标定文件 | `src/litegrip/factory_calibration.json`，md5 `1a9beb55f629a745568b44f31601a280` | ✅ | litegrip-python `v1.2.1` |
| 标定加载 | `load_calibration()` 无参 → factory；`LITEGRIP_CALIB` 可覆盖 | ✅ | SDK 源码 |
| TCP 偏移 / `payload` | — | ⬜ | 阶段 3 |

## 5. VR 遥操

参数详见 `config/vr.example.yaml`。

| 参数 | 值 | 状态 | 说明 |
|---|---|---|---|
| MDH | 见 `docs/mdh.md` | ✅ | 厂商未提供；由 `assets/urdf/litearm.urdf` 反推，`scripts/urdf_to_mdh.py` 生成，500 组随机 q 与 URDF FK 对拍位置误差 <2e-11 m。运行时仍走 URDF + IK，不消费该表 |
| rotation 映射 | `axis_remap` / `translation_remap` / `rotation_signs` | 📌 | 来源 `lite-vr`，2026-11-05 抓取 |
| scale | translation 1.0 / rotation 1.0 | ✅ | 同上 |
| `t_ee` | `[0, 0, 0]` | ⬜ | 阶段 3：法兰 → 夹爪夹持点实测 |

## 6. 阶段 1 待读清单

- [ ] `Arm.firmware` 实际版本
- [ ] 逐关节固件软限位
- [ ] `following_error` 阈值
- [ ] `home()` 前/后的 `q` 回读（零位对照）
- [ ] 夹爪 `position_mm` / `force_n` / 温度 / `error_code`

## 7. 变更记录

| 日期 | 变更 |
|---|---|
| 2026-11-05 | 建立本表；录入 SDK 版本、固件最低版本、夹爪标定与总线参数 |
| 2026-11-05 | 由 URDF 反推 MDH 并完成随机 FK 对拍（`docs/mdh.md`）；MDH 状态改为已确认 |
