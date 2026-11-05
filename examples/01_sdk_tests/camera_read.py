#!/usr/bin/env python3
"""相机读取测试（可选外设）。

LiteArm 交付包本身不含相机，本脚本用于现场外接相机时验证取流链路。
优先尝试 Intel RealSense；没有 real sense 时退回 OpenCV 的 V4L2 设备。

依赖（按需安装，不在 pyproject 默认依赖里）：
    uv pip install opencv-python          # 通用 USB 相机
    uv pip install pyrealsense2           # Intel RealSense

用法：
    python camera_read.py                       # 列出可用后端并读一帧
    python camera_read.py --backend opencv --index 0 --save frame.png
"""

from __future__ import annotations

import argparse
import sys
import time


def _read_realsense() -> tuple[int, int, str] | None:
    try:
        import pyrealsense2 as rs
    except ImportError:
        return None
    pipeline = rs.pipeline()
    config = rs.config()
    config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
    pipeline.start(config)
    try:
        for _ in range(5):
            pipeline.wait_for_frames(timeout_ms=2000)
        frames = pipeline.wait_for_frames(timeout_ms=2000)
        color = frames.get_color_frame()
        if not color:
            return None
        return color.get_width(), color.get_height(), "realsense"
    finally:
        pipeline.stop()


def _read_opencv(index: int, save: str | None) -> tuple[int, int, str] | None:
    try:
        import cv2
    except ImportError:
        return None
    capture = cv2.VideoCapture(index)
    if not capture.isOpened():
        capture.release()
        return None
    try:
        for _ in range(5):
            capture.read()
            time.sleep(0.05)
        ok, frame = capture.read()
        if not ok or frame is None:
            return None
        if save:
            cv2.imwrite(save, frame)
        height, width = frame.shape[:2]
        return width, height, "opencv"
    finally:
        capture.release()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--backend", choices=("auto", "realsense", "opencv"), default="auto"
    )
    parser.add_argument("--index", type=int, default=0, help="OpenCV 设备号")
    parser.add_argument("--save", default=None, help="保存一帧 PNG/JPG")
    args = parser.parse_args(argv)

    result = None
    if args.backend in ("auto", "realsense"):
        result = _read_realsense()
    if result is None and args.backend in ("auto", "opencv"):
        result = _read_opencv(args.index, args.save)

    if result is None:
        print(
            "没有可用的相机后端。请安装 opencv-python 或 pyrealsense2，"
            "并确认设备已连接。",
            file=sys.stderr,
        )
        return 1

    width, height, backend = result
    print(f"ok: backend={backend} resolution={width}x{height}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
