# 02 Dora Tests

验证单节点启停、`state` 发布、`action` 订阅、动作下发、控制面命令
（验收清单第 10 项 + 控制面扩展）。

## 节点

| 节点 | 角色 | 端口 |
|---|---|---|
| `robot` | 自定义节点循环（`litearm_robot/node.py`）包装 `LitearmDriver` | 输入 `tick`、`action`、`control`；输出 `state`、`robot_status`、`control_status` |
| `action_source` | 收到状态后发一次 sparse `JointCommand`，可选带 `speed` 列 | 输入 `tick`、`state`；输出 `action` |
| `control_source` | 按顺序发 `control` 命令并打印回执 | 输入 `tick`、`control_status`；输出 `control` |
| `state_print` | 慢速打印关节状态与机器人状态 | 输入 `state`、`robot_status` |

`robot` 不再使用 `forge_robot.node_runner.run_dora_robot_node`，因为标准 runner
没有扩展输入入口；`node.py` 复刻了标准语义（`tick` → `state`、`action` →
`JointCommand`、`master_state`、`is_follower` 门控、`STOP`/`ERROR` 收尾），并新增
`control` 输入。复刻基线与全部有意差异见 `node.py` 模块 docstring。
`robot_status`、`control_status` 是扩展输出：只有 dataflow 里声明了才会发送，
未声明时回执写入日志，不会触发 dora 的 "Ignoring output" 警告。

## 运行（fake，无硬件）

```bash
# Python 3.12 环境，已安装本包与 forge stable/1.x
cd examples/02_dora_tests
PATH=$HOME/.dora/bin:$PATH dora run dataflow.yaml
```

预期：
- `state_print` 每秒打印一行 7 轴角度；
- `action_source` 在启动约 2 s 后打印 `sent joint7 -> ...`，只发一次；
- fake 驱动下 `joint7` 目标更新为 +0.05 rad。

控制面 dataflow：

```bash
PATH=$HOME/.dora/bin:$PATH dora run dataflow.control.yaml
```

`control_source` 依次发 `enable` → `home` → `disable`（间隔 1 s），预期：

- `control_source` 打印 `status enable accepted`、`status home accepted`、
  `status home done`、`status disable done`；
- `state_print` 的 `status` 行从 `enabled=True` 变为 `enabled=False`；
- 全程 `faulted=False`。

## `action` 的 `speed` 列

`JointCommand` 的 `velocity` 是 rad/s，而 SDK `movej_sync(speed=...)` 用的是
0..1 归一化系数，两者映射未验证（`docs/parameters.md` §2）。因此本适配器
不借用 `velocity`，而是在标准 `JointCommand` 六列之外追加一个可选的
`float64` 列 `speed`：

- 缺省：使用 `config.speed`；
- `0..1`：SDK 速度倍率，作为该次目标的 `movej_sync(speed=...)`；
- `>1`：截断到 `1.0`；负数、`NaN`、`inf` 记录警告后回退到 `config.speed`。

`action_source.py --speed 0.5` 会在下发前追加该列。扩展列不影响
Forge 标准校验（`strict_extra_columns=False`），只用标准 `JointCommand`
的节点不会看到它。

## 控制面命令

| 命令 | 语义 | 阻塞 |
|---|---|---|
| `enable` | 调用 SDK `enable()`，恢复使能并重建后台运动 worker | 否（队列） |
| `disable` | 取消排队目标，调用 `disable()` | 是（立即） |
| `reset` | 调用 `reset()`，清除 `EMERGENCY`/故障锁存 | 否（队列） |
| `home` | 整臂回零（`home(timeout=...)`），期间取消后台 worker | 否（队列，默认 180 s 超时） |
| `stop` | 取消排队目标，以当前实测角度保持位置，保持使能 | 否（队列） |
| `emergency_stop` | 取消排队目标，调用固件 `emergency_stop()`（CMD 0x12） | 是（立即） |

`emergency_stop` 会让固件进入 `EMERGENCY` 并置故障位，只能通过 `reset()`
恢复，再 `enable()`；`disable()` 不会清掉该锁存。`disable` 与
`emergency_stop` 在事件循环里同步执行，保证急停不被前面的 `home` 挡住。
其余命令进入容量为 1 的队列；队列忙时新的普通命令回执 `rejected`。

## 运行（真机）

1. 先完成 `examples/01_sdk_tests` 的只读检查。
2. 复制 `config/robot.example.yaml` → `config/robot.yaml`（已被 `.gitignore` 忽略），
   `speed <= 0.2`；验收时可用 `move_to_initial: false` 避免上电大范围回位。
3. 运行真机版 dataflow（`args` 为字符串，dora-cli 0.4.1 不接受 YAML 列表）：

   ```bash
   PATH="$PWD/../../.venv/bin:$HOME/.dora/bin:$PATH" dora run dataflow.real.yaml
   ```

4. 确认周围无人、姿态有支撑后再运行；`action_source --delta` 保持 ≤ 0.05。
5. 真机跑控制面需把 `dataflow.control.yaml` 里 `robot.args` 的 `--fake` 去掉
   （其余不变），同样先完成第 1–4 步。`home` 会让整臂回零，务必确认周围无人、
   姿态有支撑；`home_timeout_s` 默认 180 s。真机控制面尚未在本仓验证，
   结果见 `docs/validation.md`「控制面（fake 驱动）」。

2026-11-05 真机结果：`speed=0.1`，`joint7 +0.05` 一次，状态从 `+0.000` 更新到 `+0.050`，
`sent=1`、`received=1455`，退出时正常 disconnect。

## 说明

- `action` 是 **sparse** 命令：只更新 `name` 里列出的关节，其余关节保持上一目标。
- `main._run_node` 在 `run_node` 返回后调用 `driver.disconnect()`；驱动里的
  `disconnect()` 幂等，因此正常 `STOP` 与异常退出都能收尾。
- 本交付包不含相机，`camera_topic_test` 不提供；如需相机请接 `operator-*` 的相机节点，
  或先用 `examples/01_sdk_tests/camera_read.py` 验证取流。
- 夹爪（end effector）不单独建 Dora 节点：标准 runner 已转发 `JointCommand(gripper, m)`，
  第 5 项用同一驱动接口验证过 0.080/0.000/0.080 m 往返；真机 Dora 若只是验证夹爪，
  可用 `action_source.py` 的 `JointCommand` 端口直接下发。
