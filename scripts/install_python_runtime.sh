#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BFD_KIT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
FORCE_REINSTALL=0
PRINT_PYTHON=0

print_help() {
  cat <<'USAGE'
Usage: scripts/install_python_runtime.sh [options]

Options:
  --bfd-kit-root <path>  Explicit BFD-Kit root. Default: script parent.
  --force-reinstall      Recreate the local runtime venv.
  --print-python         Print the resolved runtime python path.
  -h, --help             Show this help.
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --bfd-kit-root)
      BFD_KIT_ROOT="$2"
      shift 2
      ;;
    --force-reinstall)
      FORCE_REINSTALL=1
      shift
      ;;
    --print-python)
      PRINT_PYTHON=1
      shift
      ;;
    -h|--help)
      print_help
      exit 0
      ;;
    *)
      echo "[ERROR] unknown argument: $1" >&2
      print_help >&2
      exit 2
      ;;
  esac
done

BFD_KIT_ROOT="$(cd "$BFD_KIT_ROOT" && pwd)"
RUNTIME_ROOT="${BFD_KIT_ROOT}/.runtime"
VENV_PATH="${RUNTIME_ROOT}/venv"
PYTHON_BIN="${VENV_PATH}/bin/python3"
REQ_FILE="${BFD_KIT_ROOT}/requirements/python-tools.txt"

if [ ! -f "$REQ_FILE" ]; then
  echo "[ERROR] missing runtime requirements: $REQ_FILE" >&2
  exit 1
fi

if [ "$FORCE_REINSTALL" -eq 1 ] && [ -d "$VENV_PATH" ]; then
  rm -rf "$VENV_PATH"
fi

if [ ! -x "$PYTHON_BIN" ]; then
  mkdir -p "$RUNTIME_ROOT"
  python3 -m venv "$VENV_PATH"
fi

if ! "$PYTHON_BIN" -m pip show pyelftools >/dev/null 2>&1; then
  "$PYTHON_BIN" -m pip install --upgrade pip >&2
  "$PYTHON_BIN" -m pip install -r "$REQ_FILE" >&2
fi

if [ "$PRINT_PYTHON" -eq 1 ]; then
  printf '%s\n' "$PYTHON_BIN"
  exit 0
fi

echo "BFD_RUNTIME_PYTHON=${PYTHON_BIN}"
