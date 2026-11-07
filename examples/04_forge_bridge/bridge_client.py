#!/usr/bin/env python3
"""forge_bridge 的最小 TCP/JSON 客户端。

两种用法：

    python bridge_client.py                  # 交互式 REPL
    python bridge_client.py state            # 单条命令，打印响应后退出
    python bridge_client.py movej 0 0 0 0 0 0 0 --speed 0.2

交互命令：

    state | status
    movej <7 个弧度> [speed=0.2] [timeout=20] [nowait]
    gripper <开口 m>
    home [timeout=180]
    enable | disable | reset | stop | estop | ping
    help | quit
"""

from __future__ import annotations

import argparse
import json
import shlex
import socket
import sys

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9005


class Client:
    def __init__(self, host: str, port: int, timeout: float = 240.0) -> None:
        self._sock = socket.create_connection((host, port), timeout=timeout)
        self._reader = self._sock.makefile("rb")

    def request(self, payload: dict) -> dict:
        self._sock.sendall(
            json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\n"
        )
        line = self._reader.readline()
        if not line:
            raise ConnectionError("bridge 关闭了连接")
        return json.loads(line)

    def close(self) -> None:
        try:
            self._reader.close()
        finally:
            self._sock.close()


def _parse_repl_line(line: str) -> dict | None:
    """把一行 REPL 文本转成请求；`None` 表示退出。"""
    parts = shlex.split(line)
    if not parts:
        return None
    command = parts[0].lower()
    if command in ("quit", "exit"):
        return None
    if command == "help":
        print(__doc__)
        return None

    request: dict = {"cmd": command}
    if command == "movej":
        values: list[float] = []
        for part in parts[1:]:
            if "=" in part:
                key, _, raw = part.partition("=")
                if key in ("speed", "timeout"):
                    request[key] = float(raw)
                elif key == "nowait":
                    request["wait"] = False
                else:
                    raise ValueError(f"未知参数 {key}")
            elif part == "nowait":
                request["wait"] = False
            else:
                values.append(float(part))
        if len(values) != 7:
            raise ValueError("movej 需要 7 个关节角（rad）")
        request["q"] = values
    elif command == "gripper":
        if len(parts) != 2:
            raise ValueError("gripper 需要一个开口值（m）")
        request["opening_m"] = float(parts[1])
    elif command == "home" and len(parts) > 1:
        request["timeout_s"] = float(parts[1])
    elif command not in (
        "state",
        "status",
        "home",
        "enable",
        "disable",
        "reset",
        "stop",
        "estop",
        "ping",
    ):
        raise ValueError(f"未知命令 {command}")
    return request


def _print(response: dict) -> None:
    print(json.dumps(response, ensure_ascii=False, indent=2))


def _run_repl(client: Client) -> int:
    print("forge_bridge REPL，输入 help 查看命令，quit 退出。")
    while True:
        try:
            line = input("bridge> ")
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        try:
            request = _parse_repl_line(line)
        except ValueError as error:
            print(f"参数错误: {error}")
            continue
        if request is None:
            if line.strip().lower() in ("quit", "exit"):
                return 0
            continue
        try:
            _print(client.request(request))
        except (OSError, ConnectionError, json.JSONDecodeError) as error:
            print(f"请求失败: {error}")
            return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="forge_bridge TCP 客户端")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    # 单条命令的 socket 超时；home 默认 180 s，所以留足余量。
    parser.add_argument("--timeout", type=float, default=240.0)
    parser.add_argument("command", nargs="?", help="单条命令；缺省进入 REPL")
    parser.add_argument("values", nargs="*", help="命令参数")
    parser.add_argument("--speed", type=float, default=None)
    parser.add_argument("--opening", type=float, default=None)
    parser.add_argument("--settle-timeout", type=float, default=None)
    parser.add_argument("--no-wait", action="store_true")
    args = parser.parse_args(argv)

    try:
        client = Client(args.host, args.port, args.timeout)
    except OSError as error:
        print(f"连接 {args.host}:{args.port} 失败: {error}", file=sys.stderr)
        return 1

    try:
        if args.command is None:
            return _run_repl(client)

        parts = [args.command, *args.values]
        if args.speed is not None:
            parts.append(f"speed={args.speed}")
        if args.settle_timeout is not None:
            parts.append(f"timeout={args.settle_timeout}")
        if args.no_wait:
            parts.append("nowait")
        if args.opening is not None:
            parts.insert(1, str(args.opening))

        try:
            request = _parse_repl_line(" ".join(parts))
        except ValueError as error:
            print(f"参数错误: {error}", file=sys.stderr)
            return 2
        if request is None:
            return 0
        response = client.request(request)
        _print(response)
        return 0 if response.get("ok") else 1
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
