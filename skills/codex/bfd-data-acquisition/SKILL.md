---
name: bfd-data-acquisition
description: Use when acquiring STM32 runtime data from variables, memory regions, or RTT channels and converting captures into CSV or analysis artifacts.
---

# BFD Data Acquisition

## Self-Improvement Loop (Required)

- When this skill encounters a build, flash, debug, script-usage, or other workflow problem, do not stop at the local workaround after the issue is solved.
- Record the resolved issue and lesson in `BFD-Kit/.learnings/ERRORS.md` and/or `BFD-Kit/.learnings/LEARNINGS.md`; unresolved capability gaps go to `BFD-Kit/.learnings/FEATURE_REQUESTS.md`.
- Promote reusable fixes into the affected BFD-Kit asset in the same task when feasible: update the relevant `SKILL.md`, script, wrapper, or resource so the next run benefits by default.
- When a learning is promoted into a skill or script, append a short entry to `BFD-Kit/.learnings/CHANGELOG.md` and mention the improvement in the task close-out.

Use this skill to collect runtime data and produce analysis-ready artifacts.

## Quick Start

1. Run bootstrap profile first.
2. Select source: variable, memory address, or RTT.
3. Capture raw data first, then run analysis.

## Core Commands

```bash
# 0) Bootstrap profile (required)
python3 ./.codex/skills/bfd-project-init/scripts/bootstrap.py --project-root . --mode check
```

```bash
# Variable capture
python3 ./.codex/skills/bfd-data-acquisition/scripts/data_acq.py \
  --device "${STM32_DEVICE}" --variable g_sensorData --count 1000 \
  --output logs/data_acq/sensor_data.csv
```

```bash
# Memory region capture
python3 ./.codex/skills/bfd-data-acquisition/scripts/data_acq.py \
  --device "${STM32_DEVICE}" --address 0x20000000 --size 256 --count 100 \
  --output logs/data_acq/mem_watch.csv
```

```bash
# RTT stream capture
python3 ./.codex/skills/bfd-data-acquisition/scripts/data_acq.py \
  --device "${STM32_DEVICE}" --rtt --channel 0 --count 10000 \
  --output logs/data_acq/rtt_stream.csv
```

```bash
# Runtime-published local variable capture
python3 ./.codex/skills/bfd-data-acquisition/scripts/data_acq.py \
  --elf "${STM32_ELF}" \
  --pointer-symbol g_local_probe_addr \
  --seq-symbol g_local_probe_seq \
  --layout f32x1 \
  --count 20 \
  --interval-ms 20 \
  --mode nonstop \
  --output logs/data_acq/local_probe.csv
```

```bash
# Analysis
python3 ./.codex/skills/bfd-data-acquisition/scripts/data_analysis.py --input logs/data_acq/sensor_data.csv --stats
python3 ./.codex/skills/bfd-data-acquisition/scripts/data_analysis.py --input logs/data_acq/sensor_data.csv --fft --output logs/data_acq/spectrum.png
```

## Workflow

1. Run bootstrap profile.
2. Run short trial capture.
3. Run full capture and store raw outputs.
4. Generate stats/plots from stored artifacts.

## Hard Rules

- Fail-fast if bootstrap profile is missing.
- Save capture and analysis outputs under `logs/data_acq/`.
- Match sampling rate to signal characteristics.
- Confirm ELF symbols before variable-based capture.
- For stack-local variables, publish the runtime address from firmware first; do not assume ELF alone can locate a live stack slot.

## Scripts

- `.codex/skills/bfd-data-acquisition/scripts/data_acq.py`
- `.codex/skills/bfd-data-acquisition/scripts/data_analysis.py`

## Resources

- `.codex/skills/bfd-data-acquisition/resources/local-probe/local_probe_runtime.h`
- `.codex/skills/bfd-data-acquisition/resources/local-probe/local_probe_runtime.c`
- `.codex/skills/bfd-data-acquisition/resources/local-probe/local_probe_integration.md`

## Related Skills

- `bfd-project-init`
- `bfd-register-capture`
- `bfd-rtt-logger`
- `bfd-debug-interface`
