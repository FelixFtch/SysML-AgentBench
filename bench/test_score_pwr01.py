"""PWR-01 checklist: the budget check is FAIL, and that FAIL matches the gold."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bench.score_task import score_run

TASK = ROOT / "bench" / "tasks" / "t4_maritime_isr" / "dev" / "PWR-01"
ASSERTIONS = TASK / "gold" / "assertions.yaml"
GOLD = ROOT / "mvp" / "runs" / "20261002T232728-e49ca19a"
P0 = ROOT / "mvp" / "runs" / "20261002T233348-89c0fbc7"


class PowerScoreTests(unittest.TestCase):
    def test_gold_budget_is_fail(self):
        scored = score_run(GOLD, ASSERTIONS)
        self.assertEqual(scored["sysml_status"], "PASS")
        self.assertEqual(scored["engineering_status"], "FAIL")
        self.assertEqual(scored["status"], "FAIL")
        self.assertEqual(scored["checks"][0]["total_w"], 66.0)
        self.assertEqual(scored["checks"][0]["limit_w"], 60.0)
        self.assertTrue(scored["checks_match"])
        self.assertFalse(scored["pass"])

    def test_p0_budget_is_fail(self):
        scored = score_run(P0, ASSERTIONS)
        self.assertEqual(scored["status"], "FAIL")
        self.assertEqual(scored["must_exist"]["hit"], 6)
        self.assertEqual(scored["must_preserve"]["hit"], 1)
        self.assertTrue(scored["checks_match"])


if __name__ == "__main__":
    unittest.main()
