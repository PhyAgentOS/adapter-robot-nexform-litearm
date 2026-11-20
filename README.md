# adapter-robot-nexform-litearm

[English](README.md) | [简体中文](README_zh.md)

## BREAKING CHANGE: Forge 2.x / Dora 1.x migration

This migration from Forge 1.x / Dora 0.4.x requires coordinated deployment. Align the Forge packages, Dora CLI/coordinator/daemon, this node and its peer nodes before connecting a dataflow; replacing only one node in a Forge 1.x deployment is unsupported. Rebuild and redeploy executable artifacts with the matching environment. Keep `stable/1.x` for deployments that still use the previous stack.

The validated Python baseline is `forge-msgs==2.1.0`, `Pillow==13.0.0`, `forge-common==2.1.0`, the applicable `forge-robot` / `forge-policy` / `forge-kinematics` / `forge-tool` packages at `2.0.0`, and `dora-rs==1.0.1`. Respect this repository's Python and SDK platform requirements. Forge package families have independent versions. Rust nodes retain the published `forge_msgs` crate `2.0.0` with Dora `1.0.1`; Python Msgs `2.1.0` does not require a nonexistent Rust `2.1.0` release. The `forge_msgs.v1` message namespace remains unchanged.

This notice describes the deployment break from the previous stack; it does not declare hardware, real-model or sustained-run acceptance complete. See [this round's verification report](migration/msgs-2.1.0-report.json) for actual tests and outstanding gates.

Forge/Dora robot adapter for the NexForm LiteArm 7-DOF arm and LiteGrip gripper.

## Installation

Use Python 3.12 and install the frozen project environment:

```bash
uv sync --frozen
```

Install the project-specific optional SDK or test extras when needed. Hardware SDK and device configuration requirements remain applicable.

## Entrypoints

- `robot-litearm`: `litearm_robot.main:main`.
- `robot-litearm-bridge`: `litearm_robot.bridge:main`.

Use each entrypoint's `--help` to inspect its options. Review the supplied configurations and robot limits before enabling hardware. Existing assets, workflow examples, calibration and device setup details are preserved in the [Chinese guide](README_zh.md) and repository documentation.

## 7. Dora 节点测试

见 [`examples/02_dora_tests/`](examples/02_dora_tests/)。

```bash
cd examples/02_dora_tests
PATH=$HOME/.dora/bin:$PATH dora run dataflow.yaml
PATH=$HOME/.dora/bin:$PATH dora run dataflow.control.yaml   # enable -> home -> disable
```

先用 `--fake` 验证端口；真机配置需人工确认后再运行。

控制面通过 `control` 输入发送 `enable` / `disable` / `reset` / `home` / `stop` /
`emergency_stop`，回执在 `control_status`；`action` 支持可选的 `speed` 扩展列
（0..1）。语义见 [`docs/parameters.md` §7](docs/parameters.md)，fake 结果见
[`docs/validation.md`](docs/validation.md)「控制面记录」。

### 7.1 forge_bridge（TCP/JSON）

`examples/04_forge_bridge/` 把同一组端口暴露成一行一个 JSON 的 TCP 服务，
供 Forge Skill Gateway 或非 Python 调用方使用：

```bash
cd examples/04_forge_bridge
PATH="$PWD/../../.venv/bin:$HOME/.dora/bin:$PATH" dora run dataflow.bridge.yaml
# 另开终端
../../.venv/bin/python bridge_client.py                 # 交互式
../../.venv/bin/python bridge_client.py movej 0 0 0 0 0 0 0 --speed 0.2
```

请求命令：`state`/`status`、`movej`、`gripper`、`home`、`stop`、`enable`、
`disable`、`reset`、`estop`、`ping`；详情与线程模型见
[`docs/bridge.md`](docs/bridge.md)。桥默认只监听 `127.0.0.1:9005`，无鉴权。

驱动发布的 `state` 恒含 `joint_order` 的全部 8 项；夹爪未启用或读回超时时，
`gripper` 的位置/速度/力矩为 `NaN`（未知），桥的 JSON 输出把该值转为 `null`。

## 8. 仿真 workflow

见 [`examples/03_workflows/sim_basic_motion/`](examples/03_workflows/sim_basic_motion/)。

```bash
cd examples/03_workflows/sim_basic_motion
python offline_sweep.py                 # 离线：第 6–7 项，只需 mujoco+numpy
## Validation

Unit tests and simulated backends cover software contracts. Device motion, native SDK operation, model inference and release-artifact validation require their declared environments. A successful build alone does not establish hardware acceptance.

## Forge 2.x migration

This branch prepares node version `2.0.0` for Dora 1.x, frozen to Dora `1.0.1` for migration validation. It uses the official Forge 2.x distributions; Common is at least `2.1.0`. Regenerated locks and all executable entrypoints are part of the change.

Every change report must list repository, changes and test evidence, including per-node `dora run` records and a chained test containing `adapter-forge-gateway`. Unavailable hardware/model checks remain pending. Source PRs do not publish stable releases or synchronize GitLab; synchronization follows full acceptance.

## CI policy

Automated dependency vulnerability audits are not maintained as CI or merge gates on this branch. Existing tests, builds, and other checks remain in place. Removing the audit gate does not change locked dependencies or resolve previously reported vulnerabilities.
