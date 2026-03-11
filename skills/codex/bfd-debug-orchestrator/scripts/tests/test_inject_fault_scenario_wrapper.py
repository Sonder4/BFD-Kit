import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / 'inject_fault_scenario.sh'
SCRIPT_TEXT = SCRIPT_PATH.read_text(encoding='utf-8')


class InjectFaultScenarioWrapperTest(unittest.TestCase):
    def test_wrapper_delegates_to_official_script(self):
        self.assertIn('OFFICIAL_SCRIPT="${PROJECT_ROOT}/build_tools/jlink/inject_fault_scenario.sh"', SCRIPT_TEXT)
        self.assertIn('exec "${OFFICIAL_SCRIPT}" "$@"', SCRIPT_TEXT)


if __name__ == '__main__':
    unittest.main(verbosity=2)
