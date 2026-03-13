# BFD-Kit: AI STM32 Debug Toolkit

[简体中文](README.md) | English

BFD-Kit is a portable, CLI-first toolkit for AI-assisted STM32 debug workflows.
It standardizes `.ioc` discovery, runtime profile generation, code regeneration, flashing, RTT logging, register/data capture, and fault evidence collection for embedded projects.

## Project Note

This project contains STM32 Skills developed by NCU Roboteam during work with the DJI Type-A board and the DM MC-02 development board. There is still plenty of room for improvement, and issues are welcome.

## Scope

- Target families bundled now: `STM32F4`, `STM32H7`
- Agent targets: Codex, Claude
- Canonical source tree: `skills/{codex,claude}/bfd-*`
- Runtime profile directory: `.codex/bfd/`
- Legacy compatibility mirror: `.codex/stm32/bootstrap/`

## Directory Layout

- `skills/codex/`: canonical Codex skill pack
- `skills/claude/`: canonical Claude skill pack
- `resources/stm32/templates/`: family templates (`f4/`, `h7/`)
- `init_project.sh`: one-command project onboarding entry
- `scripts/bfd_jlink_hss.sh`: native J-Link HSS wrapper with managed local Python runtime
- `.runtime/venv`: local Python runtime installed on demand
- `scripts/migrate_bfd_skills.py`: import / cutover utility
- `STM32_AGENT_PROMPT-zh.md`: Chinese STM32 agent prompt reference

## Skill Set

- `bfd-project-init`: scan `.ioc`, startup, linker, svd, cfg, and build artifacts to generate one active profile
- `bfd-ioc-parser`: parse `.ioc` and export structured JSON to `.codex/bfd/ioc_json/`
- `bfd-cubemx-codegen`: regenerate CubeMX-managed files from an existing `.ioc` in read-only generation mode
- `bfd-flash-programmer`: deterministic J-Link / ST-Link flash flow
- `bfd-rtt-logger`: runtime RTT capture and validation
- `bfd-debug-interface`: structured debug workflow and fault context handling
- `bfd-debug-executor`: one-shot J-Link command execution
- `bfd-register-capture`: peripheral register sampling and export
- `bfd-data-acquisition`: runtime data capture and analysis
- `bfd-fault-logger`: HardFault / BusFault / UsageFault archival
- `bfd-debug-orchestrator`: end-to-end debug campaign orchestration
- `bfd-user-feedback`: user-facing status and feedback hooks

## Fast Init

The commands below assume you are running from the `BFD-Kit` repository root and installing the toolkit into a target STM32 project.

```bash
# Install or update BFD skills, refresh the target project's .codex/bfd profile, and prepare local Python runtime
bash ./init_project.sh --project-root /path/to/your/stm32-project

# Optional modes
bash ./init_project.sh --project-root /path/to/your/stm32-project --cutover-only
bash ./init_project.sh --project-root /path/to/your/stm32-project --bootstrap-only --force-refresh
bash ./init_project.sh --project-root /path/to/your/stm32-project --runtime-only
```

## Standard Workflow

The commands below are executed inside the target STM32 project root.

```bash
# 1) Generate or refresh the canonical runtime profile
python3 ./.codex/skills/bfd-project-init/scripts/bootstrap.py --project-root . --mode check

# 1.5) Optionally regenerate CubeMX-managed files from the current .ioc
python3 ./.codex/skills/bfd-cubemx-codegen/scripts/generate_from_ioc.py --project-root . --log-dir logs/skills

# 2) Flash
./build_tools/jlink/flash.sh builds/gcc/debug | tee logs/flash/flash_$(date +%Y%m%d_%H%M%S).log

# 3) RTT runtime log
./build_tools/jlink/rtt.sh logs/rtt/rtt_$(date +%Y%m%d_%H%M%S).log 5 --mode quick

# 3.5) Native HSS for high-rate, non-halting scalar sampling
bash BFD-Kit/scripts/bfd_jlink_hss.sh --json hss sample \
  --symbol chassis_parameter.IMU.yaw \
  --symbol chassis_parameter.IMU.pitch \
  --duration 0.3 \
  --period-us 1000 \
  --output logs/data_acq/imu_yaw_pitch_hss.csv

# 4) One-shot debug session
./build_tools/jlink/debug.sh | tee logs/debug/debug_$(date +%Y%m%d_%H%M%S).log
```

On `J-Link PLUS`, SEGGER's model limits and local HSS verification both indicate a 10-symbol ceiling. Do not treat `hss inspect` raw capability word 2 as the symbol-count limit. The native sampler writes a synchronized wide CSV to `--output` and a metadata sidecar JSON to `--output.meta.json`.

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

## Integrate Into an Existing Project

The commands below are executed from the `BFD-Kit` repository root to synchronize the toolkit into a target project.

```bash
bash ./init_project.sh --project-root /path/to/your/stm32-project
python3 ./scripts/migrate_bfd_skills.py --repo-root /path/to/your/stm32-project --mode stage
python3 ./scripts/migrate_bfd_skills.py --repo-root /path/to/your/stm32-project --mode cutover
```

- `stage`: import the target project's active `.codex/.claude` BFD skills into the canonical `BFD-Kit/` tree
- `cutover`: push canonical `BFD-Kit/` skills back into the target project's active mirrors and back them up under `archive/skills_migration/`

## Verification

```bash
bash ./init_project.sh --help
bash ./scripts/install_python_runtime.sh --help
python3 ./scripts/bfd_jlink_hss.py --help
python3 ./scripts/migrate_bfd_skills.py --help
```

Inside the target STM32 project root, you can further run:

```bash
python3 ./.codex/skills/bfd-project-init/scripts/bootstrap.py --project-root . --mode check
python3 ./.codex/skills/bfd-project-init/scripts/ensure_profile.py --project-root . --print-env-path
python3 ./.codex/skills/bfd-cubemx-codegen/scripts/generate_from_ioc.py --help
```

## Community

Issues are welcome for bug reports, optimization ideas, and usage feedback.
If you extend the toolkit with new STM32 debug, flashing, data acquisition, or CubeMX generation capabilities, contributions are also welcome.
