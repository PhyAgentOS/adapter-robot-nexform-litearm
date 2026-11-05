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

### Known limitations

- The firmware source for the tested 1.11.0 image is not archived; gripper
  payload is a CAD-derived estimate (0.5772 kg) rather than a dynamically
  identified value, and is not written to the firmware.
- Checklist items 8–12 were measured on a different LiteArm sample
  (`1.11.0-7J`) than the current bench arm (`1.10.1-7J`).
- The VR→Dora bridge has not yet been run against the real arm; on-site VR
  checks used lite-vr's native follow path.
