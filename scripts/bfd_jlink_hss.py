#!/usr/bin/env python3
"""Native J-Link HSS CLI for BFD-Kit."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any, Optional


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from bfd_jlink_hss_core.env import ProbeDiscoveryError, list_probes
from bfd_jlink_hss_core.hss_sampling import HssSamplingError, sample_scalar_symbol, sample_scalar_symbols
from bfd_jlink_hss_core.jlink_dll import JLinkDll, JLinkDllError, choose_probe, resolve_jlinkarm_dll


def find_profile_candidate_paths() -> list[Path]:
    roots = [Path.cwd().resolve(), SCRIPT_DIR.resolve(), *SCRIPT_DIR.resolve().parents]
    candidates: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        for parent in [root, *root.parents]:
            for candidate in (
                parent / ".codex/bfd/active_profile.env",
                parent / ".codex/stm32/bootstrap/active_profile.env",
            ):
                resolved = candidate.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    candidates.append(candidate)
    return candidates


def load_profile_defaults() -> dict[str, str]:
    values: dict[str, str] = {}
    for path in find_profile_candidate_paths():
        if not path.is_file():
            continue
        for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
        if values:
            break
    return values


PROFILE_DEFAULTS = load_profile_defaults()


def _default_value(cli_value: Optional[str], env_key: str, profile_key: str, fallback: Optional[str] = None) -> Optional[str]:
    if cli_value:
        return cli_value
    env_value = None
    if env_key:
        env_value = os.environ.get(env_key)
    if env_value:
        return env_value
    profile_value = PROFILE_DEFAULTS.get(profile_key)
    if profile_value:
        return profile_value
    return fallback


def _default_int(cli_value: Optional[int], env_key: str, profile_key: str, fallback: int) -> int:
    if cli_value is not None:
        return cli_value
    env_value = os.environ.get(env_key)
    if env_value:
        return int(env_value)
    profile_value = PROFILE_DEFAULTS.get(profile_key)
    if profile_value:
        return int(profile_value)
    return fallback


def output_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


def output_text(payload: Any) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if isinstance(value, dict):
                print(f"{key}:")
                for child_key, child_value in value.items():
                    print(f"  {child_key}: {child_value}")
            elif isinstance(value, list):
                print(f"{key}:")
                for item in value:
                    print(f"  - {item}")
            else:
                print(f"{key}: {value}")
    else:
        print(str(payload))


def emit(payload: Any, *, json_mode: bool) -> None:
    if json_mode:
        output_json(payload)
    else:
        output_text(payload)


def select_probe_or_sn(*, usb_sn: Optional[str], jlink_exe: Optional[str]) -> tuple[Optional[dict], Optional[str]]:
    if usb_sn:
        return None, usb_sn
    selected = choose_probe(list_probes(jlink_exe), None)
    return selected.to_dict(), selected.serial_number


def cmd_probes_list(args: argparse.Namespace) -> int:
    probes = [probe.to_dict() for probe in list_probes(args.jlink_exe)]
    emit({"probes": probes}, json_mode=args.json_mode)
    return 0


def cmd_hss_inspect(args: argparse.Namespace) -> int:
    device = _default_value(args.device, "STM32_DEVICE", "STM32_DEVICE")
    interface = _default_value(args.interface, "STM32_IF", "STM32_IF", "SWD")
    speed = _default_int(args.speed, "STM32_SPEED_KHZ", "STM32_SPEED_KHZ", 4000)
    if not device:
        raise ValueError("target device is required; pass --device or provide STM32_DEVICE in the profile")

    selected_probe, selected_sn = select_probe_or_sn(usb_sn=args.usb_sn, jlink_exe=args.jlink_exe)
    dll = JLinkDll(dll_path=args.jlink_dll or resolve_jlinkarm_dll())
    try:
        dll.open(usb_sn=selected_sn)
        connected_sn = dll.connect(device=device, interface=interface, speed_khz=speed)
        caps = dll.get_hss_caps()
    finally:
        dll.close()

    emit(
        {
            "jlink_dll": str(dll.dll_path),
            "selected_probe": selected_probe,
            "connected_serial_number": connected_sn,
            "caps": caps.to_dict(),
        },
        json_mode=args.json_mode,
    )
    return 0


def cmd_hss_sample(args: argparse.Namespace) -> int:
    elf_path = _default_value(args.elf, "STM32_ELF", "STM32_ELF")
    device = _default_value(args.device, "STM32_DEVICE", "STM32_DEVICE")
    interface = _default_value(args.interface, "STM32_IF", "STM32_IF", "SWD")
    speed = _default_int(args.speed, "STM32_SPEED_KHZ", "STM32_SPEED_KHZ", 4000)

    if not elf_path:
        raise ValueError("ELF path is required; pass --elf or provide STM32_ELF in the profile")
    if not device:
        raise ValueError("target device is required; pass --device or provide STM32_DEVICE in the profile")

    selected_probe, selected_sn = select_probe_or_sn(usb_sn=args.usb_sn, jlink_exe=args.jlink_exe)
    dll = JLinkDll(dll_path=args.jlink_dll or resolve_jlinkarm_dll())
    result = sample_scalar_symbols(
        dll=dll,
        elf_path=elf_path,
        symbol_expressions=list(args.symbol),
        device=device,
        interface=interface,
        speed_khz=speed,
        duration_s=args.duration,
        period_us=args.period_us,
        output_csv=args.output,
        usb_sn=selected_sn,
        read_buffer_size=args.read_buffer_size,
    )
    emit(
        {
            "selected_probe": selected_probe,
            **result.to_dict(),
        },
        json_mode=args.json_mode,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Native J-Link HSS CLI for BFD-Kit")
    parser.add_argument("--json", dest="json_mode", action="store_true", help="Output JSON")
    subparsers = parser.add_subparsers(dest="group", required=True)

    probes = subparsers.add_parser("probes", help="Probe discovery commands")
    probes_sub = probes.add_subparsers(dest="command", required=True)
    probes_list = probes_sub.add_parser("list", help="List available J-Link probes")
    probes_list.add_argument("--jlink-exe", default=None, help="Optional explicit JLinkExe path")
    probes_list.set_defaults(handler=cmd_probes_list)

    hss = subparsers.add_parser("hss", help="Native HSS commands")
    hss_sub = hss.add_subparsers(dest="command", required=True)

    inspect = hss_sub.add_parser("inspect", help="Inspect native HSS capability")
    inspect.add_argument("--device", default=None, help="Target device")
    inspect.add_argument("--interface", default=None, help="Target interface, e.g. SWD")
    inspect.add_argument("--speed", type=int, default=None, help="Target interface speed in kHz")
    inspect.add_argument("--usb-sn", default=None, help="Optional J-Link USB serial number")
    inspect.add_argument("--jlink-dll", default=None, help="Optional explicit libjlinkarm.so path")
    inspect.add_argument("--jlink-exe", default=None, help="Optional explicit JLinkExe path for probe discovery")
    inspect.set_defaults(handler=cmd_hss_inspect)

    sample = hss_sub.add_parser("sample", help="Sample one or more fixed-address scalar symbols using native HSS")
    sample.add_argument("--elf", default=None, help="ELF path; falls back to STM32_ELF profile entry")
    sample.add_argument("--symbol", action="append", required=True, help="Fixed-address symbol path to sample; repeat for multi-symbol HSS")
    sample.add_argument("--device", default=None, help="Target device")
    sample.add_argument("--interface", default=None, help="Target interface, e.g. SWD")
    sample.add_argument("--speed", type=int, default=None, help="Target interface speed in kHz")
    sample.add_argument("--duration", type=float, required=True, help="Sampling duration in seconds")
    sample.add_argument("--period-us", type=int, default=1000, help="Requested HSS sampling period in microseconds")
    sample.add_argument("--output", required=True, help="CSV output path")
    sample.add_argument("--usb-sn", default=None, help="Optional J-Link USB serial number")
    sample.add_argument("--jlink-dll", default=None, help="Optional explicit libjlinkarm.so path")
    sample.add_argument("--jlink-exe", default=None, help="Optional explicit JLinkExe path for probe discovery")
    sample.add_argument("--read-buffer-size", type=int, default=4096, help="Preferred HSS read buffer size")
    sample.set_defaults(handler=cmd_hss_sample)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except (ProbeDiscoveryError, HssSamplingError, JLinkDllError, FileNotFoundError, ValueError) as exc:
        payload = {"error": str(exc), "type": type(exc).__name__}
        if getattr(args, "json_mode", False):
            output_json(payload)
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
