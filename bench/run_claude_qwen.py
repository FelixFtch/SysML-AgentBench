"""Run the held-out tasks through Claude Code via claude-code-router (CCR), model selectable, usage recorded.

`ccr default-claude-code -- -p --output-format json --model qwen,<model> ...` sends the prompt to the
Qwen provider configured in CCR. The JSON result carries `usage` and `modelUsage`, which are saved per
task; CCR's own usage log (~/.claude-code-router/app-data/usage.sqlite) records the upstream model.
Each task is one fresh session with its own working directory holding only the task input.

    python3 bench/run_claude_qwen.py --model qwen3.8-flash --repeats 3 [--tasks GEN-01 ...] [--max-turns 40]

Output: analysis/claude-<model>-<stamp>/results.jsonl plus <task>-r<repeat>.txt and .json per task.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bench.experiment import load_env, validate_and_grade  # noqa: E402

HELD = ROOT / "bench" / "tasks" / "t4_maritime_isr" / "heldout"


def _prompt(task_dir: Path) -> str:
    case = yaml.safe_load((task_dir / "case.yaml").read_text(encoding="utf-8"))
    text = (task_dir / "input" / "requirements.md").read_text(encoding="utf-8")
    extra = []
    baseline = task_dir / "input" / "baseline"
    if baseline.is_dir():
        for path in sorted(baseline.glob("*.sysml")):
            extra.append(f"Baseline {path.name}:\n```sysml\n{path.read_text(encoding='utf-8')}```")
    given = task_dir / "input" / "model.sysml"
    if given.is_file() and case["type"] in {"QRY", "RT"}:
        extra.append(f"Given model:\n```sysml\n{given.read_text(encoding='utf-8')}```")
    body = text if not extra else text + "\n\n" + "\n\n".join(extra)
    if case["type"] in {"GEN", "MOD"}:
        body += "\n\nReply with one fenced sysml block and no other text."
    elif case["type"] == "ALN":
        body += "\n\nReply with one fenced sysml block followed by one fenced json block, and no other text."
    return body


def usage_of(result: dict) -> dict:
    usage = result.get("usage") or {}
    return {"input": usage.get("input_tokens") or 0, "cached": usage.get("cache_read_input_tokens") or 0,
            "cache_write": usage.get("cache_creation_input_tokens") or 0, "output": usage.get("output_tokens") or 0,
            "turns": result.get("num_turns"), "duration_ms": result.get("duration_ms"),
            "model_usage": result.get("modelUsage")}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="qwen3.8-flash")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--repeat-offset", type=int, default=0)
    parser.add_argument("--tasks", nargs="*", default=[])
    parser.add_argument("--max-turns", type=int, default=40)
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    load_env()
    tasks = [json.loads(line) for line in (HELD / "index.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.tasks:
        tasks = [item for item in tasks if item["id"] in args.tasks]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    out = ROOT / "analysis" / f"claude-{args.model}-{stamp}"
    out.mkdir(parents=True)
    (out / "summary.json").write_text(json.dumps({"cohort": "claude", "model": args.model, "max_turns": args.max_turns,
                                                  "repeats": args.repeats, "started": stamp}, indent=2), encoding="utf-8")
    for repeat in range(1 + args.repeat_offset, 1 + args.repeat_offset + args.repeats):
        for item in tasks:
            task_dir = ROOT / item["path"]
            record = {"repeat": repeat, "task_id": item["id"], "type": item["type"], "configuration": "P-CODE-2",
                      "cohort_id": "claude", "provider_model": args.model}
            work = ROOT / "mvp" / "agent-runs" / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-P-CODE-2-{item['id']}"
            (work / "workspace").mkdir(parents=True)
            shutil.copytree(task_dir / "input", work / "workspace" / "input")
            try:
                command = ["ccr", "default-claude-code", "--", "-p", "--output-format", "json", "--max-turns", str(args.max_turns),
                           "--model", f"qwen,{args.model}", _prompt(task_dir)]
                completed = subprocess.run(command, cwd=work / "workspace", text=True, capture_output=True, timeout=args.timeout)
                (work / "stdout.json").write_text(completed.stdout, encoding="utf-8")
                (work / "stderr.txt").write_text(completed.stderr, encoding="utf-8")
                try:
                    result = json.loads(completed.stdout)
                except json.JSONDecodeError:
                    result = {"result": completed.stdout, "is_error": True}
                text = result.get("result") or ""
                (out / f"{item['id']}-r{repeat}.txt").write_text(text, encoding="utf-8")
                scored = validate_and_grade(task_dir, text, label=f"claude-{item['id']}", workspace=work)
                record.update({"status": scored["status"], "sysml_status": scored.get("sysml_status"),
                               "engineering_status": scored.get("engineering_status"), "engine_run": scored.get("engine_run"),
                               "reason": scored.get("reason"), "usage": usage_of(result), "is_error": result.get("is_error"),
                               "stop_reason": result.get("stop_reason"), "returncode": completed.returncode, "workspace": str(work)})
                if item["type"] == "ALN":
                    record.update({"precision": scored.get("precision"), "recall": scored.get("recall")})
                (out / f"{item['id']}-r{repeat}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)[:200000], encoding="utf-8")
            except subprocess.TimeoutExpired:
                record.update({"status": "FAIL", "error": f"timeout after {args.timeout}s", "workspace": str(work)})
            except Exception as exc:
                record.update({"status": "FAIL", "error": f"{type(exc).__name__}: {exc}", "trace": traceback.format_exc()[-1200:]})
            with (out / "results.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({key: value for key, value in record.items() if key != "trace"}, ensure_ascii=False) + "\n")
            print(f"r{repeat} {item['id']} {record['status']} {(record.get('usage') or {}).get('input', '?')} in / {(record.get('usage') or {}).get('output', '?')} out", flush=True)
    print(out)


if __name__ == "__main__":
    main()
