"""Re-validate every graded ALN answer with the alignment package listed first and compare with the scorer's order.

The scorer lists the two source models first and the alignment package last. Decision 026 records that the official
Pilot 0.62 can pass a package in the other order that it fails in the scorer's order. This script checks every ALN
answer of the four scored candidates, the agents' superseded first-batch ALN answers, and the three gold packages.
Output: analysis/validator-order-20261006.json. No model is called; the Pilot runs about 4 s per answer.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bench.batches import COHORTS, rows, superseded_rows  # noqa: E402

VALIDATE = ROOT / "mvp" / "toolchain" / "validate.py"
HELD = ROOT / "bench" / "tasks" / "t4_maritime_isr" / "heldout"
OUT = ROOT / "analysis" / "validator-order-20261006.json"


def _status(files: list[Path], package: str, out: Path) -> tuple[str, list[str]]:
    proc = subprocess.run(["python3", str(VALIDATE), "--package", package, "--output", str(out), *map(str, files)],
                          text=True, capture_output=True, timeout=300)
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return "ERROR", [proc.stderr[-200:]]
    return result.get("status"), [item.get("message", "") for item in result.get("diagnostics") or [] if item.get("severity") == "ERROR"]


def _jobs() -> list[dict]:
    jobs = []
    sources = [(cohort, row) for cohort in COHORTS for row in rows(cohort)]
    sources += [(f"{cohort}-superseded", row) for cohort in ("opencode", "claude") for row in superseded_rows(cohort)]
    for cohort, row in sources:
        if row["type"] != "ALN" or not row.get("engine_run"):
            continue
        run = ROOT / "mvp" / "runs" / row["engine_run"]
        result = json.loads((run / "result.json").read_text(encoding="utf-8"))
        files = [run / item["path"] for item in result["source_manifest"]["files"]]
        parse = json.loads((run / "sysml" / "result.json").read_text(encoding="utf-8"))
        jobs.append({"set": cohort, "task_id": row["task_id"], "configuration": row.get("configuration"), "repeat": row.get("repeat"),
                     "package": result["package_name"], "scorer_order": parse.get("status"), "verdict": row["status"],
                     "files": [str(path) for path in files[-1:] + files[:-1]]})
    for case in ("ALN-01", "ALN-02", "ALN-03"):
        base = sorted((HELD / case / "input" / "baseline").glob("*.sysml"))
        for gold in sorted((HELD / case / "gold" / "reference").glob("*.sysml")):
            jobs.append({"set": "gold", "task_id": case, "package": gold.stem, "scorer_order": None, "verdict": None,
                         "files": [str(gold)] + [str(path) for path in base], "scorer_files": [str(path) for path in base] + [str(gold)]})
    return jobs


def main() -> None:
    jobs = _jobs()
    scratch = Path(tempfile.mkdtemp(prefix="validator-order-"))

    def one(index_job: tuple[int, dict]) -> dict:
        index, job = index_job
        status, errors = _status([Path(item) for item in job["files"]], job["package"], scratch / f"{index}-first")
        job = {**job, "package_first": status, "package_first_errors": errors[:3]}
        if job["set"] == "gold":
            job["scorer_order"], _ = _status([Path(item) for item in job.pop("scorer_files")], job["package"], scratch / f"{index}-scorer")
        return job

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(one, enumerate(jobs)))
    for item in results:
        item["files"] = [str(Path(path).relative_to(ROOT)) if path.startswith(str(ROOT)) else path for path in item["files"]]
    summary: dict[str, dict] = {}
    for item in results:
        slot = summary.setdefault(item["set"], {"answers": 0, "differ": 0, "pass_only_package_first": 0})
        slot["answers"] += 1
        if item["package_first"] != item["scorer_order"]:
            slot["differ"] += 1
            slot["pass_only_package_first"] += item["package_first"] == "PASS" and item["scorer_order"] == "FAIL"
    OUT.write_text(json.dumps({"summary": summary, "results": results}, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1))
    for item in results:
        if item["package_first"] != item["scorer_order"]:
            print(item["set"], item["task_id"], f"r{item.get('repeat')}", "scorer order", item["scorer_order"], "package first", item["package_first"])


if __name__ == "__main__":
    main()
