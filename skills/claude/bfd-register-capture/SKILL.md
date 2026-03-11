---
name: bfd-register-capture
description: Use when sampling STM32 peripheral registers, tracking register changes over time, or exporting register snapshots to CSV for hardware-state analysis.
---

# BFD Register Capture

## Self-Improvement Loop (Required)

- When this skill encounters a build, flash, debug, script-usage, or other workflow problem, do not stop at the local workaround after the issue is solved.
- Record the resolved issue and lesson in `BFD-Kit/.learnings/ERRORS.md` and/or `BFD-Kit/.learnings/LEARNINGS.md`; unresolved capability gaps go to `BFD-Kit/.learnings/FEATURE_REQUESTS.md`.
- Promote reusable fixes into the affected BFD-Kit asset in the same task when feasible: update the relevant `SKILL.md`, script, wrapper, or resource so the next run benefits by default.
- When a learning is promoted into a skill or script, append a short entry to `BFD-Kit/.learnings/CHANGELOG.md` and mention the improvement in the task close-out.

Use this skill to capture register evidence with repeatable scripts.

## Quick Start

1. Run bootstrap profile first.
2. Select peripheral and register set.
3. Capture short first, then extend duration.

## Core Commands

```bash
# 0) Bootstrap profile (required)
python3 ./.codex/skills/bfd-project-init/scripts/bootstrap.py --project-root . --mode check
```

```bash
# USART1, 1 second
./.codex/skills/bfd-register-capture/scripts/capture_registers.sh -p USART1 -d 1 -o logs/debug/usart1_1s.csv
```

```bash
# CAN1 key status registers (STM32F427 bxCAN)
./.codex/skills/bfd-register-capture/scripts/capture_registers.sh -p CAN1 -r MCR,MSR,TSR,RF0R,RF1R,ESR,BTR -d 5 -o logs/debug/can1_status.csv
```

```bash
# Fast status check
./.codex/skills/bfd-register-capture/scripts/capture_registers.sh -p CAN1 -s
```

```bash
# High-frequency batch capture
./.codex/skills/bfd-register-capture/scripts/jlink_batch_capture.sh USART1 10 logs/debug/usart1_batch.csv
```

## Workflow

1. Run bootstrap profile.
2. Define peripheral and registers.
3. Run short validation capture.
4. Run production capture and export CSV.

## Hard Rules

- Fail-fast if bootstrap profile is missing.
- Save final captures under `logs/debug/`.
- Do not sample unknown peripheral addresses.
- Treat zero-sample output as failed capture.

## Scripts

- `.codex/skills/bfd-register-capture/scripts/capture_registers.sh`
- `.codex/skills/bfd-register-capture/scripts/capture_registers.ps1`
- `.codex/skills/bfd-register-capture/scripts/jlink_batch_capture.sh`
- `.codex/skills/bfd-register-capture/scripts/jlink_fast_capture.py`

## Related Skills

- `bfd-project-init`
- `bfd-debug-executor`
- `bfd-rtt-logger`
- `bfd-data-acquisition`
