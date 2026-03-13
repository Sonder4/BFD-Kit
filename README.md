# BFD-Kit: AI STM32 Debug Toolkit

BFD-Kit is a portable, CLI-first toolkit for AI-assisted STM32 debug workflows.
It standardizes IOC discovery, active profile generation, flashing, RTT logging, register/data capture, and fault evidence collection.

## Scope

- Target families bundled now: `STM32F4`, `STM32H7`
- Agent targets: Codex + Claude
- Canonical source tree: `BFD-Kit/skills/{codex,claude}/bfd-*`
- Runtime profile directory: `.codex/bfd/`
- Legacy compatibility mirror: `.codex/stm32/bootstrap/`

## Directory Layout

- `BFD-Kit/skills/codex/`: canonical Codex skill pack
- `BFD-Kit/skills/claude/`: canonical Claude skill pack
- `BFD-Kit/resources/stm32/templates/`: family templates (`f4/`, `h7/`)
- `BFD-Kit/init_project.sh`: one-command project onboarding entry
- `BFD-Kit/scripts/bfd_jlink_hss.sh`: native J-Link HSS wrapper with managed Python runtime
- `BFD-Kit/.runtime/venv`: local Python runtime installed on demand for portable script execution
- `BFD-Kit/scripts/migrate_bfd_skills.py`: import/cutover utility
- `BFD-Kit/MAINTENANCE-zh.md`: maintainer-facing maintenance checklist

## Skill Set

- `bfd-project-init`: scan `.ioc`/startup/linker/svd/cfg/build artifacts and generate one active profile
- `bfd-ioc-parser`: parse `.ioc` and export structured JSON to `.codex/bfd/ioc_json/`
- `bfd-cubemx-codegen`: regenerate CubeMX-managed files from an existing `.ioc` in read-only mode
- `bfd-flash-programmer`: deterministic J-Link/ST-Link flash flow
- `bfd-rtt-logger`: runtime RTT capture and validation
- `bfd-debug-interface`: structured debug workflow and fault context handling
- `bfd-debug-executor`: one-shot J-Link command execution
- `bfd-register-capture`: peripheral register sampling/export
- `bfd-data-acquisition`: runtime data capture and analysis
- `bfd-fault-logger`: HardFault/BusFault/UsageFault archival
- `bfd-debug-orchestrator`: end-to-end debug campaign orchestration
- `bfd-user-feedback`: user-facing status/feedback hooks

Legacy overlapping STM32 skills are intended to be removed from active mirrors once the canonical `bfd-*` trees are staged and cut over.

`bfd-data-acquisition` also carries the reusable local-variable probe resource under `resources/local-probe/` for stack-variable sampling workflows.

## New in This Revision

- `bfd-data-acquisition` now supports generic `--mode symbol-auto`
- `bfd-data-acquisition` now includes a native J-Link HSS CLI path for non-halting fixed-address scalar sampling
- `symbol-auto` uses `ELF + DWARF` reflection to decode global/static objects without business-specific hardcoding
- DWARF schemas are cached under `.codex/bfd/dwarf_cache/` for reuse across repeated inspections
- RTT failure guidance now explicitly routes to RAM sampling instead of ad-hoc GDB/J-Link command design
- `bfd-debug-interface` and `bfd-rtt-logger` delegate structured symbol decoding to `bfd-data-acquisition`

Supported V1 reflected type families:

- `struct`
- `array`
- `pointer`
- `typedef`
- `enum`

Current recommendation:

- first choice: `symbol-auto` for any stable global/static symbol with usable DWARF
- second choice: `--mode symbol` with an explicit decode profile or layout
- last choice: raw address sampling or low-level debug commands

## Fast Init

```bash
# One command: install/update BFD skills, refresh .codex/bfd profile, and prepare local Python runtime
bash BFD-Kit/init_project.sh --project-root .

# Optional modes
bash BFD-Kit/init_project.sh --project-root . --cutover-only
bash BFD-Kit/init_project.sh --project-root . --bootstrap-only --force-refresh
bash BFD-Kit/init_project.sh --project-root . --runtime-only
```

## Standard Workflow

```bash
# 1) Generate/refresh the canonical runtime profile
python3 ./.codex/skills/bfd-project-init/scripts/bootstrap.py --project-root . --mode check

# 1.5) Optionally regenerate CubeMX-managed files from the current .ioc
python3 ./.codex/skills/bfd-cubemx-codegen/scripts/generate_from_ioc.py --project-root . --log-dir logs/skills

# 2) Flash
./build_tools/jlink/flash.sh builds/gcc/debug | tee logs/flash/flash_$(date +%Y%m%d_%H%M%S).log

# 3) RTT runtime log
./build_tools/jlink/rtt.sh logs/rtt/rtt_$(date +%Y%m%d_%H%M%S).log 5 --mode quick

# 3.5) If RTT has no usable payload, switch to generic RAM decode
python3 ./.codex/skills/bfd-data-acquisition/scripts/data_acq.py \
  --elf "${STM32_ELF}" \
  --mode symbol-auto \
  --symbol <global_symbol> \
  --follow-depth 1 \
  --format summary \
  --output logs/data_acq/<global_symbol>.summary

# 3.6) For high-rate, non-halting scalar sampling, switch to native HSS
bash BFD-Kit/scripts/bfd_jlink_hss.sh --json hss sample \
  --symbol chassis_parameter.IMU.yaw \
  --symbol chassis_parameter.IMU.pitch \
  --duration 0.3 \
  --period-us 1000 \
  --output logs/data_acq/imu_yaw_pitch_hss.csv

# 4) One-shot debug session
./build_tools/jlink/debug.sh | tee logs/debug/debug_$(date +%Y%m%d_%H%M%S).log
```

## Recommended Data-Acquisition Flow

```bash
# Generic global/static object decode
python3 ./.codex/skills/bfd-data-acquisition/scripts/data_acq.py \
  --elf "${STM32_ELF}" \
  --mode symbol-auto \
  --symbol g_object_state \
  --follow-depth 0 \
  --format summary

# Generic pointer-hub decode
python3 ./.codex/skills/bfd-data-acquisition/scripts/data_acq.py \
  --elf "${STM32_ELF}" \
  --mode symbol-auto \
  --symbol g_object_hub \
  --follow-depth 1 \
  --format json

# Manual fallback when DWARF auto reflection is not suitable
python3 ./.codex/skills/bfd-data-acquisition/scripts/data_acq.py \
  --elf "${STM32_ELF}" \
  --mode symbol \
  --symbol g_object_array \
  --count <N> \
  --decode-profile <profile_name> \
  --format csv

# Native J-Link HSS for one or more fixed-address scalar symbols
bash BFD-Kit/scripts/bfd_jlink_hss.sh --json hss sample \
  --symbol chassis_parameter.IMU.yaw \
  --symbol chassis_parameter.IMU.pitch \
  --duration 1 \
  --period-us 1000 \
  --output logs/data_acq/imu_yaw_pitch_hss.csv
```

On `J-Link PLUS`, SEGGER's model limits and local HSS verification both indicate a 10-symbol ceiling. Do not treat `hss inspect` raw capability word 2 as the symbol-count limit. `hss sample` writes a synchronized wide CSV to `--output` and a metadata sidecar JSON to `--output.meta.json`.

## Runtime Profile Contract

- Canonical files:
  - `.codex/bfd/active_profile.json`
  - `.codex/bfd/active_profile.env`
  - `.codex/bfd/bootstrap_report.md`
  - `.codex/bfd/ioc_json/`
- Compatibility mirror:
  - `.codex/stm32/bootstrap/active_profile.json`
  - `.codex/stm32/bootstrap/active_profile.env`
- Auto-init:
  - `build_tools/jlink/profile_env.sh` calls `ensure_profile.py`
  - `rtt_plot_live.py` prefers `.codex/bfd/active_profile.env`
- Local runtime:
  - `BFD-Kit/.runtime/venv`
  - `BFD-Kit/scripts/install_python_runtime.sh` installs `pyelftools`
  - `BFD-Kit/scripts/bfd_jlink_hss.sh` uses the local runtime automatically

## Integrate Into an Existing Project

```bash
bash BFD-Kit/init_project.sh --project-root .
python3 BFD-Kit/scripts/migrate_bfd_skills.py --mode stage
python3 BFD-Kit/scripts/migrate_bfd_skills.py --mode cutover
```

- `stage`: import active `.codex/.claude` BFD skills into `BFD-Kit/`
- `cutover`: push `BFD-Kit/` canonical skills back into active mirrors and back up old mirrors under `archive/skills_migration/`

## Maintainer Notes

- Keep BFD-Kit skills, scripts, docs, and `.learnings` aligned across maintained copies.
- Avoid exposing local absolute paths, workspace topology, mirror relationships, or repository-boundary details in project-facing docs and prompts.
- Before publishing from any repository, verify the current repo root, remote, branch, and worktree state.
- See `BFD-Kit/MAINTENANCE-zh.md` for the generic maintenance checklist.

## Verification

```bash
bash BFD-Kit/init_project.sh --help
bash BFD-Kit/scripts/install_python_runtime.sh --help
python3 BFD-Kit/scripts/bfd_jlink_hss.py --help
python3 BFD-Kit/scripts/migrate_bfd_skills.py --help
python3 ./.codex/skills/bfd-project-init/scripts/bootstrap.py --project-root . --mode check
python3 ./.codex/skills/bfd-project-init/scripts/ensure_profile.py --project-root . --print-env-path
python3 ./.codex/skills/bfd-cubemx-codegen/scripts/generate_from_ioc.py --help
```
