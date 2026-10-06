"""Text tasks resolve to PASS or FAIL."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bench.score_answer import score_answer  # noqa: E402

HELD = ROOT / "bench" / "tasks" / "t4_maritime_isr" / "heldout"


class AnswerScoreTests(unittest.TestCase):
    def test_query_exact_value(self):
        text = json.dumps({"attribute": "MaritimeISR::UnmannedSurfaceVessel::powerLimitW", "value": 60})
        scored = score_answer(HELD / "QRY-02", text)
        self.assertEqual(scored["status"], "PASS")

    def test_query_wrong_value_fails(self):
        text = json.dumps({"attribute": "MaritimeISR::UnmannedSurfaceVessel::powerLimitW", "value": 80})
        self.assertEqual(score_answer(HELD / "QRY-02", text)["status"], "FAIL")

    def test_ambiguity_question_passes_and_invented_model_fails(self):
        asked = "What latency and bandwidth should the real-time track share use?"
        self.assertEqual(score_answer(HELD / "AMB-01", asked)["status"], "PASS")
        invented = asked + "\n```sysml\nattribute latencyS : Real = 2.0;\n```"
        self.assertEqual(score_answer(HELD / "AMB-01", invented)["status"], "FAIL")

    def test_example_number_in_a_question_without_sysml_is_not_invented(self):
        asked = "What is the watt limit? Please give it as a number and a unit, e.g. 450 W."
        scored = score_answer(HELD / "AMB-02", asked)
        self.assertEqual(scored["status"], "PASS")
        self.assertEqual(scored["numbers_not_counted"], ["450 W"])
        assumed = asked + "\n```sysml\nattribute powerLimitW : Real = 450.0;\n```"
        self.assertEqual(score_answer(HELD / "AMB-02", assumed)["status"], "FAIL")

    def test_amb02_accepts_a_question_about_the_maximum_power(self):
        asked = "What is the target maximum power consumption value and unit?"
        self.assertEqual(score_answer(HELD / "AMB-02", asked)["status"], "PASS")
        self.assertEqual(score_answer(HELD / "AMB-02", "What is the operating voltage of the vessel?")["status"], "FAIL")

    def test_round_trip_requires_every_phrase(self):
        self.assertEqual(score_answer(HELD / "RT-03", "The UAV radar shares tracks with the command ship.")["status"], "PASS")
        self.assertEqual(score_answer(HELD / "RT-03", "The UAV has a radar.")["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
