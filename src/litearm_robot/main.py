"""节点入口。

无子命令 = 运行 Dora 机器人节点（标准输入 + `control` 扩展，见 node.py）。
probe = 只读状态，不进入 Dora，不做任何运动。
home = 独立回零，不进 Dora。
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from .config import load_config
from .driver import LitearmDriver
from .fake import FakeArm
from .gripper import NullGripper


def _make_driver(config_path: str | None, *, fake: bool = False) -> LitearmDriver:
    config = load_config(config_path)
    if fake:
        return LitearmDriver(config, arm=FakeArm(), gripper=NullGripper())
    return LitearmDriver(config)


def _run_node(
    config_path: str | None, *, fake: bool = False, debug: bool = False
) -> int:
    from .node import run_node

    driver = _make_driver(config_path, fake=fake)
    debug = debug or driver.config.debug
    logging.getLogger().setLevel(logging.DEBUG if debug else logging.INFO)
    driver.connect()
    try:
        return run_node(driver, debug=debug)
    finally:
        driver.disconnect()


def _probe(config_path: str | None, *, fake: bool = False) -> int:
    driver = _make_driver(config_path, fake=fake)
    driver.connect()
    try:
        state = driver.get_state()
        print(
            json.dumps(
                {
                    "name": state.name,
                    "position": state.position,
                    "velocity": state.velocity,
                    "effort": state.effort,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    finally:
        driver.disconnect()
    return 0


def _home(config_path: str | None, *, timeout: float, fake: bool = False) -> int:
    driver = _make_driver(config_path, fake=fake)
    driver.connect()
    try:
        driver.home(timeout=timeout)
        state = driver.get_state()
        print(
            json.dumps(
                {
                    "name": state.name,
                    "position": state.position,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    finally:
        driver.disconnect()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="robot-litearm")
    parser.add_argument("--config", default=None, help="YAML 配置文件路径")
    parser.add_argument("--debug", action="store_true")
    sub = parser.add_subparsers(dest="command")

    # 子命令的同名参数用 SUPPRESS：未显式提供时保留顶层值，避免顶层
    # `--config A.yaml run` 被解析成 None。
    run = sub.add_parser("run", help="运行 Dora 机器人节点")
    run.add_argument("--config", default=argparse.SUPPRESS)
    run.add_argument("--fake", action="store_true", help="使用 FakeArm")
    run.add_argument(
        "--debug", action="store_true", default=argparse.SUPPRESS, help="输出 DEBUG 日志"
    )

    probe = sub.add_parser("probe", help="只读状态，不运动")
    probe.add_argument("--config", default=argparse.SUPPRESS)
    probe.add_argument("--fake", action="store_true", help="使用 FakeArm")
    probe.add_argument(
        "--debug", action="store_true", default=argparse.SUPPRESS, help="输出 DEBUG 日志"
    )

    home = sub.add_parser("home", help="固件 home() 回零位（低速）")
    home.add_argument("--config", default=argparse.SUPPRESS)
    home.add_argument("--timeout", type=float, default=180.0)
    home.add_argument("--fake", action="store_true", help="使用 FakeArm")
    home.add_argument(
        "--debug", action="store_true", default=argparse.SUPPRESS, help="输出 DEBUG 日志"
    )

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.command == "probe":
        return _probe(args.config, fake=args.fake)
    if args.command == "home":
        return _home(args.config, timeout=args.timeout, fake=args.fake)
    if args.command == "run":
        return _run_node(args.config, fake=args.fake, debug=args.debug)
    return _run_node(
        args.config, fake=getattr(args, "fake", False), debug=args.debug
    )


if __name__ == "__main__":
    sys.exit(main())
