#!/usr/bin/env python3
"""资产一致性检查（仅标准库，无外部依赖）。

检查内容：
1. URDF / MJCF 都有 joint1..joint7，且 mesh 文件存在。
2. URDF 里没有残留的 package:// 路径。
3. MJCF scene.xml 能 include litearm7.xml。
4. URDF 与 MJCF 的关节轴方向、限位对比（已知差异会报 warn）。
5. assets/glb 是否已有 GLB。
6. assets/SHA256SUMS 台账逐文件哈希比对。

退出码：有 error 时为 1；只有 warn 时为 0。

用法：
    python scripts/validate_assets.py
    python scripts/validate_assets.py --strict   # warn 也当失败
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URDF_PATH = ROOT / "assets/urdf/litearm.urdf"
MJCF_PATH = ROOT / "assets/mjcf/litearm7.xml"
SCENE_PATH = ROOT / "assets/mjcf/scene.xml"
GLB_DIR = ROOT / "assets/glb"
LEDGER_PATH = ROOT / "assets/SHA256SUMS"
JOINTS = [f"joint{i}" for i in range(1, 8)]

errors: list[str] = []
warnings: list[str] = []


def error(message: str) -> None:
    errors.append(message)


def warn(message: str) -> None:
    warnings.append(message)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _axis(xyz: str) -> tuple[float, float, float]:
    values = [float(v) for v in xyz.split()]
    if len(values) != 3:
        raise ValueError(f"bad axis {xyz!r}")
    return tuple(values)  # type: ignore[return-value]


def _is_opposite(a: tuple[float, ...], b: tuple[float, ...]) -> bool:
    dot = sum(x * y for x, y in zip(a, b))
    return dot < 0.0


def check_urdf() -> dict[str, dict]:
    if not URDF_PATH.exists():
        error(f"missing {URDF_PATH.relative_to(ROOT)}")
        return {}

    text = URDF_PATH.read_text(encoding="utf-8")
    if "package://" in text:
        error("URDF still contains package:// mesh paths")

    root = ET.parse(URDF_PATH).getroot()
    joints: dict[str, dict] = {}

    for joint in root.findall("joint"):
        name = joint.get("name", "")
        kind = joint.get("type", "")
        if name in JOINTS:
            if kind != "revolute":
                error(f"URDF {name}: expected revolute, got {kind}")
            axis = joint.find("axis")
            limit = joint.find("limit")
            joints[name] = {
                "axis": _axis(axis.get("xyz", "0 0 1")) if axis is not None else (0.0, 0.0, 1.0),
                "lower": float(limit.get("lower")) if limit is not None else None,
                "upper": float(limit.get("upper")) if limit is not None else None,
            }
    for mesh in root.iter():
        if _local(mesh.tag) != "mesh":
            continue
        filename = mesh.get("filename", "")
        if not filename.startswith("package://"):
            target = (URDF_PATH.parent / filename).resolve()
            if not target.exists():
                error(f"URDF mesh missing: {filename}")

    for name in JOINTS:
        if name not in joints:
            error(f"URDF missing {name}")
    print(f"[ok] URDF: {len(joints)}/7 revolute joints, meshes checked")
    return joints


def check_mjcf() -> dict[str, dict]:
    if not MJCF_PATH.exists():
        error(f"missing {MJCF_PATH.relative_to(ROOT)}")
        return {}

    root = ET.parse(MJCF_PATH).getroot()
    compiler = root.find("compiler")
    meshdir = ""
    if compiler is not None:
        meshdir = compiler.get("meshdir", "")
    base = (MJCF_PATH.parent / meshdir).resolve() if meshdir else MJCF_PATH.parent

    for mesh in root.iter():
        if _local(mesh.tag) != "mesh":
            continue
        filename = mesh.get("file")
        if not filename:
            continue
        target = (base / filename).resolve()
        if not target.exists():
            error(f"MJCF mesh missing: {filename}")

    joints: dict[str, dict] = {}
    for joint in root.iter():
        if _local(joint.tag) != "joint":
            continue
        name = joint.get("name", "")
        if name not in JOINTS:
            continue
        kind = joint.get("type", "hinge")
        if kind != "hinge":
            error(f"MJCF {name}: expected hinge, got {kind}")
        axis = joint.get("axis", "0 0 1")
        limits = joint.get("range")
        lower = upper = None
        if limits:
            parts = [float(v) for v in limits.split()]
            if len(parts) == 2:
                lower, upper = parts
        joints[name] = {"axis": _axis(axis), "lower": lower, "upper": upper}

    for name in JOINTS:
        if name not in joints:
            error(f"MJCF missing {name}")
    print(f"[ok] MJCF: {len(joints)}/7 hinge joints, meshes checked")
    return joints


def check_scene() -> None:
    if not SCENE_PATH.exists():
        error("missing assets/mjcf/scene.xml")
        return
    root = ET.parse(SCENE_PATH).getroot()
    includes = [
        node.get("file", "")
        for node in root.iter()
        if _local(node.tag) == "include"
    ]
    if "litearm7.xml" not in includes:
        error(f"scene.xml does not include litearm7.xml (includes={includes})")
    else:
        print("[ok] scene.xml includes litearm7.xml")


LIMIT_WARN_RAD = 0.05


def compare(urdf: dict[str, dict], mjcf: dict[str, dict]) -> None:
    rounding = 0
    for name in JOINTS:
        if name not in urdf or name not in mjcf:
            continue
        u, m = urdf[name], mjcf[name]
        if _is_opposite(u["axis"], m["axis"]):
            warn(
                f"{name}: URDF axis {u['axis']} vs MJCF axis {m['axis']} "
                "方向相反（需确认两份资产哪一份与固件一致）"
            )
        for side in ("lower", "upper"):
            if u[side] is None or m[side] is None:
                continue
            diff = abs(u[side] - m[side])
            if diff > LIMIT_WARN_RAD:
                warn(
                    f"{name}: 限位{side} URDF {u[side]:+.4f} vs "
                    f"MJCF {m[side]:+.4f}（差 {diff:.4f} rad）"
                )
            elif diff > 1e-3:
                rounding += 1
    if rounding:
        print(
            f"[info] {rounding} 个限位端点差异 < {LIMIT_WARN_RAD} rad，"
            "视为标定取整"
        )


def check_glb() -> None:
    glb_files = sorted(GLB_DIR.glob("*.glb")) if GLB_DIR.exists() else []
    if not glb_files:
        warn("assets/glb 没有 GLB 文件（README 已标注待补）")
    else:
        print(f"[ok] GLB: {len(glb_files)} file(s)")


def check_ledger() -> None:
    if not LEDGER_PATH.exists():
        warn("missing assets/SHA256SUMS")
        return

    checked = 0
    for line in LEDGER_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        digest, sep, rel = line.partition("  ")
        if not sep or not rel:
            error(f"SHA256SUMS: malformed line {line!r}")
            continue
        path = ROOT / rel
        if not path.is_file():
            error(f"SHA256SUMS: missing {rel}")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != digest:
            error(f"SHA256SUMS: {rel} hash mismatch")
            continue
        checked += 1
    print(f"[ok] SHA256 ledger: {checked} file(s)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="warn 也返回非零")
    args = parser.parse_args(argv)

    urdf = check_urdf()
    mjcf = check_mjcf()
    check_scene()
    if urdf and mjcf:
        compare(urdf, mjcf)
    check_glb()
    check_ledger()

    for message in warnings:
        print(f"[warn] {message}")
    for message in errors:
        print(f"[error] {message}")

    print(f"\n{len(errors)} error(s), {len(warnings)} warning(s)")
    if errors:
        return 1
    if args.strict and warnings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
