"""Probe discovery helpers for the native BFD-Kit HSS CLI."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import os
import re
import shutil
import subprocess
from typing import Iterable, Optional


PROBE_PATTERN = re.compile(
    r"J-Link\[(?P<index>\d+)\]:\s+Connection:\s+(?P<connection>[^,]+),\s+Serial number:\s+(?P<serial>\d+),\s+ProductName:\s+(?P<product>.+)$"
)


class ProbeDiscoveryError(RuntimeError):
    """Raised when probe enumeration fails."""


@dataclass
class ProbeInfo:
    index: int
    connection: str
    serial_number: str
    product_name: str

    def to_dict(self) -> dict:
        return asdict(self)


def iter_default_jlink_exe_candidates() -> Iterable[str]:
    env_path = os.environ.get("JLINK_EXE")
    if env_path:
        yield env_path

    which_path = shutil.which("JLinkExe")
    if which_path:
        yield which_path

    for pattern in (
        "/opt/SEGGER/JLink*/JLinkExe",
        "/usr/bin/JLinkExe",
        "/usr/local/bin/JLinkExe",
    ):
        for path in sorted(Path("/").glob(pattern.lstrip("/"))):
            if path.is_file():
                yield str(path)


def resolve_existing_file(candidates: Iterable[Optional[str]]) -> Optional[Path]:
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate).expanduser()
        if path.is_file():
            return path.resolve()
    return None


def resolve_jlink_exe(explicit_path: Optional[str] = None) -> Path:
    candidates = [explicit_path] if explicit_path else list(iter_default_jlink_exe_candidates())
    path = resolve_existing_file(candidates)
    if path is None:
        raise ProbeDiscoveryError("JLinkExe not found")
    return path


def parse_probe_list(text: str) -> list[ProbeInfo]:
    probes: list[ProbeInfo] = []
    for line in text.splitlines():
        match = PROBE_PATTERN.search(line.strip())
        if not match:
            continue
        probes.append(
            ProbeInfo(
                index=int(match.group("index")),
                connection=match.group("connection"),
                serial_number=match.group("serial"),
                product_name=match.group("product").strip(),
            )
        )
    return probes


def list_probes(jlink_exe: Optional[str] = None) -> list[ProbeInfo]:
    jlink_path = resolve_jlink_exe(jlink_exe)
    result = subprocess.run(
        [str(jlink_path)],
        input="ShowEmuList\nexit\n",
        text=True,
        capture_output=True,
        check=False,
    )
    combined = (result.stdout or "") + (result.stderr or "")
    probes = parse_probe_list(combined)
    if result.returncode != 0 and not probes:
        raise ProbeDiscoveryError(combined.strip() or f"JLinkExe failed with exit code {result.returncode}")
    return probes
