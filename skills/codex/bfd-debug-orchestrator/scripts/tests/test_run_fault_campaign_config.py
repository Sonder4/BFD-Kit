import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / 'run_fault_campaign.sh'
SCRIPT_TEXT = SCRIPT_PATH.read_text(encoding='utf-8')


class RunFaultCampaignConfigTest(unittest.TestCase):
    def test_run_rtt_capture_passes_role_flag(self):
        self.assertRegex(
            SCRIPT_TEXT,
            r'cmd=\(\.\/build_tools\/jlink\/rtt\.sh.*--mode "\$\{mode\}".*--role "\$\{role\}"',
        )

    def test_capture_matrix_uses_role_aware_profiles(self):
        expected_calls = [
            r'run_rtt_capture rtt_base "\$\{BASELINE_RTT\}" 5 dual boot gdb-reset-go generic',
            r'run_rtt_capture "rtt_s\$\{s\}" "\$\{RTT_OUT\}" 4 quick diag none strict',
            r'run_rtt_capture "rtt_recover_s\$\{s\}" "\$\{RTT_REC\}" 6 dual boot gdb-reset-go generic',
            r'run_rtt_capture rtt_final "\$\{FINAL_RTT\}" 5 dual boot gdb-reset-go generic',
        ]
        for pattern in expected_calls:
            with self.subTest(pattern=pattern):
                self.assertRegex(SCRIPT_TEXT, pattern)

    def test_campaign_prefers_official_dynamic_inject_script(self):
        self.assertRegex(
            SCRIPT_TEXT,
            r'INJECT_SCRIPT="\$\{PROJECT_ROOT\}/build_tools/jlink/inject_fault_scenario\.sh"',
        )
        self.assertRegex(
            SCRIPT_TEXT,
            r'run_logged "inject_s\$\{s\}" "\$\{INJECT_SCRIPT\}" --scenario "\$s" --elf "\$ELF" --device "\$DEVICE" --if "\$IFACE" --speed "\$SPEED"',
        )

    def test_flash_rw_check_uses_final_capture_success(self):
        self.assertNotIn('[flash] W25Q64 ready', SCRIPT_TEXT)
        self.assertRegex(
            SCRIPT_TEXT,
            r"rtt_capture_succeeded\(\) \{[^}]*grep -Eq '\^RTT_SUCCESS=1\$' \"\$\{log_path\}\"",
        )
        self.assertRegex(
            SCRIPT_TEXT,
            r'if rtt_capture_succeeded "\$\{SESSION_DIR\}/rtt_final\.log"; then',
        )


if __name__ == '__main__':
    unittest.main(verbosity=2)
