# homomorphic_control

同构控制（验收清单第 12 项）。**模板。**

## 原理

Forge 标准 runner 已内建镜像通路：

```text
master_state (JointState)
  -> node_runner._joint_state_to_command
  -> JointCommand(mode="position")
  -> driver.set_command
```

从臂只需订阅 `master_state`，`is_follower=True`（本仓 `main.py` 默认）。

## 依赖

- 主臂的 Dora 节点（leader / master 适配器），输出完整 `JointState`；
- 本仓 `robot-litearm` 作为从臂。

## 前置

1. 主从关节名与顺序一致：`joint1..joint7`（夹爪可选）。
2. **先在仿真验证方向**：MJCF 与 URDF 已一致（`docs/joint_table.md`），
   但固件侧零位/正方向仍需真机确认后再上主从。
3. 真机 `speed <= 0.2`，从臂姿态有支撑。

## 验收判据

- 主臂缓慢走 3 个姿态（初始、中位、偏转），从臂在仿真中轨迹方向一致；
- 换真机后重复，记录主从角度差与延迟；
- 无轴向反转、无奇异跳变。

## 现有参考实现

本地已有 `lite-vr` / `litearm-vr-headset` 遥操实现（不在本仓）。本目录只负责
把同构链路映射到 Forge/Dora 端口，不重复实现头显侧。
