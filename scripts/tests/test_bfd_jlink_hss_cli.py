import importlib.util
from pathlib import Path
import sys


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

SCRIPT_PATH = SCRIPTS_DIR / "bfd_jlink_hss.py"
SPEC = importlib.util.spec_from_file_location("bfd_jlink_hss_cli", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_hss_inspect_outputs_caps(monkeypatch):
    monkeypatch.setattr(MODULE, "list_probes", lambda _jlink_exe=None: [])
    monkeypatch.setattr(MODULE, "resolve_jlinkarm_dll", lambda: "/opt/SEGGER/JLink_V864a/libjlinkarm.so")

    class FakeDll:
        dll_path = "/opt/SEGGER/JLink_V864a/libjlinkarm.so"

        def __init__(self, dll_path=None):
            self.dll_path = dll_path or self.dll_path

        def open(self, usb_sn=None):
            self.usb_sn = usb_sn

        def connect(self, *, device, interface, speed_khz):
            return 602712337

        def get_hss_caps(self):
            return type("Caps", (), {"to_dict": lambda self=None: {"raw_words": [10, 1000, 2]}})()

        def close(self):
            pass

    monkeypatch.setattr(MODULE, "JLinkDll", FakeDll)
    exit_code = MODULE.main(["--json", "hss", "inspect", "--device", "STM32F427II", "--interface", "SWD", "--speed", "4000", "--usb-sn", "602712337"])
    assert exit_code == 0


def test_hss_sample_invokes_native_sampler(monkeypatch, tmp_path):
    monkeypatch.setattr(MODULE, "list_probes", lambda _jlink_exe=None: [])
    monkeypatch.setattr(MODULE, "resolve_jlinkarm_dll", lambda: "/opt/SEGGER/JLink_V864a/libjlinkarm.so")

    class FakeDll:
        def __init__(self, dll_path=None):
            self.dll_path = dll_path

    monkeypatch.setattr(MODULE, "JLinkDll", FakeDll)
    captured = {}

    def fake_sample_scalar_symbols(**kwargs):
        captured.update(kwargs)
        return type(
            "Result",
            (),
            {
                "to_dict": lambda self=None: {
                    "csv_path": str(tmp_path / "yaw.csv"),
                    "meta_path": str(tmp_path / "yaw.csv.meta.json"),
                    "sample_count": 2,
                    "symbols": [{"expression": "chassis_parameter.IMU.yaw"}, {"expression": "chassis_parameter.IMU.pitch"}],
                    "symbol": {"expression": "chassis_parameter.IMU.yaw"},
                    "caps": {"raw_words": [10, 1000, 2]},
                    "connected_serial_number": 602712337,
                    "duration_s": 0.1,
                    "period_us": 1000,
                    "record_size_bytes": 12,
                }
            },
        )()

    monkeypatch.setattr(MODULE, "sample_scalar_symbols", fake_sample_scalar_symbols)

    exit_code = MODULE.main(
        [
            "--json",
            "hss",
            "sample",
            "--elf",
            str(tmp_path / "app.elf"),
            "--symbol",
            "chassis_parameter.IMU.yaw",
            "--symbol",
            "chassis_parameter.IMU.pitch",
            "--device",
            "STM32F427II",
            "--interface",
            "SWD",
            "--speed",
            "4000",
            "--duration",
            "0.1",
            "--output",
            str(tmp_path / "yaw.csv"),
            "--usb-sn",
            "602712337",
        ]
    )
    assert exit_code == 0
    assert captured["usb_sn"] == "602712337"
    assert captured["symbol_expressions"] == ["chassis_parameter.IMU.yaw", "chassis_parameter.IMU.pitch"]
