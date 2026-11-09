#!/usr/bin/env python3
"""离线分析同构控制记录：第 12 项判据。

输入 `state_recorder.py` 的 JSONL，输出：

- 稳态误差：每个「保持段」最后 0.5 s 的 |follower - master|；
- 方向一致性：相邻保持段之间主臂发生变化的方向，从臂是否同向；
- 全程最大误差（仅参考，含过渡段滞后）。

可同时给 `--compare` 第二份记录（另一环境），比较两边每个保持段的
**相对基准的偏置**是否一致，用来回答「仿真与真机姿态一致」。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

JOINTS = tuple(f"joint{i}" for i in range(1, 8))
EPS = 1e-4


def _load(path: str) -> list[dict]:
    rows = []
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    if not rows:
        raise SystemExit(f"{path} 为空")
    return rows


def _holds(rows: list[dict], tail: float) -> list[dict]:
    """切出 master 静止的保持段，返回每段的稳态均值。"""
    segments: list[list[dict]] = []
    current: list[dict] = []
    for row in rows:
        if current and max(
            abs(a - b) for a, b in zip(row["master"], current[-1]["master"])
        ) > EPS:
            segments.append(current)
            current = []
        current.append(row)
    if current:
        segments.append(current)

    holds = []
    for seg in segments:
        duration = seg[-1]["t"] - seg[0]["t"]
        if duration < 0.2:
            continue
        window = [row for row in seg if row["t"] >= seg[-1]["t"] - tail]
        if not window:
            continue
        holds.append(
            {
                "t0": seg[0]["t"],
                "t1": seg[-1]["t"],
                "duration": round(duration, 3),
                "master": [
                    sum(row["master"][i] for row in window) / len(window)
                    for i in range(len(JOINTS))
                ],
                "follower": [
                    sum(row["follower"][i] for row in window) / len(window)
                    for i in range(len(JOINTS))
                ],
            }
        )
    return holds


def _steady(rows: list[dict], tail: float) -> dict:
    holds = _holds(rows, tail)
    errors = []
    for hold in holds:
        errors.append(
            [abs(f - m) for m, f in zip(hold["master"], hold["follower"])]
        )

    direction_ok = True
    reversals = []
    for prev, cur in zip(holds, holds[1:]):
        for i, name in enumerate(JOINTS):
            expected = cur["master"][i] - prev["master"][i]
            actual = cur["follower"][i] - prev["follower"][i]
            if abs(expected) <= EPS:
                continue
            if actual * expected <= 0:
                direction_ok = False
                reversals.append(
                    {
                        "joint": name,
                        "master_delta": round(expected, 4),
                        "follower_delta": round(actual, 4),
                    }
                )

    max_error = max(
        abs(f - m)
        for row in rows
        for m, f in zip(row["master"], row["follower"])
    )
    per_joint = [
        round(max((err[i] for err in errors), default=0.0), 4)
        for i in range(len(JOINTS))
    ]
    return {
        "holds": len(holds),
        "hold_master": [[round(v, 4) for v in h["master"]] for h in holds],
        "hold_follower": [[round(v, 4) for v in h["follower"]] for h in holds],
        "steady_error_by_joint": dict(zip(JOINTS, per_joint)),
        "steady_error_max": round(max(per_joint, default=0.0), 4),
        "max_error_all_samples": round(max_error, 4),
        "direction_consistent": direction_ok,
        "direction_reversals": reversals,
    }


def _offsets(rows: list[dict], tail: float) -> list[list[float]]:
    """每个保持段相对第一段的偏置，用于跨环境比较。"""
    holds = _holds(rows, tail)
    if not holds:
        return []
    base = holds[0]["follower"]
    return [
        [round(f - b, 4) for b, f in zip(base, hold["follower"])] for hold in holds
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("record", help="state_recorder.py 输出")
    parser.add_argument("--compare", help="另一环境的记录，比较稳态偏置")
    parser.add_argument("--tail", type=float, default=0.5, help="稳态窗口秒")
    parser.add_argument("--tolerance", type=float, default=0.05, help="稳态误差阈值 rad")
    parser.add_argument("--offset-tolerance", type=float, default=0.05,
                        help="跨环境偏置差阈值 rad")
    parser.add_argument("--json-out", help="把摘要写入该文件")
    args = parser.parse_args(argv)

    rows = _load(args.record)
    summary = {"record": args.record, **_steady(rows, args.tail)}

    cross_ok = True
    if args.compare:
        other_rows = _load(args.compare)
        other = _steady(other_rows, args.tail)
        summary["compare"] = other
        mine_offsets = _offsets(rows, args.tail)
        other_offsets = _offsets(other_rows, args.tail)
        deviations = []
        for mine, theirs in zip(mine_offsets, other_offsets):
            deviations.append(
                [round(abs(a - b), 4) for a, b in zip(mine, theirs)]
            )
        cross_max = max((v for row in deviations for v in row), default=0.0)
        cross_ok = cross_max <= args.offset_tolerance
        summary["cross_offset_deviation"] = deviations
        summary["cross_offset_max"] = cross_max
        summary["cross_consistent"] = cross_ok

    passed = (
        summary["steady_error_max"] <= args.tolerance
        and summary["direction_consistent"]
        and cross_ok
    )
    summary["passed"] = passed
    text = json.dumps(summary, ensure_ascii=False, indent=2)
    print(text)
    if args.json_out:
        Path(args.json_out).write_text(text + "\n", encoding="utf-8")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
