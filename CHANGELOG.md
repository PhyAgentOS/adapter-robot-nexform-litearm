# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

- Forge/Dora robot driver for the NexForm LiteArm 7-DOF arm and LiteGrip
  gripper, with fake-arm support for hardware-free tests.
- URDF, MJCF, mesh, and GLB assets; joint table and parameter records.
- Modified-DH table derived from the URDF, with FK cross-check.
- SDK, Dora, and workflow examples, plus acceptance checklist.

### Known limitations

- Real-hardware acceptance is not complete. Firmware zero pose, joint
  directions, soft limits, `t_ee`, payload, and grasp threshold still require
  bench validation.
