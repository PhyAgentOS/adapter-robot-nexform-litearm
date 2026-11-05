# 02 Dora Tests

验证单节点启停、`state` 发布、`action` 订阅、动作下发（验收清单第 10 项）。

## 节点

| 节点 | 角色 | 端口 |
|---|---|---|
| `robot` | 标准 runner 包装 `LitearmDriver` | 输入 `tick`、`action`；输出 `state` |
| `action_source` | 收到状态后发一次 sparse `JointCommand` | 输入 `tick`、`state`；输出 `action` |
| `state_print` | 慢速打印状态 | 输入 `state` |

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

## 运行（真机）

1. 先完成 `examples/01_sdk_tests` 的只读检查。
2. 复制 `config/robot.example.yaml` → `config/robot.yaml`，`speed <= 0.2`。
3. 把 `dataflow.yaml` 中 `robot` 的 `args` 改为：

   ```yaml
   args: "-u -m litearm_robot.main run --config ../../config/robot.yaml"
   ```

   dora-cli 0.4.1 要求 `args` 是字符串；写成 YAML 列表会报
   `invalid type: sequence, expected a string`。

4. 确认周围无人、姿态有支撑后再运行；`action_source --delta` 保持 ≤ 0.05。

## 说明

- `action` 是 **sparse** 命令：只更新 `name` 里列出的关节，其余关节保持上一目标。
- 标准 runner 在退出时会调用 `driver.disconnect()`；驱动里的 `disconnect()` 幂等。
- 本交付包不含相机，`camera_topic_test` 不提供；如需相机请接 `operator-*` 的相机节点，
  或先用 `examples/01_sdk_tests/camera_read.py` 验证取流。
