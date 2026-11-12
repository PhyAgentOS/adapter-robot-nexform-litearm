# Safety policy

This repository can send motion commands to a physical NexForm LiteArm arm and
LiteGrip gripper. It is research and integration software, not a certified
functional-safety system and not a replacement for the manufacturer's safety
controls.

## Before connecting hardware

1. Read the arm, controller, gripper, and emergency-stop documentation. The
   vendor documents available so far are summarized in `docs/hardware.md`;
   gaps are marked there.
2. Verify that the physical emergency stop works before starting this software.
   The hardware stop method is **not yet archived** in this repository.
3. Clear and isolate the workspace. Keep people, cables, and loose objects
   outside the full reachable volume.
4. Confirm the firmware version prefix, joint order, units, limits, serial
   port, and CAN interface match the selected configuration
   (`config/robot.yaml`, `docs/parameters.md`).
5. Keep an operator at the emergency stop. Do not run unattended.

## First motion

- Use `speed: 0.2` or lower in `config/robot.yaml`.
- Test one joint at a time with a small displacement, then stop.
- Validate direction and zero pose before any multi-joint motion.
- Test the gripper without an object first.
- Stop immediately on unexpected direction, vibration, collision, stale
  feedback, communication loss, or limit disagreement.

Software range clipping does not provide collision avoidance, workspace
monitoring, force limiting, or a safety-rated stop.

## Connection lifecycle

The example configuration enables motion on connect:

- `enable_on_connect: true` calls `Arm.enable()`.
- `move_to_initial: true` calls `movej_sync(initial_position, speed)`
  **immediately after connecting** and can move the arm without any Dora
  action. Disable this or choose a supported, collision-free initial pose
  before the first hardware run.
- `move_to_reset_on_disconnect` defaults to `false`. `disconnect()` waits for
  any in-flight `movej_sync` to return, then closes the SDK connection; it does
  not park the arm. It returns only after the command thread has exited.
- `stop()` replaces pending targets with the last measured pose but keeps the
  arm enabled, so holding torque remains. An in-flight `movej_sync` cannot be
  interrupted: it runs to completion, and only then does the hold command run.
  Commands are issued by a single worker thread, so two `movej_sync` calls
  never overlap.
- `emergency_stop()` cancels pending targets and calls `arm.disable()`; it does
  **not** wait for an in-flight `movej_sync`, so the firmware stop command is
  sent immediately. The abandoned call returns on its own and is reaped before
  the next `enable()`. The arm **loses holding torque**. Support the arm before
  calling it from an unsupported pose.
- Disabling the gripper drops its force; a grasped object will fall.

## Recorded actions and playback

Command and state recordings can cause immediate physical motion. Before
playback:

- inspect the recording and test it in simulation first;
- verify `joint1` through `joint7` use radians;
- verify `gripper` is the total finger opening in meters (`0..0.080`);
- never replay millimeter or normalized values without explicit conversion;
- begin at reduced speed in an empty workspace.

## Security and incident reporting

Do not commit robot addresses, credentials, private recordings, calibration
secrets, absolute machine paths, or personally identifiable images. Report
software vulnerabilities through this repository's GitHub private
vulnerability reporting page. For an active hardware hazard, use the physical
emergency stop first.

## Disclaimer

The software and assets are provided "AS IS", without warranties or conditions
of any kind. Users are responsible for risk assessment, supervision,
regulatory compliance, and any personal injury or equipment damage arising
from use.
