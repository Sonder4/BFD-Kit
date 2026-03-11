---
name: bfd-debug-executor
description: Use when running direct J-Link command sequences for breakpoints, stepping, register reads, and one-shot debug actions on STM32 targets.
---

# BFD Debug Executor

## Self-Improvement Loop (Required)

- When this skill encounters a build, flash, debug, script-usage, or other workflow problem, do not stop at the local workaround after the issue is solved.
- Record the resolved issue and lesson in `BFD-Kit/.learnings/ERRORS.md` and/or `BFD-Kit/.learnings/LEARNINGS.md`; unresolved capability gaps go to `BFD-Kit/.learnings/FEATURE_REQUESTS.md`.
- Promote reusable fixes into the affected BFD-Kit asset in the same task when feasible: update the relevant `SKILL.md`, script, wrapper, or resource so the next run benefits by default.
- When a learning is promoted into a skill or script, append a short entry to `BFD-Kit/.learnings/CHANGELOG.md` and mention the improvement in the task close-out.

Use this skill for fast, scriptable J-Link actions without a full GDB session.

## Quick Start

1. Run bootstrap profile first.
2. Keep logs under `logs/debug/`.
3. Use command-file based execution for reproducibility.

## Core Commands

```bash
# 0) Bootstrap profile (required)
python3 ./.codex/skills/bfd-project-init/scripts/bootstrap.py --project-root . --mode check
```

```bash
# Break at main, run, and dump registers
JLinkExe -device "${STM32_DEVICE}" -if "${STM32_IF}" -speed "${STM32_SPEED_KHZ}" <<'EOF2' | tee logs/debug/debug_main.log
connect
h
bs main
go
wait
regs
exit
EOF2
```

```bash
# Recommended for multi-step sessions
cat > logs/debug/debug_cmd.jlink <<'EOF2'
connect
h
bs main
go
wait
regs
exit
EOF2
JLinkExe -device "${STM32_DEVICE}" -if "${STM32_IF}" -speed "${STM32_SPEED_KHZ}" -CommandFile logs/debug/debug_cmd.jlink | tee logs/debug/debug_cmd.log
```

```powershell
pwsh -File ./.codex/skills/bfd-debug-executor/scripts/debug.ps1 -Breakpoint "main" -AfterHit "regs"
```

## Workflow

1. Run bootstrap profile.
2. Connect and halt.
3. Execute breakpoint/step/register commands.
4. Save and report `PC/LR/xPSR` evidence.

## Hard Rules

- Fail-fast if bootstrap profile is missing.
- Use CLI commands or command files, not interactive typing.
- Save each debug session log under `logs/debug/`.
- Do not write memory/registers before device identity is confirmed.

## Scripts

- `.codex/skills/bfd-debug-executor/scripts/debug.ps1`

## Related Skills

- `bfd-project-init`
- `bfd-debug-interface`
- `bfd-register-capture`
- `bfd-rtt-logger`
