"""Pass rate and tokens per configuration from the saved 288-cell run."""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RUNS = [
    ROOT / "analysis" / "heldout-20261003T000045" / "results.jsonl",
    ROOT / "analysis" / "heldout-20261003T001321" / "results.jsonl",
]
OUT = ROOT / "analysis" / "ablation.json"


def _tokens(task_id: str, configuration: str, repeat: int) -> int:
    folders = sorted((ROOT / "mvp" / "agent-runs").glob(f"20261003T00*-{configuration}-{task_id}"))
    folders = [folder for folder in folders if (folder / "solve.json").is_file()]
    if repeat - 1 >= len(folders):
        return 0
    record = json.loads((folders[repeat - 1] / "solve.json").read_text(encoding="utf-8"))
    total = 0
    for call in record.get("calls") or []:
        total += int((call.get("usage") or {}).get("total_tokens") or 0)
    return total


def main() -> None:
    rows = []
    for path in RUNS:
        rows.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines())
    buckets = defaultdict(lambda: {"cells": 0, "pass": 0, "checklist_match": 0, "tokens": 0})
    for row in rows:
        item = buckets[row["configuration"]]
        item["cells"] += 1
        matched = row["status"] == "PASS" or (row["task_id"] == "MOD-05" and row.get("checks_match"))
        item["pass"] += row["status"] == "PASS"
        item["checklist_match"] += bool(matched)
        item["tokens"] += _tokens(row["task_id"], row["configuration"], row["repeat"])
    summary = {}
    for name in ("P0", "P1", "P2", "P3"):
        item = buckets[name]
        summary[name] = {**item,
                         "pass_rate": round(item["pass"] / item["cells"], 3),
                         "checklist_match_rate": round(item["checklist_match"] / item["cells"], 3),
                         "matches_per_1k_tokens": round(1000 * item["checklist_match"] / item["tokens"], 3) if item["tokens"] else None}
    OUT.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
