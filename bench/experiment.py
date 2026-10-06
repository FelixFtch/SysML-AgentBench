"""One replicate of the held-out set across P0, P1, P2, and P3.

The plan's later replicates use the same command with --repeats. Gold stays
on disk and is not sent to the model. Each cell is PASS or FAIL.
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.solve import solve  # noqa: E402
from bench.score_answer import score_answer  # noqa: E402
from bench.score_task import score_run  # noqa: E402

HELD = ROOT / "bench" / "tasks" / "t4_maritime_isr" / "heldout"
CONFIGS = ("P0", "P1", "P2", "P3")


def load_env() -> None:
    env = ROOT / ".env"
    if not env.is_file():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip().strip('"').strip("'")


def grade(task_dir: Path, solved: dict) -> dict:
    kind = yaml.safe_load((task_dir / "case.yaml").read_text(encoding="utf-8"))["type"]
    if kind in {"GEN", "MOD"}:
        if not solved.get("run_dir"):
            return {"status": "FAIL", "sysml_status": solved.get("sysml_status"),
                    "engineering_status": "FAIL", "reason": "The candidate produced no validated model."}
        scored = score_run(Path(solved["run_dir"]), task_dir / "gold" / "assertions.yaml")
        scored["sysml_status"] = solved.get("sysml_status") or scored.get("sysml_status")
        if scored["status"] != "PASS":
            scored["status"] = "FAIL"
        return scored
    scored = score_answer(task_dir, solved.get("text") or "")
    scored["sysml_status"] = None
    scored["engineering_status"] = scored["status"]
    return scored


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--repeat-offset", type=int, default=0)
    parser.add_argument("--configs", nargs="*", default=list(CONFIGS))
    parser.add_argument("--tasks", nargs="*", default=[])
    parser.add_argument("--rounds", type=int, default=None,
                        help="repair cap for P1-P3 (default BENCH_REPAIR_ROUNDS or 20); P0 never repairs")
    args = parser.parse_args()
    load_env()
    tasks = [json.loads(line) for line in (HELD / "index.jsonl").read_text(encoding="utf-8").splitlines()]
    if args.tasks:
        tasks = [item for item in tasks if item["id"] in args.tasks]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    out = ROOT / "analysis" / f"heldout-{stamp}"
    out.mkdir(parents=True)
    rows = []
    for repeat in range(1 + args.repeat_offset, 1 + args.repeat_offset + args.repeats):
        for item in tasks:
            for config in args.configs:
                task_dir = ROOT / item["path"]
                record = {"repeat": repeat, "task_id": item["id"], "type": item["type"], "configuration": config}
                try:
                    solved = solve(task_dir, config, max_rounds=args.rounds)
                    scored = grade(task_dir, solved)
                    record.update({"status": scored["status"], "sysml_status": scored.get("sysml_status"),
                                   "engineering_status": scored.get("engineering_status"),
                                   "structure_pass": scored.get("structure_pass"),
                                   "checks_match": scored.get("checks_match"),
                                   "engine_run": solved.get("engine_run"),
                                   "repair_rounds": solved.get("repair_rounds"),
                                   "max_rounds": solved.get("max_rounds"),
                                   "first_pass_attempt": solved.get("first_pass_attempt"),
                                   "resubmitted_unchanged": solved.get("resubmitted_unchanged"),
                                   "attempts": [{key: value for key, value in item.items() if key != "diagnostics"}
                                                | {"errors": len(item.get("diagnostics") or [])}
                                                for item in (solved.get("attempts") or [])],
                                   "calls": solved.get("calls")})
                except Exception as exc:
                    record.update({"status": "FAIL", "error": f"{type(exc).__name__}: {exc}",
                                   "trace": traceback.format_exc()[-1500:]})
                rows.append(record)
                with (out / "results.jsonl").open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps({key: value for key, value in record.items() if key != "trace"},
                                            ensure_ascii=False) + "\n")
                print(f"r{repeat} {item['id']} {config} {record['status']}", flush=True)
    counts = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    summary = {"cells": len(rows), "counts": counts, "directory": str(out)}
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
