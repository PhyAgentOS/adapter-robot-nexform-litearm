#!/usr/bin/env python3
"""最小 MoveJoints 客户端：motion_server -> 轨迹控制器 -> 本仓机器人节点。

参考启动时的机器人状态，把指定关节当前角度 + delta 作为绝对目标，发一次
MoveJointsGoal；收到 result 后打印并退出。与 operator-motion 的
motion_action_client 不同，这里只做单次、小幅、可复现的验收动作。

输入：tick、joint_state、move_joints_feedback、move_joints_result
输出：move_joints_goal
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
import uuid

from dora import Node
from forge_msgs import JointState
from forge_msgs.motion import (
    MoveJointsFeedback,
    MoveJointsGoal,
    MoveJointsResult,
)

logger = logging.getLogger("joint_action_client")

ARM_JOINTS = [f"joint{i}" for i in range(1, 8)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--joint", default="joint7", help="要动的关节名")
    parser.add_argument("--delta", type=float, default=0.05, help="相对当前角度的增量 rad")
    parser.add_argument("--group", default="litearm_arm", help="motion_server 组名")
    parser.add_argument("--velocity-scale", type=float, default=0.2)
    parser.add_argument("--acceleration-scale", type=float, default=0.2)
    parser.add_argument("--delay", type=float, default=2.0, help="等待多少秒再下发")
    parser.add_argument("--timeout", type=float, default=20.0, help="等待 result 的秒数")
    args = parser.parse_args(argv)

    if args.joint not in ARM_JOINTS:
        parser.error(f"--joint 必须是 {ARM_JOINTS}")
    if not 0.0 < args.velocity_scale <= 1.0:
        parser.error("--velocity-scale 必须在 (0, 1]")
    if not 0.0 < args.acceleration_scale <= 1.0:
        parser.error("--acceleration-scale 必须在 (0, 1]")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    node = Node()
    started = time.monotonic()
    sent_at: float | None = None
    latest: JointState | None = None
    last_feedback = 0.0

    for event in node:
        if event["type"] in ("STOP", "ERROR"):
            break
        if event["type"] != "INPUT":
            continue

        if event["id"] == "joint_state":
            latest = JointState.from_arrow(event["value"])
            continue

        if event["id"] == "move_joints_feedback":
            feedback = MoveJointsFeedback.from_arrow(event["value"])
            now = time.monotonic()
            if now - last_feedback >= 1.0:
                last_feedback = now
                logger.info(
                    "feedback phase=%s progress=%s message=%s",
                    feedback.phase,
                    f"{feedback.progress:.2f}" if feedback.progress is not None else "-",
                    feedback.message,
                )
            continue

        if event["id"] == "move_joints_result":
            result = MoveJointsResult.from_arrow(event["value"])
            logger.info(
                "result error_code=%s message=%s elapsed=%.3fs",
                result.error_code,
                result.message,
                result.elapsed_ns / 1e9,
            )
            if result.joint_names:
                logger.info("  joints=%s", result.joint_names)
                logger.info("  final_positions=%s", [round(v, 4) for v in result.final_positions])
                logger.info(
                    "  final_errors=%s",
                    [round(v, 4) for v in result.final_position_errors],
                )
            return 0 if str(result.error_code) == "SUCCESS" else 1

        if event["id"] != "tick":
            continue

        now = time.monotonic()
        if sent_at is not None:
            if now - sent_at > args.timeout:
                logger.error("未收到 move_joints_result（超时 %.1fs）", args.timeout)
                return 1
            continue
        if latest is None or now - started < args.delay:
            continue

        if args.joint not in latest.name:
            logger.error("%s not in state names %s", args.joint, latest.name)
            return 1
        index = latest.name.index(args.joint)
        positions = []
        for name in ARM_JOINTS:
            if name not in latest.name:
                logger.error("state 缺少 %s", name)
                return 1
            positions.append(float(latest.position[latest.name.index(name)]))
        target = positions[ARM_JOINTS.index(args.joint)] + args.delta
        positions[ARM_JOINTS.index(args.joint)] = target

        goal = MoveJointsGoal(
            group_name=args.group,
            joint_names=list(ARM_JOINTS),
            positions=positions,
            velocity_scale=args.velocity_scale,
            acceleration_scale=args.acceleration_scale,
        )
        # motion_server 用 Arrow metadata 的 goal_id 关联 feedback/result。
        goal_id = str(uuid.uuid4())
        node.send_output(
            "move_joints_goal", goal.to_arrow(), metadata={"goal_id": goal_id}
        )
        sent_at = now
        logger.info(
            "sent MoveJointsGoal %s -> %.4f rad (current %.4f, goal_id=%s)",
            args.joint,
            target,
            latest.position[index],
            goal_id,
        )

        continue

    if sent_at is not None:
        logger.error("未收到 move_joints_result（超时 %.1fs）", args.timeout)
        return 1
    logger.info("joint_action_client exit, sent=%s", sent_at is not None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
