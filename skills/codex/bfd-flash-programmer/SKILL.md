---
name: bfd-flash-programmer
description: Use when flashing STM32 firmware, verifying flash results, diagnosing download failures, or running repeatable CLI-based flash workflows.
---

# BFD Flash Programmer

## Self-Improvement Loop (Required)

- When this skill encounters a build, flash, debug, script-usage, or other workflow problem, do not stop at the local workaround after the issue is solved.
- Record the resolved issue and lesson in `BFD-Kit/.learnings/ERRORS.md` and/or `BFD-Kit/.learnings/LEARNINGS.md`; unresolved capability gaps go to `BFD-Kit/.learnings/FEATURE_REQUESTS.md`.
- Promote reusable fixes into the affected BFD-Kit asset in the same task when feasible: update the relevant `SKILL.md`, script, wrapper, or resource so the next run benefits by default.
- When a learning is promoted into a skill or script, append a short entry to `BFD-Kit/.learnings/CHANGELOG.md` and mention the improvement in the task close-out.

Use this skill for deterministic flash and verification workflows.

## Quick Start

1. Generate bootstrap profile first.
2. Confirm `STM32_DEVICE/STM32_ELF` in profile.
3. Flash and keep logs under `logs/flash/`.

## Core Commands

```bash
# 0) Bootstrap profile (required)
python3 ./.codex/skills/bfd-project-init/scripts/bootstrap.py --project-root . --mode check
```

```bash
# 1) Project standard flash flow
./build_tools/jlink/flash.sh | tee logs/flash/flash_$(date +%Y%m%d_%H%M%S).log
```

```bash
# 2) Optional build-dir override
./build_tools/jlink/flash.sh builds/gcc/debug | tee logs/flash/flash_builddir_$(date +%Y%m%d_%H%M%S).log
```

```bash
# 3) Python wrapper with explicit override
python3 ./.codex/skills/bfd-flash-programmer/scripts/jlink_flash.py \
  --firmware "${STM32_HEX}" \
  --device "${STM32_DEVICE}" \
  --address 0x08000000
```

## Workflow

1. Run bootstrap profile.
2. Connect and identify device.
3. Program and verify.
4. Reset and validate runtime logs.

## Hard Rules

- Fail-fast if bootstrap profile is missing.
- Save final flash logs under `logs/flash/`.
- Always run verification after programming.
- Do not erase before confirming exact device model.

## Scripts

- `./build_tools/jlink/flash.sh`
- `.codex/skills/bfd-flash-programmer/scripts/jlink_flash.py`
- `.codex/skills/bfd-flash-programmer/scripts/stlink_flash.py`

## Related Skills

- `bfd-project-init`
- `bfd-rtt-logger`
- `bfd-debug-interface`
- `verification-before-completion`
