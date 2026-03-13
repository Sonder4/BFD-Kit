---
name: bfd-debug-interface
description: Use when debugging STM32 applications with J-Link or ST-Link, including breakpoints, watchpoints, register or memory inspection, HardFault analysis, and automated fault-context capture.
---

# BFD Debug Interface

## Self-Improvement Loop (Required)

- When this skill encounters a build, flash, debug, script-usage, or other workflow problem, do not stop at the local workaround after the issue is solved.
- Record the resolved issue and lesson in `BFD-Kit/.learnings/ERRORS.md` and/or `BFD-Kit/.learnings/LEARNINGS.md`; unresolved capability gaps go to `BFD-Kit/.learnings/FEATURE_REQUESTS.md`.
- Promote reusable fixes into the affected BFD-Kit asset in the same task when feasible: update the relevant `SKILL.md`, script, wrapper, or resource so the next run benefits by default.
- When a learning is promoted into a skill or script, append a short entry to `BFD-Kit/.learnings/CHANGELOG.md` and mention the improvement in the task close-out.

## Overview

Use this skill to run standardized STM32 debug sessions with repeatable CLI and GDB commands.

This skill is for debug control, not for routine structured decoding of global/static variables. When the task is "read a symbol and decode its contents", delegate to `bfd-data-acquisition`.

## Required Precheck

Run bootstrap before any debug action:

```bash
python3 ./.codex/skills/bfd-project-init/scripts/bootstrap.py --project-root . --mode check
```

## Log and Evidence Policy (Required)

- Save debug session logs and register snapshots under repository paths.
- Use:
  - `logs/debug/` for session and register logs
  - `logs/hw_error/` for fault records
- Do not keep final artifacts in `/tmp`.
- Fail-fast when `.codex/bfd/active_profile.env` is missing.

## Delegation Rule: Global Symbol Content

Do not hand-write `x/...`, `monitor mem32`, or ad-hoc J-Link memory sequences for structured global/static objects when all of the following are true:

- the ELF is available
- the target object is a global/static symbol
- the task needs named-field output rather than raw words

In that case, switch to `bfd-data-acquisition` and use the generic `symbol-auto` contract first.

Default delegated command:

```bash
python3 BFD-Kit/skills/codex/bfd-data-acquisition/scripts/data_acq.py \
  --elf "${STM32_ELF}" \
  --mode symbol-auto \
  --symbol <global_symbol> \
  --follow-depth 1 \
  --format summary \
  --output logs/data_acq/<global_symbol>.summary
```

If `symbol-auto` cannot decode the target due to unsupported DWARF features, fall back to `bfd-data-acquisition --mode symbol` with an explicit `--decode-profile` or `--layout`.

If the task is instead “sample one fixed-address scalar symbol at high rate without halting the core”, delegate to the native HSS wrapper:

```bash
bash BFD-Kit/scripts/bfd_jlink_hss.sh --json hss sample \
  --symbol <scalar_symbol_path> \
  --duration 0.3 \
  --period-us 1000 \
  --output logs/data_acq/<scalar_symbol_path>.csv
```

Use raw GDB/J-Link memory commands only when:

- no ELF symbol is available
- the task is register-centric rather than data-centric
- the address must be inspected before a reusable decode contract exists

## Tool Resolution

| Tool | Rule |
|------|------|
| J-Link | Resolve from `PATH` (`JLinkExe`, `JLinkGDBServerCLExe`) |
| ST-Link | Resolve from `PATH` (`ST-LINK_gdbserver`) |
| SVD Files | Resolve from `STM32_SVD` in bootstrap profile |

## Quick Session (5 Steps)

1. Start GDB server.
```bash
JLinkGDBServerCLExe -device "${STM32_DEVICE}" -if "${STM32_IF}" -speed "${STM32_SPEED_KHZ}" -port 2331
# or
ST-LINK_gdbserver.exe -p 61234 -m 1
```

2. Connect GDB.
```bash
arm-none-eabi-gdb "${STM32_ELF}"
(gdb) target remote localhost:2331
# or
(gdb) target remote localhost:61234
```

3. Initialize target.
```gdb
(gdb) monitor reset halt
(gdb) load
```

4. Set critical breakpoints.
```gdb
(gdb) break main
(gdb) break HardFault_Handler
```

5. Run and capture evidence.
```gdb
(gdb) continue
(gdb) backtrace
(gdb) info registers
```

## Full Command Reference

### 1) Connect and Load

```gdb
target remote localhost:2331         connect to J-Link
target remote localhost:61234        connect to ST-Link
file build/firmware.elf              load symbols
load                                 load program to target
```

### 2) Execution Control

```gdb
run                          start execution (with load)
continue                     continue execution
continue <count>             continue, ignore count-1 breaks
step                         step into (source line)
stepi                        step into (instruction)
next                         step over (source line)
nexti                        step over (instruction)
finish                       run until function returns
until                        run until line/address
jump *0x08001000             jump to address
```

### 3) Breakpoint Management

#### Set Breakpoints

```gdb
break main                    break at function
break file.c:123              break at line
break *0x08001234             break at address
break func if var > 10        conditional breakpoint
tbreak main                   temporary breakpoint
hbreak HardFault_Handler      hardware breakpoint
thbreak func                  temporary hardware breakpoint
```

#### Manage Breakpoints

```gdb
info breakpoints              list all breakpoints
delete <num>                  delete breakpoint
disable <num>                 disable breakpoint
enable <num>                  enable breakpoint
clear main                    clear by function
clear file.c:123              clear by line
ignore <num> <count>          ignore breakpoint N times
condition <num> <expr>        set condition
commands <num>                on-hit command list
  > print var
  > continue
  > end
```

#### Hardware vs Software Breakpoints

| Type | Limit | Use Case |
|------|-------|----------|
| Hardware | 6 (Cortex-M) | Flash memory |
| Software | Unlimited | RAM only |

### 4) Watchpoints and Variable Display

```gdb
watch variable_name           break on write
rwatch variable_name          break on read
awatch variable_name          break on read/write
info watchpoints              list watchpoints
delete <num>                  delete watchpoint
```

```gdb
print variable_name
print/x variable_name
print variable_name[0]@10
display variable_name
display/x variable_name
undisplay <num>
```

### 5) Register Read and Write

#### Core Registers

```gdb
info registers
info all-registers
print $r0
print $pc
print $sp
print $lr
print $xpsr
```

#### Write Registers

```gdb
set $r0 = 0x12345678
set $pc = 0x08001000
set $sp = 0x2001FFF0
```

#### Cortex-M Fault Registers

| Register | Address | Purpose |
|----------|---------|---------|
| CFSR | 0xE000ED28 | Configurable Fault Status |
| HFSR | 0xE000ED2C | HardFault Status |
| DFSR | 0xE000ED30 | Debug Fault Status |
| MMFAR | 0xE000ED34 | MemManage Fault Address |
| BFAR | 0xE000ED38 | Bus Fault Address |

```gdb
monitor memU32 0xE000ED28 1   CFSR
monitor memU32 0xE000ED2C 1   HFSR
monitor memU32 0xE000ED34 1   MMFAR
monitor memU32 0xE000ED38 1   BFAR
```

### 6) Memory Read and Write

#### Read

```gdb
x/10x 0x20000000
x/20b 0x20000000
x/5i $pc
x/s 0x20001000
x/10wx 0x20000000
```

For one-off raw address checks these commands are appropriate. For repeatable structured RAM sampling, prefer `bfd-data-acquisition` so the symbol contract, cache, decoding, and outputs are standardized.

#### Format Specifiers

| Specifier | Size |
|-----------|------|
| b | byte (8-bit) |
| h | halfword (16-bit) |
| w | word (32-bit) |
| g | giant (64-bit) |

#### Write

```gdb
set {int}0x20000000 = 0x12345678
set {char}0x20000000 = 0x55
set {short}0x20000000 = 0x1234
set {int[10]}0x20000000 = {0}
```

### 7) Stack and Call Chain Analysis

```gdb
backtrace
backtrace full
frame <num>
info frame
info locals
info args
x/20x $sp
```

### 8) Flash, Reset, and Semihosting

#### Flash Programming

```text
JLinkExe -device "${STM32_DEVICE}" -if "${STM32_IF}" -speed "${STM32_SPEED_KHZ}"
J-Link> loadfile firmware.hex
J-Link> r
J-Link> g
```

```bash
ST-LINK_CLI.exe -P firmware.hex -V
```

#### Reset

```gdb
monitor reset
monitor reset halt
monitor halt
monitor go
```

#### Semihosting

```gdb
monitor semihosting enable
monitor semihosting disable
```

## HardFault Playbook

1. Break at fault entry.
```gdb
(gdb) break HardFault_Handler
(gdb) continue
```

2. Read core and fault status.
```gdb
(gdb) info registers
(gdb) print/x *(uint32_t*)0xE000ED28   CFSR
(gdb) print/x *(uint32_t*)0xE000ED2C   HFSR
(gdb) print/x *(uint32_t*)0xE000ED34   MMFAR
(gdb) print/x *(uint32_t*)0xE000ED38   BFAR
```

3. Decode stack frame.
```gdb
(gdb) x/8x $sp
R0, R1, R2, R3, R12, LR, PC, xPSR
```

4. Save evidence.
- `logs/debug/hardfault_<timestamp>.log`
- `logs/hw_error/<date>/...`

5. Hand off to `bfd-fault-logger`.

## Error Detection and Auto-Trigger

### RTT Keyword Monitor

| Keyword | Severity | Action |
|---------|----------|--------|
| `ERROR` | High | Log and analyze |
| `FATAL` | Critical | Halt and log |
| `HardFault` | Critical | Capture fault state |
| `BusFault` | Critical | Capture fault state |
| `MemManage` | Critical | Capture fault state |
| `UsageFault` | High | Log and analyze |

### Trigger Conditions

1. HardFault breakpoint is hit.
2. CFSR indicates BusFault-related bits.
3. Peripheral status registers expose error flags.
4. RTT stream contains high-risk keywords.

### Minimal Automation Snippet

```gdb
break HardFault_Handler
commands
  silent
  info registers
  print/x *(uint32_t*)0xE000ED28
  print/x *(uint32_t*)0xE000ED2C
  print/x *(uint32_t*)0xE000ED34
  print/x *(uint32_t*)0xE000ED38
  x/8x $sp
  continue
end
```

### Context Fields for `bfd-fault-logger`

```json
{
  "error_type": "HardFault|BusFault|PeripheralError|LogError",
  "timestamp": "<debug timestamp>",
  "registers": {
    "pc": "<program counter>",
    "lr": "<link register>",
    "sp": "<stack pointer>",
    "cfsr": "<fault status>",
    "hfsr": "<hard fault status>",
    "bfar": "<bus fault address>",
    "mmfar": "<memmanage fault address>"
  },
  "stack_trace": "<backtrace output>",
  "rtt_log": "<relevant log lines>",
  "peripheral": "<optional peripheral>"
}
```

## Hard Rules

- Capture evidence before proposing fixes.
- Fault analysis must include core registers, fault registers, and stack context.
- Save session logs under `logs/` subdirectories.
- Use `bfd-rtt-logger` for RTT capture to avoid session conflicts.
- Use `bfd-fault-logger` for structured fault archival.

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/var_monitor.py` | Real-time variable monitoring via RTT |
| `scripts/register_view.py` | Peripheral register viewer |
| `scripts/svd_parser.py` | SVD parser for register definitions |

## Reference Documentation

- `references/debug-interface-reference.md`

## Related Skills

- `systematic-debugging`
- `test-driven-development`
- `verification-before-completion`
- `bfd-fault-logger`
- `bfd-rtt-logger`
