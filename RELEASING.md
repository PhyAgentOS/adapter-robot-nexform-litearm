# Releasing the LiteArm adapter

## Versioning

The project follows Semantic Versioning. Update `project.version` in
`pyproject.toml`, regenerate `uv.lock`, and move relevant entries from
`Unreleased` into a dated section in `CHANGELOG.md`.

Public tags are immutable and use `v<version>`, for example `v0.1.0`. Never
reuse, move, or replace a published tag or package version.

## Release checks

Release from a clean, reviewed commit using Python 3.12 or newer:

```bash
uv lock --check
uv sync --frozen --extra test
uv run python -m pytest -q
uv run python -c "import forge_msgs, forge_robot"
uv run python scripts/validate_assets.py
uv run python scripts/urdf_to_mdh.py --check
uv build
uv export --frozen --format requirements-txt --no-dev --no-emit-project \
  --output-file /tmp/litearm-requirements.txt
uvx pip-audit --requirement /tmp/litearm-requirements.txt
```

Confirm CI passes and Dependabot has no open alerts. CI and these commands do
not validate physical hardware.

## Hardware and asset checks

Complete and record the checks affected by the release:

1. Verify the physical emergency stop and an isolated workspace.
2. Test low-speed, small, single-joint motion before combined motion.
3. Confirm firmware version, serial port, CAN interface, joint order, units,
   soft limits, `initial_position`, and gripper direction.
4. Test recordings in simulation before any hardware playback.
5. Load the delivered MJCF scene and verify changed GLB/URDF/MJCF assets.
6. Update asset source hashes and `THIRD_PARTY_NOTICES.md` when models change.

Follow `SAFETY.md`; store only redacted local evidence under `validation_output/`,
whose generated contents are ignored.

## Source and Python release

Before creating a tag:

1. Confirm `pyproject.toml`, `uv.lock`, `README.md`, and `CHANGELOG.md` agree.
2. Inspect wheel and source archives for `LICENSE`, `NOTICE`,
   `THIRD_PARTY_NOTICES.md`, and absence of private files.
3. Confirm no file exceeds GitHub's 100 MiB limit.
4. Run secret and private-path scans against the exact release tree.
5. Create an annotated `v<version>` tag at the validated commit.

If publishing to PyPI is explicitly authorized, test the built artifacts
against the target index before uploading. Never store registry or repository
tokens in this repository.

## Optional PyInstaller release

Build with `./scripts/build_pyinstaller.sh` only after the source release
checks pass. A bundled executable requires a separate dependency-license
review. Scan final binaries for credentials, private paths, and internal URLs;
record SHA-256 digests and test on the oldest supported Linux environment. Do
not publish local `dist/` contents without reproducing them from the tagged
commit.
