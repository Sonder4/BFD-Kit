---
name: bfd-fault-logger
description: Use when recording STM32 hardware faults such as HardFault, BusFault, and UsageFault, then exporting structured fault reports.
---

# BFD Fault Logger

## Self-Improvement Loop (Required)

- When this skill encounters a build, flash, debug, script-usage, or other workflow problem, do not stop at the local workaround after the issue is solved.
- Record the resolved issue and lesson in `BFD-Kit/.learnings/ERRORS.md` and/or `BFD-Kit/.learnings/LEARNINGS.md`; unresolved capability gaps go to `BFD-Kit/.learnings/FEATURE_REQUESTS.md`.
- Promote reusable fixes into the affected BFD-Kit asset in the same task when feasible: update the relevant `SKILL.md`, script, wrapper, or resource so the next run benefits by default.
- When a learning is promoted into a skill or script, append a short entry to `BFD-Kit/.learnings/CHANGELOG.md` and mention the improvement in the task close-out.

Use this skill to archive fault evidence in structured formats.

## Quick Start

1. Create `logs/hw_error/`.
2. Capture fault context before reset.
3. Save records, classify, and export reports.

## Core Commands

```bash
# Record one HardFault example
python3 - <<'PY'
import sys
sys.path.append('.codex/skills/bfd-fault-logger/scripts')
from error_logger import HardwareErrorLogger
logger = HardwareErrorLogger(storage_path='logs/hw_error')
record = logger.record_hard_fault(
    registers={"PC":"0x08004567","LR":"0x08002345","SP":"0x2001FFF0"},
    cfsr='0x00000200', hfsr='0x40000000',
    stack_trace=['0x08004567','0x08002345']
)
print(record.id)
PY
```

```bash
# Classify records
python3 ./.codex/skills/bfd-fault-logger/scripts/error_classifier.py
```

```bash
# Export reports
python3 ./.codex/skills/bfd-fault-logger/scripts/error_exporter.py
mv -f test_report.json logs/hw_error/
mv -f test_report.csv logs/hw_error/
```

## Workflow

1. Capture and store fault context.
2. Classify severity and source.
3. Export JSON/CSV/HTML reports.

## Hard Rules

- Save final outputs under `logs/hw_error/`.
- Each HardFault record must include `PC/LR/SP`, `CFSR/HFSR`, and `stack_trace`.
- Never reset before preserving fault evidence.

## Scripts

- `.codex/skills/bfd-fault-logger/scripts/error_logger.py`
- `.codex/skills/bfd-fault-logger/scripts/error_classifier.py`
- `.codex/skills/bfd-fault-logger/scripts/error_exporter.py`
- `.codex/skills/bfd-fault-logger/scripts/rtt_capture.py`

## Related Skills

- `bfd-debug-interface`
- `bfd-rtt-logger`
- `bfd-debug-orchestrator`
