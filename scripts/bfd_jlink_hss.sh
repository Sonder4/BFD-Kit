#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BFD_KIT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BIN="$("${SCRIPT_DIR}/install_python_runtime.sh" --bfd-kit-root "${BFD_KIT_ROOT}" --print-python)"

exec "${PYTHON_BIN}" "${SCRIPT_DIR}/bfd_jlink_hss.py" "$@"
