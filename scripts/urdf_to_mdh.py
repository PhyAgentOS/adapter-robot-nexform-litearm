#!/usr/bin/env python3
"""从 URDF 反推 Modified DH（Craig）参数（仅标准库，无外部依赖）。

约定：
    ^{i-1}T_i = Rx(alpha_{i-1}) * Tx(a_{i-1}) * Rz(theta_i + theta0_i) * Tz(d_i)

其中 frame i 的 z 轴取关节 i 的转轴（joint i 为 1..7），frame 0 固定在基座。
关节角 q_i 以 **加号** 叠到 theta0_i 上（与 URDF 关节正方向一致）。

做法：
1. 解析 URDF，按 base_link -> joint1 -> ... -> joint7 -> ee_link 建立串链。
2. 在 q=0 求各关节转轴的世界位姿（方向 + 轴上一点）。
3. 相邻转轴取公垂线构造 DH 坐标系：x_i 为 z_i 到 z_{i+1} 的公垂线。
4. 由相邻 DH 坐标系的相对变换分解出 alpha、a、theta0、d。
5. 用随机 q 对 URDF FK 与本 MDH FK 对拍。

用法：
    python scripts/urdf_to_mdh.py                 # 打印参数表
    python scripts/urdf_to_mdh.py --check         # 额外做 500 组随机 FK 对拍
    python scripts/urdf_to_mdh.py --check 2000
    python scripts/urdf_to_mdh.py --digits 9

退出码：--check 对拍超差时为 1，否则 0。
"""

from __future__ import annotations

import argparse
import math
import random
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URDF_PATH = ROOT / "assets/urdf/litearm.urdf"

Vec = tuple[float, float, float]
Mat = tuple[Vec, Vec, Vec]  # rows


# ---------- 基础线性代数 ----------
def dot(a: Vec, b: Vec) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a: Vec, b: Vec) -> Vec:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def sub(a: Vec, b: Vec) -> Vec:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def add(a: Vec, b: Vec) -> Vec:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def scale(a: Vec, s: float) -> Vec:
    return (a[0] * s, a[1] * s, a[2] * s)


def norm(a: Vec) -> float:
    return math.sqrt(dot(a, a))


def normalize(a: Vec) -> Vec:
    n = norm(a)
    if n < 1e-15:
        raise ValueError("cannot normalize a zero vector")
    return scale(a, 1.0 / n)


def mat_vec(m: Mat, v: Vec) -> Vec:
    return (dot(m[0], v), dot(m[1], v), dot(m[2], v))


def mat_mul(a: Mat, b: Mat) -> Mat:
    cols = tuple(zip(*b))
    return tuple(
        tuple(dot(row, col) for col in cols) for row in a
    )  # type: ignore[return-value]


def mat_t(m: Mat) -> Mat:
    return tuple(zip(*m))  # type: ignore[return-value]


def rx(a: float) -> Mat:
    c, s = math.cos(a), math.sin(a)
    return ((1.0, 0.0, 0.0), (0.0, c, -s), (0.0, s, c))


def ry(a: float) -> Mat:
    c, s = math.cos(a), math.sin(a)
    return ((c, 0.0, s), (0.0, 1.0, 0.0), (-s, 0.0, c))


def rz(a: float) -> Mat:
    c, s = math.cos(a), math.sin(a)
    return ((c, -s, 0.0), (s, c, 0.0), (0.0, 0.0, 1.0))


def rpy(r: float, p: float, y: float) -> Mat:
    """URDF fixed-axis rpy: R = Rz(yaw) * Ry(pitch) * Rx(roll)."""
    return mat_mul(mat_mul(rz(y), ry(p)), rx(r))


def axis_angle(axis: Vec, q: float) -> Mat:
    x, y, z = normalize(axis)
    c, s = math.cos(q), math.sin(q)
    C = 1.0 - c
    return (
        (c + x * x * C, x * y * C - z * s, x * z * C + y * s),
        (y * x * C + z * s, c + y * y * C, y * z * C - x * s),
        (z * x * C - y * s, z * y * C + x * s, c + z * z * C),
    )


# ---------- 位姿 ----------
Pose = tuple[Mat, Vec]


def compose(a: Pose, b: Pose) -> Pose:
    Ra, pa = a
    Rb, pb = b
    return mat_mul(Ra, Rb), add(pa, mat_vec(Ra, pb))


def inverse_rigid(a: Pose) -> Pose:
    R, p = a
    Rt = mat_t(R)
    return Rt, scale(mat_vec(Rt, p), -1.0)


# ---------- URDF ----------
def parse_urdf(path: Path):
    root = ET.parse(path).getroot()
    joints = []
    for j in root.findall("joint"):
        origin = j.find("origin")
        xyz = tuple(float(v) for v in (origin.get("xyz", "0 0 0")).split())
        r, p, y = (float(v) for v in (origin.get("rpy", "0 0 0")).split())
        axis_node = j.find("axis")
        axis = (
            tuple(float(v) for v in axis_node.get("xyz", "0 0 0").split())
            if axis_node is not None
            else (0.0, 0.0, 0.0)
        )
        joints.append(
            {
                "name": j.get("name"),
                "type": j.get("type"),
                "parent": j.find("parent").get("link"),
                "child": j.find("child").get("link"),
                "R": rpy(r, p, y),
                "xyz": xyz,
                "axis": axis,
            }
        )
    return joints


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--urdf", type=Path, default=URDF_PATH)
    parser.add_argument("--check", nargs="?", const=500, type=int, metavar="N",
                        help="做 N 组随机 q 的 URDF/MDH FK 对拍（默认 500）")
    parser.add_argument("--digits", type=int, default=6, help="打印小数位（默认 6）")
    args = parser.parse_args()

    joints = parse_urdf(args.urdf)

    # 串链（忽略 fixed，末端 fixed 单独处理）
    by_parent = {j["parent"]: j for j in joints if j["type"] != "fixed"}
    chain = []
    link = "base_link"
    while link in by_parent:
        joint = by_parent[link]
        chain.append(joint)
        link = joint["child"]

    fixed_tools = {j["parent"]: j for j in joints if j["type"] == "fixed"}
    tool_joint = fixed_tools["joint7"]
    tool_pose: Pose = (tool_joint["R"], tool_joint["xyz"])

    def urdf_fk(q: list[float]) -> Pose:
        pose: Pose = (((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)), (0.0, 0.0, 0.0))
        for joint, qi in zip(chain, q):
            pose = compose(pose, (joint["R"], joint["xyz"]))
            pose = compose(pose, (axis_angle(joint["axis"], qi), (0.0, 0.0, 0.0)))
        return compose(pose, tool_pose)

    n = len(chain)
    if n != 7:
        print(f"error: expected 7 revolute joints, found {n}", file=sys.stderr)
        return 1

    # q=0 时各关节转轴（世界）
    points: list[Vec] = []
    dirs: list[Vec] = []
    pose: Pose = (((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)), (0.0, 0.0, 0.0))
    for joint in chain:
        pose = compose(pose, (joint["R"], joint["xyz"]))
        R, p = pose
        points.append(p)
        dirs.append(normalize(mat_vec(R, joint["axis"])))
        pose = compose(pose, (axis_angle(joint["axis"], 0.0), (0.0, 0.0, 0.0)))
    ee_pose = urdf_fk([0.0] * n)

    # 相邻转轴公垂线
    def common_normal(p1: Vec, d1: Vec, p2: Vec, d2: Vec) -> tuple[Vec, Vec, Vec, float]:
        b = dot(d1, d2)
        w = sub(p1, p2)
        d = dot(d1, w)
        e = dot(d2, w)
        den = 1.0 - b * b
        if abs(den) < 1e-12:
            raise ValueError("parallel consecutive joint axes are not supported")
        s = (b * e - d) / den
        t = (e - b * d) / den
        q1 = add(p1, scale(d1, s))
        q2 = add(p2, scale(d2, t))
        v = sub(q2, q1)
        dist = norm(v)
        nrm = normalize(v) if dist > 1e-9 else normalize(cross(d1, d2))
        return nrm, q1, q2, dist

    # frame 1..n：z_i = 关节 i 转轴；frame 0 的 z_0 取 joint1 转轴
    zf: list[Vec] = [None] * (n + 1)  # type: ignore[list-item]
    zf[0] = dirs[0]
    for i in range(1, n + 1):
        zf[i] = dirs[i - 1]

    xf: list[Vec] = [None] * (n + 1)  # type: ignore[list-item]
    foot_a: list[Vec] = [None] * n  # type: ignore[list-item]
    foot_b: list[Vec] = [None] * n  # type: ignore[list-item]
    for i in range(1, n):
        nrm, q1, q2, _dist = common_normal(points[i - 1], dirs[i - 1], points[i], dirs[i])
        xf[i] = nrm
        foot_a[i] = q1
        foot_b[i] = q2
    # frame n 的 x 取末端 x 在垂直于 z_n 平面上的投影
    ee_x = ee_pose[0][0]
    proj = sub(ee_x, scale(zf[n], dot(ee_x, zf[n])))
    xf[n] = normalize(proj)
    xf[0] = xf[1]

    of: list[Vec] = [None] * (n + 1)  # type: ignore[list-item]
    # frame 0 原点放在 base_link 原点（仍位于 joint1 转轴上），基座高度计入 d_1
    of[0] = (0.0, 0.0, 0.0)
    for i in range(1, n):
        of[i] = foot_a[i]
    of[n] = foot_b[n - 1]

    frames: list[Pose] = []
    for i in range(n + 1):
        y = cross(zf[i], xf[i])
        # 矩阵按行存储；x/y/z 是列向量，因此转置后写入
        frames.append((mat_t((xf[i], y, zf[i])), of[i]))

    # 由相邻 frame 分解 MDH 参数
    params: list[tuple[float, float, float, float]] = []  # (alpha_{i-1}, a_{i-1}, theta0_i, d_i)
    for i in range(1, n + 1):
        A = compose(inverse_rigid(frames[i - 1]), frames[i])
        R, p = A
        alpha = math.atan2(-R[1][2], R[2][2])
        M = mat_mul(mat_t(rx(alpha)), R)  # should be Rz(theta0)
        theta0 = math.atan2(M[1][0], M[0][0])
        a = p[0]
        if abs(math.cos(alpha)) > 1e-9:
            d = p[2] / math.cos(alpha)
        else:
            d = p[1] / (-math.sin(alpha))
        # 结构残差：p 是否等于 (a, -d sin alpha, d cos alpha)
        pred = (a, -d * math.sin(alpha), d * math.cos(alpha))
        residual = norm(sub(p, pred))
        if residual > 1e-6:
            print(f"error: A{i} is not modified-DH shaped (residual {residual:.3e})", file=sys.stderr)
            return 1
        params.append((alpha, a, theta0, d))

    # frame n -> ee_link 的固定变换
    frame_n = frames[n]
    tool = compose(inverse_rigid(frame_n), ee_pose)

    def mdh_fk(q: list[float]) -> Pose:
        pose = frames[0]
        for i, (alpha, a, theta0, d) in enumerate(params):
            link = compose((rx(alpha), (a, 0.0, 0.0)), (rz(theta0 + q[i]), (0.0, 0.0, d)))
            pose = compose(pose, link)
        return compose(pose, tool)

    digits = args.digits
    print("Modified DH (Craig):  ^{i-1}T_i = Rx(alpha_{i-1}) Tx(a_{i-1}) Rz(theta_i + theta0_i) Tz(d_i)")
    print()
    print(f"{'i':>2}  {'alpha_{i-1}':>14}  {'a_{i-1} [m]':>14}  {'theta0_i [rad]':>16}  {'d_i [m]':>14}")
    for i, (alpha, a, theta0, d) in enumerate(params, start=1):
        print(f"{i:>2}  {alpha:>+14.{digits}f}  {a:>+14.{digits}f}  {theta0:>+16.{digits}f}  {d:>+14.{digits}f}")

    R0, p0 = frames[0]
    print()
    print("frame 0 (base_link 坐标系):")
    print(f"  p0 = ({p0[0]:.{digits}f}, {p0[1]:.{digits}f}, {p0[2]:.{digits}f})")
    for row in R0:
        print("  R0 = (" + ", ".join(f"{v: .{digits}f}" for v in row) + ")")

    Rt, pt = tool
    print()
    print("frame 7 -> ee_link (固定):")
    print(f"  p = ({pt[0]:.{digits}f}, {pt[1]:.{digits}f}, {pt[2]:.{digits}f})")
    for row in Rt:
        print("  R = (" + ", ".join(f"{v: .{digits}f}" for v in row) + ")")

    if args.check is not None:
        rng = random.Random(0)
        max_pos = 0.0
        max_rot = 0.0
        for _ in range(args.check):
            q = [rng.uniform(-math.pi, math.pi) for _ in range(n)]
            Ra, pa = urdf_fk(q)
            Rb, pb = mdh_fk(q)
            max_pos = max(max_pos, norm(sub(pa, pb)))
            max_rot = max(
                max_rot,
                max(abs(Ra[r][c] - Rb[r][c]) for r in range(3) for c in range(3)),
            )
        print()
        print(f"FK 对拍（{args.check} 组随机 q）：位置最大误差 {max_pos:.3e} m，旋转矩阵最大元素误差 {max_rot:.3e}")
        if max_pos > 1e-6 or max_rot > 1e-6:
            print("error: MDH FK 与 URDF FK 不一致", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
