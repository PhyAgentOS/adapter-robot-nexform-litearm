# 资产来源与校验

本目录存放 LiteArm 的 URDF/STL、MJCF/OBJ、GLB 和哈希台账，供 SDK 联调、MuJoCo 仿真、
可视化与验收使用。每个交付文件的 SHA-256 记录在 `SHA256SUMS`，来源和转换方式见下。

## 来源

| 资产组 | 交付路径 | 来源 | 源提交 | 转换 |
|---|---|---|---|---|
| URDF | `assets/urdf/litearm.urdf` | `nexform-tech/litearm-description`，`SE/litearm_description/urdf/litearm_description.urdf` | `f94eafe` | mesh 路径 `package://litearm_description/meshes/` → `../meshes/`；CRLF → LF |
| STL | `assets/meshes/*.STL` | 同上，`SE/litearm_description/meshes/*.STL` | `f94eafe` | 原样复制 |
| MJCF | `assets/mjcf/litearm7.xml` | `nexform-tech/litearm-mujoco`，`src/litearm_mujoco/assets/litearm7.xml` | `b901d49`（本地分支 `0bbc474`，资产 blob 相同） | 原样复制 |
| OBJ | `assets/mjcf/meshes/*.obj` | 同上，`src/litearm_mujoco/assets/meshes/*.obj` | `b901d49` | 原样复制（STL 简化到约 20k 面） |
| 场景入口 | `assets/mjcf/scene.xml` | 本仓编写 | — | 仅 `include litearm7.xml`；地面、灯光、`tcp` site 已在 `litearm7.xml` 内 |
| position 变体 | `assets/mjcf/litearm7_position.xml` | 本仓由 `litearm7.xml` 派生 | — | `motor` → `position`（kp/kv 取固件实测增益）；各 body 加 `gravcomp="1"` |
| position 入口 | `assets/mjcf/scene_position.xml` | 本仓编写 | — | 仅 `include litearm7_position.xml` |
| GLB | `assets/glb/litearm.glb` | 本仓生成 | — | `scripts/mjcf_to_glb.py`，MuJoCo 3.9.0 + trimesh 5.0.0；详见 `assets/glb/README.md` |

## 源文件与交付副本比对

- **URDF**：源文件 SHA-256 `655afc333d781dc1b046bade96c75e587f5a9f0fe535e9b6a369c4af153ad90b`，
  交付副本 `e0341b9226d33ed4b37e02ec22597d081965ecadc261ddd30ff3b4359dba02f2`。
  用 `diff --strip-trailing-cr` 比较，差异只有 18 处 mesh `filename`
  （9 个 link × visual/collision），几何、质量、惯量、关节定义无差异。
- **STL**：9 个文件与源文件逐字节一致（源/交付 SHA-256 相同）。
- **MJCF + OBJ**：`litearm7.xml` 和 9 个 OBJ 与源文件逐字节一致
  （`litearm7.xml` 为 `39f9d2c5d69abef7414d4e3595a7932ab2515b40f70e77b16d521b3dc8e7ef01`）；
  OBJ 哈希见 `SHA256SUMS`。
- **position / scene 变体、GLB**：本仓派生或生成，没有上游副本；重新生成后必须更新台账。

## 校验

```bash
sha256sum -c assets/SHA256SUMS
python scripts/validate_assets.py
```

`validate_assets.py` 会读取 `SHA256SUMS` 并逐文件比对，哈希不符时返回非零。

## 更新规则

- 替换或重新生成任何资产后，重算 `assets/SHA256SUMS`，并同步更新本文件的来源表。
- 修改 `litearm7_position.xml` 后不要只更新确认文件，必须同时更新台账。
