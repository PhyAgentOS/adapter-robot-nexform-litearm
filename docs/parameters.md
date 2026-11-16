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
| 零位 | URDF/MJCF `q=0`；SDK `home()` 0x2A 回 `[0]*7` | 📌 | SDK 文档 + 厂商产品手册「图示」（零位/坐标系，`docs/vendor/litearm-docs/`）；2026-11-05 固件 FK 与 URDF FK 在实测 `q` 下吻合（§3.1），零位对拍见 §3.2 |
| 正方向 | 逐关节 `+1` | 📌 | 厂商产品手册：各关节绕 URDF 定义轴按右手定则确定正方向；同次 FK 对拍一致 |
| 固件软限位 | 逐关节值与 URDF 内缩 1° 一致 | ✅ | 2026-11-05 `Arm.params.all_joint_params()`，见 `joint_table.md` §2.1 |
| `following_error` 阈值 | J1–J2 0.35 / J3–J4 0.30 / J5–J7 0.25 rad | 📌 | 固件 `params/defaults.c` + `tools/PARAM_STATE.md`（1.10.5 源码）；1.11.0 无读回命令，未实机复核 |
| `speed` 归一化 → 实际角速度 | SDK 侧 0..1 | ⬜ | 未验证（验收不要求映射关系） |
| 未使能越限容差 | `POS_RECOVER_BAND = 0.30 rad`（1.10.0 为 0.05，1.10.1 起 0.30）；越界 ≤带宽不锁存，使能时受控回程 | 📌 | 已归档固件 1.10.5 `safety/safety_check.c:97`；1.11.0 同行为待源码核对 |

连接：USB CDC `1d50:606f`，`port: null` 时由 SDK 自动发现串口。

## 3. 固件

| 参数 | 值 | 状态 |
|---|---|---|
| 版本前缀 | `Litearm` | ✅ |
| 最低版本 | `1.5.0`（SDK 常量 `MIN_FW`） | ✅ |
| 实机版本 | `Litearm1.11.0-7J` | ✅ 2026-11-05 `Arm.firmware`；已归档参考源码 `Litearm1.10.5-7J`（`litearm-stm32` `6d4dd27`，2026-11-02），1.11.0 对应源码未归档 |

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
| `grasp_torque_threshold` | 0.5 Nm | ✅ | factory calibration；`is_grasped()` 判据（`\|τ\| > 0.5`） |
| 堵转判据 | 位置窗口：连续 5 次采样（每 50 ms）净位移 < `max(0.0015 rad, 0.2 × 应走距离)` | ✅ 实测 | litegrip `MotionConfig`；50 mm/s 下阈值 0.034 rad ≈ 2.50 mm |
| 行进段力矩保护 | 0.7 Nm × 3 次采样（≈7 N） | 📌 | `stop_torque_nm`；压紧段不适用，本次未触发 |
| 脱离力矩 | 0.2 Nm（≈2 N） | 📌 | `breakaway_nm`，2026-10-29 实测 |
| 闭合端稳态压力矩 | 0.211 Nm（SDK 力读数 2.11 N）；冲击峰值 0.818 Nm | ✅ 2026-11-05 实测 | `close()` 轨迹，见 §4.1 |
| `payload`（`set_payload`） | 估算 0.5772 kg，COM ≈ `[0, 0, +0.055]` m（法兰系） | 🟡 估算 | CAD（`gripper2.urdf`），未动态辨识，见 §4.2 |
| TCP 偏移 | `[-0.0071, -0.0239, 0.140]` m（法兰系） | ✅ | 见 `docs/validation.md` §t_ee 记录 |
| 标定文件 | `src/litegrip/factory_calibration.json`，md5 `1a9beb55f629a745568b44f31601a280` | ✅ | litegrip-python `v1.2.1` |
| 标定加载 | `load_calibration()` 无参 → factory；`LITEGRIP_CALIB` 可覆盖 | ✅ | SDK 源码 |
| 空闲状态读回 | 未使能时 `fresh=False`；使能后 `get_state(wait=True)` 正常 | ✅ | 2026-11-05 实测 |

### 4.1 堵转阈值实测（2026-11-05）

`can0`、factory calibration、空载（两指之间无物），`open()` → `close()`，20 Hz 记录
`MoveProgress`。证据 `validation_output/gripper_stall_check.json`。

| 项 | 实测 |
|---|---|
| 开合位置 | 开 80.03 mm；合到 0.22 mm（标定闭合零点内侧 0.22 mm） |
| 闭合用时 / 帧数 | 1.99 s / 370 帧（斜坡 + 0.3 s 保压） |
| 闭合稳态压力矩 | **0.211 Nm**（SDK `force_n` 读数 2.11 N） |
| 闭合冲击峰值 | **0.818 Nm**（压紧区单帧；该段不适用 0.7 Nm 行进段保护） |
| 堵转触发时窗口位移 | 0.0053 rad（0.39 mm） < 阈值 0.034 rad（2.50 mm） |
| `MoveResult` | `ok=True, stalled=True, reached=False, protected=False` |
| 张开端 | 静止力矩 0.01–0.03 Nm（无负载顶住） |

判据本身是**位置增量**，不是力矩阈值：每 50 ms 采一次位置，5 个采样的窗口净位移小于
`max(0.0015 rad, 0.2 × 窗口内应走距离)` 即判堵转。50 mm/s 时应走 12.5 mm，阈值
0.2 × 12.5 mm = 2.50 mm。配置里另有三个**力矩**量，但都不是堵转判据：行进段
力矩保护 0.7 Nm、`is_grasped()` 阈值 0.5 Nm、脱离力矩 0.2 Nm。

`grasp(force_n=5, hold_s=0.4)`：闭合到限位（`reached=True, stalled=False`），保力段
命令前馈 0.5 Nm；状态帧回读的力矩为 0.27 Nm 左右（回读滞后/滤波，2 s 长保力也只升到
0.30 Nm）。**定时 `grasp()` 返回后最后一帧纯力矩仍然生效**：紧接着 `open()` 会因
残余力矩尚未让位而在位置窗口判据下误报 `stalled=True`；先 `enable()`（重初始化）再
`open()` 即正常。空载测试不要依赖 `grasp()` 自己收力。

### 4.2 末端 payload（`set_payload`）估算（2026-11-05）

- 估算值：**质量 0.5772 kg**，质心 **≈ `[0, 0, +0.055]` m（法兰系）**（轴向 ±0.02 m，
  横向 ≈0）。来源 `litegrip-isaacsim/gripper2/gripper2.urdf` 的 inertial：base_link
  0.506299 kg + 两指各 0.035454 kg；质心按刚体质量加权，法兰安装面取 CAD 后缘
  `z ≈ -0.0641 m`。**不含**法兰转接板与螺钉。
- **未做动态辨识**：SDK 的差分法（`litearm.payload.identify`）要求先有一份**空载
  基线**，而夹爪已装在法兰上，无法再采空载；绝对法在本机不可用 —— 零位下 J1 实测
  `τ ≈ -0.85 Nm`，而该姿态重力绕 J1 的力矩恒为 0，说明静态偏置/摩擦远大于可辨识信号
  （与 `payload.py` 里 0.36 kg 被辨成 1.92 kg 的历史一致）。
- 因此该值只作为 `set_payload` 的**工程估算**，未写入固件（当前固件 `payload_mass=0`）。
  要做实数：称重得质量；或拆下夹爪采空载基线后跑差分辨识。
- 证据 `validation_output/payload_check.json`。

## 5. VR 遥操

参数详见 `config/vr.example.yaml`。

| 参数 | 值 | 状态 | 说明 |
|---|---|---|---|
| MDH | 见 `docs/mdh.md` | ✅ | 厂商未提供；由 `assets/urdf/litearm.urdf` 反推，`scripts/urdf_to_mdh.py` 生成，500 组随机 q 与 URDF FK 对拍位置误差 <2e-11 m。运行时仍走 URDF + IK，不消费该表 |
| rotation 映射 | `axis_remap` / `translation_remap` / `rotation_signs` | 📌 | 来源 `lite-vr`，2026-11-05 抓取 |
| scale | translation 1.0 / rotation 1.0 | ✅ | 同上 |
| `t_ee` | `[-0.0071, -0.0239, 0.140]` m（法兰系 ee_link） | ✅ | 2026-10-27/28 handeye 实测：横向 `tool_offset_xy_m`（两指中点对准目标读 TCP）+ 轴向 `tool_pad_offset_m=0.140`（指尖 0.160）。语义 `p_tool = p_ee + R_ee·xyz`。2026-11-05 只读复核 `get_tool_tcp` 与上式差 0（`validation_output/tee_check.json`） |

## 6. 阶段一待读清单

- [x] `Arm.firmware` 实际版本：`Litearm1.11.0-7J`
- [x] 逐关节固件软限位：`arm.params.all_joint_params()`，2026-11-05
- [ ] `following_error` 阈值：SDK 无读回命令，暂用固件源码值（见 §2）
- [x] `home()` 前/后的 `q` 回读（零位对照）：2026-11-05 在零位附近执行，前后 7 轴 `q` 完全一致（`max|Δ|=0`），`flags=[]`、`joint_fault=0`、`err=1`
- [x] 夹爪 `position_mm` / `force_n` / 温度 / `error_code`：2026-11-05 `enable()` 后实测，见 §4.1

## 7. 适配器参数与控制面

适配器自有参数（不是机械臂或夹爪参数）：

| 参数 | 默认 | 约束 | 说明 |
|---|---|---|---|
| `speed` | `0.2` | `0..1` | 下发目标时的默认 SDK 速度倍率 |
| `home_timeout_s` | `180.0` | `> 0` | `control` 的 `home` 命令超时；超时后回执 `error`，驱动仍以实测角度恢复目标 |
| `enable_on_connect` | `true` | — | 连接后调用 `enable()` |
| `move_to_initial` | `true` | — | 连接后把首目标设为初始姿态 |

### 7.1 `action` 的 `speed` 列（扩展）

标准 `JointCommand` 的 `velocity` 单位是 rad/s，SDK `movej_sync(speed=...)`
使用 0..1 归一化系数，映射关系未验证（§2）。因此速度透传不使用
`velocity`，而是在标准六列之外追加一个可选 `float64` 列 `speed`：

| 输入 | 行为 |
|---|---|
| 列不存在 | 使用 `config.speed` |
| `0 <= speed <= 1` | 作为本次目标的 SDK 速度倍率 |
| `speed > 1` | 截断为 `1.0` |
| 负数 / `NaN` / `inf` | 记录警告，回退到 `config.speed` |

Forge 标准校验默认允许额外列（`strict_extra_columns=False`），只发标准
`JointCommand` 的节点不受影响。

### 7.2 `control` 命令

端口 `control`，消息 `ControlRequest`（列 `command`、`request_id`、
`timeout_s`，单行）。节点回执 `control_status`（列 `command`、`request_id`、
`status`、`message`），`status` 取值 `accepted` / `done` / `rejected` / `error`。

`control_status` 也用于上报被拒绝的 `action` / `master_state`：这些回执的
`command` 为输入端口名、`status` 为 `rejected`、`request_id` 为空（没有可回显
的 ID）。它们与 `control` 命令共用同一队列，因此只保证可观测，不提供逐条
请求关联。

节点声明 `robot_status` 输出时，每次 `tick` 还发布固件状态（列 `enabled`、
`mode`、`faulted`、`faults`、`joint_fault`、`command_error`）。`command_error`
非空表示后台 `movej_sync` 最近一次执行失败（如超时），上报一次后清空；
收到后应视为目标可能未到达，按 `state` 的实际位置重新规划。

| 命令 | SDK 调用 | 执行方式 | 说明 |
|---|---|---|---|
| `enable` | `enable()` | 队列 | 恢复使能并重建运动 worker |
| `disable` | `disable()` | 内联 | 取消排队目标后失能 |
| `reset` | `reset()` | 队列 | 清除 `EMERGENCY` / 故障锁存 |
| `home` | `home(timeout=home_timeout_s)` | 队列 | 整臂回零；期间取消后台 worker |
| `stop` | 以实测角度 `movej_sync` | 队列 | 取消排队目标，保持当前位置，保持使能 |
| `emergency_stop` | `emergency_stop()`（CMD 0x12） | 内联 | 立即急停；固件锁存 `EMERGENCY` + 故障位 |

`disable` 与 `emergency_stop` 在事件循环内同步执行，不会被队列里前面的
`home` 阻塞。队列容量 1，忙时普通命令回执 `rejected`。`emergency_stop`
造成的锁存只能用 `reset()` 清除，`disable()` 无效（固件行为，见
`docs/validation.md`）。`stop` 的前提是驱动已使能；未使能时回执 `error`。

### 7.3 `forge_bridge`（TCP/JSON）

`robot-litearm-bridge` 把上面的端口包装成一行一个 JSON 的 TCP 服务，
协议与消息格式见 [`docs/bridge.md`](bridge.md)。

| CLI | 默认 | 说明 |
|---|---|---|
| `--host` | `127.0.0.1` | 监听地址；非回环会告警，协议无鉴权 |
| `--port` | `9005` | TCP 端口 |
| `--state-timeout` | `0.5` | `state` 的 `valid` 年龄上限，秒 |
| `--settle-tol` | `0.01` | `movej` 到位容差，rad |
| `--settle-timeout` | `20.0` | `movej` 默认等待上限，秒 |
| `--control-timeout` | `10.0` | 非 `home` 控制命令回执超时，秒 |
| `--home-timeout` | `180.0` | `home` 缺省超时，秒 |

`movej` 的 `speed` 列与控制面命令的语义沿用 §7.1/§7.2；桥额外要求
`movej` 在容差内到位才算 `ok`。默认只绑定回环地址，跨机部署需显式
`--host 0.0.0.0` 并自行加访问控制。

## 8. 变更记录

| 日期 | 变更 |
|---|---|
| 2026-11-06 | 新增 §7.3 `forge_bridge` TCP/JSON 接口参数与默认端口 9005 |
| 2026-11-05 | 建立本表；录入 SDK 版本、固件最低版本、夹爪标定与总线参数 |
| 2026-11-06 | 新增 §7 适配器参数：`home_timeout_s`、`action` 的 `speed` 扩展列、六个 `control` 命令 |
| 2026-11-05 | 由 URDF 反推 MDH 并完成随机 FK 对拍（`docs/mdh.md`）；MDH 状态改为已确认 |
| 2026-11-05 | 真机只读：固件 1.11.0-7J、软限位、`kp/kd/tau_max`、静止 `q`；J4/J5 越软限位定位为未使能自然平衡点（`POS_RECOVER_BAND`） |
| 2026-11-05 | 归档固件参考源码 `Litearm1.10.5-7J`（`6d4dd27`）；按该源码更正 `POS_RECOVER_BAND` 为 0.30 rad（1.10.0 为 0.05） |
| 2026-11-05 | 夹爪堵转阈值实测（位置窗口判据，0.034 rad / 2.50 mm；闭合稳态 0.211 Nm）；payload 记为 CAD 估算 0.5772 kg（未动态辨识、未写固件） |
| 2026-11-05 | 归档厂商产品/开发手册 V1.0.4（`litearm-docs` `483b825`）到 `docs/vendor/litearm-docs/`；零位/正方向补厂商书面表述 |
