import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "summarize_campaign.py"
SPEC = importlib.util.spec_from_file_location("summarize_campaign", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class SummarizeCampaignTest(unittest.TestCase):
    def write_log(self, session_dir: Path, name: str, lines):
        path = session_dir / f"{name}.log"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def test_boot_baseline_remains_advisory(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            session_dir = Path(tmp_dir)
            self.write_log(
                session_dir,
                "rtt_base",
                [
                    "RTT_ROLE=boot",
                    "RTT_CHANNEL=0",
                    "RTT_MODE=dual",
                    "RTT_SUCCESS=0",
                    "RTT_SIGNAL=payload_missing",
                    "RTT_COMMAND_RC=2",
                ],
            )

            results = MODULE.collect_rtt_results(session_dir)
            status = MODULE.aggregate_rtt_status(results)

            self.assertEqual(results[0]["role"], "advisory")
            self.assertEqual(status["overall"], "PASS")
            self.assertEqual(status["advisory"], "WARN")

    def test_final_boot_capture_is_required(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            session_dir = Path(tmp_dir)
            self.write_log(
                session_dir,
                "rtt_final",
                [
                    "RTT_ROLE=boot",
                    "RTT_CHANNEL=0",
                    "RTT_MODE=dual",
                    "RTT_SUCCESS=0",
                    "RTT_SIGNAL=payload_missing",
                    "RTT_COMMAND_RC=2",
                ],
            )

            results = MODULE.collect_rtt_results(session_dir)
            status = MODULE.aggregate_rtt_status(results)

            self.assertEqual(results[0]["role"], "required")
            self.assertEqual(results[0]["status"], "WARN")
            self.assertEqual(status["overall"], "WARN")

    def test_softfault_requires_scenario_evidence(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            session_dir = Path(tmp_dir)
            self.write_log(
                session_dir,
                "rtt_s1",
                [
                    "RTT_ROLE=diag",
                    "RTT_CHANNEL=1",
                    "RTT_MODE=quick",
                    "RTT_SUCCESS=1",
                    "RTT_SIGNAL=structured_log",
                    "RTT_COMMAND_RC=0",
                ],
            )

            results = MODULE.collect_rtt_results(session_dir)
            status = MODULE.aggregate_rtt_status(results)

            self.assertEqual(results[0]["status"], "WARN")
            self.assertEqual(status["overall"], "WARN")


    def test_softfault_live_signal_is_strong_evidence(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            session_dir = Path(tmp_dir)
            self.write_log(
                session_dir,
                "rtt_s1",
                [
                    "RTT_ROLE=diag",
                    "RTT_CHANNEL=1",
                    "RTT_MODE=quick",
                    "RTT_SUCCESS=1",
                    "RTT_SIGNAL=live_scenario_log",
                    "RTT_COMMAND_RC=0",
                ],
            )

            results = MODULE.collect_rtt_results(session_dir)
            status = MODULE.aggregate_rtt_status(results)

            self.assertEqual(results[0]["status"], "PASS")
            self.assertEqual(status["overall"], "PASS")

    def test_campaign_passes_with_required_boot_and_diag_evidence(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            session_dir = Path(tmp_dir)
            self.write_log(
                session_dir,
                "rtt_base",
                [
                    "RTT_ROLE=boot",
                    "RTT_CHANNEL=0",
                    "RTT_MODE=dual",
                    "RTT_SUCCESS=0",
                    "RTT_SIGNAL=payload_missing",
                    "RTT_COMMAND_RC=2",
                ],
            )
            self.write_log(
                session_dir,
                "rtt_s1",
                [
                    "RTT_ROLE=diag",
                    "RTT_CHANNEL=1",
                    "RTT_MODE=quick",
                    "RTT_SUCCESS=1",
                    "RTT_SIGNAL=fallback_scenario_log",
                    "RTT_COMMAND_RC=0",
                ],
            )
            self.write_log(
                session_dir,
                "rtt_s2",
                [
                    "RTT_ROLE=diag",
                    "RTT_CHANNEL=1",
                    "RTT_MODE=quick",
                    "RTT_SUCCESS=1",
                    "RTT_SIGNAL=fallback_scenario_log",
                    "RTT_COMMAND_RC=0",
                ],
            )
            self.write_log(
                session_dir,
                "rtt_recover_s3",
                [
                    "RTT_ROLE=boot",
                    "RTT_CHANNEL=0",
                    "RTT_MODE=dual",
                    "RTT_SUCCESS=1",
                    "RTT_SIGNAL=log_init",
                    "RTT_COMMAND_RC=0",
                ],
            )
            self.write_log(
                session_dir,
                "rtt_recover_s4",
                [
                    "RTT_ROLE=boot",
                    "RTT_CHANNEL=0",
                    "RTT_MODE=dual",
                    "RTT_SUCCESS=1",
                    "RTT_SIGNAL=log_init",
                    "RTT_COMMAND_RC=0",
                ],
            )
            self.write_log(
                session_dir,
                "rtt_final",
                [
                    "RTT_ROLE=boot",
                    "RTT_CHANNEL=0",
                    "RTT_MODE=dual",
                    "RTT_SUCCESS=1",
                    "RTT_SIGNAL=structured_log",
                    "RTT_COMMAND_RC=0",
                ],
            )

            results = MODULE.collect_rtt_results(session_dir)
            status = MODULE.aggregate_rtt_status(results)

            self.assertEqual(status["overall"], "PASS")
            self.assertEqual(status["required"], "PASS")
            self.assertEqual(status["advisory"], "WARN")


if __name__ == "__main__":
    unittest.main(verbosity=2)
