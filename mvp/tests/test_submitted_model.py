"""Official-toolchain acceptance of a model that was not rendered from a fixture."""
import unittest
from pathlib import Path

from mvp.engine import run_submitted_model

SMOKE = Path(__file__).resolve().parents[1] / "toolchain" / "smoke-models"


class SubmittedModelTests(unittest.TestCase):
    def test_valid_smoke_model_passes_language_and_stays_unknown(self):
        result = run_submitted_model(
            [SMOKE / "types.sysml", SMOKE / "valid.sysml"], "Smoke", label="smoke-valid")
        self.assertEqual(result["sysml"]["status"], "PASS")
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertEqual(result["budget_status"], "NOT_APPLICABLE")
        self.assertTrue(result["model_elements"])
        self.assertEqual(result["checks"][0]["status"], "NOT_APPLICABLE")

    def test_broken_reference_fails_official_validation(self):
        result = run_submitted_model([SMOKE / "invalid-reference.sysml"], "Broken", label="smoke-broken")
        self.assertEqual(result["sysml"]["status"], "FAIL")
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["checks"][0]["id"], "BLOCKED-BY-SYSML")
        messages = " ".join(d.get("message", "") for d in result["sysml"]["diagnostics"])
        self.assertIn("MissingGatewayType", messages)


if __name__ == "__main__":
    unittest.main()
