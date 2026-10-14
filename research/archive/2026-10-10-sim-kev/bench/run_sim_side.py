"""Side batch over the 1500 active SIM tasks (bench/tasks_staging/t_sim_bank: sim_battery, sim_backlog,
sim_thermal after the 500-task curation, plus sim_harvest, sim_latency, sim_storage, sim_uplink; the
archive under _archive_unselected is never read).

One prompt per task: the full input/requirements.md as the user message, no rules beyond the
reply-format line the direct candidate always gets (the P0 shape of run_side.py: one call, no
repair). The reply goes through agents.llm.extract_json and bench.score_sim — pure code rules,
no model judges (decision 025) — with the task verdict and the design verdict reported
separately (decision 019).

    python3 bench/run_sim_side.py --candidate direct --model qwen3.8-flash                # all 1500, one repeat
    python3 bench/run_sim_side.py --candidate direct --sample 100 --stratified            # seeded stratified draw
    python3 bench/run_sim_side.py --candidate direct --sample 5 --dry-run                 # fake replies, no API call
    python3 bench/run_sim_side.py --candidate claude --sample 120 --stratified --repeats 3  # the agent examinees

The agent candidates put the same requirements.md through the harness the PURE/SysEngBench side runs used
(bench.run_side.ask, 2026-10-09): claude and opencode get one sandboxed session per task
(bench.run_claude_qwen.run_claude / agents.external.opencode_run.run_opencode, agents/external/jail.py), the
lf-* ones one message through a Langflow chat flow on 127.0.0.1:7860 (bench.run_side._ask_langflow; the flow
is probed first and the run refuses to start, not hang, when the server is down). The reply text is parsed
with extract_json and scored by score_sim exactly like the direct candidate; the sandboxed candidates need
the results page (8770) stopped, and their token usage is the flat input/cached/output of the session rather
than the by-model summary of a chat call.

Stratification dims: family x platform x difficulty, with the dims each family actually has —
sim_battery/sim_harvest get their platform from the scenario text and a duty-row count;
sim_backlog and sim_latency have platform only; sim_storage has platform and its variant/mode
(retention/preview, choice/ladder, ...); sim_uplink is the dual platform usv+uav, so its
platform dimension is the allocation scheme (fixed/preempt_usv/preempt_uav, from the family
index.jsonl) and its difficulty dimension is the phase count parsed from the schedule table.

Output: analysis/side-sim-<candidate>-<stamp>/ with results.jsonl (one row per task and
repeat: prompt summary, raw reply, parsed answer, verdicts, failing checks with their
expected bands, usage) and summary.json (pass-rate matrices by family, platform, difficulty
and the gold design boolean, plus cost at list price). A run resumes the latest matching
folder: rows that already carry a verdict are kept, everything else (including error rows)
is run again. --dry-run writes the same two files from canned replies (two tasks per new
family) and never calls the endpoint.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import shutil
import socket
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.llm import USAGE_LOG, chat, extract_json, usage_summary  # noqa: E402
from bench.experiment import load_env  # noqa: E402
from bench.score_sim import design_verdict, score_sim  # noqa: E402

BANK = ROOT / "bench" / "tasks_staging" / "t_sim_bank"
FAMILIES = ("sim_battery", "sim_backlog", "sim_thermal", "sim_harvest", "sim_latency", "sim_storage", "sim_uplink")
PREFIXES = {"sim_battery": "BAT", "sim_backlog": "BLG", "sim_thermal": "THM", "sim_harvest": "HRV",
            "sim_latency": "LAT", "sim_storage": "CMP", "sim_uplink": "SHR"}
SEED = 20261010
# The same reply-format help every direct side run gets (run_side.py); no answer rules, no examples.
SYSTEM = "Reply with one JSON object and no prose, using the field names required by the task."
# The agent candidates: the two Langflow chat flows the 2026-10-09 side matrix ran (run_side_matrix.sh),
# keyed by the candidate name; claude and opencode are the sandboxed sessions of agents/external/.
FLOWS = {"lf-memory": "Langflow Agent with memory chat · qwen3.8-max",
         "lf-pilot": "Langflow Agent, Pilot only chat"}
LOCK = threading.Lock()


# ---------- the task index ----------

def _uplink_index() -> dict[str, dict]:
    """The family index the uplink generator wrote: id -> platform, scheme. Missing entries fall back."""
    path = BANK / "sim_uplink" / "index.jsonl"
    out = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                out[row.get("id") or ""] = row
    return out


def _platform(task: Path, case: dict, uplink: dict) -> str:
    """case.yaml platform when the generator wrote one; sim_uplink's dual platform from its index;
    for sim_battery and sim_harvest the platform is only in the scenario text, where the first of
    the two platform phrases to appear names the platform (the four-node list mentions both)."""
    if case.get("platform"):
        return str(case["platform"])
    task_id = case.get("id") or task.name
    if task.name.startswith("SHR-"):
        return str(uplink.get(task_id, {}).get("platform") or "usv+uav")
    head = "\n".join((task / "input" / "requirements.md").read_text(encoding="utf-8").splitlines()[:6])
    usv, uav = head.find("unmanned surface vessel"), head.find("fixed-wing UAV")
    if usv >= 0 and (uav < 0 or usv < uav):
        return "usv"
    if uav >= 0:
        return "uav"
    return "-"


def _phases(task: Path) -> int:
    """Rows of the sensor-generation schedule table in a sim_uplink requirements.md."""
    text = (task / "input" / "requirements.md").read_text(encoding="utf-8")
    block = re.search(r"## Sensor generation schedule.*?\n\n(.*?)(?:\n\n|\Z)", text, re.S)
    if not block:
        return 0
    return len([line for line in block.group(1).splitlines() if re.match(r"\|\s*\d+\s*\|", line)])


def bank_index() -> list[dict]:
    """Every active SIM task with the stratification dims: family, platform, difficulty."""
    uplink = _uplink_index()
    rows = []
    for family in FAMILIES:
        prefix = PREFIXES[family]
        for task in sorted((BANK / family).iterdir()):
            if not (task.is_dir() and task.name.startswith(prefix + "-")):
                continue
            case = yaml.safe_load((task / "case.yaml").read_text(encoding="utf-8"))
            gold = json.loads((task / "gold" / "answer.json").read_text(encoding="utf-8"))
            assertions = yaml.safe_load((task / "gold" / "assertions.yaml").read_text(encoding="utf-8"))
            task_id = case.get("id") or task.name
            difficulty = case.get("difficulty") or case.get("variant") or "-"
            if difficulty == "-" and family in {"sim_battery", "sim_harvest"}:
                # no variant field; the duty-row count is the honest proxy
                count = (assertions.get("checks") or {}).get("key_point_count") or {}
                difficulty = f"{count.get('gold', len(gold.get('key_points') or [])) - 1}-row"
            if family == "sim_uplink":
                # the dual platform carries no signal; the scheme and the phase count do
                scheme = str(uplink.get(task_id, {}).get("scheme") or "-")
                difficulty = f"{scheme}:{_phases(task)}p"
            verdict = design_verdict(family, assertions, gold) or {}
            rows.append({"task_id": task_id, "dir": task, "family": family,
                         "platform": _platform(task, case, uplink), "difficulty": str(difficulty),
                         "design_field": verdict.get("criterion"), "design_gold": verdict.get("gold")})
    return rows


def strata(index: list[dict]) -> dict[tuple, list[dict]]:
    buckets: dict[tuple, list[dict]] = {}
    for row in index:
        buckets.setdefault((row["family"], row["platform"], row["difficulty"]), []).append(row)
    return buckets


def sample_tasks(index: list[dict], n: int, stratified: bool, seed: int) -> list[dict]:
    if n <= 0 or n >= len(index):
        return list(index)
    if not stratified:
        return sorted(random.Random(seed).sample(index, n), key=lambda row: row["task_id"])
    # proportional allocation over the strata (largest remainder), every stratum represented once
    # n is large enough; the draw inside a stratum uses a string seed, stable across processes
    buckets = strata(index)
    keys = sorted(buckets)
    exact = {key: n * len(buckets[key]) / len(index) for key in keys}
    alloc = {key: int(exact[key]) for key in keys}
    if n >= len(keys):
        for key in keys:
            alloc[key] = max(alloc[key], 1)
    order = sorted(keys, key=lambda key: (exact[key] - alloc[key], len(buckets[key])), reverse=True)
    while sum(alloc.values()) < n:
        alloc[order[0]] += 1
        order.append(order.pop(0))
    big = sorted(keys, key=lambda key: len(buckets[key]), reverse=True)
    position = 0
    while sum(alloc.values()) > n:  # the once-each minimum can over-allocate on a small n
        key = big[position % len(big)]
        position += 1
        if alloc[key] > 1:
            alloc[key] -= 1
    picked = []
    for key in keys:
        picked.extend(random.Random(f"{seed}:{key}").sample(buckets[key], min(alloc[key], len(buckets[key]))))
    chosen_ids = {row["task_id"] for row in picked}
    while len(picked) < n:  # give back seats a stratum could not fill
        left = [row for row in index if row["task_id"] not in chosen_ids]
        extra = random.Random(seed + len(picked)).choice(left)
        chosen_ids.add(extra["task_id"])
        picked.append(extra)
    return sorted(picked[:n], key=lambda row: row["task_id"])


# ---------- asking and scoring ----------

def ask_direct(model: str, prompt: str) -> dict:
    """The run_side.py direct candidate, P0 shape: one chat call, no repair loop."""
    calls: list[dict] = []
    USAGE_LOG.set(calls)
    os.environ["MVP_LLM_MODEL"] = model
    reply = chat([{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}], max_tokens=1500)
    return {"text": reply["text"], "usage": usage_summary(calls)}


def _staged_task(task: dict, scratch: Path) -> Path:
    """A task folder the sandboxed runners accept: the bank task's whole input/ (requirements.md plus the
    model.sysml the SIM tasks carry), staged under scratch. The gold never leaves the bank."""
    folder = scratch / task["task_id"]
    if not (folder / "input" / "requirements.md").is_file():
        shutil.copytree(task["dir"] / "input", folder / "input")
        (folder / "case.yaml").write_text(yaml.safe_dump({"id": task["task_id"], "type": "SIM"}), encoding="utf-8")
    return folder


def ask_agent(candidate: str, model: str, task: dict, prompt: str, scratch: Path) -> dict:
    """One SIM task through an agent examinee, the same harness the PURE/SysEngBench side runs used
    (run_side.ask, 2026-10-09): one sandboxed session for claude/opencode, one message through a
    Langflow chat flow for lf-*. The requirements.md is the whole message; the reply text is all we keep."""
    if candidate in FLOWS:
        from bench.run_side import _ask_langflow
        return _ask_langflow(FLOWS[candidate], model, task["task_id"], prompt)
    folder = _staged_task(task, scratch)
    if candidate == "opencode":
        from agents.external.opencode_run import run_opencode
        from bench.run_opencode import usage_from_log
        os.environ["MVP_LLM_MODEL"] = model
        solved = run_opencode(folder)
        return {"text": solved["text"], "usage": usage_from_log(Path(solved["workspace"]).parent / "stdout.jsonl")}
    if candidate == "claude":
        from bench.run_claude_qwen import run_claude, usage_of
        run = run_claude(folder, model=model, max_turns=30, timeout=900, label="SIM-CL")
        return {"text": run["text"], "usage": usage_of(run["result"])}
    raise ValueError(candidate)


def fake_reply(task: dict, variant: int) -> str:
    """A canned reply for --dry-run: correct / drifted / missing field / extra field, some wrapped in prose."""
    answer = json.loads((task["dir"] / "gold" / "answer.json").read_text(encoding="utf-8"))
    answer.pop("task_id", None)
    if variant == 1:
        for key in sorted(answer):
            if isinstance(answer[key], (int, float)) and not isinstance(answer[key], bool):
                answer[key] = round(answer[key] * 1.5, 3)
                break
        return "Answer:\n```json\n" + json.dumps(answer) + "\n```"
    if variant == 2:
        del answer[sorted(answer)[0]]
        return json.dumps(answer)
    if variant == 3:
        answer["harness_note"] = "an extra field the schema does not have"
        return "```json\n" + json.dumps(answer) + "\n```"
    return "```json\n" + json.dumps(answer) + "\n```"


def run_one(task: dict, args, repeat: int, scratch: Path) -> dict:
    prompt = (task["dir"] / "input" / "requirements.md").read_text(encoding="utf-8")
    record = {"bench": "sim", "candidate": args.candidate,
              "model": "dry-run" if args.dry_run else args.model, "repeat": repeat, "item": task["task_id"],
              "family": task["family"], "platform": task["platform"], "difficulty": task["difficulty"],
              "prompt_chars": len(prompt),
              "prompt_head": prompt[:160], "prompt_tail": prompt[-160:]}
    if args.candidate in FLOWS:
        record["flow"] = FLOWS[args.candidate]
    try:
        if args.dry_run:
            reply = {"text": fake_reply(task, task.get("_reply_style", (repeat - 1) % 4)),
                     "usage": {"calls": 0, "by_model": {}}}
        elif args.candidate == "direct":
            reply = ask_direct(args.model, prompt)
        else:
            prompt_id = f"{task['task_id']}-r{repeat}"
            reply = ask_agent(args.candidate, args.model, task, prompt, scratch / f"{prompt_id}")
        if not str(reply.get("text") or "").strip():
            raise RuntimeError("empty reply")
        record["answer"] = reply["text"][:4000]
        record["usage"] = reply.get("usage")
        try:
            parsed = extract_json(reply["text"])
        except (ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"no JSON in the reply: {exc}")
        scored = score_sim(task["dir"], parsed)
        record.update({"parsed": parsed, "status": scored["status"], "design_status": scored["design_status"],
                       "failed": scored["failed"], "missing_fields": scored["missing_fields"],
                       "extra_fields": scored["extra_fields"], "reason": scored["reason"],
                       "failed_checks": [row for row in scored["checks"] if not row["ok"]]})
    except Exception as exc:
        record["error"] = f"{type(exc).__name__}: {exc}"
        record["scored"] = False
        record["status"] = "ERROR"
    return record


# ---------- output, resume, summary ----------

def folder_name(args) -> str:
    slug = args.candidate + ("-dryrun" if args.dry_run else "")
    return f"side-sim-{slug}"


def _signature(args) -> dict:
    return {"bench": "sim", "candidate": args.candidate, "model": args.model, "dry_run": args.dry_run,
            "sample": args.sample, "stratified": args.stratified, "seed": args.seed, "repeats": args.repeats}


def _kept(record: dict) -> bool:
    """A row that can stand as this task's score; an error row is redone, not counted as a zero."""
    return not record.get("error") and record.get("status") in {"PASS", "FAIL"}


def _latest_folder(args) -> Path | None:
    matches = [path for path in (ROOT / "analysis").glob(folder_name(args) + "-*") if _matches(path, args)]
    return max(matches, key=lambda path: path.name) if matches else None


def _matches(folder: Path, args) -> bool:
    path = folder / "summary.json"
    if not path.is_file():
        return False
    try:
        meta = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    signature = _signature(args)
    return all(meta.get(key) == value for key, value in signature.items())


def _open_folder(args, jobs: list[tuple[dict, int]], bank_tasks: int) -> tuple[Path, list[tuple[dict, int]]]:
    """Resume the latest matching folder, or start a new one. Error rows are dropped and run again."""
    folder = _latest_folder(args)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    meta = _signature(args) | {"started": stamp, "bank": str(BANK.relative_to(ROOT)),
                               "bank_tasks": bank_tasks, "dry_run": args.dry_run}
    if folder is None:
        folder = ROOT / "analysis" / f"{folder_name(args)}-{stamp}"
        folder.mkdir(parents=True)
        (folder / "summary.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        return folder, jobs
    rows = _rows(folder)
    done = {(row.get("repeat"), row.get("item")) for row in rows if _kept(row)}
    pending = [job for job in jobs if (job[1], job[0]["task_id"]) not in done]
    if done and pending:
        print(f"resume {folder.name}: {len(done)} already scored, {len(pending)} to go", flush=True)
    elif not pending:
        print(f"already finished in {folder.name}", flush=True)
    return folder, pending


def _rows(folder: Path) -> list[dict]:
    path = folder / "results.jsonl"
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _bucket(rows: list[dict]) -> dict:
    n = len(rows)
    task_pass = sum(row.get("status") == "PASS" for row in rows)
    return {"n": n, "task_pass": task_pass, "task_pass_rate": round(task_pass / n, 4) if n else None,
            "task_pass_design_fail": sum(row.get("status") == "PASS" and row.get("design_status") == "FAIL" for row in rows),
            "errors": sum(bool(row.get("error")) for row in rows)}


def write_summary(folder: Path, args) -> dict:
    rows = [row for row in _rows(folder) if _kept(row)]
    by = lambda key: {value: _bucket([row for row in rows if row.get(key) == value])
                      for value in sorted({str(row.get(key)) for row in rows}, key=str)}
    design = {}
    cache: dict = {}
    groups: dict[tuple, list[dict]] = {}
    for row in rows:
        criterion, value = _design_of(row, cache)
        if criterion and isinstance(value, bool):
            groups.setdefault((row["family"], criterion, value), []).append(row)
    for (family, criterion, value) in sorted(groups, key=str):
        design[f"{family}/{criterion}={str(value).lower()}"] = _bucket(groups[(family, criterion, value)])
    usage = {"calls": 0, "by_model": {}}
    flat = {"rows": 0, "calls": 0, "input": 0, "cached": 0, "cache_write": 0, "output": 0}
    for row in rows:
        row_usage = row.get("usage") or {}
        for model, slot in (row_usage.get("by_model") or {}).items():
            target = usage["by_model"].setdefault(model, {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cached_tokens": 0})
            for name in target:
                target[name] += slot.get(name, 0)
            usage["calls"] += slot.get("calls", 0)
        if not row_usage.get("by_model") and (row_usage.get("input") or row_usage.get("output")):
            # an agent session: flat input/cached/output tokens, no by-model split to price
            flat["rows"] += 1
            flat["calls"] += row_usage.get("calls") or 0
            for name in ("input", "cached", "cache_write", "output"):
                flat[name] += row_usage.get(name) or 0
    if flat["rows"]:
        usage["agent_sessions"] = flat
    meta = json.loads((folder / "summary.json").read_text(encoding="utf-8")) if (folder / "summary.json").is_file() else {}
    summary = meta | {"finished": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S"),
                      "scored_rows": len(rows), "overall": _bucket(rows),
                      "by_family": by("family"), "by_platform": by("platform"), "by_difficulty": by("difficulty"),
                      "by_design_boolean": design, "cost": {"usage": usage, "usd_estimate": _usd(usage)}}
    (folder / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def _design_of(row: dict, cache: dict) -> tuple:
    """(criterion label, gold boolean) for a row's task, read from the bank at summary time.
    The criterion can depend on the task's variant (sim_storage) or span fields (sim_uplink)."""
    key = (row["family"], row["item"])
    if key not in cache:
        task = BANK / row["family"] / row["item"]
        try:
            assertions = yaml.safe_load((task / "gold" / "assertions.yaml").read_text(encoding="utf-8"))
            gold = json.loads((task / "gold" / "answer.json").read_text(encoding="utf-8"))
            verdict = design_verdict(row["family"], assertions, gold) or {}
            cache[key] = (verdict.get("criterion"), verdict.get("gold"))
        except (OSError, yaml.YAMLError, json.JSONDecodeError):
            cache[key] = (None, None)
    return cache[key]


def _usd(usage: dict) -> float | None:
    """Cost at the list price of bench/board_facts.PRICES; None when the model has no price (never a guess).
    An agent-only run (no by-model usage to price) is None, not a misleading 0."""
    from bench.board_facts import PRICES
    total = 0.0
    priced = True
    if not usage.get("by_model"):
        return None
    for model, slot in usage.get("by_model", {}).items():
        price = PRICES["models"].get(model)
        if not price:
            priced = False
            continue
        fresh = slot.get("prompt_tokens", 0) - slot.get("cached_tokens", 0)
        total += (fresh * price["input"] + slot.get("cached_tokens", 0) * price["cache"]
                  + slot.get("completion_tokens", 0) * price["output"]) / 1e6
    return round(total, 4) if priced else None


def _page_running() -> bool:
    """The results page (8770) serves answer keys; the sandbox shares the network, so the sandboxed
    candidates refuse to run while it is up (the rule of run_side_matrix.sh)."""
    with socket.socket() as probe:
        probe.settimeout(0.3)
        return probe.connect_ex(("127.0.0.1", 8770)) == 0


def _probe_flow(candidate: str) -> None:
    """Fail fast, not hang, when Langflow is down or the flow is not runnable: one login and one flow
    lookup before any task runs (bench.run_side._ask_langflow repeats this per task)."""
    try:
        import bench.langflow_exam as exam
        from bench.run_side import _ask_langflow  # noqa: F401  (the channel the rows will use)
        token = exam._token()
        flow = exam._flow(token, FLOWS[candidate])
    except SystemExit as exc:
        raise SystemExit(f"candidate {candidate} skipped: {exc}")
    except Exception as exc:
        raise SystemExit(f"candidate {candidate} skipped: Langflow on 127.0.0.1:7860 is not reachable "
                         f"({type(exc).__name__}: {exc})")
    print(f"flow probed: {flow['name']} ({flow['id']})", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", default="direct", choices=["direct", "claude", "opencode", *FLOWS],
                        help="direct: one agents/llm.py chat call per task, the P0 shape (no repair); claude / "
                             "opencode: one sandboxed session per task (agents/external/); lf-memory / lf-pilot: "
                             "one message through the Langflow chat flow of that name")
    parser.add_argument("--model", default="qwen3.8-flash")
    parser.add_argument("--sample", type=int, default=0, help="0: every task in the bank; N: draw N tasks")
    parser.add_argument("--stratified", action="store_true",
                        help="with --sample N: proportional draw over family x platform x difficulty strata")
    parser.add_argument("--seed", type=int, default=SEED, help="the sampling seed, fixed so a draw repeats")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--dry-run", action="store_true",
                        help="five tasks, canned replies, no model call: exercises prompt to verdict to files")
    args = parser.parse_args()
    if args.stratified and args.sample <= 0:
        raise SystemExit("--stratified needs --sample N")
    if not BANK.is_dir():
        raise SystemExit(f"no SIM bank at {BANK}")
    if args.candidate in {"claude", "opencode"} and not args.dry_run and _page_running():
        raise SystemExit("the results page (8770) is up and serves answer keys; stop it before a sandboxed run")
    if args.candidate in FLOWS and not args.dry_run:
        _probe_flow(args.candidate)

    index = bank_index()
    if args.dry_run:
        tasks = _dry_run_tasks(index)
    else:
        tasks = sample_tasks(index, args.sample, args.stratified, args.seed)
    jobs = [(task, repeat) for repeat in range(1, args.repeats + 1) for task in tasks]

    folder, pending = _open_folder(args, jobs, len(index))
    if not args.dry_run and pending:
        load_env()
    print(f"{folder.name}: {len(pending)} of {len(jobs)} rows to write "
          f"({len(tasks)} tasks x {args.repeats} repeat(s); dry_run={args.dry_run})", flush=True)

    scratch = ROOT / "mvp" / "exam-inbox" / f"sim-side-{args.candidate}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"

    def run(job):
        task, repeat = job
        record = run_one(task, args, repeat, scratch)
        with LOCK:
            with (folder / "results.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            line = (f"r{repeat} {record['item']} {record.get('status', 'ERROR')}"
                    + (f" (design {record['design_status']})" if record.get("design_status") else ""))
            if record.get("error"):
                line += f" :: {record['error']}"
            print(line, flush=True)

    try:
        if pending:
            with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
                list(pool.map(run, pending))
    finally:
        if scratch.is_dir():
            shutil.rmtree(scratch, ignore_errors=True)
    summary = write_summary(folder, args)
    overall = summary["overall"]
    print(f"{folder}: task {overall['task_pass']}/{overall['n']} PASS"
          f" ({(overall['task_pass_rate'] or 0) * 100:.1f}%), design FAIL on {overall['task_pass_design_fail']} of the passes",
          flush=True)
    print(folder)


def _dry_run_tasks(index: list[dict]) -> list[dict]:
    """Two tasks per new family — both sides of the design boolean, and both sim_storage variants —
    with the four reply styles of fake_reply cycled by position (correct, drift, missing, extra)."""
    def first(predicate):
        return next(row for row in index if predicate(row))
    picks = []
    for family in ("sim_harvest", "sim_latency", "sim_uplink"):
        for wanted in (False, True):
            picks.append(first(lambda row, f=family, w=wanted: row["family"] == f and row["design_gold"] is w))
    picks.append(first(lambda row: row["family"] == "sim_storage" and row["difficulty"].startswith("retention")))
    picks.append(first(lambda row: row["family"] == "sim_storage" and row["difficulty"].startswith("choice")))
    return [dict(task, _reply_style=position % 4) for position, task in enumerate(picks)]


if __name__ == "__main__":
    main()
