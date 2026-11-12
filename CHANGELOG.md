# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

- Forge/Dora robot driver for the NexForm LiteArm 7-DOF arm and LiteGrip
  gripper, with fake-arm support for hardware-free tests.
- URDF, MJCF, mesh, and GLB assets; joint table and parameter records.
- Asset provenance README and SHA-256 ledger (`assets/README.md`,
  `assets/SHA256SUMS`), verified by `validate_assets.py`.
- Modified-DH table derived from the URDF, with FK cross-check.
- SDK, Dora, and workflow examples, plus acceptance checklist.
- VR→Dora bridge (`vr_bridge_dora.py`) that accepts lite-vr's
  `arm_follow_server` TCP/JSON protocol and publishes Forge `JointCommand`;
  validated end-to-end in simulation with lite-vr teleop and `mujoco_sim`.
- Optional `control` input (`enable`/`disable`/`reset`/`home`/`stop`/
  `emergency_stop`) with `control_status` receipts, plus an optional `speed`
  column on `action` that overrides `config.speed`.
- `robot-litearm-bridge`, a line-oriented TCP/JSON bridge over the Dora
  ports, with an example dataflow, client, and protocol documentation.
- `node.py` now documents that it is a fork of
  `forge_robot.node_runner.run_dora_robot_node` (baseline forge_robot 1.0.1)
  and lists every intentional divergence. The fork gained the standard runner's
  `is_follower` gate, empty `joint_order` guard, configurable Arrow validation,
  external subscriptions / `on_external_event`, and `on_tick_after_state`
  hook. Rejected `action` / `master_state` inputs emit a `control_status`
  receipt.

### Fixed

- `robot-litearm --config A.yaml <subcommand>` no longer silently falls back to
  the default configuration; all subcommands accept `--debug`, and
  `run --debug` and `debug: true` now both enable node debug output.

### Fixed

- A failure partway through `connect()` (firmware check, `enable()`, initial
  move, or gripper connect) now closes the already-opened arm/gripper sessions
  instead of leaving `_connected=False` and leaking the SDK connection.

### Known limitations

- The firmware source for the tested 1.11.0 image is not archived; gripper
  payload is a CAD-derived estimate (0.5772 kg) rather than a dynamically
  identified value, and is not written to the firmware.
- Checklist items 8–12 were measured on a different LiteArm sample
  (`1.11.0-7J`) than the current bench arm (`1.10.1-7J`).
- The VR→Dora bridge has not yet been run against the real arm; on-site VR
  checks used lite-vr's native follow path.
- The control plane and the TCP/JSON bridge were validated on the fake driver
  only; real-arm motion, gripper, and emergency-stop behavior are untested.
