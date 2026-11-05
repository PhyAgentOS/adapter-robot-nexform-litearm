# Third-party notices

The repository's original Python code, configuration, workflows, and
documentation are licensed under Apache License 2.0 unless a file or directory
states otherwise. The following bundled assets and parameters retain their
upstream attribution.

## LiteArm URDF and STL meshes

- Paths: `assets/urdf/`, `assets/meshes/`
- Source: `nexform-tech/litearm-description`
  (`SE/litearm_description`), commit `f94eafe`
- License: Apache-2.0

The delivered URDF was adjusted to use repository-relative mesh paths.

## LiteArm MJCF, OBJ meshes, and derived GLB

- Paths: `assets/mjcf/`, `assets/glb/`
- Source: `nexform-tech/litearm-mujoco` (`b901d49` onwards), rebuilt from the
  URDF above
- License: Apache-2.0

`assets/glb/litearm.glb` is a converted form of the MJCF visual meshes and
retains the same upstream attribution. Conversion details are recorded in
`assets/glb/README.md`.

## VR teleoperation parameters

- Paths: `config/vr.example.yaml`
- Source: `nexform-tech/lite-vr`
  (`litearm-vr-teleop/teleop/config/teleop.yaml`), captured 2026-11-05
- License: Apache-2.0

Only numeric parameters are recorded; no source code is vendored.

## Runtime dependencies

Python dependencies are not vendored into this repository. Their licenses are
provided by their respective distributions, including:

- `dora-rs`: MIT (according to the installed PyPI distribution metadata)
- `forge-msgs`, `forge-robot`: see their PyPI distributions
- `PyYAML`: MIT
- `litearm-python`, `litegrip-python`: internal NexForm SDKs, installed from
  their source repositories, not redistributed here

Distributing a bundled executable, including a PyInstaller artifact, may
create additional license obligations. Review all bundled dependency licenses
before publishing binary releases.
