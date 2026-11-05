"""把 MJCF 的视觉网格导出为自包含 GLB。

仅用于离线生成 `assets/glb/litearm.glb`，不参与运行时。依赖 MuJoCo 与
trimesh（不在本项目运行时依赖内）：

    python scripts/mjcf_to_glb.py \
        --mjcf assets/mjcf/litearm7.xml \
        --out assets/glb/litearm.glb

导出姿态为 MJCF 默认 qpos（全零），只包含 `type="mesh"` 的视觉 geom；
地面、灯光、站点不导出。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import mujoco
import numpy as np
import trimesh


def build_scene(mjcf_path: Path) -> tuple[trimesh.Scene, list[str]]:
    model = mujoco.MjModel.from_xml_path(str(mjcf_path))
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)

    scene = trimesh.Scene()
    names: list[str] = []

    for geom_id in range(model.ngeom):
        if model.geom_type[geom_id] != mujoco.mjtGeom.mjGEOM_MESH:
            continue
        mesh_id = model.geom_dataid[geom_id]
        if mesh_id < 0:
            continue

        vert_adr = model.mesh_vertadr[mesh_id]
        vert_num = model.mesh_vertnum[mesh_id]
        face_adr = model.mesh_faceadr[mesh_id]
        face_num = model.mesh_facenum[mesh_id]

        vertices = np.array(
            model.mesh_vert[vert_adr : vert_adr + vert_num], dtype=np.float64
        )
        vertices *= np.array(model.mesh_scale[mesh_id], dtype=np.float64)
        faces = np.array(
            model.mesh_face[face_adr : face_adr + face_num], dtype=np.int64
        )

        rotation = np.array(data.geom_xmat[geom_id], dtype=np.float64).reshape(3, 3)
        position = np.array(data.geom_xpos[geom_id], dtype=np.float64)
        vertices = vertices @ rotation.T + position

        mat_id = int(model.geom_matid[geom_id])
        if mat_id >= 0:
            rgba = model.mat_rgba[mat_id]
        else:
            rgba = model.geom_rgba[geom_id]
        colors = np.tile(
            np.clip(np.asarray(rgba[:4], dtype=np.float64) * 255.0, 0, 255).astype(
                np.uint8
            ),
            (vert_num, 1),
        )

        mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
        mesh.visual.vertex_colors = colors

        name = (
            mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, geom_id)
            or f"geom_{geom_id}"
        )
        scene.add_geometry(mesh, node_name=name, geom_name=name)
        names.append(name)

    return scene, names


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mjcf_to_glb")
    parser.add_argument(
        "--mjcf", default="assets/mjcf/litearm7.xml", help="输入 MJCF 路径"
    )
    parser.add_argument(
        "--out", default="assets/glb/litearm.glb", help="输出 GLB 路径"
    )
    args = parser.parse_args(argv)

    mjcf_path = Path(args.mjcf)
    out_path = Path(args.out)
    if not mjcf_path.is_file():
        print(f"MJCF 不存在: {mjcf_path}", file=sys.stderr)
        return 2

    scene, names = build_scene(mjcf_path)
    if not names:
        print("MJCF 中没有可导出的 mesh geom", file=sys.stderr)
        return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(scene.export(file_type="glb"))

    print(f"mujoco {mujoco.__version__}, trimesh {trimesh.__version__}")
    print(f"geoms ({len(names)}): {', '.join(names)}")
    print(f"wrote {out_path} ({out_path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
