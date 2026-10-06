"""Run the held-out tasks through pinned OpenCode (v1.18.27), model selectable, usage recorded. Configuration name: P-CODE.

    python3 bench/run_opencode.py --model qwen3.8-flash --repeats 3 [--tasks GEN-01 ...]

Each task runs in a fresh workspace holding only the task input and AGENTS.md (agents/external/opencode_run.py).
Tokens are summed from OpenCode's own step events in stdout.jsonl. Output: analysis/opencode-<model>-<stamp>/results.jsonl.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.external.opencode_run import run_opencode  # noqa: E402
from bench.experiment import load_env, validate_and_grade  # noqa: E402

HELD = ROOT / "bench" / "tasks" / "t4_maritime_isr" / "heldout"


def usage_from_log(path: Path) -> dict:
    total = {"input": 0, "cached": 0, "cache_write": 0, "output": 0, "calls": 0}
    if not path.is_file():
        return total
    for line in path.read_text(encoding="utf-8").splitlines():
        if '"tokens"' not in line:
            continue
        try:
            tokens = (json.loads(line).get("part") or {}).get("tokens") or {}
        except json.JSONDecodeError:
            continue
        cache = tokens.get("cache") or {}
        total["input"] += (tokens.get("input") or 0) + (cache.get("read") or 0) + (cache.get("write") or 0)
        total["cached"] += cache.get("read") or 0
        total["cache_write"] += cache.get("write") or 0
        total["output"] += (tokens.get("output") or 0) + (tokens.get("reasoning") or 0)
        total["calls"] += 1
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="qwen3.8-flash")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--repeat-offset", type=int, default=0)
    parser.add_argument("--tasks", nargs="*", default=[])
    args = parser.parse_args()
    load_env()
    os.environ["MVP_LLM_MODEL"] = args.model
    tasks = [json.loads(line) for line in (HELD / "index.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.tasks:
        tasks = [item for item in tasks if item["id"] in args.tasks]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    out = ROOT / "analysis" / f"opencode-{args.model}-{stamp}"
    out.mkdir(parents=True)
    (out / "summary.json").write_text(json.dumps({"cohort": "opencode", "model": args.model, "version": "1.18.27",
                                                  "repeats": args.repeats, "started": stamp}, indent=2), encoding="utf-8")
    for repeat in range(1 + args.repeat_offset, 1 + args.repeat_offset + args.repeats):
        for item in tasks:
            task_dir = ROOT / item["path"]
            record = {"repeat": repeat, "task_id": item["id"], "type": item["type"], "configuration": "P-CODE",
                      "cohort_id": "opencode", "provider_model": args.model}
            try:
                solved = run_opencode(task_dir)
                workspace = Path(solved["workspace"])
                scored = validate_and_grade(task_dir, solved["text"], label=f"P-CODE-{item['id']}", workspace=workspace)
                record.update({"status": scored["status"], "sysml_status": scored.get("sysml_status"),
                               "engineering_status": scored.get("engineering_status"), "engine_run": scored.get("engine_run"),
                               "reason": scored.get("reason"), "usage": usage_from_log(workspace.parent / "stdout.jsonl"),
                               "returncode": solved["returncode"], "workspace": str(workspace)})
                if item["type"] == "ALN":
                    record.update({"precision": scored.get("precision"), "recall": scored.get("recall")})
            except Exception as exc:
                record.update({"status": "FAIL", "error": f"{type(exc).__name__}: {exc}", "trace": traceback.format_exc()[-1500:]})
            with (out / "results.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({key: value for key, value in record.items() if key != "trace"}, ensure_ascii=False) + "\n")
            print(f"r{repeat} {item['id']} {record['status']} {(record.get('usage') or {}).get('input', '?')} in / {(record.get('usage') or {}).get('output', '?')} out", flush=True)
    print(out)


if __name__ == "__main__":
    main()
