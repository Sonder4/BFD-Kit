import importlib.util
from pathlib import Path
import ctypes
import struct
import sys

import pytest


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from bfd_jlink_hss_core.env import ProbeInfo, parse_probe_list
from bfd_jlink_hss_core.hss_sampling import (
    HssSamplingError,
    decode_scalar_bytes,
    parse_hss_samples,
    read_hss_payload_with_backoff,
    sample_scalar_symbols,
    sample_scalar_symbol,
)
from bfd_jlink_hss_core.jlink_dll import HssBlock, JLinkDll, JLinkDllError, _NativeHssBlock, choose_probe


class FakeFunction:
    def __init__(self, return_value=0):
        self.return_value = return_value
        self.argtypes = None
        self.restype = None
        self.calls = []

    def __call__(self, *args):
        self.calls.append(args)
        return self.return_value


class FakeNativeDll:
    def __init__(self):
        self.JLINKARM_Open = FakeFunction(None)
        self.JLINKARM_Close = FakeFunction(None)
        self.JLINKARM_EMU_SelectByUSBSN = FakeFunction(0)
        self.JLINKARM_ExecCommand = FakeFunction(0)
        self.JLINKARM_TIF_Select = FakeFunction(0)
        self.JLINKARM_SetSpeed = FakeFunction(0)
        self.JLINKARM_Connect = FakeFunction(0)
        self.JLINKARM_GetSN = FakeFunction(602712337)
        self.JLINK_HSS_GetCaps = FakeFunction(0)
        self.JLINK_HSS_Start = FakeFunction(0)
        self.JLINK_HSS_Read = FakeFunction(0)
        self.JLINK_HSS_Stop = FakeFunction(0)


class FakeSamplingDll:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.stopped = False
        self.closed = False
        self.read_sizes = []

    def open(self, usb_sn=None):
        self.usb_sn = usb_sn

    def connect(self, *, device, interface, speed_khz):
        self.connect_args = (device, interface, speed_khz)
        return 602712337

    def get_hss_caps(self):
        return type(
            "Caps",
            (),
            {
                "max_buffer_bytes_inferred": 64,
                "raw_word_2_unknown": 2,
                "to_dict": lambda self=None: {"raw_words": [10, 64, 2], "raw_word_2_unknown": 2},
            },
        )()

    def hss_start(self, blocks, period_us):
        self.start_args = (blocks, period_us)

    def hss_read(self, size):
        self.read_sizes.append(size)
        if self.payloads:
            return self.payloads.pop(0)
        return b""

    def hss_stop(self):
        self.stopped = True

    def close(self):
        self.closed = True


def _resolved_symbol(expression="chassis_parameter.IMU.yaw", address=0x200002BC):
    leaf_name = expression.split(".")[-1]
    return type(
        "Resolved",
        (),
        {
            "expression": expression,
            "final_type_tag": "DW_TAG_base_type",
            "final_type_name": "float",
            "final_type_display": "float",
            "byte_size": 4,
            "final_address": address,
            "leaf_name": leaf_name,
            "to_dict": lambda self=None: {"expression": expression, "final_address_hex": f"0x{address:08X}"},
        },
    )()


def test_parse_probe_list_extracts_usb_probe_rows():
    probes = parse_probe_list("J-Link[0]: Connection: USB, Serial number: 602712337, ProductName: J-Link PLUS")
    assert len(probes) == 1
    assert probes[0].serial_number == "602712337"


def test_choose_probe_returns_only_probe_when_usb_sn_missing():
    probes = [ProbeInfo(index=0, connection="USB", serial_number="602712337", product_name="J-Link PLUS")]
    selected = choose_probe(probes, usb_sn=None)
    assert selected.serial_number == "602712337"


def test_choose_probe_rejects_ambiguous_selection():
    probes = [
        ProbeInfo(index=0, connection="USB", serial_number="602712337", product_name="J-Link PLUS"),
        ProbeInfo(index=1, connection="USB", serial_number="123456789", product_name="J-Link EDU"),
    ]
    with pytest.raises(JLinkDllError):
        choose_probe(probes, usb_sn=None)


def test_jlink_dll_connect_uses_expected_commands(tmp_path):
    fake = FakeNativeDll()
    wrapper = JLinkDll(dll_path=tmp_path / "libjlinkarm.so", dll=fake)
    wrapper.open(usb_sn="602712337")
    serial = wrapper.connect(device="STM32F427II", interface="SWD", speed_khz=4000)

    assert serial == 602712337
    assert fake.JLINKARM_EMU_SelectByUSBSN.calls == [(602712337,)]
    assert fake.JLINKARM_TIF_Select.calls == [(1,)]
    assert fake.JLINKARM_SetSpeed.calls == [(4000,)]
    assert fake.JLINKARM_Connect.calls == [()]


def test_jlink_dll_hss_start_supports_multiple_blocks(tmp_path):
    fake = FakeNativeDll()
    wrapper = JLinkDll(dll_path=tmp_path / "libjlinkarm.so", dll=fake)
    wrapper._is_open = True
    wrapper.hss_start(
        [
            HssBlock(address=0x20000000, byte_size=4),
            HssBlock(address=0x20000004, byte_size=4),
        ],
        period_us=1000,
    )

    assert len(fake.JLINK_HSS_Start.calls) == 1
    native_blocks, block_count, period_us, flags = fake.JLINK_HSS_Start.calls[0]
    assert block_count == 2
    assert period_us == 1000
    assert flags == 0
    assert native_blocks[0].address == 0x20000000
    assert native_blocks[0].byte_size == 4
    assert native_blocks[1].address == 0x20000004
    assert native_blocks[1].byte_size == 4


def test_native_hss_block_matches_segger_stride_requirement():
    assert ctypes.sizeof(_NativeHssBlock) == 16


def test_jlink_dll_hss_read_treats_positive_return_value_as_byte_count(tmp_path):
    fake = FakeNativeDll()
    fake.JLINK_HSS_Read = FakeFunction(12)
    wrapper = JLinkDll(dll_path=tmp_path / "libjlinkarm.so", dll=fake)
    wrapper._is_open = True
    payload = wrapper.hss_read(32)
    assert len(payload) == 12


def test_decode_scalar_bytes_supports_float():
    resolved = _resolved_symbol()
    assert abs(decode_scalar_bytes(resolved, struct.pack("<f", 1.25)) - 1.25) < 1e-6


def test_parse_hss_samples_handles_remainder_bytes():
    resolved = _resolved_symbol()
    payload = struct.pack("<If", 3, 1.5) + struct.pack("<If", 4, 2.5)
    partial = payload[:-2]
    samples, trailing = parse_hss_samples(partial, symbol=resolved, period_us=1000)
    assert len(samples) == 1
    assert samples[0].sample_index == 3
    assert trailing

    samples2, trailing2 = parse_hss_samples(payload[-2:], symbol=resolved, period_us=1000, remainder=trailing)
    assert len(samples2) == 1
    assert samples2[0].sample_index == 4
    assert trailing2 == b""


def test_parse_hss_samples_supports_multiple_symbols_and_remainder():
    resolved_symbols = [
        _resolved_symbol("chassis_parameter.IMU.yaw", 0x200002BC),
        _resolved_symbol("chassis_parameter.IMU.pitch", 0x200002C0),
        _resolved_symbol("chassis_parameter.IMU.roll", 0x200002C4),
    ]
    payload = struct.pack("<Ifff", 3, 1.5, 2.5, 3.5) + struct.pack("<Ifff", 4, 4.5, 5.5, 6.5)
    partial = payload[:-3]

    samples, trailing = parse_hss_samples(partial, symbols=resolved_symbols, period_us=1000)
    assert len(samples) == 1
    assert samples[0].sample_index == 3
    assert samples[0].values["chassis_parameter.IMU.pitch"] == pytest.approx(2.5)
    assert trailing

    samples2, trailing2 = parse_hss_samples(payload[-3:], symbols=resolved_symbols, period_us=1000, remainder=trailing)
    assert len(samples2) == 1
    assert samples2[0].sample_index == 4
    assert samples2[0].values["chassis_parameter.IMU.roll"] == pytest.approx(6.5)
    assert trailing2 == b""


def test_sample_scalar_symbol_writes_csv(tmp_path, monkeypatch):
    payload = struct.pack("<If", 0, 1.0) + struct.pack("<If", 1, 2.0)
    fake_dll = FakeSamplingDll([payload])
    monkeypatch.setattr("bfd_jlink_hss_core.hss_sampling.resolve_symbol_path", lambda *_args, **_kwargs: _resolved_symbol())

    values = iter([0.0, 0.01, 0.02, 0.03])
    monkeypatch.setattr("bfd_jlink_hss_core.hss_sampling.time.monotonic", lambda: next(values))
    monkeypatch.setattr("bfd_jlink_hss_core.hss_sampling.time.sleep", lambda _seconds: None)

    result = sample_scalar_symbol(
        dll=fake_dll,
        elf_path=str(tmp_path / "app.elf"),
        symbol_expression="chassis_parameter.IMU.yaw",
        device="STM32F427II",
        interface="SWD",
        speed_khz=4000,
        duration_s=0.02,
        period_us=1000,
        output_csv=str(tmp_path / "yaw.csv"),
    )

    content = Path(result.csv_path).read_text(encoding="utf-8")
    assert "sample_index,time_us,symbol,value,raw_hex,address" in content
    assert "chassis_parameter.IMU.yaw" in content
    assert result.sample_count == 2
    assert fake_dll.read_sizes == [64, 64]
    assert fake_dll.stopped is True
    assert fake_dll.closed is True


def test_sample_scalar_symbols_writes_wide_csv_and_meta(tmp_path, monkeypatch):
    payload = struct.pack("<Ifff", 0, 1.0, 2.0, 3.0) + struct.pack("<Ifff", 1, 4.0, 5.0, 6.0)
    fake_dll = FakeSamplingDll([payload])
    resolved_map = {
        "chassis_parameter.IMU.yaw": _resolved_symbol("chassis_parameter.IMU.yaw", 0x200002BC),
        "chassis_parameter.IMU.pitch": _resolved_symbol("chassis_parameter.IMU.pitch", 0x200002C0),
        "chassis_parameter.IMU.roll": _resolved_symbol("chassis_parameter.IMU.roll", 0x200002C4),
    }
    monkeypatch.setattr(
        "bfd_jlink_hss_core.hss_sampling.resolve_symbol_path",
        lambda _elf, expression: resolved_map[expression],
    )

    values = iter([0.0, 0.01, 0.02, 0.03])
    monkeypatch.setattr("bfd_jlink_hss_core.hss_sampling.time.monotonic", lambda: next(values))
    monkeypatch.setattr("bfd_jlink_hss_core.hss_sampling.time.sleep", lambda _seconds: None)

    result = sample_scalar_symbols(
        dll=fake_dll,
        elf_path=str(tmp_path / "app.elf"),
        symbol_expressions=list(resolved_map.keys()),
        device="STM32F427II",
        interface="SWD",
        speed_khz=4000,
        duration_s=0.02,
        period_us=1000,
        output_csv=str(tmp_path / "imu.csv"),
    )

    content = Path(result.csv_path).read_text(encoding="utf-8")
    assert "sample_index,time_us,chassis_parameter_IMU_yaw__value,chassis_parameter_IMU_yaw__raw_hex" in content
    assert "chassis_parameter_IMU_pitch__value" in content
    assert "chassis_parameter_IMU_roll__value" in content
    meta = Path(result.meta_path).read_text(encoding="utf-8")
    assert '"expression": "chassis_parameter.IMU.yaw"' in meta
    assert '"record_size_bytes": 16' in meta
    assert result.sample_count == 2
    assert len(result.symbols) == 3
    assert fake_dll.read_sizes == [64, 64]
    assert fake_dll.stopped is True
    assert fake_dll.closed is True


def test_sample_scalar_symbols_does_not_treat_raw_word_2_as_symbol_limit(tmp_path, monkeypatch):
    payload = struct.pack("<Ifff", 0, 1.0, 2.0, 3.0)
    fake_dll = FakeSamplingDll([payload])
    resolved_map = {
        "chassis_parameter.IMU.yaw": _resolved_symbol("chassis_parameter.IMU.yaw", 0x200002BC),
        "chassis_parameter.IMU.pitch": _resolved_symbol("chassis_parameter.IMU.pitch", 0x200002C0),
        "chassis_parameter.IMU.roll": _resolved_symbol("chassis_parameter.IMU.roll", 0x200002C4),
    }
    monkeypatch.setattr(
        "bfd_jlink_hss_core.hss_sampling.resolve_symbol_path",
        lambda _elf, expression: resolved_map[expression],
    )
    values = iter([0.0, 0.01, 0.02, 0.03])
    monkeypatch.setattr("bfd_jlink_hss_core.hss_sampling.time.monotonic", lambda: next(values))
    monkeypatch.setattr("bfd_jlink_hss_core.hss_sampling.time.sleep", lambda _seconds: None)

    result = sample_scalar_symbols(
        dll=fake_dll,
        elf_path=str(tmp_path / "app.elf"),
        symbol_expressions=list(resolved_map.keys()),
        device="STM32F427II",
        interface="SWD",
        speed_khz=4000,
        duration_s=0.02,
        period_us=1000,
        output_csv=str(tmp_path / "imu.csv"),
    )

    assert result.sample_count == 1


def test_sample_scalar_symbol_fails_when_no_samples(tmp_path, monkeypatch):
    fake_dll = FakeSamplingDll([b""])
    monkeypatch.setattr("bfd_jlink_hss_core.hss_sampling.resolve_symbol_path", lambda *_args, **_kwargs: _resolved_symbol())
    values = iter([0.0, 0.02, 0.03])
    monkeypatch.setattr("bfd_jlink_hss_core.hss_sampling.time.monotonic", lambda: next(values))
    monkeypatch.setattr("bfd_jlink_hss_core.hss_sampling.time.sleep", lambda _seconds: None)

    with pytest.raises(HssSamplingError):
        sample_scalar_symbol(
            dll=fake_dll,
            elf_path=str(tmp_path / "app.elf"),
            symbol_expression="chassis_parameter.IMU.yaw",
            device="STM32F427II",
            interface="SWD",
            speed_khz=4000,
            duration_s=0.01,
            period_us=1000,
            output_csv=str(tmp_path / "yaw.csv"),
        )
    assert fake_dll.stopped is True
    assert fake_dll.closed is True


def test_read_hss_payload_with_backoff_retries_smaller_buffers():
    class BackoffDll:
        def __init__(self):
            self.calls = []

        def hss_read(self, size):
            self.calls.append(size)
            if size > 16:
                raise JLinkDllError("too large")
            return b"x" * size

    dll = BackoffDll()
    payload = read_hss_payload_with_backoff(dll, preferred_size=64, record_size=8)
    assert dll.calls == [64, 32, 16]
    assert len(payload) == 16
