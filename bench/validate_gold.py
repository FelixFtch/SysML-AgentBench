"""Run the official toolchain on every held-out reference model and score it.

GEN and MOD references must satisfy their own checklists. MOD-05 must FAIL
the power check. This does not call a language model.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bench.score_task import score_run  # noqa: E402
from mvp.engine import run_submitted_model  # noqa: E402

HELD = ROOT / "bench" / "tasks" / "t4_maritime_isr" / "heldout"


def main() -> None:
    failures = []
    for line in (HELD / "index.jsonl").read_text(encoding="utf-8").splitlines():
        item = json.loads(line)
        if item["type"] not in {"GEN", "MOD"}:
            continue
        task = HELD / item["id"]
        case = yaml.safe_load((task / "case.yaml").read_text(encoding="utf-8"))
        model = next((task / "gold" / "reference").glob("*.sysml"))
        validated = run_submitted_model([model], case["package"], label=f"gold-{item['id']}")
        scored = score_run(Path(validated["run_dir"]), task / "gold" / "assertions.yaml")
        ok = scored["structure_pass"] and validated["sysml"]["status"] == "PASS" and scored["status"] == "PASS"
        if item["id"] == "MOD-05":
            ok = ok and scored["checks_match"] and scored["engineering_status"] == "FAIL"
        print(item["id"], validated["sysml"]["status"], scored["status"], scored["engineering_status"],
              "structure", scored["structure_pass"])
        if not ok:
            failures.append({"id": item["id"], "score": scored, "sysml": validated["sysml"]["status"]})
    if failures:
        print(json.dumps(failures, ensure_ascii=False, indent=2)[:4000])
        raise SystemExit(1)
    print("gold models match their checklists")


if __name__ == "__main__":
    main()
