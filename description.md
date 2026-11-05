# nexform_litearm 构型说明

## 构型概览

NexForm LiteArm 单机械臂构型：7 个旋转关节，末端为 LiteGrip 两指夹爪。
真机通过 USB CDC 连接 litearm SDK；夹爪通过 SocketCAN 连接。

- **构型类别**：机械臂
- **自由度**：7（`joint1` … `joint7`），另加 1 个夹爪开合自由度
- **关节单位**：弧度；夹爪在 Forge 侧为米（两指总开口 0–0.080 m）

## 支持引擎

| 引擎 | 支持情况 | 依据 |
|---|---|---|
| 真机 | 支持 | `src/litearm_robot/` |
| MuJoCo | 支持 | `assets/mjcf/scene.xml` |
| Dora | 支持 | `examples/02_dora_tests/` |
| Isaac Sim / Isaac Lab | 未提供 USD 资产 | — |

“支持”仅表示仓库中存在对应驱动、模型或可执行工作流；实际运行仍需满足硬件、
SDK 与运行环境要求。真机验收进度见 `docs/validation.md`。

## 模型资产

- [`assets/urdf/litearm.urdf`](assets/urdf/litearm.urdf)
- [`assets/mjcf/litearm7.xml`](assets/mjcf/litearm7.xml)
- [`assets/mjcf/scene.xml`](assets/mjcf/scene.xml)
- [`assets/glb/litearm.glb`](assets/glb/litearm.glb)
- [`assets/meshes/`](assets/meshes/)（STL，供 URDF）
- [`assets/mjcf/meshes/`](assets/mjcf/meshes/)（OBJ，供 MJCF）

## 参数与来源

- joint 限位/零位/正方向：`docs/joint_table.md`
- SDK、固件、夹爪、VR 参数：`docs/parameters.md`
- MDH：`docs/mdh.md`
- 资产来源与许可：`THIRD_PARTY_NOTICES.md`
