#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PROJECT_ROOT="$SOURCE_ROOT"
MODE="init"
FORCE_REFRESH=0
INSTALL_RUNTIME=1

print_help() {
  cat <<'USAGE'
Usage: BFD-Kit/init_project.sh [options]

Options:
  --project-root <path>  Target STM32 project root. Default: current BFD-Kit host repo.
  --stage-only           Import active bfd-* mirrors into target BFD-Kit only.
  --cutover-only         Push canonical BFD-Kit bfd-* skills into target active mirrors only.
  --bootstrap-only       Refresh target .codex/bfd active profile only.
  --runtime-only         Install or refresh the target BFD-Kit local Python runtime only.
  --skip-runtime         Do not install the target BFD-Kit local Python runtime.
  --force-refresh        Force profile refresh even if fingerprint matches.
  -h, --help             Show this help.
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --project-root)
      PROJECT_ROOT="$2"
      shift 2
      ;;
    --stage-only)
      MODE="stage"
      shift
      ;;
    --cutover-only)
      MODE="cutover"
      shift
      ;;
    --bootstrap-only)
      MODE="bootstrap"
      shift
      ;;
    --runtime-only)
      MODE="runtime"
      shift
      ;;
    --skip-runtime)
      INSTALL_RUNTIME=0
      shift
      ;;
    --force-refresh)
      FORCE_REFRESH=1
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

PROJECT_ROOT="$(cd "$PROJECT_ROOT" && pwd)"
TARGET_BFD_KIT="${PROJECT_ROOT}/BFD-Kit"
TARGET_CODEX_SKILLS="${PROJECT_ROOT}/.codex/skills"
TARGET_CLAUDE_SKILLS="${PROJECT_ROOT}/.claude/skills"
TARGET_TEMPLATES_ROOT="${PROJECT_ROOT}/.codex/stm32"
TARGET_BOOTSTRAP="${PROJECT_ROOT}/.codex/skills/bfd-project-init/scripts/bootstrap.py"
TARGET_ENSURE="${PROJECT_ROOT}/.codex/skills/bfd-project-init/scripts/ensure_profile.py"
TARGET_MIGRATE="${PROJECT_ROOT}/BFD-Kit/scripts/migrate_bfd_skills.py"
TARGET_RUNTIME_INSTALL="${PROJECT_ROOT}/BFD-Kit/scripts/install_python_runtime.sh"

sync_tree() {
  local src="$1"
  local dst="$2"
  python3 - "$src" "$dst" <<'PY'
from pathlib import Path
import shutil
import sys
src = Path(sys.argv[1])
dst = Path(sys.argv[2])
if dst.exists():
    shutil.rmtree(dst)
dst.parent.mkdir(parents=True, exist_ok=True)
shutil.copytree(src, dst)
PY
}

ensure_target_bfd_kit() {
  if [ "$SOURCE_ROOT" != "$PROJECT_ROOT" ] || [ ! -d "$TARGET_BFD_KIT" ]; then
    sync_tree "${SOURCE_ROOT}/BFD-Kit" "$TARGET_BFD_KIT"
  fi
}

run_stage() {
  ensure_target_bfd_kit
  python3 "$TARGET_MIGRATE" --repo-root "$PROJECT_ROOT" --mode stage
}

run_cutover() {
  ensure_target_bfd_kit
  python3 "$TARGET_MIGRATE" --repo-root "$PROJECT_ROOT" --mode cutover
}

run_bootstrap() {
  if [ ! -f "$TARGET_ENSURE" ]; then
    echo "[ERROR] missing target ensure_profile.py: $TARGET_ENSURE" >&2
    echo "[HINT] run without --bootstrap-only first, or install bfd-project-init into the target repo." >&2
    exit 1
  fi
  local args=(--project-root "$PROJECT_ROOT" --print-env-path)
  if [ "$FORCE_REFRESH" -eq 1 ]; then
    args=(--project-root "$PROJECT_ROOT" --force-refresh --print-env-path)
  fi
  local profile_env_rel
  profile_env_rel="$(python3 "$TARGET_ENSURE" "${args[@]}")"
  echo "INIT_PROFILE_ENV=${profile_env_rel}"
  if [ -f "${PROJECT_ROOT}/${profile_env_rel}" ]; then
    local profile_json_rel="${profile_env_rel%.env}.json"
    echo "INIT_PROFILE_JSON=${profile_json_rel}"
  fi
}

run_runtime() {
  ensure_target_bfd_kit
  if [ ! -f "$TARGET_RUNTIME_INSTALL" ]; then
    echo "[ERROR] missing target install_python_runtime.sh: $TARGET_RUNTIME_INSTALL" >&2
    exit 1
  fi
  bash "$TARGET_RUNTIME_INSTALL" --bfd-kit-root "$TARGET_BFD_KIT"
}

mkdir -p "$PROJECT_ROOT" "$TARGET_CODEX_SKILLS" "$TARGET_CLAUDE_SKILLS" "$TARGET_TEMPLATES_ROOT"

echo "INIT_MODE=${MODE}"
echo "INIT_PROJECT_ROOT=${PROJECT_ROOT}"
echo "INIT_SOURCE_ROOT=${SOURCE_ROOT}"
echo "INIT_INSTALL_RUNTIME=${INSTALL_RUNTIME}"

case "$MODE" in
  stage)
    run_stage
    if [ "$INSTALL_RUNTIME" -eq 1 ]; then
      run_runtime
    fi
    ;;
  cutover)
    run_cutover
    if [ "$INSTALL_RUNTIME" -eq 1 ]; then
      run_runtime
    fi
    ;;
  bootstrap)
    run_bootstrap
    ;;
  runtime)
    run_runtime
    ;;
  init)
    run_cutover
    run_bootstrap
    if [ "$INSTALL_RUNTIME" -eq 1 ]; then
      run_runtime
    fi
    ;;
esac
