# STM32 `g_debug_fault_scenario` Integration Guide

This resource directory provides the smallest reusable baseline required by `bfd-debug-orchestrator` when moving the skill into another STM32 firmware project. The goal is to let J-Link write a scenario value directly into `g_debug_fault_scenario` and have the firmware consume it from an existing periodic task.

## Required capability

A target project must provide all of the following:

- A global symbol named exactly `volatile uint32_t g_debug_fault_scenario`
- A one-time init entry `DebugFaultInit()`
- A periodic polling entry `DebugFaultTask()`
- Recoverable RTT evidence for soft-fault scenarios
- Deterministic CPU exceptions for hard-fault scenarios

## Files to add

Copy these templates into the target project's user-maintained source tree, for example:

- `USER/Modules/debug_fault/debug_fault.h`
- `USER/Modules/debug_fault/debug_fault.c`

Recommended source templates:

- `f4/debug_fault_template.h`
- `f4/debug_fault_template.c`

If the target is not STM32F4, keep the same public symbol and API names, but adapt include files and trap instructions as needed.

## Files to modify

Update at least one existing periodic application entry point, such as:

- Main application loop
- FreeRTOS periodic task body
- Central scheduler tick

Minimal integration steps:

1. Call `DebugFaultInit()` during normal application initialization.
2. Call `DebugFaultTask()` from a periodic task that runs roughly every 1-10 ms.
3. Ensure `debug_fault.c` is part of the final firmware build.

If the project uses recursive CMake source discovery for `USER/**/*.c`, simply placing the files in the user source tree may be enough. If sources are listed explicitly, add `debug_fault.c` to that list.

## Required symbol

The inject script resolves this exact symbol name from the ELF:

```c
volatile uint32_t g_debug_fault_scenario;
```

If the symbol name changes, `inject_fault_scenario.sh` fails with:

```text
symbol g_debug_fault_scenario not found in ELF
```

## Scenario meanings

- `1`: recoverable IMU communication fault log; system keeps running
- `2`: recoverable flash parameter fault log; system keeps running
- `3`: illegal address write; produces a real HardFault or equivalent hard exception
- `4`: undefined instruction; produces a UsageFault or escalated HardFault

Unknown values should log a warning only once until the scenario register returns to zero.

## Recommended hook pattern

```c
void AppInit(void)
{
  DebugFaultInit();
}

void AppTask(void)
{
  DebugFaultTask();
}
```

Hook the task into a central application loop rather than a subsystem-specific path to keep the integration portable.

## What to adapt in the templates

These parts usually need to match the target project:

- Logging header, for example `bsp_log.h`
- Common MCU header, for example `main.h`
- Logging macros, for example `LOGWARNING` and `LOGERROR`
- Fault trigger details if toolchain or core behavior differs

## Verification

### Baseline

- Boot firmware with `g_debug_fault_scenario = 0`
- Confirm RTT baseline output remains normal
- Confirm no new periodic spam appears

### RTT semantics

- `quick` is attach-only and is intended for scenarios `1/2`
- `quick` must not reset the target after `inject_fault_scenario.sh`, otherwise the RAM-backed `g_debug_fault_scenario` value is lost before the soft-fault log is emitted
- `dual` is for scenarios `3/4` after snapshot/reflash and may use GDB-driven `reset/go`
- If a migrated project also uses RAM injection for soft faults, preserve this split instead of treating `quick` and `dual` as name-only variants

### Per-scenario

- Write `1`: expect one recoverable soft-fault log
- Write `2`: expect one recoverable parameter-fault log
- Write `3`: expect a real target fault captured by debug tooling
- Write `4`: expect a second real target fault path
- Write `99`: expect one warning only

### End-to-end orchestrator

- Rebuild the ELF and confirm `arm-none-eabi-nm` can find `g_debug_fault_scenario`
- Run `inject_fault_scenario.sh --scenario 1`
- Run `run_fault_campaign.sh --skip-build --build-dir <your-build-dir> --scenarios 1`
- Repeat for scenarios `2`, `3`, and `4`
- Confirm soft faults leave RTT evidence and hard faults advance into snapshot capture

## Why use resource files

When migrating the skill, copy the template files from this resource directory instead of pasting code from `SKILL.md`. That keeps:

- Symbol names consistent
- Scenario numbers consistent
- API names consistent
- Documentation and templates versioned together
