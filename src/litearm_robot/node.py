"""Dora 节点循环：标准机器人输入 + 本适配器的控制面扩展。

本模块**复刻**自 `forge_robot.node_runner.run_dora_robot_node`（基线
forge_robot 1.0.1），因为标准 runner 没有挂载扩展输入的入口。以下标准语义
保持一致：

- `tick`：读状态并输出 `state`，随后调用 `on_tick_after_state`
- `action` / `action/<source>`：稀疏 `JointCommand`
- `master_state`：leader `JointState` 镜像为位置命令
- `action` / `master_state` 仅在 `is_follower=True` 时下发
- `joint_order` 为空时拒绝并记 error
- Arrow 校验可通过 `validate_control_arrow` / `strict_extra_arrow_columns` 配置
- external subscriptions 经 `merge_external_events` 合并，事件交给
  `on_external_event`
- 未知输入忽略；`STOP` / `ERROR` 结束循环

与标准 runner 的有意差异：

- 新增 `control` 输入：离散控制命令，见 control.py。
- 新增 `robot_status` / `control_status` 输出，仅当 dataflow 声明时发送。
- `action` 载荷可多带一个 float 列 `speed`（0..1），作为该条 movej 的 SDK
  速度倍率；默认非 strict 校验正是为了放行这一扩展列。
- `set_command()` 的异常不向上传播：记录日志并投递一条 `control_status`
  rejected 回执，节点继续运行。标准 runner 会让异常终止循环。
- 本模块不负责 connect/disconnect，由 main 管理；标准 runner 会在 finally
  中调用 `driver.disconnect()`。
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


def _has_joint_order(input_id: str, joint_order: list[str]) -> bool:
    """与标准 runner 一致：关节表为空时拒绝下发。"""
    if joint_order:
        return True
    logger.error("忽略 %s：joint_order 不能为空", input_id)
    return False


def _reject(
    results: queue.Queue[ControlStatus], command: str, error: Exception
) -> None:
    """把被拒绝的输入变成可观测的 control_status 回执。"""
    results.put(
        ControlStatus(
            command=command,
            status="rejected",
            message=str(error) or type(error).__name__,
        )
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
    joint_order: list[str],
    debug: bool,
    on_tick_after_state=None,
) -> None:
    state, status = driver.snapshot()
    node.send_output("state", state.to_arrow())
    if "robot_status" in outputs:
        node.send_output("robot_status", _status_to_arrow(status))
    if debug:
        sample = {
            name: float(state.to_np([name], "position")[0])
            for name in joint_order[:3]
            if name in state.name
        }
        logger.debug(
            "tick state sample=%s enabled=%s mode=%s faults=%s",
            sample,
            status.enabled,
            status.mode,
            status.faults or "-",
        )
    if on_tick_after_state is not None:
        on_tick_after_state(node, driver)


def _handle_action(
    driver: LitearmDriver,
    value: Any,
    results: queue.Queue[ControlStatus],
    joint_order: list[str],
    debug: bool,
    *,
    validate_control_arrow: bool = True,
    strict_extra_arrow_columns: bool = False,
) -> None:
    if not _has_joint_order("action", joint_order):
        return
    if validate_control_arrow:
        try:
            validate_robot_control_arrow(
                value,
                joint_order,
                strict_extra_columns=strict_extra_arrow_columns,
            )
        except RobotArrowSchemaError as error:
            logger.error("忽略 action（Arrow schema）: %s", error)
            _reject(results, "action", error)
            return

    command = JointCommand.from_arrow(value)
    try:
        speed = _read_speed_column(value)
        driver.set_command(command, speed=speed)
    except Exception as error:
        logger.error("拒绝 action: %s", error)
        _reject(results, "action", error)
        return

    if debug:
        sample = {
            name: float(command.to_np([name], "position")[0])
            for name in joint_order[:3]
            if name in command.name
        }
        logger.debug("收到 action sample=%s speed=%s", sample, speed)


def _handle_master_state(
    driver: LitearmDriver,
    value: Any,
    results: queue.Queue[ControlStatus],
    joint_order: list[str],
    debug: bool,
) -> None:
    if not _has_joint_order("master_state", joint_order):
        return
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
        _reject(results, "master_state", error)
        return

    if debug:
        sample = {
            name: float(command.to_np([name], "position")[0])
            for name in joint_order[:3]
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


def run_node(
    driver: LitearmDriver,
    *,
    debug: bool = False,
    is_follower: bool = True,
    joint_order: list[str] | None = None,
    validate_control_arrow: bool = True,
    strict_extra_arrow_columns: bool = False,
    external_subscriptions: list[Any] | None = None,
    on_external_event=None,
    on_tick_after_state=None,
) -> int:
    order = driver.joint_order if joint_order is None else joint_order
    if external_subscriptions and on_external_event is None:
        raise ValueError("external_subscriptions 需要同时传入 on_external_event")

    node = Node()
    for subscription in external_subscriptions or []:
        node.merge_external_events(subscription)
    outputs = _declared_outputs(node)
    results: queue.Queue[ControlStatus] = queue.Queue()
    executor = _ControlExecutor(driver, results)

    try:
        for event in node:
            kind = event.get("kind")
            if kind == "external":
                if on_external_event is not None:
                    on_external_event(event.get("value"))
                continue
            if kind not in (None, "dora"):
                continue

            match event.get("type"):
                case "INPUT":
                    input_id = event["id"]
                    value = event.get("value")
                    if input_id == "tick":
                        _handle_tick(
                            node,
                            driver,
                            outputs,
                            order,
                            debug,
                            on_tick_after_state,
                        )
                    elif input_id == "control":
                        _handle_control(
                            driver, executor, results, value, debug
                        )
                    elif _is_action_input(input_id):
                        if is_follower:
                            _handle_action(
                                driver,
                                value,
                                results,
                                order,
                                debug,
                                validate_control_arrow=validate_control_arrow,
                                strict_extra_arrow_columns=(
                                    strict_extra_arrow_columns
                                ),
                            )
                    elif input_id == "master_state":
                        if is_follower:
                            _handle_master_state(
                                driver, value, results, order, debug
                            )
                    elif input_id == "locomotion_command":
                        if is_follower:
                            logger.warning(
                                "忽略 locomotion_command：本驱动不支持底盘"
                            )
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
