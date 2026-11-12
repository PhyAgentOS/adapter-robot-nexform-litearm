"""TCP/JSON 桥接节点：给 Forge Skill Gateway 等非 Python 调用方用。

拓扑：本节点与机器人节点同在一个 dataflow 里。

- 订阅 `state` / `robot_status` / `control_status`
- 发布 `action`（稀疏 `JointCommand`）与 `control`（`ControlRequest`）
- 在 TCP 上提供一行一个 JSON 的请求/响应接口

设计约束：

- 只有 Dora 事件循环线程调用 `node.send_output`；TCP 客户端线程把待发消息
  放进 outbox，由事件循环在每次事件后 pump 出去。
- `movej` 是阻塞语义：下发后轮询 `state`，直到所有关节进入容差或超时，
  避免调用方以为到位而实际仍在运动。
- `home` 等耗时命令通过 `control_status` 回执等待，用内部生成的
  `request_id` 关联，调用方不必理解 Dora。
- 只读命令（`state`/`status`/`ping`）不触碰机器人。

协议（请求 -> 响应，均为单行 JSON）：

    {"cmd":"state"}                                  -> q/gripper_m/age_s/robot
    {"cmd":"movej","q":[7 floats],"speed":0.1}       -> ok/settled/elapsed_s
    {"cmd":"gripper","opening_m":0.06}               -> ok/opening_m
    {"cmd":"home","timeout_s":120}                   -> ok/status/message
    {"cmd":"stop"} / {"cmd":"enable"} / ...          -> ok/status/message
    {"cmd":"estop"}                                  -> 等价 emergency_stop
    {"cmd":"ping"}                                   -> ok/pong

所有响应都会回显可选字段 `id`（别名 `request_id`）。
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
from dataclasses import dataclass, field
from typing import Any

import pyarrow as pa
from dora import Node
from forge_msgs import JointCommand, JointState
from forge_msgs.arrow import ensure_record_batch

from .codec import (
    ARM_JOINTS,
    GRIPPER,
    GRIPPER_MAX_M,
    clip_arm_positions,
    clip_gripper_opening,
)
from .control import ControlRequest

logger = logging.getLogger(__name__)

MAX_LINE = 64 * 1024
"""单行 JSON 上限；超过即断开，避免客户端把桥当字节流。"""

CONTROL_CLIENT_COMMANDS = frozenset(
    {
        "home",
        "stop",
        "enable",
        "disable",
        "reset",
        "estop",
        "emergency_stop",
    }
)
CONTROL_ALIASES = {"estop": "emergency_stop"}

#: `control_status` 里只有这些是终态；`accepted` 只代表已排队。
FINAL_STATUSES = frozenset({"done", "rejected", "error"})


@dataclass(frozen=True)
class BridgeOptions:
    host: str = "127.0.0.1"
    port: int = 9005
    state_timeout: float = 0.5
    settle_tol: float = 0.01
    settle_timeout: float = 20.0
    control_timeout: float = 10.0
    home_timeout: float = 180.0
    dispatch_timeout: float = 2.0
    poll_period: float = 0.02
    #: 与 robot 配置的 gripper.max_opening_m 保持一致。
    max_opening_m: float = GRIPPER_MAX_M


@dataclass
class _Outbound:
    output_id: str
    batch: pa.RecordBatch
    sent: threading.Event = field(default_factory=threading.Event)
    error: str | None = None


@dataclass
class _Waiter:
    event: threading.Event = field(default_factory=threading.Event)
    status: str = ""
    message: str = ""


def _column(value: Any, name: str) -> str:
    if name not in value.schema.names:
        return ""
    raw = value[name][0].as_py()
    return "" if raw is None else str(raw)


def _finite_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} 必须是数字")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} 必须是有限数")
    return number


def _parse_status(batch: pa.RecordBatch) -> dict[str, Any]:
    def py(name: str, default: Any) -> Any:
        if name not in batch.schema.names:
            return default
        raw = batch[name][0].as_py()
        return default if raw is None else raw

    return {
        "enabled": bool(py("enabled", False)),
        "mode": str(py("mode", "")),
        "faulted": bool(py("faulted", False)),
        "faults": str(py("faults", "")),
        "joint_fault": int(py("joint_fault", 0)),
    }


class Bridge:
    """跨线程共享的状态缓存、outbox 与回执等待表。"""

    def __init__(self, options: BridgeOptions | None = None) -> None:
        self.options = options or BridgeOptions()
        self._lock = threading.Lock()
        self._state: JointState | None = None
        self._state_at: float | None = None
        self._robot: dict[str, Any] = {}

        self._outbox: list[_Outbound] = []
        self._outbox_cond = threading.Condition(self._lock)

        self._waiters: dict[str, _Waiter] = {}
        self._closed = False
        self._counter = 0

    # ------------------------------------------------------------- state cache

    def set_state(self, state: JointState) -> None:
        with self._lock:
            self._state = state
            self._state_at = time.monotonic()

    def set_robot_status(self, value: Any) -> None:
        status = _parse_status(ensure_record_batch(value))
        with self._lock:
            self._robot = status

    def state_age(self) -> float | None:
        with self._lock:
            if self._state_at is None:
                return None
            return time.monotonic() - self._state_at

    def positions(self, *, since: float | None = None) -> dict[str, float] | None:
        """返回 name->position；`since` 用于要求命令之后的新鲜状态。"""
        with self._lock:
            state = self._state
            state_at = self._state_at
        if state is None or state_at is None:
            return None
        if since is not None and state_at < since:
            return None
        return {
            str(name): float(value)
            for name, value in zip(state.name, state.position, strict=True)
        }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            state = self._state
            state_at = self._state_at
            robot = dict(self._robot)
        age = None if state_at is None else time.monotonic() - state_at
        payload: dict[str, Any] = {"valid": age is not None and age <= self.options.state_timeout}
        if state is None or age is None:
            payload.update({"q": None, "gripper_m": None, "age_s": None})
        else:
            positions = {
                str(name): float(value)
                for name, value in zip(state.name, state.position, strict=True)
            }
            missing = [name for name in ARM_JOINTS if name not in positions]
            if missing:
                payload.update(
                    {
                        "valid": False,
                        "q": None,
                        "gripper_m": positions.get(GRIPPER),
                        "age_s": age,
                        "error": f"state 缺少关节 {missing}",
                    }
                )
            else:
                payload.update(
                    {
                        "q": [positions[name] for name in ARM_JOINTS],
                        "gripper_m": positions.get(GRIPPER),
                        "age_s": age,
                    }
                )
        payload.update(robot)
        return payload

    # ---------------------------------------------------------------- outbox

    def submit_output(self, output_id: str, batch: pa.RecordBatch) -> _Outbound:
        outbound = _Outbound(output_id=output_id, batch=batch)
        with self._outbox_cond:
            if self._closed:
                outbound.error = "bridge closed"
                outbound.sent.set()
                return outbound
            self._outbox.append(outbound)
        return outbound

    def pump(self, node: Node) -> None:
        """在 Dora 事件循环里调用，把 outbox 里的消息真正发出去。"""
        with self._outbox_cond:
            pending, self._outbox = self._outbox, []
        for outbound in pending:
            try:
                node.send_output(outbound.output_id, outbound.batch)
            except Exception as error:  # noqa: BLE001 - 上报给等待方
                outbound.error = str(error) or type(error).__name__
                logger.exception("发送 %s 失败", outbound.output_id)
            finally:
                outbound.sent.set()

    # ------------------------------------------------------------- waiters

    def next_request_id(self, command: str) -> str:
        with self._lock:
            self._counter += 1
            return f"bridge-{command}-{self._counter}"

    def expect_status(self, request_id: str) -> _Waiter:
        waiter = _Waiter()
        with self._lock:
            if self._closed:
                waiter.status = "closed"
                waiter.message = "bridge closed"
                waiter.event.set()
            else:
                self._waiters[request_id] = waiter
        return waiter

    def abandon(self, request_id: str) -> None:
        with self._lock:
            self._waiters.pop(request_id, None)

    def on_control_status(self, value: Any) -> None:
        batch = ensure_record_batch(value)
        request_id = _column(batch, "request_id")
        if not request_id:
            return
        status = _column(batch, "status")
        with self._lock:
            waiter = self._waiters.get(request_id)
            if waiter is None:
                return
            if status not in FINAL_STATUSES:
                return
            self._waiters.pop(request_id, None)
        waiter.status = status
        waiter.message = _column(batch, "message")
        waiter.event.set()

    def close(self) -> None:
        with self._outbox_cond:
            self._closed = True
            pending, self._outbox = self._outbox, []
            waiters = list(self._waiters.values())
            self._waiters.clear()
        for outbound in pending:
            outbound.error = "bridge closed"
            outbound.sent.set()
        for waiter in waiters:
            waiter.status = "closed"
            waiter.message = "bridge closed"
            waiter.event.set()


# ---------------------------------------------------------------- requests


def _echo_id(msg: dict[str, Any]) -> str:
    value = msg.get("request_id", msg.get("id", ""))
    return "" if value is None else str(value)


def _dispatch_state(bridge: Bridge, msg: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, "cmd": str(msg.get("cmd")), **bridge.snapshot()}


def _dispatch_movej(
    bridge: Bridge, msg: dict[str, Any], options: BridgeOptions
) -> dict[str, Any]:
    raw_q = msg.get("q")
    if not isinstance(raw_q, (list, tuple)) or len(raw_q) != len(ARM_JOINTS):
        raise ValueError(f"q 必须是 {len(ARM_JOINTS)} 个数字的数组")
    targets = {
        name: _finite_number(value, f"q[{index}]")
        for index, (name, value) in enumerate(zip(ARM_JOINTS, raw_q, strict=True))
    }
    clipped = clip_arm_positions(targets)
    clipped_flag = any(
        abs(clipped[name] - targets[name]) > 1e-12 for name in ARM_JOINTS
    )

    speed: float | None = None
    if msg.get("speed") is not None:
        speed = _finite_number(msg["speed"], "speed")
        if speed < 0.0:
            raise ValueError("speed 必须 >= 0")
        if speed > 1.0:
            speed = 1.0

    command = JointCommand(
        name=list(ARM_JOINTS),
        mode="position",
        position=[clipped[name] for name in ARM_JOINTS],
    )
    batch = command.to_arrow()
    if speed is not None:
        batch = batch.append_column(
            "speed", pa.array([speed], type=pa.float64())
        )

    wait = bool(msg.get("wait", True))
    send_at = time.monotonic()
    outbound = bridge.submit_output("action", batch)
    if not outbound.sent.wait(options.dispatch_timeout):
        raise RuntimeError("Dora 事件循环未取走 action（检查 dataflow 是否在运行）")
    if outbound.error:
        raise RuntimeError(f"发送 action 失败：{outbound.error}")

    result: dict[str, Any] = {
        "ok": True,
        "cmd": "movej",
        "settled": None,
        "elapsed_s": None,
        "target_q": [clipped[name] for name in ARM_JOINTS],
        "clipped": clipped_flag,
        "speed": speed,
    }
    if not wait:
        return result

    timeout = options.settle_timeout
    if msg.get("timeout_s") is not None:
        timeout = _finite_number(msg["timeout_s"], "timeout_s")
        if timeout <= 0.0:
            raise ValueError("timeout_s 必须 > 0")

    deadline = send_at + timeout
    while time.monotonic() < deadline:
        positions = bridge.positions(since=send_at)
        if positions is not None and all(
            name in positions
            and abs(positions[name] - clipped[name]) <= options.settle_tol
            for name in ARM_JOINTS
        ):
            result["settled"] = True
            result["elapsed_s"] = time.monotonic() - send_at
            return result
        time.sleep(options.poll_period)

    result["ok"] = False
    result["settled"] = False
    result["elapsed_s"] = time.monotonic() - send_at
    result["error"] = f"movej 在 {timeout:g}s 内未到位"
    return result


def _dispatch_gripper(
    bridge: Bridge, msg: dict[str, Any], options: BridgeOptions
) -> dict[str, Any]:
    raw = msg.get("opening_m", msg.get("position_m"))
    if raw is None:
        raise ValueError("缺少 opening_m")
    opening = _finite_number(raw, "opening_m")
    clipped = clip_gripper_opening(opening, options.max_opening_m)
    command = JointCommand(
        name=[GRIPPER], mode="position", position=[clipped]
    )
    outbound = bridge.submit_output("action", command.to_arrow())
    if not outbound.sent.wait(options.dispatch_timeout):
        raise RuntimeError("Dora 事件循环未取走 action（检查 dataflow 是否在运行）")
    if outbound.error:
        raise RuntimeError(f"发送 action 失败：{outbound.error}")
    return {
        "ok": True,
        "cmd": "gripper",
        "opening_m": clipped,
        "clipped": abs(clipped - opening) > 1e-12,
        "max_opening_m": options.max_opening_m,
    }


def _dispatch_control(
    bridge: Bridge, msg: dict[str, Any], options: BridgeOptions
) -> dict[str, Any]:
    client_command = str(msg.get("cmd"))
    command = CONTROL_ALIASES.get(client_command, client_command)
    timeout_s: float | None = None
    if msg.get("timeout_s") is not None:
        timeout_s = _finite_number(msg["timeout_s"], "timeout_s")
        if timeout_s <= 0.0:
            raise ValueError("timeout_s 必须 > 0")
    elif command == "home":
        timeout_s = options.home_timeout

    request_id = bridge.next_request_id(client_command)
    waiter = bridge.expect_status(request_id)
    request = ControlRequest(
        command=command, request_id=request_id, timeout_s=timeout_s
    )
    outbound = bridge.submit_output("control", request.to_arrow())
    if not outbound.sent.wait(options.dispatch_timeout):
        bridge.abandon(request_id)
        raise RuntimeError("Dora 事件循环未取走 control（检查 dataflow 是否在运行）")
    if outbound.error:
        bridge.abandon(request_id)
        raise RuntimeError(f"发送 control 失败：{outbound.error}")

    if command == "home":
        wait_timeout = (timeout_s or options.home_timeout) + 5.0
    else:
        wait_timeout = options.control_timeout
    completed = waiter.event.wait(wait_timeout)
    if not completed:
        bridge.abandon(request_id)
        return {
            "ok": False,
            "cmd": client_command,
            "status": "timeout",
            "message": f"{command} 在 {wait_timeout:g}s 内没有回执",
        }
    return {
        "ok": waiter.status == "done",
        "cmd": client_command,
        "status": waiter.status or "closed",
        "message": waiter.message,
        "command": command,
    }


def handle_request(
    bridge: Bridge, msg: Any, options: BridgeOptions | None = None
) -> dict[str, Any]:
    """处理一条已解析的请求，返回响应 dict。"""
    options = options or bridge.options
    if not isinstance(msg, dict):
        return {"ok": False, "error": "请求必须是 JSON 对象"}

    command = msg.get("cmd")
    request_id = _echo_id(msg)
    base: dict[str, Any] = {"cmd": command}
    if request_id:
        base["id"] = request_id

    try:
        if command in ("state", "status"):
            response = _dispatch_state(bridge, msg)
        elif command == "ping":
            response = {"ok": True, "cmd": "ping", "pong": True}
        elif command == "movej":
            response = _dispatch_movej(bridge, msg, options)
        elif command == "gripper":
            response = _dispatch_gripper(bridge, msg, options)
        elif command in CONTROL_CLIENT_COMMANDS:
            response = _dispatch_control(bridge, msg, options)
        else:
            return {**base, "ok": False, "error": f"未知命令 {command!r}"}
    except Exception as error:  # noqa: BLE001 - 协议层统一转为 JSON
        logger.warning("处理请求 %r 失败: %s", command, error)
        return {**base, "ok": False, "error": str(error) or type(error).__name__}

    return {**base, **response}


def handle_line(
    bridge: Bridge, raw_line: bytes | str, options: BridgeOptions | None = None
) -> dict[str, Any]:
    """把一行字节解析成请求并处理；任何异常都变成 `ok: false` 响应。"""
    try:
        text = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
        msg = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        return {"ok": False, "error": f"JSON 解析失败: {error}"}
    return handle_request(bridge, msg, options)


# ------------------------------------------------------------------ server


class BridgeServer:
    """单行 JSON 的 TCP 服务；每条连接一个 daemon 线程。"""

    def __init__(self, bridge: Bridge, options: BridgeOptions | None = None) -> None:
        self.bridge = bridge
        self.options = options or bridge.options
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._conns: set[threading.Thread] = set()
        self._conns_lock = threading.Lock()

    def start(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.options.host, self.options.port))
        sock.listen(5)
        sock.settimeout(0.5)
        self._sock = sock
        self._thread = threading.Thread(
            target=self._accept_loop, name="litearm-bridge", daemon=True
        )
        self._thread.start()
        logger.info(
            "forge_bridge 监听 %s:%d", self.options.host, self.options.port
        )

    @property
    def bound_port(self) -> int | None:
        if self._sock is None:
            return None
        return int(self._sock.getsockname()[1])

    def _accept_loop(self) -> None:
        assert self._sock is not None
        while not self._stop.is_set():
            try:
                conn, address = self._sock.accept()
            except socket.timeout:
                continue
            except OSError as error:
                if not self._stop.is_set():
                    logger.error("accept 失败: %s", error)
                return
            thread = threading.Thread(
                target=self._serve_conn,
                args=(conn, address),
                name=f"litearm-bridge-{address[1]}",
                daemon=True,
            )
            with self._conns_lock:
                self._conns.add(thread)
            thread.start()

    def _serve_conn(self, conn: socket.socket, address: tuple[str, int]) -> None:
        logger.debug("客户端连接 %s:%s", *address)
        buffer = b""
        try:
            conn.settimeout(0.5)
            while not self._stop.is_set():
                try:
                    chunk = conn.recv(4096)
                except socket.timeout:
                    continue
                except OSError:
                    break
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if not line.strip():
                        continue
                    response = handle_line(self.bridge, line, self.options)
                    conn.sendall(
                        json.dumps(response, ensure_ascii=False).encode("utf-8")
                        + b"\n"
                    )
                if len(buffer) > MAX_LINE:
                    response = {
                        "ok": False,
                        "error": f"行长度超过 {MAX_LINE} 字节",
                    }
                    conn.sendall(
                        json.dumps(response, ensure_ascii=False).encode("utf-8")
                        + b"\n"
                    )
                    break
        except OSError as error:
            logger.warning("客户端 %s:%s 断开: %s", *address, error)
        finally:
            try:
                conn.close()
            except OSError:
                pass
            with self._conns_lock:
                self._conns.discard(threading.current_thread())
            logger.debug("客户端 %s:%s 关闭", *address)

    def close(self) -> None:
        self._stop.set()
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
        if self._thread is not None:
            self._thread.join(timeout=2.0)


# -------------------------------------------------------------------- node


def run_bridge(
    options: BridgeOptions | None = None, *, debug: bool = False
) -> int:
    options = options or BridgeOptions()
    bridge = Bridge(options)
    server = BridgeServer(bridge, options)
    server.start()

    node = Node()
    try:
        for event in node:
            kind = event.get("kind")
            if kind not in (None, "dora"):
                continue

            match event.get("type"):
                case "INPUT":
                    input_id = event["id"]
                    value = event.get("value")
                    if input_id == "state":
                        try:
                            state = JointState.from_arrow(value)
                        except Exception as error:  # noqa: BLE001
                            logger.warning("忽略 state: %s", error)
                        else:
                            bridge.set_state(state)
                            if debug:
                                logger.debug(
                                    "state age=%.3fs joints=%d",
                                    bridge.state_age() or 0.0,
                                    len(state.name),
                                )
                    elif input_id == "robot_status":
                        try:
                            bridge.set_robot_status(value)
                        except Exception as error:  # noqa: BLE001
                            logger.warning("忽略 robot_status: %s", error)
                    elif input_id == "control_status":
                        try:
                            bridge.on_control_status(value)
                        except Exception as error:  # noqa: BLE001
                            logger.warning("忽略 control_status: %s", error)
                    else:
                        logger.debug("忽略未知输入 %s", input_id)
                case "STOP":
                    break
                case "ERROR":
                    logger.error(
                        "节点收到 ERROR: %s", event.get("error", "unknown")
                    )
                    break
                case _:
                    pass
            bridge.pump(node)
    finally:
        server.close()
        bridge.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="robot-litearm-bridge")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9005)
    parser.add_argument("--state-timeout", type=float, default=0.5)
    parser.add_argument("--settle-tol", type=float, default=0.01)
    parser.add_argument("--settle-timeout", type=float, default=20.0)
    parser.add_argument("--control-timeout", type=float, default=10.0)
    parser.add_argument("--home-timeout", type=float, default=180.0)
    parser.add_argument(
        "--max-opening-m",
        type=float,
        default=GRIPPER_MAX_M,
        help="夹爪最大开口（m），应与 robot 配置一致",
    )
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args(argv)
    if not 0.0 < args.max_opening_m <= GRIPPER_MAX_M:
        parser.error(
            f"--max-opening-m must be in (0, {GRIPPER_MAX_M}], "
            f"got {args.max_opening_m}"
        )

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if args.host not in ("127.0.0.1", "localhost", "::1"):
        logger.warning(
            "forge_bridge 绑定非回环地址 %s；协议无鉴权，仅限可信网络",
            args.host,
        )

    options = BridgeOptions(
        host=args.host,
        port=args.port,
        state_timeout=args.state_timeout,
        settle_tol=args.settle_tol,
        settle_timeout=args.settle_timeout,
        control_timeout=args.control_timeout,
        home_timeout=args.home_timeout,
        max_opening_m=args.max_opening_m,
    )
    try:
        return run_bridge(options, debug=args.debug)
    except OSError as error:
        logger.error("启动失败: %s", error)
        return 1


if __name__ == "__main__":
    sys.exit(main())
