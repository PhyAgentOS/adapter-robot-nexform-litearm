#!/usr/bin/env python3
"""Fake headset that rotates the right controller about WebXR +Y (yaw).

Used only for the LiteArm VR simulation validation: verifies that a commanded
hand rotation produces a smooth end-effector rotation about the expected axis.
"""
import argparse
import asyncio
import json
import math
import time


def controller_frame(pos, quat, *, grip, trigger=0.0):
    x, y, z, w = quat
    return {
        "tracked": True,
        "position": {"x": pos[0], "y": pos[1], "z": pos[2]},
        "rotation": {"x": x, "y": y, "z": z},
        "quaternion": {"x": x, "y": y, "z": z, "w": w},
        "gripActive": grip,
        "trigger": trigger,
    }


async def main(args):
    import websockets

    url = f"ws://{args.host}:{args.port}/"
    pos = (0.25, 1.05, -0.35)
    print(f"[rot] connecting {url} hz={args.hz} amp={args.amp_deg}deg period={args.period}s")
    async with websockets.connect(url, max_queue=None) as ws:
        t0 = time.time()
        n = 0
        while True:
            t = time.time() - t0
            if args.duration and t >= args.duration:
                break
            grip = t >= args.warmup
            ang = math.radians(args.amp_deg) * math.sin(2 * math.pi * t / args.period)
            quat = (0.0, math.sin(ang / 2), 0.0, math.cos(ang / 2))
            ts = int(time.time() * 1000)
            frame = {
                "timestamp": ts,
                "leftController": controller_frame(pos, (0, 0, 0, 1), grip=False),
                "rightController": controller_frame(pos, quat, grip=grip),
            }
            await ws.send(json.dumps(frame, separators=(",", ":")))
            n += 1
            await asyncio.sleep(1.0 / args.hz)
        print(f"[rot] done: {n} frames, {t:.1f}s")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--hz", type=float, default=90.0)
    ap.add_argument("--amp-deg", type=float, default=20.0)
    ap.add_argument("--period", type=float, default=6.0)
    ap.add_argument("--warmup", type=float, default=1.5)
    ap.add_argument("--duration", type=float, default=12.0)
    raise SystemExit(asyncio.run(main(ap.parse_args())))
