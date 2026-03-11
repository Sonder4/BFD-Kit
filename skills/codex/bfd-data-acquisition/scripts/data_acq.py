#!/usr/bin/env python3
"""
STM32 Data Acquisition Script
通过 J-Link 在目标运行时读取变量/地址数据，并导出 CSV/JSON。
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


def load_profile_defaults() -> Dict[str, str]:
    script_path = Path(__file__).resolve()
    repo_root = script_path.parents[4]
    candidates = [
        repo_root / ".codex/bfd/active_profile.env",
        repo_root / ".codex/stm32/bootstrap/active_profile.env",
    ]

    values: Dict[str, str] = {}
    for path in candidates:
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

DEFAULT_DEVICE = os.environ.get("STM32_DEVICE", PROFILE_DEFAULTS.get("STM32_DEVICE", "STM32H743VI"))
DEFAULT_INTERFACE = os.environ.get("STM32_IF", PROFILE_DEFAULTS.get("STM32_IF", "SWD"))
DEFAULT_SPEED = int(os.environ.get("STM32_SPEED_KHZ", PROFILE_DEFAULTS.get("STM32_SPEED_KHZ", "4000")))
DEFAULT_ELF = os.environ.get("STM32_ELF", PROFILE_DEFAULTS.get("STM32_ELF", ""))
DEFAULT_OUTPUT_DIR = Path("logs/data_acq")
DEFAULT_GDB_PORT = 2331
GDB_MARKER = "__DATA_ACQ_END__"
SRAM_ADDRESS_RANGES = (
    (0x20000000, 0x20040000),
    (0x10000000, 0x10010000),
)

JLINK_EXE = shutil.which("JLinkExe") or "JLinkExe"
JLINK_GDB_SERVER = shutil.which("JLinkGDBServerCLExe") or "JLinkGDBServerCLExe"
JLINK_RTT_VIEWER = shutil.which("JLinkRTTLogger") or "JLinkRTTLogger"
ARM_NONE_EABI_NM = shutil.which("arm-none-eabi-nm") or "arm-none-eabi-nm"
ARM_NONE_EABI_GDB = shutil.which("arm-none-eabi-gdb") or "arm-none-eabi-gdb"


@dataclass(frozen=True)
class Layout:
    element_type: str
    count: int
    element_size: int
    decode_format: str

    @property
    def total_size(self) -> int:
        return self.element_size * self.count

    def decode(self, data: bytes) -> List[Any]:
        if len(data) != self.total_size:
            raise ValueError(
                f"layout {self.element_type}x{self.count} expects {self.total_size} bytes, got {len(data)}"
            )
        fmt = "<" + (self.decode_format * self.count)
        return list(struct.unpack(fmt, data))

    def decode_words(self, values: Sequence[int]) -> List[Any]:
        if len(values) != self.count:
            raise ValueError(f"expected {self.count} values, got {len(values)}")

        if self.element_size == 1:
            raw = b"".join(struct.pack("<B", value & 0xFF) for value in values)
        elif self.element_size == 2:
            raw = b"".join(struct.pack("<H", value & 0xFFFF) for value in values)
        elif self.element_size == 4:
            raw = b"".join(struct.pack("<I", value & 0xFFFFFFFF) for value in values)
        else:
            raise ValueError(f"unsupported element size: {self.element_size}")
        return self.decode(raw)


def parse_layout(layout_text: str) -> Layout:
    match = re.fullmatch(r"(u8|u16|u32|s8|s16|s32|f32)x([1-9][0-9]*)", layout_text.strip())
    if not match:
        raise ValueError(f"unsupported layout: {layout_text}")

    element_type = match.group(1)
    count = int(match.group(2))
    element_size = {
        "u8": 1,
        "s8": 1,
        "u16": 2,
        "s16": 2,
        "u32": 4,
        "s32": 4,
        "f32": 4,
    }[element_type]
    decode_format = {
        "u8": "B",
        "s8": "b",
        "u16": "H",
        "s16": "h",
        "u32": "I",
        "s32": "i",
        "f32": "f",
    }[element_type]
    return Layout(
        element_type=element_type,
        count=count,
        element_size=element_size,
        decode_format=decode_format,
    )


def build_nonstop_setup_commands(port: int = DEFAULT_GDB_PORT) -> List[str]:
    return [f"target extended-remote :{port}", "monitor exec SetAllowStopMode = 0"]


def build_nonstop_read_command(address: int, layout: Layout) -> str:
    command_name = {
        1: "mem8",
        2: "mem16",
        4: "mem32",
    }[layout.element_size]
    return f"{command_name} 0x{address:08X} {layout.count}"


def build_nonstop_read_commands(address: int, layout: Layout) -> List[str]:
    return [build_nonstop_read_command(address, layout)]


def build_snapshot_savebin_command(bin_path: Path, address: int, size: int) -> str:
    return f"savebin {bin_path} 0x{address:08X} 0x{size:X}"


def parse_monitor_values(output: str, element_size: int) -> List[int]:
    width = element_size * 2
    values: List[int] = []
    gdb_data_re = re.compile(rf"Reading from address 0x[0-9A-Fa-f]+ \(Data = 0x([0-9A-Fa-f]{{{width}}})\)")
    jlink_mem_re = re.compile(rf"^[0-9A-Fa-f]{{8}}\s*=\s*(?:[0-9A-Fa-f]{{{width}}}(?:\s+|$))+$")
    token_re = re.compile(rf"\b([0-9A-Fa-f]{{{width}}})\b")

    for line in output.splitlines():
        stripped = line.strip()

        match = gdb_data_re.search(stripped)
        if match:
            values.append(int(match.group(1), 16))
            continue

        if not jlink_mem_re.fullmatch(stripped):
            continue

        right = stripped.split("=", 1)[1]
        for token in token_re.findall(right):
            values.append(int(token, 16))
    return values


def is_valid_sram_pointer(address: int) -> bool:
    return any(start <= address < end for start, end in SRAM_ADDRESS_RANGES)


def is_consistent_pointer_sample(seq_before: int, seq_after: int, pointer_value: int) -> bool:
    return seq_before == seq_after and (seq_before % 2) == 0 and is_valid_sram_pointer(pointer_value)


def ensure_output_path(output: Optional[str], fmt: str, prefix: str) -> Path:
    if output:
        path = Path(output)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = DEFAULT_OUTPUT_DIR / f"{prefix}_{timestamp}.{fmt}"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def write_samples_csv(output_path: Path, samples: Sequence[Dict[str, Any]], value_count: int) -> None:
    headers = ["host_time_s", "sample_idx", "symbol", "address", "capture_mode"]
    if any("pointer_symbol" in sample for sample in samples):
        headers.extend(["pointer_symbol", "pointer_value", "seq_before", "seq_after"])
    headers.extend(f"value{index}" for index in range(value_count))

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        for sample in samples:
            row = [
                sample["host_time_s"],
                sample["sample_idx"],
                sample["symbol"],
                sample["address"],
                sample["capture_mode"],
            ]
            if "pointer_symbol" in sample:
                row.extend(
                    [
                        sample.get("pointer_symbol", ""),
                        sample.get("pointer_value", ""),
                        sample.get("seq_before", ""),
                        sample.get("seq_after", ""),
                    ]
                )
            row.extend(sample["values"])
            writer.writerow(row)


def write_memory_csv(output_path: Path, samples: Sequence[Dict[str, Any]]) -> None:
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["host_time_s", "sample_idx", "symbol", "address", "capture_mode", "data_hex"])
        for sample in samples:
            writer.writerow(
                [
                    sample["host_time_s"],
                    sample["sample_idx"],
                    sample["symbol"],
                    sample["address"],
                    sample["capture_mode"],
                    sample["data_hex"],
                ]
            )


def write_json(output_path: Path, metadata: Dict[str, Any], samples: Sequence[Dict[str, Any]]) -> None:
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump({"metadata": metadata, "data": list(samples)}, handle, indent=2)


class GdbCommandSession:
    def __init__(self, gdb_exe: str = ARM_NONE_EABI_GDB) -> None:
        self.gdb_exe = gdb_exe
        self.process: Optional[subprocess.Popen[str]] = None

    def __enter__(self) -> "GdbCommandSession":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()

    def start(self) -> None:
        if self.process is not None:
            return

        self.process = subprocess.Popen(
            [
                self.gdb_exe,
                "--quiet",
                "--nx",
                "-ex",
                "set confirm off",
                "-ex",
                "set pagination off",
                "-ex",
                "set height 0",
                "-ex",
                "set width 0",
                "-ex",
                "set prompt ",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

    def run(self, commands: Sequence[str], timeout: float = 10.0) -> str:
        if self.process is None or self.process.stdin is None or self.process.stdout is None:
            raise RuntimeError("GDB session is not started")

        for command in commands:
            self.process.stdin.write(command + "\n")
        self.process.stdin.write(f"echo {GDB_MARKER}\\n\n")
        self.process.stdin.flush()

        lines: List[str] = []
        deadline = time.time() + timeout
        while time.time() < deadline:
            line = self.process.stdout.readline()
            if line == "":
                if self.process.poll() is not None:
                    raise RuntimeError("GDB exited unexpectedly while reading output")
                continue
            stripped = line.rstrip("\r\n")
            if stripped == GDB_MARKER:
                return "\n".join(lines)
            lines.append(stripped)

        raise TimeoutError(f"GDB command timeout after {timeout:.1f}s: {commands[-1] if commands else 'no command'}")

    def stop(self) -> None:
        if self.process is None:
            return

        try:
            if self.process.stdin is not None:
                self.process.stdin.write("quit\n")
                self.process.stdin.flush()
        except BrokenPipeError:
            pass

        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)
        finally:
            self.process = None


class JLinkGdbServer:
    def __init__(self, device: str, interface: str, speed: int, port: int) -> None:
        self.device = device
        self.interface = interface
        self.speed = speed
        self.port = port
        self.process: Optional[subprocess.Popen[str]] = None

    def __enter__(self) -> "JLinkGdbServer":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()

    def start(self) -> None:
        if self.process is not None:
            return

        self.process = subprocess.Popen(
            [
                JLINK_GDB_SERVER,
                "-device",
                self.device,
                "-if",
                self.interface,
                "-speed",
                str(self.speed),
                "-port",
                str(self.port),
                "-nohalt",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        deadline = time.time() + 8.0
        while time.time() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(f"J-Link GDB Server exited early: {self._drain_output()}")
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=0.2):
                    return
            except OSError:
                time.sleep(0.1)

        raise TimeoutError(f"J-Link GDB Server did not open port {self.port}: {self._drain_output()}")

    def _drain_output(self) -> str:
        if self.process is None or self.process.stdout is None:
            return ""
        try:
            return self.process.stdout.read()
        except Exception:
            return ""

    def stop(self) -> None:
        if self.process is None:
            return

        self.process.terminate()
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=2)
        finally:
            self.process = None


class DataAcquisition:
    def __init__(self, device: str, interface: str = "SWD", speed: int = 4000) -> None:
        self.device = device
        self.interface = interface
        self.speed = speed
        self.elf_file: Optional[str] = None
        self.symbols: Dict[str, int] = {}

    def find_elf_file(self, search_dir: str = ".") -> Optional[str]:
        for root, _dirs, files in os.walk(search_dir):
            for filename in files:
                if filename.endswith(".elf") or filename.endswith(".axf"):
                    return os.path.join(root, filename)
        return None

    def load_symbols(self, elf_file: str) -> bool:
        self.elf_file = elf_file
        try:
            result = subprocess.run(
                [ARM_NONE_EABI_NM, "-n", elf_file],
                capture_output=True,
                text=True,
                timeout=30,
                check=True,
            )
        except (subprocess.CalledProcessError, OSError, subprocess.TimeoutExpired) as exc:
            print(f"Warning: Could not load symbols: {exc}", file=sys.stderr)
            return False

        self.symbols.clear()
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 3 and re.fullmatch(r"[0-9A-Fa-f]+", parts[0]):
                self.symbols[parts[2]] = int(parts[0], 16)
        return True

    def get_symbol_address(self, name: str) -> Optional[int]:
        return self.symbols.get(name)

    def run_jlink_command(self, commands: Sequence[str], timeout: int = 30) -> str:
        with tempfile.TemporaryDirectory(prefix="data_acq_jlink_") as tmp_dir:
            script_path = Path(tmp_dir) / "data_acq.jlink"
            script_lines = [
                f"device {self.device}",
                f"si {self.interface}",
                f"speed {self.speed}",
                *commands,
                "exit",
            ]
            script_path.write_text("\n".join(script_lines) + "\n", encoding="utf-8")

            result = subprocess.run(
                [JLINK_EXE, "-CommandFile", str(script_path)],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return result.stdout + result.stderr

    def read_snapshot_block(self, address: int, size: int) -> bytes:
        with tempfile.TemporaryDirectory(prefix="data_acq_snapshot_") as tmp_dir:
            bin_path = Path(tmp_dir) / "capture.bin"
            output = self.run_jlink_command(
                [
                    "connect",
                    "h",
                    build_snapshot_savebin_command(bin_path, address, size),
                    "go",
                ]
            )
            if not bin_path.exists():
                raise RuntimeError(f"snapshot capture failed at 0x{address:08X}: {output}")
            return bin_path.read_bytes()

    def read_nonstop_layout(self, address: int, layout: Layout) -> List[Any]:
        output = self.run_jlink_command(["connect", *build_nonstop_read_commands(address, layout)])
        raw_values = parse_monitor_values(output, layout.element_size)
        if len(raw_values) < layout.count:
            raise RuntimeError(f"non-stop read returned {len(raw_values)} values, expected {layout.count}: {output}")
        return layout.decode_words(raw_values[: layout.count])

    def read_snapshot_layout(self, address: int, layout: Layout) -> List[Any]:
        return layout.decode(self.read_snapshot_block(address, layout.total_size))

    def read_layout_once(self, mode: str, address: int, layout: Layout) -> List[Any]:
        if mode == "nonstop":
            return self.read_nonstop_layout(address, layout)
        return self.read_snapshot_layout(address, layout)

    def resolve_pointer_target_address(self, mode: str, pointer_symbol_addr: int, max_retries: int) -> int:
        u32_layout = parse_layout("u32x1")

        for _ in range(max_retries):
            pointer_value = int(self.read_layout_once(mode, pointer_symbol_addr, u32_layout)[0])
            if is_valid_sram_pointer(pointer_value):
                return pointer_value

        raise RuntimeError(f"pointer symbol at 0x{pointer_symbol_addr:08X} did not publish a valid SRAM address")

    def capture_pointer_sample_nonstop(self, pointer_value: int, seq_symbol_addr: int, layout: Layout) -> Dict[str, Any]:
        if layout.element_size != 4:
            raise ValueError("pointer mode currently supports only 32-bit element layouts")

        u32_layout = parse_layout("u32x1")
        commands = [
            "connect",
            build_nonstop_read_command(seq_symbol_addr, u32_layout),
            build_nonstop_read_command(pointer_value, layout),
            build_nonstop_read_command(seq_symbol_addr, u32_layout),
        ]
        output = self.run_jlink_command(commands)
        raw_values = parse_monitor_values(output, 4)
        expected = layout.count + 2
        if len(raw_values) < expected:
            raise RuntimeError(f"pointer non-stop capture returned {len(raw_values)} values, expected {expected}: {output}")

        return {
            "seq_before": int(raw_values[0]),
            "values": layout.decode_words(raw_values[1 : 1 + layout.count]),
            "seq_after": int(raw_values[1 + layout.count]),
        }

    def capture_pointer_sample_snapshot(self, pointer_value: int, seq_symbol_addr: int, layout: Layout) -> Dict[str, Any]:
        if layout.element_size != 4:
            raise ValueError("pointer mode currently supports only 32-bit element layouts")

        u32_layout = parse_layout("u32x1")
        with tempfile.TemporaryDirectory(prefix="data_acq_pointer_snapshot_") as tmp_dir:
            bin_path = Path(tmp_dir) / "pointer_capture.bin"
            commands = [
                "connect",
                "h",
                build_nonstop_read_command(seq_symbol_addr, u32_layout),
                build_snapshot_savebin_command(bin_path, pointer_value, layout.total_size),
                build_nonstop_read_command(seq_symbol_addr, u32_layout),
                "go",
            ]
            output = self.run_jlink_command(commands)
            if not bin_path.exists():
                raise RuntimeError(f"pointer snapshot capture failed at 0x{pointer_value:08X}: {output}")

            raw_values = parse_monitor_values(output, 4)
            if len(raw_values) < 2:
                raise RuntimeError(f"pointer snapshot capture returned {len(raw_values)} sequence values: {output}")

            return {
                "seq_before": int(raw_values[0]),
                "values": layout.decode(bin_path.read_bytes()),
                "seq_after": int(raw_values[1]),
            }

    def sample_nonstop(
        self,
        *,
        symbol: str,
        address: int,
        layout: Layout,
        count: int,
        interval_ms: int,
    ) -> List[Dict[str, Any]]:
        samples: List[Dict[str, Any]] = []
        for sample_idx in range(count):
            values = self.read_nonstop_layout(address, layout)
            samples.append(
                {
                    "host_time_s": time.time(),
                    "sample_idx": sample_idx,
                    "symbol": symbol,
                    "address": f"0x{address:08X}",
                    "capture_mode": "nonstop",
                    "values": values,
                }
            )
            if interval_ms > 0 and sample_idx + 1 < count:
                time.sleep(interval_ms / 1000.0)
        return samples

    def sample_snapshot_typed(
        self,
        *,
        symbol: str,
        address: int,
        layout: Layout,
        count: int,
        interval_ms: int,
    ) -> List[Dict[str, Any]]:
        samples: List[Dict[str, Any]] = []
        for sample_idx in range(count):
            values = self.read_snapshot_layout(address, layout)
            samples.append(
                {
                    "host_time_s": time.time(),
                    "sample_idx": sample_idx,
                    "symbol": symbol,
                    "address": f"0x{address:08X}",
                    "capture_mode": "snapshot_intrusive",
                    "values": values,
                }
            )
            if interval_ms > 0 and sample_idx + 1 < count:
                time.sleep(interval_ms / 1000.0)
        return samples

    def sample_pointer_target(
        self,
        *,
        mode: str,
        pointer_symbol: str,
        pointer_symbol_addr: int,
        seq_symbol: str,
        seq_symbol_addr: int,
        layout: Layout,
        count: int,
        interval_ms: int,
        max_retries: int,
    ) -> List[Dict[str, Any]]:
        samples: List[Dict[str, Any]] = []
        pointer_value = self.resolve_pointer_target_address(mode, pointer_symbol_addr, max_retries)

        for sample_idx in range(count):
            sample: Optional[Dict[str, Any]] = None
            for _ in range(max_retries):
                if mode == "nonstop":
                    sample_data = self.capture_pointer_sample_nonstop(pointer_value, seq_symbol_addr, layout)
                else:
                    sample_data = self.capture_pointer_sample_snapshot(pointer_value, seq_symbol_addr, layout)

                if not is_consistent_pointer_sample(
                    sample_data["seq_before"], sample_data["seq_after"], pointer_value
                ):
                    continue

                sample = {
                    "host_time_s": time.time(),
                    "sample_idx": sample_idx,
                    "symbol": pointer_symbol,
                    "address": f"0x{pointer_symbol_addr:08X}",
                    "capture_mode": "snapshot_intrusive" if mode == "snapshot" else "nonstop",
                    "pointer_symbol": pointer_symbol,
                    "pointer_value": f"0x{pointer_value:08X}",
                    "seq_before": sample_data["seq_before"],
                    "seq_after": sample_data["seq_after"],
                    "values": sample_data["values"],
                }
                break

            if sample is None:
                raise RuntimeError(
                    f"pointer target capture failed for {pointer_symbol} after {max_retries} retries "
                    f"(seq symbol {seq_symbol})"
                )

            samples.append(sample)
            if interval_ms > 0 and sample_idx + 1 < count:
                time.sleep(interval_ms / 1000.0)

        return samples

    def sample_snapshot_raw(
        self,
        *,
        symbol: str,
        address: int,
        size: int,
        count: int,
        interval_ms: int,
    ) -> List[Dict[str, Any]]:
        samples: List[Dict[str, Any]] = []
        for sample_idx in range(count):
            data = self.read_snapshot_block(address, size)
            samples.append(
                {
                    "host_time_s": time.time(),
                    "sample_idx": sample_idx,
                    "symbol": symbol,
                    "address": f"0x{address:08X}",
                    "capture_mode": "snapshot_intrusive",
                    "data_hex": data.hex(),
                }
            )
            if interval_ms > 0 and sample_idx + 1 < count:
                time.sleep(interval_ms / 1000.0)
        return samples

    def start_rtt_capture(self, channel: int, output_file: Path) -> None:
        print(f"Starting RTT capture on channel {channel}...")
        print(f"Target device: {self.device}")
        print(f"Interface: {self.interface} @ {self.speed} kHz")

        script_path = output_file.with_suffix(".jlink")
        script_path.write_text(
            "\n".join(
                [
                    f"device {self.device}",
                    f"si {self.interface}",
                    f"speed {self.speed}",
                    "connect",
                    "rsetrttblock 0x20000000 0x1000",
                    "rsetrttblock 0x24000000 0x1000",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        print(f"RTT capture script created: {script_path}")
        print("Use JLinkRTTLogger for interactive RTT capture")
        print(
            f"Command: {JLINK_RTT_VIEWER} -device {self.device} -if {self.interface} "
            f"-speed {self.speed} -RTTTelnetPort 19021"
        )


def resolve_interval_ms(args: argparse.Namespace) -> int:
    if args.interval_ms is not None:
        return args.interval_ms
    if args.interval is not None:
        return args.interval
    if args.rate > 0:
        return max(1, int(1000 / args.rate))
    return 10


def build_metadata(
    *,
    args: argparse.Namespace,
    symbol: str,
    address: int,
    layout: Optional[Layout],
    interval_ms: int,
) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {
        "device": args.device,
        "interface": args.interface,
        "speed_khz": args.speed,
        "symbol": symbol,
        "address": f"0x{address:08X}",
        "count": args.count,
        "mode": args.mode,
        "interval_ms": interval_ms,
        "timestamp": datetime.now().isoformat(),
    }
    if layout is not None:
        metadata["layout"] = f"{layout.element_type}x{layout.count}"
        metadata["size"] = layout.total_size
    else:
        metadata["size"] = args.size
    if getattr(args, "pointer_symbol", None):
        metadata["pointer_symbol"] = args.pointer_symbol
        metadata["seq_symbol"] = args.seq_symbol
    if args.elf:
        metadata["elf"] = args.elf
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser(
        description="STM32 Data Acquisition Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --variable g_sensorData --layout f32x3 --count 200 --mode nonstop
  %(prog)s --address 0x20000000 --layout u32x4 --count 50 --mode snapshot
  %(prog)s --address 0x20001000 --size 64 --count 10 --mode snapshot
        """,
    )

    parser.add_argument("--device", "-d", default=DEFAULT_DEVICE, help=f"Target device (default: {DEFAULT_DEVICE})")
    parser.add_argument(
        "--interface",
        "-i",
        default=DEFAULT_INTERFACE,
        choices=["SWD", "JTAG"],
        help="Debug interface",
    )
    parser.add_argument("--speed", "-s", type=int, default=DEFAULT_SPEED, help="Interface speed in kHz")

    source_group = parser.add_mutually_exclusive_group()
    source_group.add_argument("--variable", "-v", help="Variable name to monitor")
    source_group.add_argument("--address", "-a", help="Memory address (hex)")
    source_group.add_argument("--pointer-symbol", help="Symbol that stores a runtime target address")
    source_group.add_argument("--rtt", action="store_true", help="Generate RTT capture helper script")

    parser.add_argument("--mode", choices=["nonstop", "snapshot"], default="nonstop", help="Capture mode")
    parser.add_argument("--layout", help="Typed layout, e.g. u32x1, s16x8, f32x3")
    parser.add_argument("--size", type=int, default=4, help="Raw memory block size in bytes")
    parser.add_argument("--count", "-c", type=int, default=100, help="Number of samples")
    parser.add_argument("--rate", "-r", type=int, default=1000, help="Sample rate in Hz")
    parser.add_argument("--interval-ms", type=int, help="Sample interval in ms")
    parser.add_argument("--interval", type=int, help="Legacy alias for interval-ms")
    parser.add_argument("--channel", type=int, default=0, help="RTT channel number")
    parser.add_argument("--elf", "-e", default=DEFAULT_ELF, help="ELF file path")
    parser.add_argument("--output", "-o", help="Output file path")
    parser.add_argument("--format", "-f", choices=["csv", "json"], default="csv", help="Output format")
    parser.add_argument("--gdb-port", type=int, default=DEFAULT_GDB_PORT, help="J-Link GDB Server port")
    parser.add_argument("--seq-symbol", default="g_local_probe_seq", help="Sequence symbol used by pointer mode")
    parser.add_argument("--max-retries", type=int, default=5, help="Retries per sample in pointer mode")

    args = parser.parse_args()
    interval_ms = resolve_interval_ms(args)
    acq = DataAcquisition(args.device, args.interface, args.speed)

    if args.rtt:
        output_path = ensure_output_path(args.output, args.format, "rtt_data")
        acq.start_rtt_capture(args.channel, output_path)
        return 0

    layout: Optional[Layout] = parse_layout(args.layout) if args.layout else None

    elf_file = args.elf or acq.find_elf_file()
    pointer_symbol_addr: Optional[int] = None
    seq_symbol_addr: Optional[int] = None
    if args.variable:
        if not elf_file:
            print("Error: no ELF file found for symbol resolution", file=sys.stderr)
            return 1
        if not acq.load_symbols(elf_file):
            print(f"Error: failed to load symbols from {elf_file}", file=sys.stderr)
            return 1
        address = acq.get_symbol_address(args.variable)
        if address is None:
            print(f"Error: variable '{args.variable}' not found in {elf_file}", file=sys.stderr)
            return 1
        symbol_name = args.variable
    elif args.address:
        try:
            address = int(args.address, 16)
        except ValueError:
            print(f"Error: invalid address '{args.address}'", file=sys.stderr)
            return 1
        symbol_name = ""
    elif args.pointer_symbol:
        if not elf_file:
            print("Error: no ELF file found for pointer symbol resolution", file=sys.stderr)
            return 1
        if not acq.load_symbols(elf_file):
            print(f"Error: failed to load symbols from {elf_file}", file=sys.stderr)
            return 1
        pointer_symbol_addr = acq.get_symbol_address(args.pointer_symbol)
        if pointer_symbol_addr is None:
            print(f"Error: pointer symbol '{args.pointer_symbol}' not found in {elf_file}", file=sys.stderr)
            return 1
        seq_symbol_addr = acq.get_symbol_address(args.seq_symbol)
        if seq_symbol_addr is None:
            print(f"Error: sequence symbol '{args.seq_symbol}' not found in {elf_file}", file=sys.stderr)
            return 1
        address = pointer_symbol_addr
        symbol_name = args.pointer_symbol
    else:
        parser.print_help()
        return 1

    if layout is None and args.variable:
        layout = parse_layout("u32x1")

    if args.pointer_symbol and layout is None:
        print("Error: --pointer-symbol requires --layout", file=sys.stderr)
        return 1

    if args.mode == "nonstop" and layout is None:
        print("Error: --mode nonstop requires --layout", file=sys.stderr)
        return 1

    output_prefix = "data_acq"
    output_path = ensure_output_path(args.output, args.format, output_prefix)

    print(f"Capture mode: {args.mode}")
    print(f"Target: {args.device} {args.interface}@{args.speed}kHz")
    print(f"Address: 0x{address:08X}")
    if symbol_name:
        print(f"Symbol: {symbol_name}")
    if args.pointer_symbol:
        print(f"Sequence symbol: {args.seq_symbol}")
    if layout is not None:
        print(f"Layout: {layout.element_type}x{layout.count}")
    else:
        print(f"Raw size: {args.size} bytes")
    print(f"Samples: {args.count}, interval: {interval_ms} ms")

    try:
        if args.pointer_symbol:
            assert layout is not None
            assert pointer_symbol_addr is not None
            assert seq_symbol_addr is not None
            samples = acq.sample_pointer_target(
                mode=args.mode,
                pointer_symbol=args.pointer_symbol,
                pointer_symbol_addr=pointer_symbol_addr,
                seq_symbol=args.seq_symbol,
                seq_symbol_addr=seq_symbol_addr,
                layout=layout,
                count=args.count,
                interval_ms=interval_ms,
                max_retries=args.max_retries,
            )
        elif args.mode == "nonstop":
            assert layout is not None
            samples = acq.sample_nonstop(
                symbol=symbol_name,
                address=address,
                layout=layout,
                count=args.count,
                interval_ms=interval_ms,
            )
        elif layout is not None:
            samples = acq.sample_snapshot_typed(
                symbol=symbol_name,
                address=address,
                layout=layout,
                count=args.count,
                interval_ms=interval_ms,
            )
        else:
            samples = acq.sample_snapshot_raw(
                symbol=symbol_name,
                address=address,
                size=args.size,
                count=args.count,
                interval_ms=interval_ms,
            )
    except (RuntimeError, TimeoutError, OSError, subprocess.SubprocessError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    metadata = build_metadata(
        args=args,
        symbol=symbol_name,
        address=address,
        layout=layout,
        interval_ms=interval_ms,
    )

    if args.format == "csv":
        if layout is not None:
            write_samples_csv(output_path, samples, layout.count)
        else:
            write_memory_csv(output_path, samples)
    else:
        write_json(output_path, metadata, samples)

    print(f"Data saved to: {output_path}")
    print(f"Total samples: {len(samples)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
