"""Dora 节点循环：标准机器人输入 + 本适配器的控制面扩展。

标准部分与 `forge_robot.node_runner.run_dora_robot_node` 语义一致：

- `tick`：读状态并输出 `state`
- `action` / `action/<source>`：稀疏 `JointCommand`
- `master_state`：leader `JointState` 镜像为位置命令

扩展部分：

- `action` 载荷可多带一个 float 列 `speed`（0..1），作为该条 movej 的 SDK 速度倍率。
- 输入 `control`：离散控制命令，见 control.py。
- 输出 `robot_status`：每 tick 的使能/模式/故障摘要（dataflow 声明了才发）。
- 输出 `control_status`：控制命令回执（dataflow 声明了才发，否则写日志）。

本模块不负责 connect/disconnect，由 main 管理。
"""

from __future__ import annotations

import logging
import queue
import threading
from typing import Any

import pyarrow as pa
from dora import Node
from forge_msgs import JointCommand, JointState
from forge_msgs.arrow import ensure_record_batch
from forge_robot.arrow_validation import (
    RobotArrowSchemaError,
    validate_robot_control_arrow,
)

from .control import ControlRequest, ControlStatus
from .driver import LitearmDriver, RobotStatus

logger = logging.getLogger(__name__)

#: 在节点线程直接执行的安全命令；其余命令进工作线程，避免 home 阻塞 tick。
INLINE_COMMANDS = frozenset({"emergency_stop", "disable"})


def _is_action_input(input_id: str) -> bool:
    return input_id == "action" or (
        input_id.startswith("action/") and len(input_id) > len("action/")
    )


def _declared_outputs(node: Node) -> set[str]:
    try:
        return set(node.node_config().get("outputs") or [])
    except Exception:
        logger.warning("无法读取 dataflow 的 outputs 声明，按空集合处理")
        return set()


def _read_speed_column(value: Any) -> float | None:
    batch = ensure_record_batch(value)
    if "speed" not in batch.schema.names:
        return None
    raw = batch["speed"][0].as_py()
    return None if raw is None else float(raw)


def _status_to_arrow(status: RobotStatus) -> pa.RecordBatch:
    return pa.RecordBatch.from_pydict(
        {
            "enabled": pa.array([status.enabled], type=pa.bool_()),
            "mode": pa.array([status.mode], type=pa.string()),
            "faulted": pa.array([status.faulted], type=pa.bool_()),
            "faults": pa.array([status.faults], type=pa.string()),
            "joint_fault": pa.array([status.joint_fault], type=pa.int64()),
        }
    )


def _execute_control(driver: LitearmDriver, request: ControlRequest) -> str:
    command = request.command
    if command == "home":
        driver.home(timeout=request.timeout_s)
        timeout = request.timeout_s or driver.config.home_timeout_s
        return f"home complete (timeout={timeout:g}s)"
    if command == "stop":
        driver.stop()
        return "pending targets cancelled; holding current pose"
    if command == "enable":
        driver.enable()
        return "enabled"
    if command == "disable":
        driver.disable()
        return "disabled"
    if command == "emergency_stop":
        driver.emergency_stop()
        return "emergency stop latched; reset required before enable"
    if command == "reset":
        driver.reset()
        return "faults reset"
    raise ValueError(f"unknown control command: {command!r}")


class _ControlExecutor:
    """串行执行耗时控制命令；home 十几秒，不能占用 tick 线程。"""

    def __init__(
        self,
        driver: LitearmDriver,
        results: queue.Queue[ControlStatus],
    ) -> None:
        self._driver = driver
        self._results = results
        self._queue: queue.Queue[ControlRequest] = queue.Queue(maxsize=1)
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run, name="litearm-control", daemon=True
        )
        self._thread.start()

    def submit(self, request: ControlRequest) -> bool:
        try:
            self._queue.put_nowait(request)
        except queue.Full:
            return False
        return True

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                request = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                message = _execute_control(self._driver, request)
                status = "done"
            except Exception as error:
                message = str(error) or type(error).__name__
                status = "error"
                logger.exception("control %s failed", request.command)
            self._results.put(
                ControlStatus(
                    command=request.command,
                    request_id=request.request_id,
                    status=status,
                    message=message,
                )
            )

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2.0)


def _flush_statuses(
    node: Node,
    results: queue.Queue[ControlStatus],
    outputs: set[str],
) -> None:
    while True:
        try:
            status = results.get_nowait()
        except queue.Empty:
            return
        if "control_status" in outputs:
            node.send_output("control_status", status.to_arrow())
        else:
            level = (
                logging.ERROR
                if status.status in ("error", "rejected")
                else logging.INFO
            )
            logger.log(
                level,
                "control %s %s: %s",
                status.command,
                status.status,
                status.message,
            )


def _handle_tick(
    node: Node,
    driver: LitearmDriver,
    outputs: set[str],
    debug: bool,
) -> None:
    state, status = driver.snapshot()
    node.send_output("state", state.to_arrow())
    if "robot_status" in outputs:
        node.send_output("robot_status", _status_to_arrow(status))
    if debug:
        sample = {
            name: float(state.to_np([name], "position")[0])
            for name in driver.joint_order[:3]
            if name in state.name
        }
        logger.debug(
            "tick state sample=%s enabled=%s mode=%s faults=%s",
            sample,
            status.enabled,
            status.mode,
            status.faults or "-",
        )


def _handle_action(
    driver: LitearmDriver,
    value: Any,
    debug: bool,
) -> None:
    try:
        validate_robot_control_arrow(value, driver.joint_order)
    except RobotArrowSchemaError as error:
        logger.error("忽略 action（Arrow schema）: %s", error)
        return

    command = JointCommand.from_arrow(value)
    try:
        speed = _read_speed_column(value)
        driver.set_command(command, speed=speed)
    except Exception as error:
        logger.error("拒绝 action: %s", error)
        return

    if debug:
        sample = {
            name: float(command.to_np([name], "position")[0])
            for name in driver.joint_order[:3]
            if name in command.name
        }
        logger.debug("收到 action sample=%s speed=%s", sample, speed)


def _handle_master_state(driver: LitearmDriver, value: Any, debug: bool) -> None:
    try:
        master = JointState.from_arrow(value)
        command = JointCommand(
            name=master.name,
            mode="position",
            position=master.position,
        )
        driver.set_command(command)
    except Exception as error:
        logger.error("拒绝 master_state: %s", error)
        return

    if debug:
        sample = {
            name: float(command.to_np([name], "position")[0])
            for name in driver.joint_order[:3]
            if name in command.name
        }
        logger.debug("收到 master_state，镜像为 command sample=%s", sample)


def _handle_control(
    driver: LitearmDriver,
    executor: _ControlExecutor,
    results: queue.Queue[ControlStatus],
    value: Any,
    debug: bool,
) -> None:
    try:
        request = ControlRequest.from_arrow(value)
    except Exception as error:
        logger.error("拒绝 control: %s", error)
        results.put(
            ControlStatus(
                command="",
                status="rejected",
                message=str(error),
            )
        )
        return

    if debug:
        logger.debug(
            "收到 control command=%s request_id=%r timeout_s=%s",
            request.command,
            request.request_id,
            request.timeout_s,
        )

    if request.command in INLINE_COMMANDS:
        try:
            message = _execute_control(driver, request)
            status = "done"
        except Exception as error:
            message = str(error) or type(error).__name__
            status = "error"
            logger.exception("control %s failed", request.command)
        results.put(
            ControlStatus(
                command=request.command,
                request_id=request.request_id,
                status=status,
                message=message,
            )
        )
        return

    if executor.submit(request):
        results.put(
            ControlStatus(
                command=request.command,
                request_id=request.request_id,
                status="accepted",
                message="queued",
            )
        )
    else:
        results.put(
            ControlStatus(
                command=request.command,
                request_id=request.request_id,
                status="rejected",
                message="another control command is running",
            )
        )


def run_node(driver: LitearmDriver, *, debug: bool = False) -> int:
    node = Node()
    outputs = _declared_outputs(node)
    results: queue.Queue[ControlStatus] = queue.Queue()
    executor = _ControlExecutor(driver, results)

    try:
        for event in node:
            kind = event.get("kind")
            if kind not in (None, "dora"):
                continue

            match event.get("type"):
                case "INPUT":
                    input_id = event["id"]
                    value = event.get("value")
                    if input_id == "tick":
                        _handle_tick(node, driver, outputs, debug)
                    elif input_id == "control":
                        _handle_control(
                            driver, executor, results, value, debug
                        )
                    elif _is_action_input(input_id):
                        _handle_action(driver, value, debug)
                    elif input_id == "master_state":
                        _handle_master_state(driver, value, debug)
                    elif input_id == "locomotion_command":
                        logger.warning("忽略 locomotion_command：本驱动不支持底盘")
                    else:
                        logger.debug("忽略未知输入 %s", input_id)
                    _flush_statuses(node, results, outputs)
                case "STOP":
                    break
                case "ERROR":
                    logger.error(
                        "节点收到 ERROR: %s", event.get("error", "unknown")
                    )
                    break
                case _:
                    pass
    finally:
        executor.close()
    return 0
