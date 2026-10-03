"""Apply the current scorer to every saved GEN/MOD answer of the 2026-10-03 cohorts.

The archived results files are not rewritten. Each line of the output holds the
archived status beside the status the current scorer gives the same official parse.

    python3 bench/rescore.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = ROOT / "analysis" / "rescore-20261003.jsonl"
HELD = ROOT / "bench" / "tasks" / "t4_maritime_isr" / "heldout"
COHORTS = {
    "flash": ["heldout-20261003T000045", "heldout-20261003T001321"],
    "opencode": ["opencode-20261003T001321"],
    "claude1": ["claude-qwen-20261003T014507"],
    "claude2": ["claude-qwen-20261003T034819"],
}
RULE = "题目通过 = 官方语法通过，必须存在的名字和连接都在，没有多写数字，必须保留的数没改，清单里的检查结果和标准答案预期一致。"
RULE_EN = ("A task passes when the official parse passes, every required name and connection is present, no number was invented, "
           "every value to keep is unchanged, and every engineering check comes out as the answer key expects.")


def _key(cohort_id: str, row: dict) -> tuple:
    return cohort_id, row["task_id"], row.get("configuration"), int(row.get("repeat") or 1)


def load() -> dict[tuple, dict]:
    if not OUT.is_file():
        return {}
    table = {}
    for line in OUT.read_text(encoding="utf-8").splitlines():
        if line.strip():
            item = json.loads(line)
            table[(item["cohort_id"], item["task_id"], item["configuration"], int(item["repeat"]))] = item
    return table


def apply(cohort_id: str, row: dict, table: dict[tuple, dict]) -> dict:
    """The row with the re-scored status; `archived_status` is kept when the two differ."""
    item = table.get(_key(cohort_id, row))
    if not item or item["status"] == row.get("status"):
        return row
    return {**row, "status": item["status"], "engineering_status": item["engineering_status"],
            "archived_status": row.get("status"), "rescore_note": item["note"]}


def _stamp(name: str) -> datetime:
    return datetime.strptime(name.rsplit("-", 1)[-1][:15], "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)


def _agent_run(label: str, start: datetime, end: datetime | None, index: dict) -> Path | None:
    found = [path for created, path in index.get(label, []) if created >= start and (end is None or created < end)]
    return found[-1] if found else None


def main() -> None:
    from bench.exam_board import RUNS_BY_LABEL, _attempt_paths
    from bench.score_task import score_run

    starts = {cohort: _stamp(folders[0]) for cohort, folders in COHORTS.items()}
    ends = {"flash": None, "opencode": None, "claude1": starts["claude2"], "claude2": None}
    lines = []
    for cohort_id, folders in COHORTS.items():
        for folder in folders:
            for raw in (ROOT / "analysis" / folder / "results.jsonl").read_text(encoding="utf-8").splitlines():
                if not raw.strip():
                    continue
                row = json.loads(raw)
                if row.get("type") not in {"GEN", "MOD"}:
                    continue
                task = row["task_id"]
                if cohort_id == "flash":
                    paths = _attempt_paths({**row, "cohort_id": "flash"})
                    run = paths[-1] if paths else None
                else:
                    label = f"P-CODE-{task}" if cohort_id == "opencode" else f"claude-{task}"
                    run = _agent_run(label, starts[cohort_id], ends[cohort_id], RUNS_BY_LABEL)
                item = {"cohort_id": cohort_id, "task_id": task, "type": row["type"],
                        "configuration": row.get("configuration"), "repeat": int(row.get("repeat") or 1),
                        "archived_status": row.get("status"), "run": run.name if run else None}
                if run is None or not (run / "sysml" / "validation.json").is_file():
                    item.update({"status": row.get("status"), "engineering_status": row.get("engineering_status"),
                                 "note": "没有找到官方运行目录，保留原判。"})
                else:
                    scored = score_run(run, HELD / task / "gold" / "assertions.yaml")
                    status = "PASS" if scored["status"] == "PASS" else "FAIL"
                    item.update({"status": status, "engineering_status": scored.get("engineering_status"),
                                 "sysml_status": scored.get("sysml_status"), "checks_match": scored.get("checks_match"),
                                 "must_exist": {key: scored["must_exist"][key] for key in ("hit", "expected")} if "must_exist" in scored else None,
                                 "must_preserve": scored.get("must_preserve"),
                                 "checks": [{key: check.get(key) for key in ("id", "expected", "actual", "match", "total_w", "limit_w")}
                                            for check in scored.get("checks") or []]})
                    if status == row.get("status"):
                        item["note"] = "和原判一致。"
                    elif scored.get("checks"):
                        item["note"] = "清单预期的检查结果和实际一致，必须保留的数都在：按题目判定通过。设计判定仍是 " + str(scored.get("engineering_status")) + "。"
                    else:
                        item["note"] = "按现行清单重算后结果不同。"
                item["changed"] = item["status"] != item["archived_status"]
                lines.append(item)
    OUT.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in lines), encoding="utf-8")
    changed = [item for item in lines if item["changed"]]
    print(json.dumps({"rule": RULE, "rows": len(lines), "changed": len(changed),
                      "without_run": sum(1 for item in lines if item["run"] is None),
                      "changes": [(item["cohort_id"], item["task_id"], item["configuration"], item["repeat"],
                                   item["archived_status"], item["status"]) for item in changed]},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
