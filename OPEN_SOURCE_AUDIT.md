# Open-source release audit

Audit date: 2026-11-05

## Decision

The audited snapshot is suitable for publication as a new Git repository with a
clean initial history. Project-owned code and documentation use Apache-2.0.
Bundled robot assets come from NexForm repositories that are also Apache-2.0.

## Completed checks

- Python 3.12.13, `uv 0.11.8`; `uv lock --check` resolves 27 packages, all from
  `https://pypi.org/simple`.
- All 23 unit tests passed without physical hardware.
- `robot-litearm probe --fake` and the fake Dora dataflow
  (`examples/02_dora_tests/`) ran successfully; `state_print` received all
  seven joints and the sparse `joint7` command updated state.
- All 12 YAML files parse; all five dataflow descriptors pass `dora build`
  with dora-cli 0.4.1.
- `scripts/validate_assets.py` reports 0 errors and 0 warnings.
- `scripts/urdf_to_mdh.py --check` passes: 500 random joint configurations,
  maximum position error 1.9e-11 m.
- MuJoCo 3.9.0 loads `assets/mjcf/scene.xml` (`nq=7`, `nu=7`, `ngeom=10`).
- trimesh 5.0.0 loads `assets/glb/litearm.glb` with 9 geometries.
- `scripts/check_sdk_api.py` passes against litearm-python `v1.3.0`
  (`__version__` 2.1.0) and litegrip-python `v1.2.1`.
- Wheel and sdist builds succeed and include `LICENSE`, `NOTICE`, and
  `THIRD_PARTY_NOTICES.md`.
- `detect-secrets` 1.5.0 reports no findings in publishable text files
  (binaries, assets, and `uv.lock` excluded).
- No source file contains an absolute home directory, private IP address, or
  personal identifier.
- No file exceeds GitHub's 100 MiB limit. The largest file is a 12.7 MiB STL.

## Dependency audit

`pip-audit` reports 39 advisories against `pillow 12.3.0`, all fixed in
`pillow 13.0.0`. `forge-msgs` 1.3.0 (required by the Forge stable/1.x line)
constrains `pillow>=10,<13`, so the patched version cannot be selected without
breaking the supported Forge line.

Mitigation and tracking:

- This adapter does not decode, receive, or forward images; forge-msgs image
  helpers are not used on untrusted input.
- CI allows only Pillow advisories and fails on every other advisory.
- Remove this exception once a `forge-msgs` release for stable/1.x accepts
  `pillow>=13`.

## License findings

- Project-owned Python, configuration, workflows, and documentation:
  Apache-2.0.
- LiteArm URDF and meshes: Apache-2.0, from
  `nexform-tech/litearm-description`.
- LiteArm MJCF, OBJ meshes, and derived GLB: Apache-2.0, from
  `nexform-tech/litearm-mujoco`.
- VR teleoperation parameters: Apache-2.0, from `nexform-tech/lite-vr`.
- Runtime dependencies are installed from PyPI and are not vendored.
- `litearm-python` and `litegrip-python` are internal SDKs installed from their
  source repositories and are not redistributed here.

See `THIRD_PARTY_NOTICES.md` for the detailed attribution map.

## Known limitations

- CI and the audit do not command physical hardware.
- The physical arm, gripper, firmware zero pose, joint directions, soft limits,
  emergency stop, and lifecycle positions require bench validation.
- End-to-end workflows require external Forge runtime nodes and deployment
  paths configured through environment variables.
- The GLB is a static q=0 mesh without joint hierarchy and does not include the
  gripper.
- This audit is an engineering review, not legal advice or safety
  certification.

## Publication model

Only the audited current snapshot is published. The public repository starts
with one initial commit on `main`; prior development history is not part of the
public release.
