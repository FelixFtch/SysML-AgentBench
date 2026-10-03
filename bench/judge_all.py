"""Second model, qwen3.8-max, judges every saved held-out answer.

The verdict does not change the archived score.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.llm import chat, extract_json  # noqa: E402
from bench.experiment import load_env  # noqa: E402

SYSTEM = """You judge whether an answer meets the task.
Reply with one JSON object and no prose: {"overall":"pass|fail","reason":"..."}
Use fail when required content is missing, a name or number is wrong, or a stated budget is exceeded.
"""
RUNS = [
    ROOT / "analysis" / "heldout-20261003T000045" / "results.jsonl",
    ROOT / "analysis" / "heldout-20261003T001321" / "results.jsonl",
]
OUT = ROOT / "analysis" / "validator-all-max.jsonl"


def _submission(row: dict) -> str:
    if row.get("engine_run"):
        model = ROOT / "mvp" / "runs" / row["engine_run"] / "model"
        files = list(model.glob("*.sysml")) if model.is_dir() else []
        if files:
            return files[0].read_text(encoding="utf-8")
    folders = sorted((ROOT / "mvp" / "agent-runs").glob(f"20261003T00*-{row['configuration']}-{row['task_id']}"))
    folders = [folder for folder in folders if (folder / "response.txt").is_file()]
    index = row["repeat"] - 1
    if 0 <= index < len(folders):
        return (folders[index] / "response.txt").read_text(encoding="utf-8")
    return ""


def main() -> None:
    load_env()
    rows = []
    for path in RUNS:
        rows.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines())
    done = set()
    if OUT.is_file():
        for line in OUT.read_text(encoding="utf-8").splitlines():
            item = json.loads(line)
            done.add((item["task_id"], item["configuration"], item["repeat"]))
    with OUT.open("a", encoding="utf-8") as handle:
        for row in rows:
            key = (row["task_id"], row["configuration"], row["repeat"])
            if key in done:
                continue
            requirements = (ROOT / "bench" / "tasks" / "t4_maritime_isr" / "heldout" / row["task_id"] / "input" / "requirements.md").read_text(encoding="utf-8")
            completed = chat([
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"Task:\n{requirements}\n\nSubmission:\n{_submission(row)[:8000]}"},
            ], max_tokens=200, temperature=0)
            try:
                verdict = str(extract_json(completed["text"]).get("overall", "")).lower()
            except (ValueError, json.JSONDecodeError):
                verdict = ""
            tool_fail = row["status"] == "FAIL"
            record = {"task_id": row["task_id"], "configuration": row["configuration"], "repeat": row["repeat"],
                      "tool_status": row["status"], "validator_overall": verdict or "unparsed",
                      "judge_model": completed["model"],
                      "agree": tool_fail == (verdict == "fail") if verdict in {"pass", "fail"} else False,
                      "false_pass": bool(tool_fail and verdict == "pass")}
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            handle.flush()
            print(f"{row['repeat']} {row['task_id']} {row['configuration']} tool={row['status']} judge={verdict}", flush=True)
    items = [json.loads(line) for line in OUT.read_text(encoding="utf-8").splitlines()]
    agreed = sum(item["agree"] for item in items)
    print(json.dumps({"cells": len(items), "agree": agreed,
                      "agreement_rate": round(agreed / len(items), 3) if items else None,
                      "false_pass": sum(item["false_pass"] for item in items)}))


if __name__ == "__main__":
    main()
