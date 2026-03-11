# BFD Skill Dedup Audit

Date: 2026-03-11

## Goal

Use `bfd-*` as the only STM32 debug/flash/data-acquisition skill line and remove overlapping legacy skills from active mirrors.

## Compared Skill Pairs

| Legacy skill | BFD replacement | Decision | Complement absorbed |
|---|---|---|---|
| `stm32-data-acquisition` | `bfd-data-acquisition` | Remove legacy | Added local-variable probe resource and pointer-symbol workflow to BFD |
| `stm32-debug-interface` | `bfd-debug-interface` | Remove legacy | No missing core debug capability found |
| `stm32-flash-programmer` | `bfd-flash-programmer` | Remove legacy | No missing core flash capability found |
| `stm32-user-feedback` | `bfd-user-feedback` | Remove legacy | Chinese trigger wording already preserved in BFD |
| `ioc-parser` | `bfd-ioc-parser` | Remove legacy | No missing parser path found |
| `register-capture` | `bfd-register-capture` | Remove legacy | No missing register capture path found |
| `rtt-logger` | `bfd-rtt-logger` | Remove legacy | BFD adds RTT address helper and profile-driven defaults |
| `debug-tool` | `bfd-debug-executor` | Remove legacy | No missing one-shot J-Link action found |
| `hardware-error-logger` | `bfd-fault-logger` | Remove legacy | No blocking gap for fault record/export path found |

## Local Probe Consolidation

The temporary firmware demo was removed from `USER/APP/`.

Reusable local-variable probing assets now live under:

- `BFD-Kit/skills/codex/bfd-data-acquisition/resources/local-probe/`
- `.codex/skills/bfd-data-acquisition/resources/local-probe/`

The supported model is:

1. Publish a stack-local variable address into a global probe slot at runtime.
2. Sample with `data_acq.py --pointer-symbol ... --seq-symbol ...`.
3. Use `nonstop` for live observation and `snapshot` only when intrusive halt is acceptable.

## Active Cleanup Scope

Delete the following duplicated skills from active mirrors after BFD canonical content is staged:

- `debug-tool`
- `hardware-error-logger`
- `ioc-parser`
- `register-capture`
- `rtt-logger`
- `stm32-data-acquisition`
- `stm32-debug-interface`
- `stm32-flash-programmer`
- `stm32-user-feedback`
