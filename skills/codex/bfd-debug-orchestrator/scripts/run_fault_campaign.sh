#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"
cd "$PROJECT_ROOT"

PROFILE_HELPER="${PROJECT_ROOT}/build_tools/jlink/profile_env.sh"
if [[ ! -f "${PROFILE_HELPER}" ]]; then
  echo "[ERROR] profile helper not found: ${PROFILE_HELPER}" >&2
  exit 2
fi
# shellcheck source=build_tools/jlink/profile_env.sh
source "${PROFILE_HELPER}"
load_stm32_profile_env "${PROJECT_ROOT}" || exit 2

BUILD_DIR=""
if [[ -n "${STM32_ELF:-}" ]]; then
  BUILD_DIR="$(dirname "${STM32_ELF}")"
fi
ELF="${STM32_ELF:-}"
DEVICE="${STM32_DEVICE}"
IFACE="${STM32_IF:-SWD}"
SPEED="${STM32_SPEED_KHZ:-4000}"
SCENARIOS=(1 2 3 4)
SKIP_BUILD=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --build-dir)
      BUILD_DIR="$2"
      shift 2
      ;;
    --elf)
      ELF="$2"
      shift 2
      ;;
    --skip-build)
      SKIP_BUILD=1
      shift
      ;;
    --scenarios)
      IFS=',' read -r -a SCENARIOS <<< "$2"
      shift 2
      ;;
    -h|--help)
      cat <<USAGE
Usage:
  run_fault_campaign.sh [--build-dir <dir>] [--elf <path>] [--skip-build] [--scenarios 1,2,3,4]
USAGE
      exit 0
      ;;
    *)
      echo "[ERROR] unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

if [[ -z "${ELF}" && -n "${BUILD_DIR}" ]]; then
  ELF="$(find "${BUILD_DIR}" -maxdepth 1 -type f -name '*.elf' | sort | head -n 1 || true)"
fi

mkdir -p logs/debug/orchestrator logs/rtt logs/flash logs/build .codex/debug
SESSION_TS="$(date +%Y-%m-%d_%H%M%S)"
SESSION_DIR="logs/debug/orchestrator/${SESSION_TS}"
mkdir -p "$SESSION_DIR"
RTT_CAPTURE_STATUS="WARN"
RTT_REQUIRED_STATUS="WARN"
RTT_ADVISORY_STATUS="PASS"
RTT_MODE_USED=""
SUMMARY_PATH=".codex/debug/bfd-debug-orchestrator-campaign.md"
INJECT_SCRIPT="${PROJECT_ROOT}/build_tools/jlink/inject_fault_scenario.sh"
LEGACY_INJECT_SCRIPT="${PROJECT_ROOT}/.codex/skills/bfd-debug-orchestrator/scripts/inject_fault_scenario.sh"
if [[ ! -f "${INJECT_SCRIPT}" ]]; then
  INJECT_SCRIPT="${LEGACY_INJECT_SCRIPT}"
fi
if [[ ! -f "${INJECT_SCRIPT}" ]]; then
  echo "[ERROR] inject script not found: ${PROJECT_ROOT}/build_tools/jlink/inject_fault_scenario.sh" >&2
  exit 2
fi

run_logged() {
  local name="$1"
  shift
  local log="${SESSION_DIR}/${name}.log"
  echo "[RUN] $*"
  "$@" > >(tee "$log") 2>&1
}

append_mode() {
  local mode="$1"
  if [[ -z "${RTT_MODE_USED}" ]]; then
    RTT_MODE_USED="${mode}"
  else
    RTT_MODE_USED="${RTT_MODE_USED},${mode}"
  fi
}

run_rtt_capture() {
  local tag="$1"
  local out="$2"
  local timeout_s="$3"
  local mode="$4"
  local role="$5"
  local reset_policy="${6:-}"
  local success_profile="${7:-}"
  local log="${SESSION_DIR}/${tag}.log"
  local status=0
  local cmd=(./build_tools/jlink/rtt.sh "${out}" "${timeout_s}" --mode "${mode}" --role "${role}" --device "${DEVICE}" --if "${IFACE}" --speed "${SPEED}" --elf "${ELF}")

  if [[ -n "${reset_policy}" ]]; then
    cmd+=(--reset-policy "${reset_policy}")
  fi
  if [[ -n "${success_profile}" ]]; then
    cmd+=(--success-profile "${success_profile}")
  fi

  set +e
  run_logged "${tag}" "${cmd[@]}"
  status=$?
  set -e
  append_mode "${mode}"
  printf 'RTT_COMMAND_RC=%s\n' "${status}" >> "${log}"
}

rtt_capture_succeeded() {
  local log_path="$1"
  grep -Eq '^RTT_SUCCESS=1$' "${log_path}"
}

if [[ ${SKIP_BUILD} -eq 0 ]]; then
  run_logged build ./build_tools/scripts/build_fast.sh GCC Debug false 8
fi

if [[ -z "${ELF}" || ! -f "$ELF" ]]; then
  echo "[ERROR] ELF not found: ${ELF:-<empty>}" | tee "${SESSION_DIR}/fatal.log"
  exit 1
fi

if [[ -n "${BUILD_DIR}" ]]; then
  run_logged flash_base ./build_tools/jlink/flash.sh "$BUILD_DIR"
else
  run_logged flash_base ./build_tools/jlink/flash.sh
fi

BASELINE_RTT="logs/rtt/${SESSION_TS}_baseline_rtt.log"
run_rtt_capture rtt_base "${BASELINE_RTT}" 5 dual boot gdb-reset-go generic

for s in "${SCENARIOS[@]}"; do
  run_logged "inject_s${s}" "${INJECT_SCRIPT}" --scenario "$s" --elf "$ELF" --device "$DEVICE" --if "$IFACE" --speed "$SPEED"

  if [[ "$s" == "1" || "$s" == "2" ]]; then
    RTT_OUT="logs/rtt/${SESSION_TS}_s${s}.log"
    run_rtt_capture "rtt_s${s}" "${RTT_OUT}" 4 quick diag none strict
  else
    sleep 1
    run_logged "capture_s${s}" ./.codex/skills/bfd-debug-orchestrator/scripts/capture_hardfault_snapshot.sh --elf "$ELF" --scenario "$s" --device "$DEVICE" --if "$IFACE" --speed "$SPEED"

    HF_JSON="$(grep -E '^JSON=' "${SESSION_DIR}/capture_s${s}.log" | tail -n1 | cut -d= -f2-)"
    HF_MD="$(grep -E '^MD=' "${SESSION_DIR}/capture_s${s}.log" | tail -n1 | cut -d= -f2-)"
    if [[ -n "$HF_JSON" && -f "$HF_JSON" ]]; then
      cp "$HF_JSON" "${SESSION_DIR}/hardfault_s${s}.json"
      if [[ -n "$HF_MD" && -f "$HF_MD" ]]; then
        cp "$HF_MD" "${SESSION_DIR}/hardfault_s${s}.md"
      fi
      run_logged "evolution_s${s}" ./.codex/skills/bfd-debug-orchestrator/scripts/update_error_evolution.py "$HF_JSON"
    fi

    if [[ -n "${BUILD_DIR}" ]]; then
      run_logged "flash_recover_s${s}" ./build_tools/jlink/flash.sh "$BUILD_DIR"
    else
      run_logged "flash_recover_s${s}" ./build_tools/jlink/flash.sh
    fi
    RTT_REC="logs/rtt/${SESSION_TS}_recover_s${s}.log"
    run_rtt_capture "rtt_recover_s${s}" "${RTT_REC}" 6 dual boot gdb-reset-go generic
  fi
done

FINAL_RTT="logs/rtt/${SESSION_TS}_final.log"
run_rtt_capture rtt_final "${FINAL_RTT}" 5 dual boot gdb-reset-go generic

if rtt_capture_succeeded "${SESSION_DIR}/rtt_final.log"; then
  echo "FLASH_RW_CHECK=PASS" | tee "${SESSION_DIR}/result.env"
else
  echo "FLASH_RW_CHECK=WARN" | tee "${SESSION_DIR}/result.env"
fi

run_logged summary ./.codex/skills/bfd-debug-orchestrator/scripts/summarize_campaign.py --session-dir "$SESSION_DIR" --output "${SUMMARY_PATH}"

RTT_CAPTURE_STATUS="$(grep -E '^RTT_CAPTURE_STATUS=' "${SESSION_DIR}/summary.log" | tail -n1 | cut -d= -f2-)"
RTT_REQUIRED_STATUS="$(grep -E '^RTT_REQUIRED_STATUS=' "${SESSION_DIR}/summary.log" | tail -n1 | cut -d= -f2-)"
RTT_ADVISORY_STATUS="$(grep -E '^RTT_ADVISORY_STATUS=' "${SESSION_DIR}/summary.log" | tail -n1 | cut -d= -f2-)"

if [[ -z "${RTT_CAPTURE_STATUS}" ]]; then
  RTT_CAPTURE_STATUS="WARN"
fi
if [[ -z "${RTT_REQUIRED_STATUS}" ]]; then
  RTT_REQUIRED_STATUS="WARN"
fi
if [[ -z "${RTT_ADVISORY_STATUS}" ]]; then
  RTT_ADVISORY_STATUS="WARN"
fi

echo "SESSION_DIR=${SESSION_DIR}" | tee -a "${SESSION_DIR}/result.env"
echo "SUMMARY=${SUMMARY_PATH}" | tee -a "${SESSION_DIR}/result.env"
echo "RTT_MODE_USED=${RTT_MODE_USED}" | tee -a "${SESSION_DIR}/result.env"
echo "RTT_CAPTURE_STATUS=${RTT_CAPTURE_STATUS}" | tee -a "${SESSION_DIR}/result.env"
echo "RTT_REQUIRED_STATUS=${RTT_REQUIRED_STATUS}" | tee -a "${SESSION_DIR}/result.env"
echo "RTT_ADVISORY_STATUS=${RTT_ADVISORY_STATUS}" | tee -a "${SESSION_DIR}/result.env"

echo "CAMPAIGN_DONE=${SESSION_DIR}"
