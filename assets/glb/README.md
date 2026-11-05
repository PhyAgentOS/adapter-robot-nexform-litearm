# GLB / 可视化

本目录放面向 Web / 可视化 / 资源分发的自包含产物，与 `assets/mjcf/`
（MuJoCo 仿真主数据）分开。

## 当前文件

| 文件 | 说明 |
|---|---|
| `litearm.glb` | 由 `../mjcf/litearm7.xml` 导出，3.1 MB |

## 来源与生成方式

| 项 | 值 |
|---|---|
| 源文件 | `assets/mjcf/litearm7.xml`（由 `nexform-tech/litearm-description` `f94eafe` 的 URDF 重建） |
| 生成脚本 | `scripts/mjcf_to_glb.py` |
| 命令 | `python3 scripts/mjcf_to_glb.py` |
| MuJoCo | 3.9.0 |
| trimesh | 5.0.0 |
| 导出姿态 | MJCF 默认 `qpos`（全零） |
| 坐标系 / 单位 | MuJoCo 世界系，米、弧度；导出的是 q=0 静态网格，**不含关节层级与动画** |
| 内容 | 9 个视觉网格（`base_link`、`joint1`…`joint7`、`ee_link`）；不含地面、灯光、`tcp` site |
| 夹爪 | 不含（LiteGrip 为独立末端器件，本仓无其网格资产） |
| SHA-256 | `e51a45ad760d6f13bcc2ebe6ff820df540d1acb3e1b4bab518451c76d5408f1b` |

重新生成：

```bash
python3 -m pip install mujoco==3.9.0 trimesh==5.0.0
python3 scripts/mjcf_to_glb.py --mjcf assets/mjcf/litearm7.xml --out assets/glb/litearm.glb
```

## 许可

模型源自 `nexform-tech/litearm-description` 与 `nexform-tech/litearm-mujoco`，
两者均为 Apache-2.0。仓库级汇总见 [`../../THIRD_PARTY_NOTICES.md`](../../THIRD_PARTY_NOTICES.md)。
