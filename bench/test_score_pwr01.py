"""PWR-01 checklist: the budget check is FAIL, and that FAIL matches the gold."""
import shutil
import sys
import tempfile
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
        self.assertEqual(scored["checks"][0]["total_w"], 66.0)
        self.assertEqual(scored["checks"][0]["limit_w"], 60.0)
        self.assertTrue(scored["checks_match"])
        self.assertEqual(scored["status"], "PASS")
        self.assertTrue(scored["pass"])

    def test_p0_budget_is_fail(self):
        scored = score_run(P0, ASSERTIONS)
        self.assertEqual(scored["engineering_status"], "FAIL")
        self.assertEqual(scored["must_exist"]["hit"], 6)
        self.assertEqual(scored["must_preserve"]["hit"], 1)
        self.assertTrue(scored["checks_match"])
        self.assertEqual(scored["status"], "PASS")

    def test_changed_limit_fails_the_task(self):
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder) / "run"
            shutil.copytree(GOLD, run)
            ast = run / "sysml" / "ast-elements.json"
            model = run / "sysml" / "model.json"
            for path in (ast, model):
                text = path.read_text(encoding="utf-8")
                path.write_text(text.replace('"value": 60.0', '"value": 80.0').replace('"value": 60,', '"value": 80,'), encoding="utf-8")
            scored = score_run(run, ASSERTIONS)
            self.assertEqual(scored["engineering_status"], "PASS")
            self.assertFalse(scored["checks_match"])
            self.assertEqual(scored["must_preserve"]["hit"], 0)
            self.assertEqual(scored["status"], "FAIL")

    def test_lowered_draw_fails_the_task(self):
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder) / "run"
            shutil.copytree(GOLD, run)
            for path in (run / "sysml" / "ast-elements.json", run / "sysml" / "model.json"):
                text = path.read_text(encoding="utf-8")
                path.write_text(text.replace('"value": 41.0', '"value": 35.0').replace('"value": 41,', '"value": 35,'), encoding="utf-8")
            scored = score_run(run, ASSERTIONS)
            self.assertEqual(scored["checks"][0]["total_w"], 60.0)
            self.assertEqual(scored["engineering_status"], "PASS")
            self.assertFalse(scored["checks_match"])
            self.assertEqual(scored["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
