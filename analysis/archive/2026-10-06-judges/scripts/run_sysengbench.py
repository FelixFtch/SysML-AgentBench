"""Score the question IDs already listed in analysis/sysengbench-ids.txt.

The ID file is the subset. This script does not choose extra questions.
Jev picks A–D. The dataset answer is used only after Jev responds.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IDS = ROOT / "analysis" / "sysengbench-ids.txt"
OUT = ROOT / "analysis" / "sysengbench-jev.json"
API = "https://api.typesafe.ai/v1/systemone"
ROWS = "https://datasets-server.huggingface.co/rows"


def key() -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("TYPESAFE_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("TYPESAFE_API_KEY missing")


def wanted() -> list[int]:
    return [int(line.strip()) for line in IDS.read_text(encoding="utf-8").splitlines() if line.strip()]


def fetch_rows(count: int) -> list[dict]:
    query = urllib.parse.urlencode({
        "dataset": "rabell/SysEngBench",
        "config": "default",
        "split": "test",
        "offset": 0,
        "length": count,
    })
    with urllib.request.urlopen(ROWS + "?" + query, timeout=60) as response:
        payload = json.loads(response.read())
    return [item["row"] for item in payload["rows"]]


def ask(questions: dict, token: str) -> dict:
    body = json.dumps({
        "state": "Multiple-choice systems engineering quiz. Pick the best option. Do not explain.",
        "model": "jev-latest",
        "questions": questions,
    }).encode()
    request = urllib.request.Request(
        API, data=body, method="POST",
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.loads(response.read())


def main() -> None:
    ids = wanted()
    rows = {row["Question ID"]: row for row in fetch_rows(max(ids))}
    missing = [item for item in ids if item not in rows]
    if missing:
        raise SystemExit(f"missing ids {missing}")
    questions = {}
    for item in ids:
        row = rows[item]
        questions[f"q{item}"] = {
            "type": "choice",
            "instructions": row["question"],
            "criteria": {
                "A": row["choiceA"],
                "B": row["choiceB"],
                "C": row["choiceC"],
                "D": row["choiceD"],
            },
        }
    data = ask(questions, key())
    answers = data.get("answers") or {}
    graded = []
    for item in ids:
        picked = (answers.get(f"q{item}") or {}).get("choice")
        gold = rows[item]["answer"]
        graded.append({"id": item, "jev": picked, "gold": gold, "correct": picked == gold})
    payload = {
        "ids": ids,
        "n": len(graded),
        "correct": sum(item["correct"] for item in graded),
        "model": data.get("model"),
        "usage": data.get("usage"),
        "rows": graded,
        "note": "题号先写在 sysengbench-ids.txt。这是选择题，不并进海事主表。",
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: payload[k] for k in ("n", "correct", "model", "usage")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
