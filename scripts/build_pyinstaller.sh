#!/usr/bin/env bash
# 打包 robot-litearm 为单文件可执行程序。
#
# 产物：dist/robot-litearm（Windows 为 .exe），中间文件在 build/pyinstaller/。
# 使用隔离的局部 venv，不依赖当前 shell 的 Python 环境。
#
# 厂商 SDK 不在 PyPI 上。如果构建时要一起打包，先安装到构建 venv：
#   LITEARM_SDK=/path/to/litearm-python LITEGRIP_SDK=/path/to/litegrip-python \
#     scripts/build_pyinstaller.sh
# 未设置时会跳过，产物运行时仍需目标机器安装 SDK。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DIST_DIR="${PACKAGE_DIR}/dist"
WORK_DIR="${PACKAGE_DIR}/build/pyinstaller"
VENV_DIR="${PACKAGE_DIR}/.venv_build"

cd "${PACKAGE_DIR}"
mkdir -p "${DIST_DIR}" "${WORK_DIR}"
rm -f "${DIST_DIR}/robot-litearm" "${DIST_DIR}/robot-litearm.exe"
rm -rf "${VENV_DIR}"
trap 'rm -rf "${VENV_DIR}"' EXIT

echo "==> [robot-litearm] 创建隔离构建环境..."
uv venv --python 3.12 "${VENV_DIR}"
PY="${VENV_DIR}/bin/python"

uv pip install --python "${PY}" --editable "${PACKAGE_DIR}[build]"

for sdk in "${LITEARM_SDK:-}" "${LITEGRIP_SDK:-}"; do
  if [[ -n "${sdk}" ]]; then
    echo "==> 安装厂商 SDK: ${sdk}"
    uv pip install --python "${PY}" --editable "${sdk}"
  fi
done

PYI_ARGS=(
  --noconfirm
  --clean
  --onefile
  --name robot-litearm
  --distpath "${DIST_DIR}"
  --workpath "${WORK_DIR}"
  --paths "${PACKAGE_DIR}/src"
)

for module in litearm litegrip; do
  if "${PY}" -c "import ${module}" >/dev/null 2>&1; then
    PYI_ARGS+=(--collect-submodules "${module}")
  else
    echo "==> 跳过 ${module}（构建环境未安装）"
  fi
done

echo "==> PyInstaller 打包..."
"${VENV_DIR}/bin/pyinstaller" "${PYI_ARGS[@]}" "${SCRIPT_DIR}/build_entry.py"

EXE="${DIST_DIR}/robot-litearm"
if [[ -f "${EXE}" ]]; then
  echo "OK: ${EXE}"
elif [[ -f "${EXE}.exe" ]]; then
  echo "OK: ${EXE}.exe"
else
  echo "WARNING: 未找到产物，请检查 PyInstaller 输出。" >&2
  exit 1
fi
