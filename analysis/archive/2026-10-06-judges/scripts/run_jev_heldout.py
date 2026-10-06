"""Ask Jev whether each archived flash answer passes its gold. Does not change tool scores.

The question does not include the tool's PASS/FAIL. MOD-05's twelve files are identical;
this run still sends every cell so the page can show that.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELD = ROOT / "bench" / "tasks" / "t4_maritime_isr" / "heldout"
RUNS = ROOT / "mvp" / "runs"
AGENTS = ROOT / "mvp" / "agent-runs"
API = "https://api.typesafe.ai/v1/systemone"
OUT = ROOT / "analysis" / "jev-heldout-20261003.json"


def key() -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("TYPESAFE_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("TYPESAFE_API_KEY missing")


def flash_rows() -> list[dict]:
    rows = []
    for path in sorted((ROOT / "analysis").glob("heldout-*/results.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    rows.sort(key=lambda row: (row["task_id"], row["configuration"], row["repeat"]))
    return rows


def gold_text(task_id: str) -> str:
    folder = HELD / task_id / "gold"
    parts = []
    for path in sorted(folder.iterdir()):
        if path.is_file() and path.suffix in {".yaml", ".yml", ".json"}:
            parts.append(path.read_text(encoding="utf-8", errors="replace")[:2200])
    return "\n".join(parts)


def answers_for(task_id: str, config: str) -> list[str]:
    texts = []
    for path in sorted(AGENTS.glob(f"*-{config}-{task_id}")):
        answer = path / "response.txt"
        if answer.is_file():
            texts.append(answer.read_text(encoding="utf-8", errors="replace")[:3500])
    return texts


def candidate(row: dict, cache: dict) -> str:
    run_id = row.get("engine_run")
    if run_id:
        folder = RUNS / run_id / "model"
        files = sorted(folder.glob("*.sysml")) if folder.is_dir() else []
        if files:
            return files[0].read_text(encoding="utf-8", errors="replace")[:3500]
    key = (row["task_id"], row["configuration"])
    if key not in cache:
        cache[key] = answers_for(*key)
    group = cache[key]
    index = int(row["repeat"]) - 1
    if 0 <= index < len(group):
        return group[index]
    return ""


def ask(state: str, questions: dict, token: str) -> dict:
    body = json.dumps({"state": state, "model": "jev-latest", "questions": questions}).encode()
    request = urllib.request.Request(
        API, data=body, method="POST",
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
    )
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as exc:
            detail = exc.read(300).decode("utf-8", "replace")
            if attempt == 3 or exc.code not in {429, 500, 502, 503}:
                raise SystemExit(f"http {exc.code} {detail[:180]}")
            time.sleep(2 * (attempt + 1))
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))
    return {}


def main() -> None:
    token = key()
    rows = flash_rows()
    cache: dict = {}
    state = (
        "Synthetic exam grading. Decide only from the grading standard and the candidate in each question. "
        "The tool's PASS/FAIL is not provided. "
        "A submission passes only when it satisfies the standard. "
        "If the standard says a power total above the stated limit must fail, preserving every number is not a pass. "
        "A syntax failure is not a pass. Missing required names, connections, phrases, or a wrong JSON value is not a pass."
    )
    cells = []
    usage = {"input_tokens": 0, "output_tokens": 0}
    batch = 8
    prepared = []
    for index, row in enumerate(rows):
        text = candidate(row, cache)
        prepared.append((index, row, text))
    for start in range(0, len(prepared), batch):
        chunk = prepared[start:start + batch]
        questions = {}
        for index, row, text in chunk:
            questions[f"c{index}"] = {
                "type": "noul",
                "instructions": (
                    f"Task {row['task_id']} configuration {row['configuration']} repeat {row['repeat']}.\n"
                    f"Grading standard:\n{gold_text(row['task_id'])}\n"
                    f"Candidate:\n{text or '(empty)'}\n"
                    "Is the overall grade PASS?"
                ),
            }
        data = ask(state, questions, token)
        usage["input_tokens"] += (data.get("usage") or {}).get("input_tokens") or 0
        usage["output_tokens"] += (data.get("usage") or {}).get("output_tokens") or 0
        answers = data.get("answers") or {}
        for index, row, text in chunk:
            noul = (answers.get(f"c{index}") or {}).get("noul")
            jev_pass = isinstance(noul, (int, float)) and noul >= 0.5
            tool_pass = row["status"] == "PASS"
            cells.append({
                "task_id": row["task_id"],
                "configuration": row["configuration"],
                "repeat": row["repeat"],
                "tool": row["status"],
                "jev_p_pass": noul,
                "jev_pass": jev_pass,
                "agree": jev_pass == tool_pass,
                "false_pass": jev_pass and not tool_pass,
                "empty": not text,
            })
        print(f"{start + len(chunk)}/{len(prepared)}", flush=True)
    agree = sum(item["agree"] for item in cells)
    false_pass = sum(item["false_pass"] for item in cells)
    summary = {
        "cells": len(cells),
        "agree": agree,
        "false_pass": false_pass,
        "empty": sum(item["empty"] for item in cells),
        "model": "jev-1.13.0",
        "usage": usage,
        "note": "同一问法：相对评分标准，总评是不是通过。不含工具原判。MOD-05 的 12 份文件内容相同。",
    }
    OUT.write_text(json.dumps({"summary": summary, "cells": cells}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
