# forge_bridge：TCP/JSON 接口

`src/litearm_robot/bridge.py` 把机器人节点包装成一行一个 JSON 的 TCP 服务，
供 Forge Skill Gateway、`nc` 或非 Python 调用方使用。桥不导入 LiteArm SDK，
只负责 Dora 端口与 JSON 之间的转换；运动与状态仍由 `robot-litearm` 节点执行。

## 拓扑与线程模型

```text
TCP 客户端 ──JSON──> bridge 节点 ──action/control──> robot 节点 ──> 机械臂
          <──JSON──           <──state/robot_status/control_status──
```

- Dora 事件循环线程是唯一调用 `node.send_output` 的线程。
- 每条 TCP 连接由一个 daemon 线程服务；请求线程只把待发消息放进 outbox，
  事件循环在每次事件后 `pump` 出去。
- `movej` 的到位判断依赖持续到达的 `state`。dataflow 必须给 robot 节点保留
  `tick`（示例为 20 ms）；没有 tick 时桥只能确认“已取走 action”，等待会超时。

## 启动

```yaml
nodes:
  - id: robot
    path: python
    args: "-u -m litearm_robot.main run --fake"
    inputs:
      tick: dora/timer/millis/20
      action: bridge/action
      control: bridge/control
    outputs: [state, robot_status, control_status]

  - id: bridge
    path: python
    args: "-u -m litearm_robot.bridge --port 9005"
    inputs:
      state: robot/state
      robot_status: robot/robot_status
      control_status: robot/control_status
    outputs: [action, control]
```

完整示例见 [`examples/04_forge_bridge/`](../examples/04_forge_bridge/)。
安装本包后也可直接使用入口 `robot-litearm-bridge`。夹爪开口上限通过
`--max-opening-m` 配置，应与 robot 节点的 `gripper.max_opening_m` 相同。

## 协议

请求与响应都是单行 JSON（NDJSON）。响应总是包含 `cmd`；若请求带 `id` 或
`request_id`，响应原样回显到 `id`。`ok` 表示协议层是否成功，细节见下节。

### 只读

| 请求 | 响应字段 |
|---|---|
| `{"cmd":"state"}` 或 `{"cmd":"status"}` | `ok`、`valid`、`q`（7 轴 rad）、`gripper_m`、`age_s`，以及缓存的 `enabled`、`mode`、`faulted`、`faults`、`joint_fault` |
| `{"cmd":"ping"}` | `ok`、`pong` |

`valid` 表示最近一帧 `state` 的年龄不超过 `--state-timeout`（默认 0.5 s）。
状态过期时仍返回最后一次的 `q`，但 `valid:false`；从未收到状态时 `q` 为 `null`。

`state` 始终包含 `joint_order` 里的全部关节。夹爪未启用或读不到时，`gripper_m`
为 `null`（节点侧用 `NaN` 占位，桥在输出前转成 `null`）；`q` 不受影响。

### 运动

| 请求 | 响应 |
|---|---|
| `{"cmd":"movej","q":[7 floats],"speed":0.2,"timeout_s":20,"wait":true}` | `ok`、`settled`、`elapsed_s`、`target_q`、`clipped`、`speed` |
| `{"cmd":"gripper","opening_m":0.05}` | `ok`、`opening_m`、`clipped`、`max_opening_m` |

- `q` 必须恰好 7 个数；超出 URDF 限位的分量会夹到边界，`clipped:true`。
- `speed` 是 0..1 的 SDK 倍率；负数拒绝，`>1` 截断为 1。
- 默认 `wait:true`：命令下发后轮询新鲜 `state`，所有关节进入
  `--settle-tol`（默认 0.01 rad）才返回 `settled:true`；超过
  `--settle-timeout`（默认 20 s，可由 `timeout_s` 覆盖）返回
  `ok:false`、`settled:false`。命令之后才到达的状态才算数，旧状态不会掩盖
  仍在进行的运动。
- `gripper` 的 `opening_m` 是两指总开口，范围 0..`max_opening_m`，超出即
  夹到边界。桥的 `--max-opening-m`（默认 0.080 m）应与 robot 配置的
  `gripper.max_opening_m` 保持一致，否则桥侧裁剪与驱动侧裁剪会不同。
- `movej`/`gripper` 的 `ok` 只保证 action 已被 Dora 取走；机器人节点仍可能
  因配置或驱动状态拒绝（例如夹爪未启用），目前没有 action 级回执。

### 控制面

`home`、`stop`、`enable`、`disable`、`reset`、`estop`（等价
`emergency_stop`）映射到 `control` 端口。桥为每个请求生成内部
`request_id`，在 `control_status` 中等待终态。

| 请求 | 说明 |
|---|---|
| `{"cmd":"home","timeout_s":120}` | 缺省超时取 `--home-timeout`（180 s）；等待时间额外留 5 s 余量 |
| `{"cmd":"stop"}` / `enable` / `disable` / `reset` | 等待时间取 `--control-timeout`（10 s） |
| `{"cmd":"estop"}` | 立即急停并锁存；恢复必须先 `reset` 再 `enable` |

响应为 `ok`、`status`（`done`/`rejected`/`error`/`timeout`）、`message`、
`command`（归一化后的命令名）。`accepted` 只是排队回执，不会提前结束等待。
超时返回 `ok:false`、`status:"timeout"`，桥不再跟踪该 `request_id`。

### 错误

JSON 解析失败、非对象请求、未知命令、参数不合法都返回
`{"ok":false,"error":"..."}`。单行长度超过 64 KiB 时服务端回一条错误并断开。
每个请求的异常都被转换成 JSON，不会让连接线程崩溃。

## 参数

| CLI | 默认 | 说明 |
|---|---|---|
| `--host` | `127.0.0.1` | 监听地址；非回环地址会记录警告 |
| `--port` | `9005` | TCP 端口 |
| `--state-timeout` | `0.5` | `valid` 判定的状态年龄上限，秒 |
| `--settle-tol` | `0.01` | `movej` 到位容差，rad |
| `--settle-timeout` | `20.0` | `movej` 默认等待上限，秒 |
| `--control-timeout` | `10.0` | 非 `home` 控制命令的回执超时，秒 |
| `--home-timeout` | `180.0` | `home` 缺省超时，秒 |
| `--debug` | 关 | 输出 DEBUG 日志 |

`BridgeOptions` 还包含 `dispatch_timeout`（默认 2 s，等待事件循环取走
action/control）和 `poll_period`（默认 0.02 s，到位轮询间隔），目前只供
测试与库内使用，未暴露为 CLI。

## 安全与限制

- 协议**没有鉴权**，默认只绑定 `127.0.0.1`。跨机部署必须放在可信网络或
  外层加访问控制。
- 多个客户端可同时连接；`movej`/`gripper` 不做互斥，同一时刻的并发运动
  由机器人节点“合并最新目标”的语义决定。耗时控制命令由节点侧容量为 1 的
  队列串行执行，忙时回执 `rejected`。
- 当前只支持位置命令；没有轨迹流、力矩/MIT 模式、IK 或视觉接口。
- `home` 会让整臂回零，`estop` 会让臂失去保持力；调用前确认周围无人、
  姿态有支撑。
- fake 驱动的夹爪是 `NullGripper`，`gripper` 请求会在机器人节点侧被拒绝，
  但桥只能看到“已下发”。该限制在真机 `gripper.enabled: true` 时不存在。
