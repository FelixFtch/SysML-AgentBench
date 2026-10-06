"""Compare the retry of the failed tasks (agent + qwen3.8-max, relaxed limits; bench/run_agents_retry.py, decision 029)
with the four scored batches on the same tasks. Reads saved files only; no model is called.

    python3 bench/summarize_retry.py

Output: analysis/retry-summary.json, which the results page reads. The retry is not part of the frozen scores.
Claude Code reports tokens only when a run ends, so runs stopped on a pass, at the time limit or by a batch restart
have none; its batch total is taken from CCR's request log (~/.claude-code-router/app-data/usage.sqlite) between the
batch start and its last result. Nothing else sent qwen3.8-max requests through CCR on 2026-10-06.
"""
from __future__ import annotations

import json
import sqlite3
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bench.batches import ANALYSIS, COHORTS, rows, usage_of_row  # noqa: E402
from bench.board_facts import _usd  # noqa: E402
from bench.classify_failures import classify  # noqa: E402

AGENTS = {"opencode": "OpenCode", "claude": "Claude Code"}
OUT = ANALYSIS / "retry-summary.json"
CCR_LOG = Path.home() / ".claude-code-router" / "app-data" / "usage.sqlite"


def ccr_usage(model: str, start: datetime, end: datetime) -> dict:
    """Requests CCR forwarded for `model` between start and end (UTC), as input (with cache), cached and output tokens."""
    if not CCR_LOG.is_file():
        return {}
    con = sqlite3.connect(f"file:{CCR_LOG}?mode=ro", uri=True)
    calls, fresh, output, cached, written = con.execute(
        "select count(*), coalesce(sum(input_tokens), 0), coalesce(sum(output_tokens), 0), coalesce(sum(cache_read_tokens), 0), "
        "coalesce(sum(cache_write_tokens), 0) from usage_events where model = ? and created_at >= ? and created_at <= ?",
        (model, start.strftime("%Y-%m-%dT%H:%M:%S"), end.strftime("%Y-%m-%dT%H:%M:%S.999Z"))).fetchone()
    con.close()
    return {"input": fresh + cached + written, "cached": cached, "output": output, "calls": calls,
            "window": [start.strftime("%Y-%m-%dT%H:%M:%SZ"), end.strftime("%Y-%m-%dT%H:%M:%SZ")]}


def retry_dir(agent: str) -> Path | None:
    found = sorted(path for path in ANALYSIS.glob(f"retry-{agent}-qwen3.8-max-*") if (path / "results.jsonl").is_file())
    return found[-1] if found else None


def _lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def summarize() -> dict:
    agents, tasks = {}, []
    for agent, label in AGENTS.items():
        folder = retry_dir(agent)
        if not folder:
            continue
        meta = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
        tasks = tasks or meta["tasks"]
        runs = sorted(_lines(folder / "results.jsonl"), key=lambda row: (row["task_id"], row["repeat"]))
        for row in runs:
            if row["status"] != "PASS":
                row["class"], row["detail"] = classify(row)
        reported = [row for row in runs if agent == "opencode" or (row.get("usage") or {}).get("model_usage")]
        usage = [usage_of_row(row) for row in reported] + [item["usage"] for item in meta.get("interrupted", []) if item.get("usage")]
        total = {key: sum(item.get(key) or 0 for item in usage) for key in ("input", "cached", "output")}
        source = "per run (OpenCode step events), including runs cut off by a restart"
        if agent == "claude":
            start = datetime.strptime(meta["started"], "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
            end = datetime.fromtimestamp((folder / "results.jsonl").stat().st_mtime, timezone.utc) + timedelta(seconds=60)
            logged = ccr_usage("qwen3.8-max", start, end)
            if logged:
                total, source = {key: logged[key] for key in ("input", "cached", "output")}, f"CCR request log, {logged['calls']} requests"
        elapsed = [row["elapsed_s"] for row in runs if row.get("elapsed_s") is not None]
        calls = [row.get("validate_calls") or 0 for row in runs]
        agents[agent] = {
            "label": f"{label} · qwen3.8-max", "folder": folder.name, "settings": {key: meta.get(key) for key in
                                                                                  ("validate_limit", "timeout_s", "max_turns", "stop_on_pass", "poll_s", "repeats", "workers")},
            "pass": sum(row["status"] == "PASS" for row in runs), "n": len(runs), "planned": len(meta["tasks"]) * meta["repeats"],
            "pass_from": {where: sum(row["status"] == "PASS" and (row.get("scored_from") or "answer.md") == where for row in runs)
                          for where in ("answer.md", "workspace model", "final message", "stdout")},
            "stopped_on_pass": sum(bool(row.get("stopped_on_pass")) for row in runs),
            "timeouts": sum(row.get("returncode") == "timeout" for row in runs),
            "errors": sum(bool(row.get("error")) for row in runs),
            "interrupted": len(meta.get("interrupted", [])),
            "validate_calls": {"max": max(calls, default=0), "median": statistics.median(calls) if calls else 0,
                               "at_limit": sum(call >= (meta.get("validate_limit") or 0) for call in calls)},
            "elapsed_s": {"median": statistics.median(elapsed) if elapsed else None, "max": max(elapsed, default=None)},
            "usage": total, "usage_source": source, "usd": round(_usd("qwen3.8-max", total), 4),
            "unreported_runs": len(runs) - len(reported),
            "runs": [{"task_id": row["task_id"], "repeat": row["repeat"], "status": row["status"],
                      "returncode": row.get("returncode"), "elapsed_s": row.get("elapsed_s"), "validate_calls": row.get("validate_calls"),
                      "stopped_on_pass": row.get("stopped_on_pass"), "scored_from": row.get("scored_from") or "answer.md",
                      "usd": round(_usd("qwen3.8-max", usage_of_row(row)), 4) if row in reported else None,
                      **({"class": row["class"], "detail": row["detail"]} if row["status"] != "PASS" else {})} for row in runs]}
    before = {cohort: {task: {"pass": 0, "n": 0} for task in tasks} for cohort in COHORTS}
    for cohort in COHORTS:
        for row in rows(cohort):
            if row["task_id"] in tasks:
                cell = before[cohort][row["task_id"]]
                cell["n"] += 1
                cell["pass"] += row["status"] == "PASS"
    per_task = []
    for task in tasks:
        entry = {"task_id": task, "before": {cohort: before[cohort][task] for cohort in COHORTS}}
        for agent, data in agents.items():
            mine = [run for run in data["runs"] if run["task_id"] == task]
            entry[agent] = {"pass": sum(run["status"] == "PASS" for run in mine), "n": len(mine),
                            "statuses": [run["status"] for run in mine]}
        per_task.append(entry)
    totals_before = {cohort: {"pass": sum(cell["pass"] for cell in before[cohort].values()),
                              "n": sum(cell["n"] for cell in before[cohort].values())} for cohort in COHORTS}
    return {"tasks": tasks, "agents": agents, "per_task": per_task, "before": totals_before,
            "cohort_labels": {cohort: spec["label"] for cohort, spec in COHORTS.items()}}


def main() -> None:
    summary = summarize()
    OUT.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for agent, data in summary["agents"].items():
        print(f"{data['label']}: {data['pass']}/{data['n']} of {data['planned']} planned; pass from {data['pass_from']}; "
              f"stopped on pass {data['stopped_on_pass']}; timeouts {data['timeouts']}; ./validate max {data['validate_calls']['max']}; "
              f"${data['usd']:.2f} ({data['usage_source']})")
    print("before on these tasks:", {cohort: f"{value['pass']}/{value['n']}" for cohort, value in summary["before"].items()})
    for entry in summary["per_task"]:
        print(entry["task_id"], {cohort: f"{cell['pass']}/{cell['n']}" for cohort, cell in entry["before"].items()},
              {agent: " ".join(entry[agent]["statuses"]) for agent in summary["agents"]})
    print(OUT)


if __name__ == "__main__":
    main()
