---
name: bfd-rtt-logger
description: Use when capturing STM32 RTT output, validating runtime behavior after flash/reset, or collecting short runtime evidence from J-Link RTT channels.
---

# BFD RTT Logger

## Self-Improvement Loop (Required)

- When this skill encounters a build, flash, debug, script-usage, or other workflow problem, do not stop at the local workaround after the issue is solved.
- Record the resolved issue and lesson in `BFD-Kit/.learnings/ERRORS.md` and/or `BFD-Kit/.learnings/LEARNINGS.md`; unresolved capability gaps go to `BFD-Kit/.learnings/FEATURE_REQUESTS.md`.
- Promote reusable fixes into the affected BFD-Kit asset in the same task when feasible: update the relevant `SKILL.md`, script, wrapper, or resource so the next run benefits by default.
- When a learning is promoted into a skill or script, append a short entry to `BFD-Kit/.learnings/CHANGELOG.md` and mention the improvement in the task close-out.

Use this skill to capture RTT logs with profile-driven defaults.

## Quick Start

1. Run bootstrap profile first.
2. Use `quick` mode for routine runtime checks.
3. Use `dual` mode after reset/reconnect flows.

## Core Commands

```bash
# 0) Bootstrap profile (required)
python3 ./.codex/skills/bfd-project-init/scripts/bootstrap.py --project-root . --mode check
```

```bash
# 1) Quick mode
./build_tools/jlink/rtt.sh logs/rtt/rtt_quick.log 5 --mode quick
```

```bash
# 2) Dual mode for reset-follow capture
./build_tools/jlink/rtt.sh logs/rtt/rtt_dual.log 6 --mode dual --reset-policy gdb-reset-go
```

```bash
# 3) Resolve RTT address from profile ELF
./.codex/skills/bfd-rtt-logger/scripts/get_rtt_address.sh \
  --elf "${STM32_ELF}" \
  --device "${STM32_DEVICE}" \
  --out logs/debug/rtt_addr_probe.log
```

## Workflow

1. Run bootstrap and verify profile env.
2. Confirm RTT symbol/address.
3. Capture with `quick` or `dual`.
4. Archive logs and extract key evidence lines.
5. If `quick` mode reports `fallback_no_payload`, `RTT_SUCCESS=0`, or `RTT Control Block not found`, stop RTT-based judgment and switch to standardized RAM sampling.

## Mandatory Fallback: RTT Failure to RAM Sampling

Trigger this branch when any of the following is observed:

- `fallback_no_payload`
- `RTT_SUCCESS=0`
- `RTT Control Block not found`
- RTT attaches but produces no usable application payload

Do not treat these results as proof that motors are offline.

Primary fallback target:

- first choice: `bfd-data-acquisition --mode symbol-auto`
- second choice: `bfd-data-acquisition --mode symbol` when the target type requires a manual profile or layout
- last choice: raw address sampling or low-level debug commands

### Fallback Step 1: Generic Symbol-Auto Decode

```bash
python3 BFD-Kit/skills/codex/bfd-data-acquisition/scripts/data_acq.py \
  --elf "${STM32_ELF}" \
  --mode symbol-auto \
  --symbol <global_symbol> \
  --follow-depth 1 \
  --format summary \
  --output logs/data_acq/<global_symbol>.summary
```

### Fallback Step 2: Manual Symbol Fallback When Auto Reflection Is Not Suitable

```bash
python3 BFD-Kit/skills/codex/bfd-data-acquisition/scripts/data_acq.py \
  --elf "${STM32_ELF}" \
  --mode symbol \
  --symbol <global_symbol> \
  --count <N> \
  --decode-profile <profile_name> \
  --format summary \
  --output logs/data_acq/<global_symbol>.summary
```

Archival form:

```bash
python3 BFD-Kit/skills/codex/bfd-data-acquisition/scripts/data_acq.py \
  --elf "${STM32_ELF}" \
  --mode symbol \
  --symbol <global_symbol> \
  --count <N> \
  --decode-profile <profile_name> \
  --format json \
  --output logs/data_acq/<global_symbol>.json
```

This fallback is the default next action after RTT payload failure. Do not invent a new J-Link or GDB command first.

If the required output is not a decoded object snapshot but a high-rate, non-halting fixed-address scalar stream, switch to the native HSS wrapper:

```bash
bash BFD-Kit/scripts/bfd_jlink_hss.sh --json hss sample \
  --symbol <scalar_symbol_path> \
  --duration 0.3 \
  --period-us 1000 \
  --output logs/data_acq/<scalar_symbol_path>.csv
```

## Hard Rules

- Fail-fast if bootstrap profile is missing.
- Save final logs under `logs/rtt/`.
- In `dual` mode, do not open competing J-Link sessions.
- Keep final evidence in repository paths only.
- RTT attach can succeed while still producing no usable application payload; treat `fallback_no_payload` as an acquisition limitation, not proof that the target object is stale or offline.
- After RTT fallback, use `bfd-data-acquisition` as the primary RAM-decoding path. Use `bfd-debug-interface` only if symbol resolution fails or lower-level debug control is required.

## Scripts

- `.codex/skills/bfd-rtt-logger/scripts/rtt_log.sh`
- `.codex/skills/bfd-rtt-logger/scripts/rtt_log.ps1`
- `.codex/skills/bfd-rtt-logger/scripts/get_rtt_address.sh`

## Related Skills

- `bfd-project-init`
- `bfd-debug-interface`
- `bfd-fault-logger`
- `bfd-debug-orchestrator`
