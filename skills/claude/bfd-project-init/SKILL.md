---
name: bfd-project-init
description: Use when preparing an STM32 project for debug/flash/RTT workflows by scanning ioc/startup/linker/svd/cfg files, generating a unified profile, and optionally creating missing baseline files.
---

# BFD Project Init

## Self-Improvement Loop (Required)

- When this skill encounters a build, flash, debug, script-usage, or other workflow problem, do not stop at the local workaround after the issue is solved.
- Record the resolved issue and lesson in `BFD-Kit/.learnings/ERRORS.md` and/or `BFD-Kit/.learnings/LEARNINGS.md`; unresolved capability gaps go to `BFD-Kit/.learnings/FEATURE_REQUESTS.md`.
- Promote reusable fixes into the affected BFD-Kit asset in the same task when feasible: update the relevant `SKILL.md`, script, wrapper, or resource so the next run benefits by default.
- When a learning is promoted into a skill or script, append a short entry to `BFD-Kit/.learnings/CHANGELOG.md` and mention the improvement in the task close-out.

Use this skill to generate one canonical STM32 runtime profile consumed by all debug/flash/RTT skills.

## Quick Start

1. Run the profile scan.
2. Check blockers and warnings.
3. Re-run with `--mode apply --apply` only when missing baseline files must be created.

## Core Commands

```bash
# Canonical profile refresh
python3 ./.codex/skills/bfd-project-init/scripts/bootstrap.py \
  --project-root . \
  --mode check \
  --out-json .codex/bfd/active_profile.json \
  --out-env .codex/bfd/active_profile.env \
  --report .codex/bfd/bootstrap_report.md
```

```bash
# Auto-init / freshness check for downstream scripts
python3 ./.codex/skills/bfd-project-init/scripts/ensure_profile.py \
  --project-root . \
  --print-env-path
```

```bash
# Safe autofix (explicit apply required)
python3 ./.codex/skills/bfd-project-init/scripts/bootstrap.py \
  --project-root . \
  --mode apply \
  --apply
```

## Workflow

1. Parse `.ioc` and detect MCU family/device.
2. Locate startup/linker/svd/cfg/build artifacts.
3. Export IOC JSON into `.codex/bfd/ioc_json/`.
4. Emit canonical profile JSON/env into `.codex/bfd/`.
5. Mirror profile outputs into legacy `.codex/stm32/bootstrap/` for compatibility.
6. Fail on blockers; keep warnings as evidence.

## Hard Rules

- Do not run flash/debug/RTT skills before profile generation.
- Canonical runtime files live under `.codex/bfd/`.
- Legacy `.codex/stm32/bootstrap/` is compatibility-only.
- In apply mode, do not overwrite existing files unless `--force` is set.

## Outputs

- `.codex/bfd/active_profile.json`
- `.codex/bfd/active_profile.env`
- `.codex/bfd/bootstrap_report.md`
- `.codex/bfd/ioc_json/`
- `.codex/stm32/bootstrap/active_profile.json`
- `.codex/stm32/bootstrap/active_profile.env`

## Scripts

- `.codex/skills/bfd-project-init/scripts/bootstrap.py`
- `.codex/skills/bfd-project-init/scripts/ensure_profile.py`

## References

- `.codex/skills/bfd-project-init/references/file-matrix.md`
- `.codex/skills/bfd-project-init/references/profile-schema.md`

## Related Skills

- `bfd-ioc-parser`
- `bfd-cubemx-codegen`
- `bfd-flash-programmer`
- `bfd-rtt-logger`
- `bfd-debug-executor`
- `bfd-debug-orchestrator`
