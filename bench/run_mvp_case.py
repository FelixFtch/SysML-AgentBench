"""One model change on a MOD task: the model edits the baseline, the official tool scores it,
then the model reads the edited model back.

Gold is not placed in either prompt. A limit written in the baseline is not edited to obtain a pass.

    python3 bench/run_mvp_case.py [MOD-01 … MOD-05]
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.approvals import approval_gate  # noqa: E402
from agents.llm import chat, extract_sysml  # noqa: E402
from agents.solve import _generate, _task  # noqa: E402
from bench.experiment import grade, load_env  # noqa: E402

HELD = ROOT / "bench" / "tasks" / "t4_maritime_isr" / "heldout"
TASKS = ("MOD-01", "MOD-02", "MOD-03", "MOD-04", "MOD-05")
LITERAL = re.compile(r"=\s*([0-9]+(?:\.[0-9]+)?)\s*;")


def _archived(task_id: str) -> dict:
    """The same task's cells in the scored direct-flash batch (bench/batches.py), for comparison with this run."""
    from bench.batches import rows
    counts = {"PASS": 0, "FAIL": 0, "other": 0}
    for row in rows("flash"):
        if row.get("task_id") == task_id:
            status = row.get("status")
            counts[status if status in counts else "other"] += 1
    return counts


def _limit_value(source: str) -> str | None:
    match = re.search(r"powerLimitW\s*:\s*Real\s*=\s*([0-9]+(?:\.[0-9]+)?)", source)
    return f"{float(match.group(1)):g}" if match else None


def main() -> None:
    from agents.llm import USAGE_LOG, usage_summary
    from bench.discover import numbers_in
    from mvp.engine import run_submitted_model

    task_id = sys.argv[1] if len(sys.argv) > 1 else "MOD-05"
    if task_id not in TASKS:
        raise SystemExit(f"task must be one of {', '.join(TASKS)}")
    load_env()
    calls: list[dict] = []
    USAGE_LOG.set(calls)
    task_dir = HELD / task_id
    case, prompt = _task(task_dir)
    baseline = "\n".join(path.read_text(encoding="utf-8") for path in sorted((task_dir / "input" / "baseline").glob("*.sysml")))
    hazards = (ROOT / "scenario" / "maritime-isr" / "hazards.sysml").read_text(encoding="utf-8")
    written = _generate(prompt)
    try:
        source = extract_sysml(written["text"])
    except ValueError:
        source = ""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    solved = {"text": written["text"], "run_dir": None, "sysml_status": "FAIL"}
    diagnostics = [{"line": None, "message": "The model output contains no SysML package."}] if not source else []
    if source:
        scratch = ROOT / "mvp" / "exam-inbox" / f"mvp-case-{stamp}-{task_id}"
        scratch.mkdir(parents=True)
        path = scratch / f"{case['package']}.sysml"
        path.write_text(source, encoding="utf-8")
        validated = run_submitted_model([path], case["package"], label=f"mvp-case-{task_id}")
        solved.update({"run_dir": validated["run_dir"], "sysml_status": validated["sysml"]["status"]})
        diagnostics = [{"line": item.get("line"), "message": item.get("message", "")} for item in validated["sysml"].get("diagnostics", [])[:6]]
    scored = grade(task_dir, solved)
    limit, base_limit = _limit_value(source), _limit_value(baseline)
    gate = approval_gate(decision_required=False, limit_changed=base_limit is not None and limit != base_limit)
    restatement = ""
    mentioned: dict[str, bool] = {}
    if source:
        restatement = chat([
            {"role": "system", "content": "Restate only the requirements that are written in the given model. Plain sentences. Do not add numbers that are not in the model."},
            {"role": "user", "content": source},
        ], max_tokens=800)["text"]
        said = numbers_in(restatement)
        mentioned = {value: value in said for value in sorted({f"{float(raw):g}" for raw in LITERAL.findall(source)}, key=float)}
    record = {
        "id": stamp,
        "title": f"{task_id} change: the model edits an existing model, the official tool judges it, then it is read back as text",
        "synthetic": True,
        "task_id": task_id,
        "configuration": "P0",
        "model": written.get("model"),
        "requirements": prompt,
        "baseline": baseline,
        "gold_note": "The answer key is opened only for scoring; neither model call saw it.",
        "answer": source or written["text"],
        "sysml_status": solved["sysml_status"],
        "diagnostics": diagnostics,
        "status": scored.get("status"),
        "engineering_status": scored.get("engineering_status"),
        "checks": scored.get("checks"),
        "checks_match": scored.get("checks_match"),
        "must_exist": scored.get("must_exist"),
        "must_connect": scored.get("must_connect"),
        "must_preserve": scored.get("must_preserve"),
        "invented_numbers": scored.get("invented_numbers"),
        "run_dir": solved["run_dir"],
        "approval": gate,
        "limit_in_model": limit,
        "limit_in_baseline": base_limit,
        "round_trip": restatement,
        "round_trip_mentions": mentioned,
        "usage": usage_summary(calls),
        "safety": {
            "file": "scenario/maritime-isr/hazards.sysml",
            "kept": "LossOfSeparation" in hazards and "HazardTrackNotShared" in hazards,
            "note": "These two hazard requirements were not given to the model to rewrite. That they parse is not a safety pass.",
        },
        "interoperability": "This model goes to the Pilot as official SysML v2 text. It does not test the links between vessel, UAV and command ship.",
        "reliability": {
            "this_run": scored.get("status"),
            "archived": _archived(task_id),
            "note": "The same task's 12 cells in the scored direct-flash batch, to see whether the verdict is stable. This new run counts separately.",
        },
    }
    out = ROOT / "analysis" / f"mvp-case-{stamp}-{task_id}"
    out.mkdir(parents=True)
    text = json.dumps(record, ensure_ascii=False, indent=2)
    (out / "case.json").write_text(text, encoding="utf-8")
    (ROOT / "analysis" / f"mvp-case-latest-{task_id}.json").write_text(text, encoding="utf-8")
    if task_id == "MOD-05":
        (ROOT / "analysis" / "mvp-case-latest.json").write_text(text, encoding="utf-8")
    print(json.dumps({
        "id": stamp,
        "task_id": task_id,
        "sysml_status": record["sysml_status"],
        "status": record["status"],
        "engineering_status": record["engineering_status"],
        "must_preserve": record["must_preserve"],
        "checks": record["checks"],
        "approval": gate["answer"],
        "limit_in_model": limit,
        "round_trip_mentions": mentioned,
        "directory": str(out),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
