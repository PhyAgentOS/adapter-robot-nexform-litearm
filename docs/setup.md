本页说明如何安装并验证 LiteArm 接入包，适用于首次部署的开发者。

# 安装与自检

## 前置

- Python 3.12（`forge-robot` stable/1.x 的硬要求）。
- [`uv`](https://docs.astral.sh/uv/)。
- 真机连接：USB CDC `1d50:606f`；夹爪走 SocketCAN `can0`（1 Mbit/s）。

## 1. 安装 SDK 与本包

在仓库根目录执行，`/path/to/*` 换成本机 clone 路径：

```bash
uv venv --python 3.12
uv pip install -e /path/to/litearm-python      # v1.3.0
uv pip install -e /path/to/litegrip-python     # v1.2.1
uv pip install -e ".[test]"
```

版本必须与 [`parameters.md` §1](parameters.md) 一致；同版本号的旧拷贝不含
`set_tcp_offset`，不要混用。

## 2. 配置

```bash
cp config/robot.example.yaml config/robot.yaml
```

按现场修改 `config/robot.yaml`。`port: null` 表示由 SDK 自动发现串口。

## 3. 验证

无硬件自检：

```bash
env -u PYTHONPATH python scripts/validate_assets.py      # 资产/关节/网格一致性
env -u PYTHONPATH python scripts/urdf_to_mdh.py --check  # URDF 反推 MDH + FK 对拍
env -u PYTHONPATH python -m pytest -q                    # codec/config；driver 用例自动跳过
env -u PYTHONPATH robot-litearm probe --fake             # 需已装 forge-msgs / forge-robot
```

预期：脚本退出码为 0，pytest 全部通过（无硬件时 driver 用例跳过）。

真机只读探针（不做运动）：

```bash
robot-litearm probe --config config/robot.yaml
```

## 故障排查

**pytest 插件加载失败或 Python 版本混乱**

当前 shell 若已 source ROS 2，`PYTHONPATH` 会包含 Python 3.10 的 site-packages，
污染 Python 3.12。所有命令前加 `env -u PYTHONPATH`。

**`probe --fake` 报缺少模块**

先安装 Forge 依赖：`uv pip install -e ".[test]"` 会带入 `forge-msgs` /
`forge-robot`；仍失败时核对 [`parameters.md` §1](parameters.md) 的版本区间。

**真机找不到串口**

确认 USB CDC 设备存在（`lsusb | grep 1d50:606f`），并在 `config/robot.yaml`
把 `port` 显式写成 `/dev/serial/by-id/...`。
