---
name: bfd-debug-orchestrator
description: Use when running end-to-end STM32 debug campaigns that coordinate flash, RTT, register capture, HardFault snapshots, and error archival across multiple tools.
---

# BFD Debug Orchestrator

## Self-Improvement Loop (Required)

- When this skill encounters a build, flash, debug, script-usage, or other workflow problem, do not stop at the local workaround after the issue is solved.
- Record the resolved issue and lesson in `BFD-Kit/.learnings/ERRORS.md` and/or `BFD-Kit/.learnings/LEARNINGS.md`; unresolved capability gaps go to `BFD-Kit/.learnings/FEATURE_REQUESTS.md`.
- Promote reusable fixes into the affected BFD-Kit asset in the same task when feasible: update the relevant `SKILL.md`, script, wrapper, or resource so the next run benefits by default.
- When a learning is promoted into a skill or script, append a short entry to `BFD-Kit/.learnings/CHANGELOG.md` and mention the improvement in the task close-out.

Use this skill to coordinate multi-step debug campaigns with profile-driven device settings.

## Execution Order

1. `bfd-project-init`
2. `systematic-debugging`
3. `bfd-rtt-logger`
4. `bfd-debug-executor`
5. `bfd-register-capture`
6. `bfd-fault-logger`
7. `verification-before-completion`

## Core Commands

```bash
# 0) Bootstrap profile (required)
python3 ./.codex/skills/bfd-project-init/scripts/bootstrap.py --project-root . --mode check
```

```bash
# Full fault campaign
./.codex/skills/bfd-debug-orchestrator/scripts/run_fault_campaign.sh
```

```bash
# Inject one scenario
./.codex/skills/bfd-debug-orchestrator/scripts/inject_fault_scenario.sh --scenario 3
```

```bash
# Capture one HardFault snapshot
./.codex/skills/bfd-debug-orchestrator/scripts/capture_hardfault_snapshot.sh
```

```bash
# Manual quick RTT capture without reset (attach-only, for soft fault 1/2)
./build_tools/jlink/rtt.sh logs/rtt/manual_quick.log 4 --mode quick
```

```bash
# Manual dual RTT capture after recovery reset/go
./build_tools/jlink/rtt.sh logs/rtt/manual_dual.log 6 --mode dual --reset-policy gdb-reset-go
```

## Scenario Set

- `1`: recoverable IMU communication fault
- `2`: recoverable Flash parameter fault
- `3`: illegal address write (HardFault)
- `4`: UDF trap (UsageFault/HardFault)

## RTT Mode Semantics

- `quick`: attach-only RTT capture for scenarios `1/2`; do not issue reset before collecting the injected soft-fault log.
- `dual`: reset-aware recovery capture for scenarios `3/4`; use GDBServer + RTTClient and let GDB own the reset/go sequence.
- Baseline and final smoke checks may still use `quick`, but those calls are no longer allowed to depend on `build_tools/jlink/rtt.jlink`.

## Hard Rules

- Fail-fast if bootstrap profile is missing.
- Output only key conclusions and evidence paths by default.
- For each HardFault, generate both `md` and `json` records.
- Save all artifacts under `logs/` or `.codex/debug/`.
- `quick` mode is attach-only and must not reset away `g_debug_fault_scenario` before soft-fault evidence is captured.
- `dual` mode is reserved for reset-aware recovery verification and should drive reset/go through the same GDB server backend.

## References

- `.codex/skills/bfd-debug-orchestrator/references/hardfault_record_template.md`
- `.codex/skills/bfd-debug-orchestrator/references/error_evolution_schema.md`
- `.codex/skills/bfd-debug-orchestrator/references/token_saving_output_rules.md`
- `.codex/skills/bfd-debug-orchestrator/resources/README.md`
- `.codex/skills/bfd-debug-orchestrator/resources/f4/debug_fault_template.h`
- `.codex/skills/bfd-debug-orchestrator/resources/f4/debug_fault_template.c`
