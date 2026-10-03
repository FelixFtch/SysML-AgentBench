"""Walk one task through the plan, then record the engineering result.

Order: task text, submitted model, official validation, power check, query,
optional second-model review, checklist score, approval script, evidence file.
The second model does not change a FAIL into anything else.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.approvals import approval_gate  # noqa: E402
from bench.score_task import _load_assertions, score_run  # noqa: E402
from mvp.engine import dump  # noqa: E402
from tools.toolbox import check, diff_runs, query_power  # noqa: E402


def walk(task_dir: Path, run_dir: Path, *, role: str, against: Path | None = None,
         call_validator: bool = False) -> dict:
    requirements_path = task_dir / "input" / "requirements.md"
    assertions_path = task_dir / "gold" / "assertions.yaml"
    requirements = requirements_path.read_text(encoding="utf-8")
    assertions = _load_assertions(assertions_path)
    scored = score_run(run_dir, assertions_path)
    checked = check(run_dir)
    limit_changed = any(item.get("actual") != item.get("expected") for item in scored["must_preserve"]["missing"])
    record = {
        "task_id": assertions.get("task_id"),
        "role": role,
        "engineering_status": scored["engineering_status"],
        "status": scored["status"],
        "steps": {
            "1_task": {"requirements": str(requirements_path), "gold_hidden_from_candidate": True},
            "2_submission": {"run_dir": str(run_dir)},
            "3_validate": {"sysml_status": scored["sysml_status"]},
            "3_check": checked,
            "3_query": query_power(run_dir),
            "3_diff": diff_runs(run_dir, against) if against else None,
            "4_validator": None,
            "5_score": scored,
            "6_approval": approval_gate(
                decision_required=bool(assertions.get("decision_required")),
                limit_changed=limit_changed),
        },
    }
    if call_validator:
        from agents.validator import review
        model_text = (run_dir / "model").joinpath("PowerCheck.sysml").read_text(encoding="utf-8")
        record["steps"]["4_validator"] = review(requirements, model_text, tool_status=checked["status"])
    else:
        record["steps"]["4_validator"] = {"skipped": True,
                                           "reason": "The reference model is the answer key. It is not sent to a second model."}
    out = task_dir / "walk" / f"{role}.json"
    dump(out, record)
    record["evidence"] = str(out)
    return record


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--role", required=True)
    parser.add_argument("--against", type=Path)
    parser.add_argument("--validator", action="store_true")
    args = parser.parse_args()
    result = walk(args.task, args.run, role=args.role, against=args.against, call_validator=args.validator)
    print(json.dumps({"status": result["status"], "engineering_status": result["engineering_status"],
                      "evidence": result["evidence"],
                      "check": result["steps"]["3_check"],
                      "checks_match": result["steps"]["5_score"]["checks_match"],
                      "validator": result["steps"]["4_validator"]}, ensure_ascii=False, indent=2))
