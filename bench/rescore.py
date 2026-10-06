"""Re-score saved answers under freeze revision 2 (decision 028). No model is called.

Revision 2 changed the keys of MOD-01 (it also checks the radio part and link the statement says to keep) and AMB-02
(more ways to ask for the limit), and the AMB invented-number rule (bench/score_answer.py). For each scored batch folder
in bench/batches.py that ran before the revision, AMB rows are re-scored from the saved answer text and MOD-01 rows from
the saved official parse, with the same grade() the batch used; every other row is copied unchanged. Writes
results-r2.jsonl next to results.jsonl, which stays as run, and rescore-r2.json listing every row whose verdict changed.
The P3 reruns (heldout-p3doc-*) ran under revision 2 and are not touched.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bench.batches import AGENT_RUNS, COHORTS, _direct_folders, _lines, _start, batch_dir, rerun_dir  # noqa: E402
from bench.experiment import grade  # noqa: E402

HELD = ROOT / "bench" / "tasks" / "t4_maritime_isr" / "heldout"
RUNS = ROOT / "mvp" / "runs"


def _final_run(row: dict) -> str | None:
    ids = [item.get("run_id") for item in row.get("attempts") or [] if item.get("run_id")]
    return ids[-1] if ids else row.get("engine_run")


def _answer_text(row: dict, folders: dict) -> str:
    if row.get("workspace"):
        path = Path(row["workspace"]) / "answer.md"
    else:
        names = folders.get((row["configuration"], row["task_id"])) or []
        repeat = int(row.get("repeat") or 0)
        path = AGENT_RUNS / names[repeat - 1] / "response.txt" if 1 <= repeat <= len(names) else Path("-")
    if not path.is_file():
        raise FileNotFoundError(f"saved answer not found for {row['task_id']} r{row.get('repeat')}: {path}")
    return path.read_text(encoding="utf-8", errors="replace")


def rescore_folder(cohort: str, folder: Path) -> list[dict]:
    spec = COHORTS[cohort]
    folders = _direct_folders(spec["model"], _start(folder)) if spec["kind"] == "direct" else {}
    out, changed, touched = [], [], False
    for row in _lines(folder / "results.jsonl"):
        new = dict(row)
        if row["type"] == "AMB" or row["task_id"] == "MOD-01":
            touched = True
            task_dir = HELD / row["task_id"]
            if row["type"] == "AMB":
                scored = grade(task_dir, {"text": _answer_text(row, folders)})
            else:
                run = _final_run(row)
                scored = grade(task_dir, {"run_dir": str(RUNS / run) if run else None, "sysml_status": row.get("sysml_status")})
            new["status"] = scored["status"]
            new["rescored"] = "r2"
            if new["status"] != row["status"]:
                new["status_before_r2"] = row["status"]
                changed.append({"cohort": cohort, "batch": folder.name, "task_id": row["task_id"],
                                "configuration": row.get("configuration"), "repeat": row.get("repeat"),
                                "before": row["status"], "after": new["status"]})
        out.append(new)
    if touched:
        (folder / "results-r2.jsonl").write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in out), encoding="utf-8")
    return changed


def main() -> None:
    changed = []
    for cohort in COHORTS:
        for folder in (batch_dir(cohort), rerun_dir(cohort)):
            if folder and not folder.name.startswith("heldout-p3doc-"):
                changed += rescore_folder(cohort, folder)
    record = {"revision": "r2", "decision": "docs/decisions/028-freeze-revision-2.md",
              "rescored_at": datetime.now(timezone.utc).isoformat(), "changed": changed}
    (ROOT / "analysis" / "rescore-r2.json").write_text(json.dumps(record, indent=1), encoding="utf-8")
    print(json.dumps(changed, indent=1))


if __name__ == "__main__":
    main()
