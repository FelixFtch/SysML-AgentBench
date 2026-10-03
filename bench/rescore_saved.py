"""Re-apply the scorer to saved official parses and compare with the archived table."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bench.score_task import score_run  # noqa: E402

RUNS = [
    ROOT / "analysis" / "heldout-20261003T000045" / "results.jsonl",
    ROOT / "analysis" / "heldout-20261003T001321" / "results.jsonl",
]


def main() -> None:
    mismatches = []
    checked = 0
    for path in RUNS:
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row["type"] not in {"GEN", "MOD"} or not row.get("engine_run"):
                continue
            task = ROOT / "bench" / "tasks" / "t4_maritime_isr" / "heldout" / row["task_id"]
            scored = score_run(ROOT / "mvp" / "runs" / row["engine_run"], task / "gold" / "assertions.yaml")
            checked += 1
            if scored["status"] != row["status"] or scored.get("engineering_status") != row.get("engineering_status"):
                mismatches.append({"task_id": row["task_id"], "configuration": row["configuration"],
                                   "repeat": row["repeat"], "archived": row["status"], "rescored": scored["status"]})
    print(json.dumps({"checked": checked, "mismatches": mismatches}, ensure_ascii=False, indent=2))
    if mismatches:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
