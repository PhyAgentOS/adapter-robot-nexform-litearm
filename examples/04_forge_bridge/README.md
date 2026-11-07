# 04 Forge Bridge

把机器人节点包装成 TCP/JSON 接口，供 Forge Skill Gateway、`nc` 或其它
非 Python 调用方使用。桥接节点不导入 LiteArm SDK，只做 Dora 端口
（`state`/`robot_status`/`control_status` ↔ `action`/`control`）与 JSON
协议之间的转换。

## 节点

| 节点 | 角色 | 端口 |
|---|---|---|
| `robot` | 机器人节点（`litearm_robot.main run`） | 输入 `tick`、`action`、`control`；输出 `state`、`robot_status`、`control_status` |
| `bridge` | `litearm_robot.bridge`，监听 TCP NDJSON | 输入 `state`、`robot_status`、`control_status`；输出 `action`、`control` |

Dora 事件循环线程是唯一调用 `node.send_output` 的线程；TCP 客户端线程只把
消息放进 outbox，由每个 `state` tick（20 ms）后的 `pump` 发出。因此 dataflow
必须给 `robot` 保留 `tick`，否则桥接节点的下发会一直等不到事件循环。

## 运行（fake，无硬件）

```bash
cd examples/04_forge_bridge
PATH="$PWD/../../.venv/bin:$HOME/.dora/bin:$PATH" dora run dataflow.bridge.yaml

# 另开终端
../../.venv/bin/python bridge_client.py
```

`bridge_client.py` 不带参数进入交互式 REPL；也可以单条执行：

```bash
../../.venv/bin/python bridge_client.py ping
../../.venv/bin/python bridge_client.py state
../../.venv/bin/python bridge_client.py movej 0.1 0.1 0.1 0 0.1 0.1 0.1 --speed 0.2
../../.venv/bin/python bridge_client.py gripper 0.05
../../.venv/bin/python bridge_client.py home 30
../../.venv/bin/python bridge_client.py estop
```

REPL 里 `movej` 还支持 `speed=0.2`、`timeout=10`、`nowait` 后缀，例如：

```
bridge> movej 0 0 0 0 0 0 0 speed=0.2 timeout=10
```

所有响应都是单行 JSON；`movej` 默认等到所有关节进入 0.01 rad 容差才返回
`settled: true`，`nowait`/`wait:false` 才只回显下发结果。

## 协议

| 请求 | 说明 |
|---|---|
| `{"cmd":"state"}` / `{"cmd":"status"}` | 只读；返回 `q`（7 轴，rad）、`gripper_m`、`age_s`、`valid` 和机器人状态 |
| `{"cmd":"movej","q":[7],"speed":0.2,"timeout_s":20,"wait":true}` | 位置命令；`speed` 为 0..1 倍率，`wait=false` 立即返回 |
| `{"cmd":"gripper","opening_m":0.05}` | 两指总开口，自动夹到 0..0.080 m |
| `{"cmd":"home","timeout_s":180}` | 固件回零，等待 `control_status` 终态 |
| `{"cmd":"stop"}` / `enable` / `disable` / `reset` | 映射到 `control` 命令 |
| `{"cmd":"estop"}` | 等价 `emergency_stop`；锁存后需 `reset` |
| `{"cmd":"ping"}` | 连通性检查 |

任何请求都可以带 `id`（或 `request_id`），响应原样回显。`ok` 表示协议层
是否成功执行：对 `movej` 还要求到位；对 `control` 类命令要求回执
`done`。超时返回 `ok:false` 与 `status:"timeout"`。

## 真机

1. 先完成 `examples/01_sdk_tests` 的只读检查。
2. 把 `dataflow.bridge.yaml` 中 `robot.args` 的 `--fake` 去掉，改成
   `"-u -m litearm_robot.main run --config ../../config/robot.yaml"`。
3. 确认周围无人、姿态有支撑后再调用 `home`/`movej`；`home` 默认 180 s 超时。
4. 桥接默认只绑定 `127.0.0.1`。协议没有鉴权，确实需要跨机访问时显式
   `--host 0.0.0.0`，并限制在可信网络内。

## fake 模式限制

fake 驱动使用 `NullGripper`，`gripper` 命令虽然会被 TCP 层接受并 `ok:true`
（因为它只保证“已下发到 Dora”），机器人节点会记录
`拒绝 action: gripper is disabled in config`。夹爪的真实行为需要真机配置
`gripper.enabled: true` 或 `examples/02_dora_tests` 的夹爪验证。
