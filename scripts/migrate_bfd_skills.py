#!/usr/bin/env python3
"""Sync canonical BFD-Kit skills with active Codex/Claude mirrors."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List

BFD_SKILLS = [
    'bfd-project-init',
    'bfd-flash-programmer',
    'bfd-rtt-logger',
    'bfd-debug-interface',
    'bfd-debug-executor',
    'bfd-register-capture',
    'bfd-data-acquisition',
    'bfd-fault-logger',
    'bfd-debug-orchestrator',
    'bfd-ioc-parser',
    'bfd-cubemx-codegen',
    'bfd-user-feedback',
]

LEGACY_DUPLICATE_SKILLS = [
    'debug-tool',
    'hardware-error-logger',
    'ioc-parser',
    'register-capture',
    'rtt-logger',
    'stm32-data-acquisition',
    'stm32-debug-interface',
    'stm32-flash-programmer',
    'stm32-user-feedback',
]

NAMESPACE_MAP = {
    'codex': '.codex/skills',
    'claude': '.claude/skills',
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Sync BFD-Kit canonical skill trees with active runtime mirrors')
    parser.add_argument('--repo-root', default='.', help='Repository root')
    parser.add_argument('--mode', choices=['stage', 'cutover', 'all'], default='all', help='stage: import active mirrors into BFD-Kit; cutover: push BFD-Kit into active mirrors; all: stage then cutover')
    return parser.parse_args()


def reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def ensure_readme_files(repo_root: Path) -> None:
    for rel in ['BFD-Kit/README.md', 'BFD-Kit/README-zh.md', 'BFD-Kit/STM32_AGENT_PROMPT-zh.md']:
        path = repo_root / rel
        if not path.is_file():
            raise FileNotFoundError(path)


def stage(repo_root: Path) -> Dict[str, List[str]]:
    changed: Dict[str, List[str]] = {'stage': []}
    ensure_readme_files(repo_root)
    for namespace, active_root_rel in NAMESPACE_MAP.items():
        source_root = repo_root / active_root_rel
        dest_root = repo_root / 'BFD-Kit' / 'skills' / namespace
        dest_root.mkdir(parents=True, exist_ok=True)
        for skill in BFD_SKILLS:
            src = source_root / skill
            if not src.is_dir():
                continue
            dst = dest_root / skill
            copy_tree(src, dst)
            changed['stage'].append(str(dst.relative_to(repo_root)))

    templates_src = repo_root / '.codex' / 'stm32' / 'templates'
    templates_dst = repo_root / 'BFD-Kit' / 'resources' / 'stm32' / 'templates'
    if templates_src.is_dir():
        copy_tree(templates_src, templates_dst)
        changed['stage'].append(str(templates_dst.relative_to(repo_root)))
    return changed


def backup_active(repo_root: Path) -> Path:
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_root = repo_root / 'archive' / 'skills_migration' / timestamp
    backup_root.mkdir(parents=True, exist_ok=True)

    for namespace, active_root_rel in NAMESPACE_MAP.items():
        active_root = repo_root / active_root_rel
        backup_ns = backup_root / namespace
        backup_ns.mkdir(parents=True, exist_ok=True)
        for skill in BFD_SKILLS:
            src = active_root / skill
            if src.is_dir():
                copy_tree(src, backup_ns / skill)

    templates_src = repo_root / '.codex' / 'stm32' / 'templates'
    if templates_src.is_dir():
        copy_tree(templates_src, backup_root / 'templates')
    return backup_root


def cutover(repo_root: Path) -> Dict[str, List[str]]:
    changed: Dict[str, List[str]] = {'cutover': []}
    backup_root = backup_active(repo_root)
    changed['cutover'].append(str(backup_root.relative_to(repo_root)))

    for namespace, active_root_rel in NAMESPACE_MAP.items():
        source_root = repo_root / 'BFD-Kit' / 'skills' / namespace
        active_root = repo_root / active_root_rel
        active_root.mkdir(parents=True, exist_ok=True)
        for skill in BFD_SKILLS:
            src = source_root / skill
            if not src.is_dir():
                continue
            dst = active_root / skill
            copy_tree(src, dst)
            changed['cutover'].append(str(dst.relative_to(repo_root)))

        for legacy_skill in LEGACY_DUPLICATE_SKILLS:
            legacy_path = active_root / legacy_skill
            if legacy_path.exists():
                shutil.rmtree(legacy_path)
                changed['cutover'].append(str(legacy_path.relative_to(repo_root)))

    templates_src = repo_root / 'BFD-Kit' / 'resources' / 'stm32' / 'templates'
    templates_dst = repo_root / '.codex' / 'stm32' / 'templates'
    if templates_src.is_dir():
        copy_tree(templates_src, templates_dst)
        changed['cutover'].append(str(templates_dst.relative_to(repo_root)))
    return changed


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    summary: Dict[str, object] = {'mode': args.mode}

    if args.mode in {'stage', 'all'}:
        summary.update(stage(repo_root))
    if args.mode in {'cutover', 'all'}:
        summary.update(cutover(repo_root))

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
