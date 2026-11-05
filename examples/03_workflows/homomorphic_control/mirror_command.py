#!/usr/bin/env python3
"""主臂 JointState -> 从臂 JointCommand(position)，供仿真链路使用。

转换语义与 `forge_robot.node_runner._joint_state_to_command` 一致：
name / position 原样传递，mode 固定 position。真机链路由标准 runner 内建，
不需要本节点。
"""

from __future__ import annotations

import logging
import sys

from dora import Node
from forge_msgs import JointCommand, JointState

logger = logging.getLogger("mirror_command")


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    node = Node()
    count = 0

    for event in node:
        if event["type"] in ("STOP", "ERROR"):
            break
        if event["type"] != "INPUT" or event["id"] != "master":
            continue

        master = JointState.from_arrow(event["value"])
        command = JointCommand(
            name=list(master.name),
            mode="position",
            position=[float(v) for v in master.position],
            velocity=[],
            effort=[],
            kp=[],
            kd=[],
        )
        node.send_output("action", command.to_arrow())
        count += 1

    logger.info("mirror_command exit, forwarded=%d", count)
    return 0


if __name__ == "__main__":
    sys.exit(main())
