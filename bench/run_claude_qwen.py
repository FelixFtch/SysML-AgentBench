"""Run the held-out tasks through Claude Code via claude-code-router (CCR) in the sandbox. Configuration name: P-CODE-2.

    python3 bench/run_claude_qwen.py --model qwen3.8-flash --repeats 3 --workers 3 [--tasks GEN-01 ...] [--max-turns 60]

Same workspace, rules file, ./validate and prompt as OpenCode (agents/external/jail.py, decision 026). Claude Code
gets the tools OpenCode has (Bash, Read, Write, Edit, Glob, Grep) pre-approved; without them every Bash and Write
call is denied in -p mode, which is what happened in the first 2026-10-06 batch. The answer is answer.md if the
agent wrote one, else its final message. Usage comes from the JSON result; CCR's usage log records the upstream model.
Output: analysis/claude-jail-<model>-<stamp>/results.jsonl plus <task>-r<repeat>.json per run.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.external.jail import PROMPT_SUFFIX, fake_home, prepare_workspace, wrap  # noqa: E402
from bench.experiment import load_env, validate_and_grade  # noqa: E402

HELD = ROOT / "bench" / "tasks" / "t4_maritime_isr" / "heldout"
TOOLS = ["Bash", "Read", "Write", "Edit", "Glob", "Grep"]
LOCK = threading.Lock()


def usage_of(result: dict) -> dict:
    usage = result.get("usage") or {}
    cached = usage.get("cache_read_input_tokens") or 0
    return {"input": (usage.get("input_tokens") or 0) + cached + (usage.get("cache_creation_input_tokens") or 0),
            "cached": cached, "cache_write": usage.get("cache_creation_input_tokens") or 0,
            "output": usage.get("output_tokens") or 0, "turns": result.get("num_turns"),
            "duration_ms": result.get("duration_ms"), "model_usage": result.get("modelUsage")}


def claude_argv(model: str, *, max_turns: int, tools: list[str]) -> list[str]:
    """The Claude Code command for one model name, without the prompt.

    CLAUDE_CODE_MODEL in .env ("provider,model") wins for cloud names: "anthropic,<model>" runs `claude` itself on
    Claude Code's own login; any other provider goes through claude-code-router (`ccr`), whose provider page holds the
    key. Without it, the routes our runs used: the router's provider "qwen" for the cloud Qwen names, and its provider
    "ollama" for a local name ("<tag> (Ollama)", agents/llm_local.local_tag)."""
    from agents.llm_local import local_tag
    base = ["-p", "--output-format", "json", "--max-turns", str(max_turns), "--allowedTools", *tools]
    tag = local_tag(model)
    own = os.environ.get("CLAUDE_CODE_MODEL", "").strip()
    if own and tag is None:
        provider, _, name = own.partition(",")
        if provider.strip().lower() == "anthropic" and name.strip():
            return ["claude", *base, "--model", name.strip()]
        return ["ccr", "default-claude-code", "--", *base, "--model", own]
    return ["ccr", "default-claude-code", "--", *base, "--model", f"ollama,{tag}" if tag else f"qwen,{model}"]


def run_claude(task_dir: Path, *, model: str, max_turns: int, timeout: int, label: str = "P-CODE-2") -> dict:
    """One Claude Code session on one task folder (input/requirements.md is the prompt), inside the sandbox.
    Returns the answer text (answer.md, else the final message), the parsed JSON result and the run folder."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    work = ROOT / "mvp" / "agent-runs" / f"{stamp}-{uuid.uuid4().hex[:4]}-{label}-{task_dir.name}"
    workspace = work / "workspace"
    workspace.mkdir(parents=True)
    prepare_workspace(task_dir, workspace)
    prompt = (workspace / "input" / "requirements.md").read_text(encoding="utf-8") + PROMPT_SUFFIX
    command = [*claude_argv(model, max_turns=max_turns, tools=TOOLS), prompt]
    home = fake_home(work.name)
    try:
        completed = subprocess.run(wrap(command, workspace, home), cwd=workspace, text=True, capture_output=True, timeout=timeout)
        stdout, stderr, returncode = completed.stdout, completed.stderr, completed.returncode
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr, returncode = f"timeout after {timeout}s", "timeout"
    finally:
        shutil.rmtree(home, ignore_errors=True)
    (work / "stdout.json").write_text(stdout, encoding="utf-8")
    (work / "stderr.txt").write_text(stderr, encoding="utf-8")
    try:
        result = json.loads(stdout)
    except json.JSONDecodeError:
        result = {"result": stdout, "is_error": True}
    answer = workspace / "answer.md"
    text = answer.read_text(encoding="utf-8") if answer.is_file() else (result.get("result") or "")
    return {"text": text, "result": result, "work": work, "workspace": workspace, "answer_file": answer.is_file(),
            "returncode": returncode}


def one(item: dict, repeat: int, args, out: Path) -> None:
    task_dir = ROOT / item["path"]
    record = {"repeat": repeat, "task_id": item["id"], "type": item["type"], "configuration": "P-CODE-2",
              "cohort_id": "claude", "provider_model": args.model, "jailed": True, "max_turns": args.max_turns}
    try:
        run = run_claude(task_dir, model=args.model, max_turns=args.max_turns, timeout=args.timeout)
        result = run["result"]
        (out / f"{item['id']}-r{repeat}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)[:200000], encoding="utf-8")
        scored = validate_and_grade(task_dir, run["text"], label=f"claude-{item['id']}", workspace=run["work"] / "graded")
        record.update({"status": scored["status"], "sysml_status": scored.get("sysml_status"),
                       "engineering_status": scored.get("engineering_status"), "engine_run": scored.get("engine_run"),
                       "reason": scored.get("reason"), "usage": usage_of(result), "is_error": result.get("is_error"),
                       "stop_reason": result.get("stop_reason"), "denials": len(result.get("permission_denials") or []),
                       "answer_file": run["answer_file"], "returncode": run["returncode"], "workspace": str(run["workspace"])})
        if item["type"] == "ALN":
            record.update({"precision": scored.get("precision"), "recall": scored.get("recall")})
    except Exception as exc:
        record.update({"status": "FAIL", "error": f"{type(exc).__name__}: {exc}", "trace": traceback.format_exc()[-1200:]})
    with LOCK:
        with (out / "results.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({key: value for key, value in record.items() if key != "trace"}, ensure_ascii=False) + "\n")
        usage = record.get("usage") or {}
        print(f"r{repeat} {item['id']} {record['status']} {usage.get('input', '?')} in / {usage.get('output', '?')} out", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="qwen3.8-flash")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--repeat-offset", type=int, default=0)
    parser.add_argument("--tasks", nargs="*", default=[])
    parser.add_argument("--max-turns", type=int, default=60)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--resume", default="", help="an existing output folder: runs already in its results.jsonl are skipped")
    parser.add_argument("--name", default="claude-jail", help="output folder prefix: analysis/<name>-<model>-<stamp>")
    parser.add_argument("--note", default="", help="stored in summary.json")
    args = parser.parse_args()
    load_env()
    tasks = [json.loads(line) for line in (HELD / "index.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.tasks:
        tasks = [item for item in tasks if item["id"] in args.tasks]
    done: set[tuple[str, int]] = set()
    if args.resume:
        out = Path(args.resume)
        if (out / "results.jsonl").is_file():
            done = {(row["task_id"], int(row["repeat"])) for row in map(json.loads, (out / "results.jsonl").read_text(encoding="utf-8").splitlines()) if row}
        summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
        summary.setdefault("resumed", []).append({"at": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S"),
                                                  "kept_rows": len(done), "workers": args.workers})
        (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        out = ROOT / "analysis" / f"{args.name}-{args.model}-{stamp}"
        out.mkdir(parents=True)
        (out / "summary.json").write_text(json.dumps({"cohort": "claude", "model": args.model, "jailed": True, "tools": TOOLS,
                                                      "max_turns": args.max_turns, "timeout_s": args.timeout, "repeats": args.repeats,
                                                      "tasks": args.tasks or "all", "workers": args.workers, "started": stamp,
                                                      **({"note": args.note} if args.note else {})}, indent=2), encoding="utf-8")
    jobs = [(item, repeat) for repeat in range(1 + args.repeat_offset, 1 + args.repeat_offset + args.repeats) for item in tasks
            if (item["id"], repeat) not in done]
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        for item, repeat in jobs:
            pool.submit(one, item, repeat, args, out)
    print(out)


if __name__ == "__main__":
    main()
