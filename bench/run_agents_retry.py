"""Retry the tasks that failed anywhere with an agent on qwen3.8-max and relaxed limits (decision 029).

    python3 bench/run_agents_retry.py --agent opencode --repeats 3 --workers 2
    python3 bench/run_agents_retry.py --agent claude --repeats 3 --workers 2

Same sandbox, workspace, rules file and prompt as the scored agent batches (agents/external/jail.py, decision 026),
with the limits the user chose on 2026-10-06:
- ./validate may be called at most 50 times in a run; each call prints "call n of at most 50", later calls are refused;
- a run may take 60 minutes (scored batches: 15) and Claude Code 200 turns (scored batches: 60);
- a run ends as soon as its answer passes the scorer. The answer is answer.md; until the agent writes one, it is the
  newest .sysml file the agent wrote that declares the task's package (GEN, MOD, ALN). The file is scored from outside
  the sandbox each time it changes, so the agent never sees the key; a run that ends this way is a PASS with that
  answer, and `scored_from` says which file it was.
Tasks: every task with a failing cell in one of the four scored batches (bench/batches.py), unless --tasks is given.
Claude Code reports its usage only when a run ends (through CCR the per-message usage in stream-json is 0), so a run
that is stopped has no usage of its own; bench/summarize_retry.py takes the Claude Code batch total from CCR's request
log instead. --resume lists the runs that were cut off when the batch was stopped (`interrupted` in summary.json).
Output: analysis/retry-<agent>-<model>-<stamp>/results.jsonl and summary.json. Not part of the frozen scores.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import traceback
import uuid
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.external.jail import PROMPT_SUFFIX, TOOLCHAIN, VALIDATE, fake_home, prepare_workspace, wrap  # noqa: E402
from agents.external.opencode_run import BINARY, _base_url  # noqa: E402
from bench.batches import COHORTS, rows  # noqa: E402
from bench.experiment import load_env, validate_and_grade  # noqa: E402
from bench.run_claude_qwen import TOOLS, usage_of  # noqa: E402
from bench.run_opencode import usage_from_log  # noqa: E402

HELD = ROOT / "bench" / "tasks" / "t4_maritime_isr" / "heldout"
LOCK = threading.Lock()
# One scorer JVM at a time next to the agents' own validator runs: the machine has little free memory and no swap.
SCORING = threading.BoundedSemaphore(1)
ANCHOR = "package, files = sys.argv[1], sys.argv[2:]\n"
CAP = r'''ledger = Path(__file__).resolve().with_name(".validate-calls")
used = len(ledger.read_text().splitlines()) if ledger.is_file() else 0
if used >= @LIMIT@:
    sys.exit(f"./validate: limit reached ({used} of at most @LIMIT@ calls in this task); no more validation")
with ledger.open("a") as handle:
    handle.write(" ".join(sys.argv[1:]) + "\n")
print(f"./validate call {used + 1} of at most @LIMIT@", file=sys.stderr, flush=True)
'''


def capped_validate(limit: int) -> str:
    """The scored batches' ./validate (scorer's file order) with a call ledger in front of it."""
    if ANCHOR not in VALIDATE:
        raise RuntimeError("agents/external/jail.py changed: ./validate has no argument line to put the cap before")
    return VALIDATE.replace(ANCHOR, CAP.replace("@LIMIT@", str(limit)) + ANCHOR).replace("@VALIDATOR@", str(TOOLCHAIN / "validate.py"))


def failed_cells() -> dict[str, dict[str, int]]:
    """Failing cells per task and candidate in the four scored batches."""
    found: dict[str, Counter] = defaultdict(Counter)
    for cohort in COHORTS:
        for row in rows(cohort):
            if row["status"] != "PASS":
                found[row["task_id"]][cohort] += 1
    return {task: dict(counts) for task, counts in sorted(found.items())}


def opencode_argv(workspace: Path, model: str, prompt: str) -> list[str]:
    config = {"model": f"qwen/{model}",
              "provider": {"qwen": {"npm": "@ai-sdk/openai-compatible",
                                    "options": {"baseURL": _base_url(), "apiKey": "{env:MVP_LLM_API_KEY}"},
                                    "models": {model: {"name": model}}}}}
    (workspace / "opencode.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    return [str(BINARY), "run", "--pure", "--auto", "--format", "json", "--dir", str(workspace), "--model", f"qwen/{model}", prompt]


def claude_argv(model: str, max_turns: int, prompt: str) -> list[str]:
    return ["ccr", "default-claude-code", "--", "-p", "--output-format", "stream-json", "--verbose",
            "--max-turns", str(max_turns), "--allowedTools", *TOOLS, "--model", f"qwen,{model}", prompt]


def claude_result(path: Path) -> dict:
    """The final result event of a stream-json log; {} when the run was stopped before Claude Code wrote it."""
    result = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "result":
            result = event
    return result


def newest_model(workspace: Path, package: str, since: float) -> Path | None:
    """The newest .sysml file written during the run (not under validation/) that declares `package`."""
    declares = re.compile(r"\bpackage\s+" + re.escape(package) + r"\b")
    found = [path for path in workspace.rglob("*.sysml")
             if "validation" not in path.relative_to(workspace).parts and path.stat().st_mtime >= since
             and declares.search(path.read_text(encoding="utf-8", errors="replace"))]
    return max(found, key=lambda path: path.stat().st_mtime) if found else None


def supervise(argv: list[str], workspace: Path, work: Path, task_dir: Path, *, package: str | None, timeout: int, poll: int,
              label: str) -> dict:
    """Run the sandboxed agent; score its answer from outside whenever it changes and stop the agent on a PASS."""
    answer, checks, seen, passed = workspace / "answer.md", [], None, None
    started, wall = time.monotonic(), time.time()
    with (work / "stdout.jsonl").open("w", encoding="utf-8") as out, (work / "stderr.txt").open("w", encoding="utf-8") as err:
        process = subprocess.Popen(argv, cwd=workspace, env=os.environ.copy(), stdout=out, stderr=err, text=True)
        while True:
            try:
                returncode = process.wait(timeout=poll)
                break
            except subprocess.TimeoutExpired:
                pass
            if time.monotonic() - started > timeout:
                process.kill()
                process.wait()
                returncode = "timeout"
                break
            target, source = (answer, "answer.md") if answer.is_file() else (newest_model(workspace, package, wall) if package else None, "workspace model")
            if not target:
                continue
            stat = target.stat()
            # Only a file that has not changed for 5 s is scored, so a half-written answer is not read.
            if (str(target), stat.st_mtime_ns, stat.st_size) == seen or time.time() - stat.st_mtime < 5:
                continue
            seen = (str(target), stat.st_mtime_ns, stat.st_size)
            text = target.read_text(encoding="utf-8", errors="replace")
            if source == "workspace model":
                text = f"```sysml\n{text}\n```\n"
            with SCORING:
                scored = validate_and_grade(task_dir, text, label=label, workspace=work / f"check-{len(checks) + 1}")
            checks.append({"at_s": round(time.monotonic() - started), "file": str(target.relative_to(workspace)), "status": scored["status"]})
            if scored["status"] == "PASS":
                process.kill()
                process.wait()
                returncode, passed = "stopped-on-pass", (text, scored, source)
                break
    return {"returncode": returncode, "checks": checks, "passed": passed, "elapsed_s": round(time.monotonic() - started)}


def interrupted(agent: str, out: Path, started: str) -> list[dict]:
    """Run folders of this batch without a result row, i.e. cut off when the batch was stopped, with their tokens."""
    results = out / "results.jsonl"
    kept = {json.loads(line).get("workspace") for line in results.read_text(encoding="utf-8").splitlines() if line.strip()} if results.is_file() else set()
    found = []
    for work in sorted((ROOT / "mvp" / "agent-runs").glob(f"*-retry-{agent}-*")):
        log = work / "stdout.jsonl"
        if work.name[:15] < started or str(work / "workspace") in kept or not log.is_file():
            continue
        usage = usage_from_log(log) if agent == "opencode" else (usage_of(claude_result(log)) if claude_result(log) else {})
        found.append({"task_id": work.name.split(f"-retry-{agent}-", 1)[1], "work": str(work.relative_to(ROOT)), "usage": usage,
                      "usage_reported": bool(usage)})
    return found


def one(item: dict, repeat: int, args, out: Path) -> None:
    task_dir = ROOT / item["path"]
    agent = args.agent
    record = {"repeat": repeat, "task_id": item["id"], "type": item["type"],
              "configuration": "P-CODE" if agent == "opencode" else "P-CODE-2", "cohort_id": f"retry-{agent}",
              "provider_model": args.model, "jailed": True, "validate_limit": args.validate_limit, "timeout_s": args.timeout,
              **({"max_turns": args.max_turns} if agent == "claude" else {})}
    home = None
    try:
        case = yaml.safe_load((task_dir / "case.yaml").read_text(encoding="utf-8"))
        package = case.get("package") if case["type"] in {"GEN", "MOD", "ALN"} else None
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        work = ROOT / "mvp" / "agent-runs" / f"{stamp}-{uuid.uuid4().hex[:4]}-retry-{agent}-{item['id']}"
        workspace = work / "workspace"
        workspace.mkdir(parents=True)
        prepare_workspace(task_dir, workspace)
        script = workspace / "validate"
        script.write_text(capped_validate(args.validate_limit), encoding="utf-8")
        script.chmod(0o755)
        prompt = (workspace / "input" / "requirements.md").read_text(encoding="utf-8") + PROMPT_SUFFIX
        argv = opencode_argv(workspace, args.model, prompt) if agent == "opencode" else claude_argv(args.model, args.max_turns, prompt)
        home = fake_home(work.name)
        label = f"retry-{agent}-{item['id']}"
        run = supervise(wrap(argv, workspace, home), workspace, work, task_dir, package=package, timeout=args.timeout,
                        poll=args.poll, label=label)
        answer, log = workspace / "answer.md", work / "stdout.jsonl"
        final: dict = {}
        if agent == "opencode":
            usage = usage_from_log(log)
            fallback = log.read_text(encoding="utf-8", errors="replace")
        else:
            final = claude_result(log)
            usage = usage_of(final) if final else {}
            fallback = final.get("result") or ""
            (out / f"{item['id']}-r{repeat}.json").write_text(json.dumps(final, ensure_ascii=False, indent=2)[:200000], encoding="utf-8")
        if run["passed"]:
            text, scored, scored_from = run["passed"]
        else:
            scored_from = "answer.md" if answer.is_file() else ("stdout" if agent == "opencode" else "final message")
            text = answer.read_text(encoding="utf-8", errors="replace") if answer.is_file() else fallback
            with SCORING:
                scored = validate_and_grade(task_dir, text, label=label, workspace=work / "graded")
        ledger = workspace / ".validate-calls"
        record.update({"status": scored["status"], "sysml_status": scored.get("sysml_status"),
                       "engineering_status": scored.get("engineering_status"), "engine_run": scored.get("engine_run"),
                       "reason": scored.get("reason"), "usage": usage, **({"usage_reported": bool(usage)} if agent == "claude" else {}),
                       "returncode": run["returncode"],
                       "stopped_on_pass": bool(run["passed"]), "scored_from": scored_from, "elapsed_s": run["elapsed_s"],
                       "checks": run["checks"],
                       "validate_calls": len(ledger.read_text(encoding="utf-8").splitlines()) if ledger.is_file() else 0,
                       "answer_file": answer.is_file(), "workspace": str(workspace)})
        if final:
            record.update({"is_error": final.get("is_error"), "stop_reason": final.get("stop_reason"),
                           "denials": len(final.get("permission_denials") or [])})
        if item["type"] == "ALN":
            record.update({"precision": scored.get("precision"), "recall": scored.get("recall")})
    except Exception as exc:
        record.update({"status": "FAIL", "error": f"{type(exc).__name__}: {exc}", "trace": traceback.format_exc()[-1500:]})
    finally:
        if home:
            shutil.rmtree(home, ignore_errors=True)
    with LOCK:
        with (out / "results.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({key: value for key, value in record.items() if key != "trace"}, ensure_ascii=False) + "\n")
        usage = record.get("usage") or {}
        print(f"r{repeat} {item['id']} {record['status']} {record.get('returncode', '')} {record.get('elapsed_s', '?')} s "
              f"{record.get('validate_calls', '?')} validate · {usage.get('input', '?')} in / {usage.get('output', '?')} out"
              f"{' · ' + record['error'] if record.get('error') else ''}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--agent", choices=["opencode", "claude"], required=True)
    parser.add_argument("--model", default="qwen3.8-max")
    parser.add_argument("--tasks", nargs="*", default=[], help="default: every task with a failing cell in the scored batches")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--validate-limit", type=int, default=50)
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument("--max-turns", type=int, default=200)
    parser.add_argument("--poll", type=int, default=15, help="seconds between checks of answer.md")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--resume", default="", help="an existing output folder: runs already in its results.jsonl are skipped")
    parser.add_argument("--name", default="retry", help="output folder prefix: analysis/<name>-<agent>-<model>-<stamp>")
    parser.add_argument("--note", default="", help="stored in summary.json")
    args = parser.parse_args()
    load_env()
    failed = failed_cells()
    wanted = args.tasks or list(failed)
    tasks = [json.loads(line) for line in (HELD / "index.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    tasks = [item for item in tasks if item["id"] in wanted]
    done: set[tuple[str, int]] = set()
    if args.resume:
        out = Path(args.resume)
        if (out / "results.jsonl").is_file():
            done = {(row["task_id"], int(row["repeat"])) for row in map(json.loads, (out / "results.jsonl").read_text(encoding="utf-8").splitlines()) if row}
        summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
        cut = [item for item in interrupted(args.agent, out, summary["started"])
               if item["work"] not in {known["work"] for known in summary.get("interrupted", [])}]
        summary.setdefault("interrupted", []).extend(cut)
        summary.setdefault("resumed", []).append({"at": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S"), "kept_rows": len(done),
                                                  "interrupted_runs": len(cut), "workers": args.workers,
                                                  **({"note": args.note} if args.note else {})})
        (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        out = ROOT / "analysis" / f"{args.name}-{args.agent}-{args.model}-{stamp}"
        out.mkdir(parents=True)
        summary = {"cohort": f"retry-{args.agent}", "agent": args.agent, "model": args.model, "jailed": True,
                   "validate_limit": args.validate_limit, "timeout_s": args.timeout, "stop_on_pass": True, "poll_s": args.poll,
                   **({"version": "1.18.27"} if args.agent == "opencode" else {"tools": TOOLS, "max_turns": args.max_turns}),
                   "repeats": args.repeats, "tasks": [item["id"] for item in tasks],
                   "failed_cells": {task: failed[task] for task in wanted if task in failed},
                   "workers": args.workers, "started": stamp, **({"note": args.note} if args.note else {})}
        (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    jobs = [(item, repeat) for repeat in range(1, 1 + args.repeats) for item in tasks if (item["id"], repeat) not in done]
    print(f"{out} · {len(jobs)} runs", flush=True)
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        for item, repeat in jobs:
            pool.submit(one, item, repeat, args, out)
    print(out)


if __name__ == "__main__":
    main()
