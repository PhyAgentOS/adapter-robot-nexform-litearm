#!/usr/bin/env python3
"""VR → Dora 桥：把 lite-vr teleop 的 TCP 关节流转成 Forge JointCommand。

lite-vr 的 teleop（IK/映射之后）是一个 TCP 客户端，按 ``arm_follow_server``
的 JSON 协议往 ``:9001`` 逐帧发 7 关节角。本节点在该端口起一个最小服务端，
把 ``{"cmd":"q","q":[7]}`` 转成 Dora ``action`` 上的 ``JointCommand``（position），
再用 ``state`` 输入（仿真 ``mujoco/proprio_state`` 或真机 ``robot/state``）
回答 ``{"cmd":"state","request_id":N}`` 查询。这样 lite-vr 无需改动即可驱动
本仓的 robot 节点或 mujoco_sim。

协议（与 lite-vr arm_follow_server 一致，每条命令回一行 JSON）：
  {"cmd":"start"}          开始跟随（以当前实测角为锚点）
  {"cmd":"q","q":[7]}      一帧 7 关节目标（逐帧跟随）
  {"cmd":"movej","q":[7]}  直接跳到目标构型
  {"cmd":"latch"}          停止跟随，就地持位
  {"cmd":"hold"}           丢弃目标，就地持位
  {"cmd":"stop"}           停止跟随并持位（仿真里不动臂，不做失能）
  {"cmd":"state","request_id":N}
  {"cmd":"ping"}

输入：tick（定时器）、state（mujoco/proprio_state 或 robot/state）
输出：action（JointCommand，全部 7 轴）

仅用于仿真验证或现场真机；真机运行前确认急停在手边、速度已限制。
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import socket
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from dora import Node  # noqa: E402
from forge_msgs import JointCommand, JointState  # noqa: E402

from litearm_robot.codec import (  # noqa: E402
    ARM_JOINTS,
    clip_arm_positions,
)

logger = logging.getLogger("vr_bridge")

Q_TOL = 1e-6


def _parse_q7(value) -> list[float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 7:
        return None
    try:
        q = [float(x) for x in value]
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(x) for x in q):
        return None
    return q


class Shared:
    """Dora 主线程与 TCP 连接线程之间共享的最小状态。"""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.latest_q: list[float] | None = None
        self.latest_at: float | None = None
        self.following = False
        self.holding = False
        self.target: list[float] | None = None   # teleop 下发的原始目标
        self.cmd_q: list[float] | None = None    # 限位裁剪后真正下发的目标
        self.last_log: dict[str, float] = {}     # 命令日志限频

    def set_state(self, q: list[float]) -> None:
        with self.lock:
            self.latest_q = q
            self.latest_at = time.monotonic()

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "latest_q": None if self.latest_q is None else list(self.latest_q),
                "latest_at": self.latest_at,
                "following": self.following,
                "holding": self.holding,
                "target": None if self.target is None else list(self.target),
                "cmd_q": None if self.cmd_q is None else list(self.cmd_q),
            }


def _measured_response(shared: Shared, request_id, state_timeout: float) -> dict:
    snap = shared.snapshot()
    q = snap["latest_q"]
    now = time.monotonic()
    age = None if snap["latest_at"] is None else now - snap["latest_at"]
    valid = (
        q is not None
        and age is not None
        and 0.0 <= age <= state_timeout
        and all(math.isfinite(x) for x in q)
    )
    return {
        "ok": True,
        "cmd": "state",
        "request_id": request_id,
        "valid": bool(valid),
        "q": q if valid else None,
        "age_s": round(age, 6) if valid else None,
        "error": None if valid else "no fresh measured state",
    }


def _handle(shared: Shared, msg: dict, state_timeout: float) -> dict:
    cmd = msg.get("cmd")

    if cmd == "start":
        snap = shared.snapshot()
        q = snap["latest_q"]
        with shared.lock:
            shared.following = True
            shared.holding = False
            shared.target = None
            if shared.cmd_q is None and q is not None:
                shared.cmd_q = list(q)
        resp = {"ok": True, "cmd": cmd}
        if q is not None:
            resp["q"] = q
        logger.info("start (anchor=%s)", "measured" if q is not None else "none")
        return resp

    if cmd == "q":
        q = _parse_q7(msg.get("q"))
        if q is None:
            return {"ok": False, "cmd": cmd, "error": "q 必须是 7 个有限数值"}
        with shared.lock:
            shared.target = q
            shared.holding = False
        return {"ok": True, "cmd": cmd}

    if cmd == "movej":
        q = _parse_q7(msg.get("q"))
        if q is None:
            return {"ok": False, "cmd": cmd, "error": "q 必须是 7 个有限数值"}
        with shared.lock:
            shared.following = True
            shared.holding = False
            shared.target = q
        logger.info("movej -> %s", [round(x, 4) for x in q])
        return {"ok": True, "cmd": cmd}

    if cmd in ("latch", "hold", "stop"):
        now = time.monotonic()
        with shared.lock:
            was_holding = shared.holding
            q = (shared.cmd_q if shared.holding and shared.cmd_q is not None
                 else shared.latest_q)
            if q is None:
                return {"ok": False, "cmd": cmd,
                        "error": "no measured or commanded hold position"}
            shared.following = False
            shared.holding = True
            shared.cmd_q = list(q)
            shared.target = None
            # teleop 在持位期间每 50 ms 重发一次 hold 保活，只在状态变化或 2 s
            # 打一条，避免日志被保活刷屏。
            should_log = (not was_holding
                          or now - shared.last_log.get("holding", 0.0) > 2.0)
            if should_log:
                shared.last_log["holding"] = now
        if should_log:
            logger.info("%s -> hold at %s", cmd, [round(x, 4) for x in q])
        return {"ok": True, "cmd": cmd, "measured": True}

    if cmd == "state":
        return _measured_response(shared, msg.get("request_id"), state_timeout)

    if cmd == "ping":
        snap = shared.snapshot()
        return {"ok": True, "state": "FOLLOWING" if snap["following"] else "HOLD",
                "q": snap["latest_q"], "cmd_q": snap["cmd_q"],
                "following": snap["following"], "holding": snap["holding"]}

    return {"ok": False, "error": f"unknown cmd {cmd!r}"}


def _serve_conn(conn: socket.socket, shared: Shared, state_timeout: float) -> None:
    addr = conn.getpeername()
    logger.info("client connected: %s", addr)
    buf = b""
    with conn:
        while True:
            try:
                data = conn.recv(4096)
            except OSError:
                break
            if not data:
                break
            buf += data
            if len(buf) > 65536:
                logger.warning("client %s buffer overflow, dropping", addr)
                break
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line.decode("utf-8", "replace"))
                except (ValueError, TypeError):
                    resp = {"ok": False, "error": "bad json"}
                else:
                    resp = (_handle(shared, msg, state_timeout)
                            if isinstance(msg, dict)
                            else {"ok": False, "error": "message must be a JSON object"})
                try:
                    conn.sendall((json.dumps(resp) + "\n").encode())
                except OSError:
                    break
    logger.info("client disconnected: %s", addr)


def _serve(server: socket.socket, shared: Shared, state_timeout: float) -> None:
    while True:
        try:
            conn, _ = server.accept()
        except socket.timeout:
            continue
        except OSError:
            return
        threading.Thread(
            target=_serve_conn,
            args=(conn, shared, state_timeout),
            daemon=True,
        ).start()


def _state_vector(value) -> list[float] | None:
    try:
        state = JointState.from_arrow(value)
        by_name = {name: float(pos) for name, pos in zip(state.name, state.position)}
        q = [by_name[name] for name in ARM_JOINTS]
    except (KeyError, TypeError, ValueError):
        return None
    if not all(math.isfinite(x) for x in q):
        return None
    return q


def _step(node: Node, shared: Shared, warn: dict, output: dict | None) -> None:
    snap = shared.snapshot()
    if snap["latest_q"] is None:
        return

    if snap["following"] and snap["target"] is not None:
        raw = dict(zip(ARM_JOINTS, snap["target"]))
        clipped = clip_arm_positions(raw)
        cmd_q = [clipped[name] for name in ARM_JOINTS]
        if any(abs(clipped[name] - snap["target"][i]) > Q_TOL
               for i, name in enumerate(ARM_JOINTS)):
            now = time.monotonic()
            if now - warn["clamped_at"] > 2.0:
                warn["clamped_at"] = now
                detail = ", ".join(
                    f"J{i + 1}: {snap['target'][i]:+.3f}->{cmd_q[i]:+.3f}"
                    for i in range(7)
                    if abs(cmd_q[i] - snap["target"][i]) > Q_TOL
                )
                logger.warning("target out of joint limits, clamped: %s", detail)
    elif snap["holding"] and snap["cmd_q"] is not None:
        cmd_q = snap["cmd_q"]
    else:
        return

    node.send_output(
        "action",
        JointCommand(name=list(ARM_JOINTS), mode="position", position=cmd_q).to_arrow(),
    )
    with shared.lock:
        shared.cmd_q = list(cmd_q)

    if output is not None:
        now = time.monotonic()
        if now - output["last_at"] >= 1.0 / output["hz"]:
            output["last_at"] = now
            output["handle"].write(json.dumps({
                "t": round(now, 6),
                "cmd_q": [round(x, 6) for x in cmd_q],
                "measured_q": [round(x, 6) for x in snap["latest_q"]],
                "following": snap["following"],
                "holding": snap["holding"],
            }) + "\n")
            output["handle"].flush()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="lite-vr TCP -> Dora JointCommand 桥")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9001)
    parser.add_argument("--state-timeout", type=float, default=0.25,
                        help="实测状态视为新鲜的最大年龄 s")
    parser.add_argument("--output", default=None,
                        help="可选：按 --output-hz 写 command/measured 采样 JSONL")
    parser.add_argument("--output-hz", type=float, default=10.0)
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    shared = Shared()
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((args.host, args.port))
    server.listen(5)
    server.settimeout(0.5)
    threading.Thread(
        target=_serve, args=(server, shared, args.state_timeout), daemon=True
    ).start()
    logger.info("listening on %s:%d", args.host, args.port)

    output = None
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        output = {
            "handle": path.open("w", encoding="utf-8"),
            "hz": max(1.0, args.output_hz),
            "last_at": 0.0,
        }

    warn = {"clamped_at": 0.0}
    node = Node()
    logger.info("dora node ready, joint order %s", ARM_JOINTS)
    try:
        for event in node:
            if event["type"] in ("STOP", "ERROR"):
                break
            if event["type"] != "INPUT":
                continue
            if event["id"] == "state":
                q = _state_vector(event["value"])
                if q is not None:
                    shared.set_state(q)
                continue
            if event["id"] == "tick":
                _step(node, shared, warn, output)
    finally:
        server.close()
        if output is not None:
            output["handle"].close()
        snap = shared.snapshot()
        logger.info(
            "vr_bridge exit (following=%s holding=%s)", snap["following"], snap["holding"]
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
