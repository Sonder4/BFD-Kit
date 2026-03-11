import csv
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "data_acq.py"
SPEC = importlib.util.spec_from_file_location("data_acq", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class DataAcqTest(unittest.TestCase):
    def test_parse_layout_supports_u32_vectors(self):
        layout = MODULE.parse_layout("u32x2")

        self.assertEqual(layout.element_type, "u32")
        self.assertEqual(layout.count, 2)
        self.assertEqual(layout.element_size, 4)
        self.assertEqual(layout.total_size, 8)
        self.assertEqual(layout.decode(b"\x01\x00\x00\x00\x02\x00\x00\x00"), [1, 2])

    def test_nonstop_read_uses_monitor_mem_command(self):
        layout = MODULE.parse_layout("u32x2")

        self.assertEqual(
            MODULE.build_nonstop_read_command(0x20000000, layout),
            "mem32 0x20000000 2",
        )

    def test_nonstop_setup_enforces_background_access(self):
        self.assertEqual(
            MODULE.build_nonstop_setup_commands(),
            ["target extended-remote :2331", "monitor exec SetAllowStopMode = 0"],
        )

    def test_nonstop_vector_reads_use_block_mem_command(self):
        layout = MODULE.parse_layout("u32x3")

        self.assertEqual(
            MODULE.build_nonstop_read_commands(0x20000000, layout),
            ["mem32 0x20000000 3"],
        )

    def test_parse_monitor_values_accepts_data_equals_format(self):
        output = "\n".join(
            [
                "Reading from address 0x2000F860 (Data = 0x00000003)",
                "Reading from address 0x2000F864 (Data = 0x00000004)",
            ]
        )

        self.assertEqual(MODULE.parse_monitor_values(output, 4), [3, 4])

    def test_parse_monitor_values_ignores_register_dump_lines(self):
        output = "\n".join(
            [
                "R0 = 00000000, R1 = A5A5A5A5, R2 = A5A5A5A5, R3 = 00000001",
                "SP(R13)= 20000E88, MSP= 2002FFE0, PSP= 20000E88, R14(LR) = 0800DD51",
                "20010490 = 00018E88 ",
                "20010494 = 00000004 ",
            ]
        )

        self.assertEqual(MODULE.parse_monitor_values(output, 4), [0x00018E88, 0x00000004])

    def test_snapshot_savebin_command_uses_hex_size(self):
        self.assertEqual(
            MODULE.build_snapshot_savebin_command(Path("/tmp/capture.bin"), 0x2000F860, 12),
            "savebin /tmp/capture.bin 0x2000F860 0xC",
        )

    def test_is_valid_sram_pointer_accepts_internal_sram(self):
        self.assertTrue(MODULE.is_valid_sram_pointer(0x20000000))
        self.assertTrue(MODULE.is_valid_sram_pointer(0x2001FFFC))
        self.assertFalse(MODULE.is_valid_sram_pointer(0x00000000))
        self.assertFalse(MODULE.is_valid_sram_pointer(0x08000000))

    def test_pointer_sample_consistency_requires_even_stable_seq(self):
        self.assertTrue(MODULE.is_consistent_pointer_sample(8, 8, 0x20001000))
        self.assertFalse(MODULE.is_consistent_pointer_sample(7, 8, 0x20001000))
        self.assertFalse(MODULE.is_consistent_pointer_sample(9, 9, 0x20001000))
        self.assertFalse(MODULE.is_consistent_pointer_sample(8, 8, 0x00000000))

    def test_write_samples_csv_uses_metadata_columns(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "sample.csv"
            MODULE.write_samples_csv(
                csv_path,
                [
                    {
                        "host_time_s": 1.25,
                        "sample_idx": 3,
                        "symbol": "g_test",
                        "address": "0x20000000",
                        "capture_mode": "nonstop",
                        "values": [10, 20],
                    }
                ],
                value_count=2,
            )

            with csv_path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.reader(handle))

        self.assertEqual(
            rows[0],
            ["host_time_s", "sample_idx", "symbol", "address", "capture_mode", "value0", "value1"],
        )
        self.assertEqual(rows[1], ["1.25", "3", "g_test", "0x20000000", "nonstop", "10", "20"])

    def test_write_samples_csv_includes_pointer_metadata_columns(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "pointer_sample.csv"
            MODULE.write_samples_csv(
                csv_path,
                [
                    {
                        "host_time_s": 1.0,
                        "sample_idx": 0,
                        "symbol": "g_local_probe_addr",
                        "address": "0x20001000",
                        "capture_mode": "nonstop",
                        "pointer_symbol": "g_local_probe_addr",
                        "pointer_value": "0x20002000",
                        "seq_before": 2,
                        "seq_after": 2,
                        "values": [3.5],
                    }
                ],
                value_count=1,
            )

            with csv_path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.reader(handle))

        self.assertEqual(
            rows[0],
            [
                "host_time_s",
                "sample_idx",
                "symbol",
                "address",
                "capture_mode",
                "pointer_symbol",
                "pointer_value",
                "seq_before",
                "seq_after",
                "value0",
            ],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
