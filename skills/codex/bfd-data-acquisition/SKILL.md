---
name: bfd-data-acquisition
description: Use when acquiring STM32 runtime data from global symbols, memory regions, stack-published local slots, or RTT channels and converting captures into structured artifacts for analysis.
---

# BFD Data Acquisition

## Self-Improvement Loop (Required)

- When this skill encounters a build, flash, debug, script-usage, or other workflow problem, do not stop at the local workaround after the issue is solved.
- Record the resolved issue and lesson in `BFD-Kit/.learnings/ERRORS.md` and/or `BFD-Kit/.learnings/LEARNINGS.md`; unresolved capability gaps go to `BFD-Kit/.learnings/FEATURE_REQUESTS.md`.
- Promote reusable fixes into the affected BFD-Kit asset in the same task when feasible: update the relevant `SKILL.md`, script, wrapper, or resource so the next run benefits by default.
- When a learning is promoted into a skill or script, append a short entry to `BFD-Kit/.learnings/CHANGELOG.md` and mention the improvement in the task close-out.

## Purpose

Use this skill when the task is "show the contents of this global/static object" and the object can be resolved from an ELF.

This skill is the default path for:

- global/static object inspection
- pointer-hub decoding
- enum-bearing state objects
- stack-published local-slot capture through pointer symbols
- raw RAM capture only when no stable symbol exists

This skill is not tied to any motor model or business object. The primary workflow is generic `ELF + symbol + DWARF`.

## Required Precheck

Run bootstrap before any acquisition command:

```bash
python3 ./.codex/skills/bfd-project-init/scripts/bootstrap.py --project-root . --mode check
```

Fail fast if `${STM32_ELF}` or the active bootstrap profile is missing.

## Primary Command Contract

Primary script:

```bash
python3 BFD-Kit/skills/codex/bfd-data-acquisition/scripts/data_acq.py ...
```

Primary mode:

```bash
python3 BFD-Kit/skills/codex/bfd-data-acquisition/scripts/data_acq.py \
  --elf "${STM32_ELF}" \
  --mode symbol-auto \
  --symbol <global_symbol> \
  --follow-depth 1 \
  --format summary \
  --output logs/data_acq/<symbol>.summary
```

Meaning of the primary arguments:

- `--mode symbol-auto`: resolve the symbol from ELF, reflect its DWARF type, reuse or rebuild schema cache, sample RAM, and decode named fields.
- `--symbol <global_symbol>`: required global or static object symbol.
- `--follow-depth <N>`: pointer follow depth.
- `--format summary|json|csv`: output renderer.

`symbol-auto` rules:

- requires `--symbol`
- supports only `--capture-mode snapshot`
- rejects manual decode options such as `--decode-profile`, `--layout`, `--pointer-array`, and `--follow-pointer`
- writes or reuses cache under `.codex/bfd/dwarf_cache/`

## Follow-Depth Rules

- `--follow-depth 0`: decode the root object only; pointers remain address metadata.
- `--follow-depth 1`: follow one pointer layer. Use this first for pointer hubs and object tables.
- `--follow-depth >1`: recursively follow nested pointers. Increase only when the object layout requires it.

## Standard Workflow Order

1. Use `--mode symbol-auto` first when the target object has DWARF-supported type information.
2. Fall back to `--mode symbol` only when:
   - the target type contains unsupported DWARF features
   - a manual decode profile is intentionally narrower than the full object
   - a typed scalar layout is sufficient
3. Use `--pointer-symbol` only for stack-published local data.
4. Use raw `--address` capture only when no stable symbol exists.

## Native HSS Escalation

When the requirement is high-rate, non-halting sampling of a fixed-address scalar global/static variable on a J-Link target, prefer the native HSS CLI path instead of GUI J-Scope automation or halt/read/go loops:

```bash
bash BFD-Kit/scripts/bfd_jlink_hss.sh --json hss sample \
  --symbol chassis_parameter.IMU.yaw \
  --symbol chassis_parameter.IMU.pitch \
  --duration 0.3 \
  --period-us 1000 \
  --output logs/data_acq/imu_yaw_pitch_hss.csv
```

Use this path only for fixed-address scalar globals/statics. Repeat `--symbol` for multi-symbol sampling. On `J-Link PLUS`, SEGGER's model limits and local HSS verification both indicate a 10-symbol ceiling; do not treat `hss inspect` raw capability word 2 as the symbol-count limit. The wrapper uses `BFD-Kit/.runtime/venv` automatically after `bash BFD-Kit/init_project.sh --project-root .`. If the target is a pointer-driven object graph or needs DWARF field decoding, stay on `symbol-auto`. The command writes a wide CSV to `--output` and a metadata sidecar JSON to `--output.meta.json`.

## Generic Command Templates

### 1. Decode a Global or Static Object

```bash
python3 BFD-Kit/skills/codex/bfd-data-acquisition/scripts/data_acq.py \
  --elf "${STM32_ELF}" \
  --mode symbol-auto \
  --symbol g_object_state \
  --follow-depth 0 \
  --format summary \
  --output logs/data_acq/g_object_state.summary
```

### 2. Decode a Pointer Hub or Pointer Array

```bash
python3 BFD-Kit/skills/codex/bfd-data-acquisition/scripts/data_acq.py \
  --elf "${STM32_ELF}" \
  --mode symbol-auto \
  --symbol g_object_hub \
  --follow-depth 1 \
  --format json \
  --output logs/data_acq/g_object_hub.json
```

### 3. Manual Symbol Fallback When Auto Reflection Is Not Suitable

```bash
python3 BFD-Kit/skills/codex/bfd-data-acquisition/scripts/data_acq.py \
  --elf "${STM32_ELF}" \
  --mode symbol \
  --symbol g_object_array \
  --count <N> \
  --decode-profile <profile_name> \
  --format csv \
  --output logs/data_acq/g_object_array.csv
```

### 4. Stack-Published Local Variable Capture

```bash
python3 BFD-Kit/skills/codex/bfd-data-acquisition/scripts/data_acq.py \
  --elf "${STM32_ELF}" \
  --pointer-symbol g_local_probe_addr \
  --seq-symbol g_local_probe_seq \
  --layout f32x1 \
  --count 20 \
  --interval-ms 20 \
  --mode nonstop \
  --output logs/data_acq/local_probe.csv
```

### 5. Raw Address Capture

```bash
python3 BFD-Kit/skills/codex/bfd-data-acquisition/scripts/data_acq.py \
  --address 0x20000000 \
  --layout u32x4 \
  --count 20 \
  --mode snapshot \
  --output logs/data_acq/raw_u32.csv
```

## Output Policy

- Save final artifacts under `logs/data_acq/`.
- Use `summary` for fast operator judgment.
- Use `json` for downstream AI or tool consumption.
- Use `csv` for manual table review.
- Treat `.codex/bfd/dwarf_cache/` as a reusable cache, not as the final evidence artifact.
- Do not run multiple J-Link RAM sampling, RTT, or GDB attach flows against the same target in parallel.

## Decision Rules

Use this skill instead of hand-written GDB or J-Link memory expressions when:

- an ELF symbol exists
- the task is "inspect this global/static object"
- the task needs named fields rather than raw words
- RTT produced no payload and RAM is the next validation path

Switch to `bfd-debug-interface` only when:

- the task is register-centric
- the symbol is not available
- lower-level breakpoint, watchpoint, or fault control is required
