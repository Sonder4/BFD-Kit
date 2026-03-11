---
name: bfd-ioc-parser
description: Use when parsing STM32CubeMX .ioc files to extract hardware configuration and generate structured JSON outputs for review or downstream analysis.
---

# BFD IOC Parser

## Self-Improvement Loop (Required)

- When this skill encounters a build, flash, debug, script-usage, or other workflow problem, do not stop at the local workaround after the issue is solved.
- Record the resolved issue and lesson in `BFD-Kit/.learnings/ERRORS.md` and/or `BFD-Kit/.learnings/LEARNINGS.md`; unresolved capability gaps go to `BFD-Kit/.learnings/FEATURE_REQUESTS.md`.
- Promote reusable fixes into the affected BFD-Kit asset in the same task when feasible: update the relevant `SKILL.md`, script, wrapper, or resource so the next run benefits by default.
- When a learning is promoted into a skill or script, append a short entry to `BFD-Kit/.learnings/CHANGELOG.md` and mention the improvement in the task close-out.

Use this skill to parse `.ioc` files and produce normalized configuration artifacts.

## Quick Start

1. Use CLI only.
2. Parse one `.ioc` file or scan a directory.
3. Store outputs in a repository path.

## Core Commands

```bash
# Scan current directory
python3 ./.codex/skills/bfd-ioc-parser/scripts/parse_ioc.py --scan .
```

```bash
# Recursive scan
python3 ./.codex/skills/bfd-ioc-parser/scripts/parse_ioc.py --scan ./example_projects --recursive
```

```bash
# Parse a specific ioc file
python3 ./.codex/skills/bfd-ioc-parser/scripts/parse_ioc.py --ioc ./example_projects/RC2026_h7/RSCF_H7.ioc
```

```bash
# Parse with explicit output directory
python3 ./.codex/skills/bfd-ioc-parser/scripts/parse_ioc.py --ioc RSCF_H7.ioc --output ./logs/ioc_json
```

## Workflow

1. Locate `.ioc` file(s).
2. Parse and generate JSON artifacts.
3. Validate generated files before downstream use.

## Outputs

- `summary.json`
- `clock_config.json`
- `gpio_config.json`
- peripheral-specific config JSON files

## Hard Rules

- Do not modify `.ioc` files in this skill.
- Keep final outputs inside the repository.
- Use explicit output paths for reproducibility.

## Scripts

- `.codex/skills/bfd-ioc-parser/scripts/parse_ioc.py`
- `.codex/skills/bfd-ioc-parser/scripts/analyze_startup.py`

## References

- `.codex/skills/bfd-ioc-parser/references/ioc_format.md`
- `.codex/skills/bfd-ioc-parser/references/memory_map_stm32h723.md`
