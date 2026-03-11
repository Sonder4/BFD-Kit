#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"
OFFICIAL_SCRIPT="${PROJECT_ROOT}/build_tools/jlink/inject_fault_scenario.sh"

if [[ ! -f "${OFFICIAL_SCRIPT}" ]]; then
  echo "[ERROR] official inject script not found: ${OFFICIAL_SCRIPT}" >&2
  exit 2
fi

exec "${OFFICIAL_SCRIPT}" "$@"
