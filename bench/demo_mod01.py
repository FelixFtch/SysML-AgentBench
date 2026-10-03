"""Replay the saved MOD-01 chain: score, approval gate, then one round-trip.

The submitted model is the replicate-1 P1 file. Round-trip is a new model call
that only sees that file. Its text is checked for the two facts in the task.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.approvals import approval_gate  # noqa: E402
from agents.llm import chat  # noqa: E402
from bench.experiment import load_env  # noqa: E402
from bench.score_task import score_run  # noqa: E402

RUN = ROOT / "mvp" / "runs" / "20261003T000522-7a243a69"
TASK = ROOT / "bench" / "tasks" / "t4_maritime_isr" / "heldout" / "MOD-01"


def main() -> None:
    load_env()
    scored = score_run(RUN, TASK / "gold" / "assertions.yaml")
    gate = approval_gate(decision_required=False, limit_changed=not scored["structure_pass"])
    model = (RUN / "model" / "UsvPlain.sysml").read_text(encoding="utf-8")
    restated = chat([
        {"role": "system", "content": "Restate only the requirements visible in the SysML. Plain sentences."},
        {"role": "user", "content": model},
    ], max_tokens=400)
    text = restated["text"].lower()
    phrases = {"infrared or ir": ("ir" in text), "limit 60": ("60" in text)}
    record = {"sysml_status": scored["sysml_status"], "checklist_status": scored["status"],
              "structure_pass": scored["structure_pass"], "approval": gate,
              "round_trip_hit": phrases, "round_trip_pass": all(phrases.values()),
              "usage": restated["usage"]}
    out = ROOT / "analysis" / "demo-mod01.json"
    out.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
