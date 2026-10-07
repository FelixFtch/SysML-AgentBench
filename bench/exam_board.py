"""Exam board. Saved cells can be replayed. A run calls the model to write a new answer."""
from __future__ import annotations

import hashlib
import json
import re
import sys
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
HELD = ROOT / "bench" / "tasks" / "t4_maritime_isr" / "heldout"
PAGE = Path(__file__).with_name("exam_board.html")
NUM = re.compile(r"(\w+)\s*:\s*Real\s*=\s*([0-9]+(?:\.[0-9]+)?)")
STATIC = {
    "/board.css": ("board.css", "text/css; charset=utf-8"),
    "/board.js": ("board.js", "text/javascript; charset=utf-8"),
    "/scenes.js": ("scenes.js", "text/javascript; charset=utf-8"),
}
AGENT_RUNS = ROOT / "mvp" / "agent-runs"


def _read(path: Path, limit: int = 20000) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")[:limit]


def _lines(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _task_dir(task_id: str) -> Path:
    return HELD / task_id


def _gold(task_id: str) -> str:
    gold = _task_dir(task_id) / "gold"
    parts = []
    for path in sorted(gold.rglob("*")):
        if path.is_file() and path.suffix in {".yaml", ".json", ".sysml", ".md"}:
            parts.append(f"# {path.relative_to(gold)}\n{_read(path)}")
    return "\n\n".join(parts) or "No answer key file was found for this task."


def _requirements(task_id: str) -> str:
    return _read(_task_dir(task_id) / "input" / "requirements.md") or "No task statement file was found."


def _validator_runs(workspace: str | None) -> int:
    """How many times an agent ran ./validate in its sandbox: each call leaves one folder under validation/."""
    if not workspace:
        return 0
    folder = Path(workspace) / "validation"
    return sum(1 for path in folder.iterdir() if path.is_dir()) if folder.is_dir() else 0


def _response_text(row: dict) -> str:
    """The candidate's full final reply: response.txt of a direct run, answer.md of an agent run."""
    folder = row.get("_folder")
    if folder and (Path(folder) / "response.txt").is_file():
        return _read(Path(folder) / "response.txt", 40000)
    workspace = row.get("workspace")
    if workspace and (Path(workspace) / "answer.md").is_file():
        return _read(Path(workspace) / "answer.md", 40000)
    return ""


def _model_text(row: dict) -> str:
    response = _response_text(row)
    run = row.get("engine_run")
    if row.get("type") in {"GEN", "MOD"} and run:
        model = ROOT / "mvp" / "runs" / run / "model"
        files = sorted(model.glob("*.sysml")) if model.is_dir() else []
        if files:
            return "\n\n".join(f"# {path.name}\n{_read(path)}" for path in files[-1:])
    if response:
        return response
    return "The answer text of this cell was not found. The verdict still comes from the saved score row."


def _watts(text: str) -> list[tuple[str, float]]:
    return [(name, float(value)) for name, value in NUM.findall(text)]


def _step(title: str, state: str, detail: str) -> dict:
    return {"title": title, "state": state, "detail": detail}


STOP_TEXT = {"pass": "the official parse passed", "cap": "the cap of 20 repairs was reached",
             "identical x3": "three identical resubmissions in a row; the loop stopped"}


def _flow(row: dict, answer: str) -> list[dict]:
    kind = row.get("type")
    status = row.get("status")
    syntax = row.get("sysml_status")
    repairs = int(row.get("repair_rounds") or 0)
    agent = row.get("cohort_id") in {"opencode", "claude"}
    config = row.get("configuration")
    calls = row.get("calls") or []
    steps = [_step("Issue task", "pass", "Task statement sent. The answer key is not in the prompt" + (" and not in the agent's sandbox." if agent else "."))]
    if not agent and config == "P3":
        steps.append(_step("Retrieve notes", "pass", "MiniLM + FAISS over the official-examples library and the notes; up to 3 seeds plus one hop."))
    if not agent and config in {"P2", "P3"}:
        steps.append(_step("Outline", "pass", "A JSON outline of parts, ports and connections, written before the answer."))
    if agent:
        usage = row.get("usage") or {}
        turns = usage.get("turns") or usage.get("calls")
        runs = _validator_runs(row.get("workspace"))
        wrote = bool(row.get("workspace")) and (Path(row["workspace"]) / "answer.md").is_file()
        if wrote:
            steps.append(_step("Write answer", "pass", f"One {row.get('cohort', '')} session in the sandbox: {turns or '?'} model turns, "
                                                       f"{runs} run(s) of ./validate."))
        elif str(row.get("returncode")) == "timeout":
            steps.append(_step("Write answer", "fail", f"The session hit the 900 s limit before writing answer.md, after {runs} run(s) of ./validate."))
        else:
            steps.append(_step("Write answer", "pass", f"No answer.md; the session's final message was scored. {runs} run(s) of ./validate."))
    else:
        steps.append(_step("Write answer", "pass" if answer else "fail", "Recorded calls: " + (", ".join(item.get("step", "") for item in calls) or "none")))
    if kind in {"GEN", "MOD", "ALN"}:
        tries = len(row.get("attempts") or []) or (1 if syntax else 0)
        if syntax == "PASS":
            steps.append(_step("Official syntax", "pass", f"The official Pilot passed it ({tries} parse(s)). That only means the syntax is valid."))
        elif syntax == "FAIL" and (row.get("engine_run") or row.get("attempts")):
            steps.append(_step("Official syntax", "fail", "The official Pilot rejected the final version. The checklist is not applied."))
        else:
            steps.append(_step("Official syntax", "fail", "No official syntax result: no SysML package was submitted."))
        if agent:
            steps.append(_step("Repair from errors", "skip", "The agent repairs inside its own session with ./validate; the grader parses only the final answer."))
        elif config == "P0":
            steps.append(_step("Repair from errors", "skip", "P0 writes once and is not repaired."))
        elif repairs:
            stop = STOP_TEXT.get(row.get("stop_reason") or "", row.get("stop_reason") or "")
            first = row.get("first_pass_attempt")
            detail = f"{repairs} repair(s) in one conversation with every earlier version and error list; " + (f"first passing version: attempt {first}." if first else f"stopped: {stop}.")
            if row.get("resubmitted_unchanged"):
                detail += f" {row['resubmitted_unchanged']} resubmission(s) were identical to the one before."
            steps.append(_step("Repair from errors", "pass" if syntax == "PASS" else "fail", detail))
        else:
            steps.append(_step("Repair from errors", "skip", "The first version passed; no repair needed."))
    else:
        steps.append(_step("Official syntax", "skip", "Query, ambiguity and round-trip answers are JSON or text, not SysML."))
        steps.append(_step("Repair from errors", "skip", "No syntax repair for this task type."))
    numbers = _watts(answer)
    if numbers:
        steps.append(_step("Read values", "pass", "Read from the answer: " + ", ".join(f"{name} {value:g}" for name, value in numbers) + "."))
    else:
        steps.append(_step("Read values", "skip", "No Real wattage values in this answer."))
    if status == "PASS":
        note = "Matches the answer key."
        if row.get("engineering_status") == "FAIL":
            note = ("Design verdict FAIL: power 41 + 25 + 12 = 78 W against a 60 W limit, as the answer key expects; every kept value is present and the limit is unchanged. Task verdict PASS."
                    if row.get("task_id") == "MOD-05" else "Design verdict FAIL, as the answer key expects. Task verdict PASS.")
        steps.append(_step("Check against key", "pass", note))
    elif status == "FAIL":
        steps.append(_step("Check against key", "fail", row.get("reason") or row.get("error") or "Does not match the answer key."))
    else:
        steps.append(_step("Check against key", "skip", f"Status is {status}."))
    steps.append(_step("Approval gate", "skip", "No requirement change was requested in this cell."))
    steps.append(_step("Archive", "pass", f"Score row in analysis/{row.get('batch', '')}/results.jsonl."))
    return steps


def _cells() -> list[dict]:
    from bench.batches import COHORTS, rows
    cells = []
    for cohort in COHORTS:
        for row in rows(cohort):
            row["id"] = f"{cohort}:{row.get('repeat')}:{row['task_id']}:{row.get('configuration')}"
            cells.append(row)
    return cells


CELLS = _cells()
BY_ID = {row["id"]: row for row in CELLS}


def _attempt(path: Path, number: int, previous: str | None) -> dict:
    validation = path / "sysml" / "validation.json"
    data = json.loads(validation.read_text(encoding="utf-8")) if validation.is_file() else {}
    files = sorted((path / "model").glob("*.sysml"))
    text = _read(files[-1], 4000) if files else ""
    sha = hashlib.sha256(text.encode()).hexdigest()[:12]
    return {
        "attempt": number, "run_id": path.name, "status": data.get("status") or "?",
        "diagnostics": [{"line": item.get("line"), "message": item.get("message", "")} for item in (data.get("diagnostics") or [])],
        "sha": sha, "same_as_previous": previous == sha, "text": text,
    }


def _attempt_paths(row: dict) -> list[Path]:
    """Run directories of every official parse behind one cell, oldest first: every attempt of a direct cell,
    the grader's single parse of an agent's final answer."""
    if row.get("type") not in {"GEN", "MOD", "ALN"}:
        return []
    ids = [item.get("run_id") for item in row.get("attempts") or [] if item.get("run_id")] or ([row["engine_run"]] if row.get("engine_run") else [])
    return [ROOT / "mvp" / "runs" / run for run in ids if (ROOT / "mvp" / "runs" / run).is_dir()]


VERDICT_KEYS = ("status", "sysml_status", "engineering_status", "must_exist", "must_connect", "must_preserve",
                "checks", "checks_match", "invented_numbers", "reason")


def _verdict(row: dict, answer: str, response: str) -> dict:
    """What the scorer found in this cell's final answer: missing names and links, changed values, mappings, answer fields."""
    from bench.score_alignment import score_alignment
    from bench.score_answer import score_answer
    from bench.score_task import score_run
    task_dir = HELD / row["task_id"]
    if not (task_dir / "case.yaml").is_file():
        return {}
    try:
        if row.get("type") in {"GEN", "MOD", "ALN"}:
            paths = _attempt_paths(row)
            if row.get("type") == "ALN":
                return score_alignment(paths[-1] if paths else None, task_dir / "gold" / "assertions.yaml", response or answer,
                                       sysml_status=row.get("sysml_status"))
            if not paths:
                return {"reason": "No official run: the answer had no SysML package."}
            scored = score_run(paths[-1], task_dir / "gold" / "assertions.yaml")
            return {key: scored[key] for key in VERDICT_KEYS if key in scored}
        return score_answer(task_dir, response or answer or "")
    except Exception as exc:  # a broken saved answer must not break the page
        return {"reason": f"{type(exc).__name__}: {exc}"}


def _attempts(row: dict) -> list[dict]:
    attempts, previous = [], None
    for number, path in enumerate(_attempt_paths(row), 1):
        item = _attempt(path, number, previous)
        previous = item["sha"]
        attempts.append(item)
    return attempts


def _public(row: dict) -> dict:
    return {
        "id": row["id"], "cohort": row["cohort"], "cohort_id": row.get("cohort_id"), "model": row.get("model"),
        "task_id": row["task_id"], "type": row.get("type"), "configuration": row.get("configuration"), "repeat": row.get("repeat"),
        "status": row.get("status"), "engineering_status": row.get("engineering_status"), "sysml_status": row.get("sysml_status"),
        "repair_rounds": row.get("repair_rounds"), "first_pass_attempt": row.get("first_pass_attempt"),
        "stop_reason": row.get("stop_reason"), "resubmitted_unchanged": row.get("resubmitted_unchanged"),
    }


def _detail(row: dict) -> dict:
    from bench.batches import usage_of_row
    from bench.board_facts import _usd
    response = _response_text(row)
    answer = _model_text(row)
    outline, retrieved = "", []
    folder = row.get("_folder")
    if folder:
        outline = _read(Path(folder) / "outline.txt", 4000)
        notes = Path(folder) / "retrieved.json"
        if notes.is_file():
            retrieved = json.loads(notes.read_text(encoding="utf-8"))
    usage = usage_of_row(row)
    calls = row.get("calls") or []
    return {
        **_public(row),
        "requirements": _requirements(row["task_id"]),
        "answer": answer,
        "gold": _gold(row["task_id"]),
        "outline": outline,
        "retrieved": retrieved,
        "attempts": _attempts(row),
        "tokens": usage["input"] + usage["output"],
        "usage": {"input": usage["input"], "cached": usage["cached"], "output": usage["output"]},
        "usd": round(_usd(row.get("model") or "qwen3.8-flash", usage), 6),
        "calls": [call.get("step") for call in calls],
        "validator_runs": _validator_runs(row.get("workspace")),
        "steps": _flow(row, answer),
        "verdict": _verdict(row, answer, response),
    }


JOBS: dict[str, dict] = {}
JOB_LOCK = threading.Lock()
BUSY = False
STYLE = ROOT / "mvp" / "app" / "style.css"


def _tasks() -> list[dict]:
    rows = []
    for line in (HELD / "index.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        case_path = ROOT / item["path"] / "case.yaml"
        package = ""
        if case_path.is_file():
            for raw in case_path.read_text(encoding="utf-8").splitlines():
                if raw.startswith("package:"):
                    package = raw.split(":", 1)[1].strip()
        rows.append({"id": item["id"], "type": item["type"], "package": package})
    return rows


def _push(job: dict, step: dict) -> None:
    with JOB_LOCK:
        for index, item in enumerate(job["steps"]):
            if item["title"] == step["title"]:
                item["state"] = step["state"]
                item["detail"] = step["detail"]
                job["current"] = index
                job["phase"] = ""
                return
        job["steps"].append(step)
        job["current"] = len(job["steps"]) - 1
        job["phase"] = ""


def _phase(job: dict, title: str, detail: str) -> None:
    with JOB_LOCK:
        job["phase"] = title
        job["phase_detail"] = detail


def _gold_dir(task_dir: Path) -> str:
    gold = task_dir / "gold"
    parts = []
    if gold.is_dir():
        for path in sorted(gold.rglob("*")):
            if path.is_file() and path.suffix in {".yaml", ".json", ".sysml", ".md"}:
                parts.append(f"# {path.relative_to(gold)}\n{_read(path)}")
    return "\n\n".join(parts)


def _prepare_inbox(payload: dict) -> Path:
    kind = payload.get("type") or ""
    if kind not in {"GEN", "MOD", "QRY", "AMB", "RT"}:
        raise ValueError("Type must be one of GEN, MOD, QRY, AMB, RT.")
    requirements = (payload.get("requirements") or "").strip()
    gold = (payload.get("gold") or "").strip()
    if not requirements or not gold:
        raise ValueError("Both a task statement and an answer key are required.")
    package = (payload.get("package") or "Inbox").strip()
    if kind in {"GEN", "MOD"} and not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", package):
        raise ValueError("The package name must start with a letter and use only letters, digits and underscores.")
    if kind == "QRY":
        json.loads(gold)
    else:
        import yaml
        parsed = yaml.safe_load(gold)
        if not isinstance(parsed, dict):
            raise ValueError("The answer key must be a YAML mapping.")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    folder = ROOT / "mvp" / "exam-inbox" / stamp
    (folder / "input").mkdir(parents=True)
    (folder / "gold").mkdir()
    case = {"id": f"INBOX-{stamp}", "type": kind, "package": package, "synthetic": True}
    import yaml
    (folder / "case.yaml").write_text(yaml.safe_dump(case, allow_unicode=True), encoding="utf-8")
    (folder / "input" / "requirements.md").write_text(requirements + "\n", encoding="utf-8")
    name = "answer.json" if kind == "QRY" else "assertions.yaml"
    (folder / "gold" / name).write_text(gold + "\n", encoding="utf-8")
    return folder


def _execute(task_dir: Path, config: str, job: dict) -> None:
    from agents.llm_local import chat  # the cloud models as before; the local Qwen when a Langflow run selects it
    from agents.solve import _answer, _retrieve, _task
    from bench.experiment import grade, load_env

    load_env()
    case, prompt = _task(task_dir)
    with JOB_LOCK:
        job["requirements"] = prompt
        job["gold"] = _gold_dir(task_dir)
        job["task_id"] = case["id"]
        job["type"] = case["type"]
        job["configuration"] = config
    _push(job, _step("Issue task", "pass", "Task statement given to the model. The gold folder is not in the prompt."))
    prefix: list[dict] = []
    if config in {"P2", "P3"}:
        notes = ""
        if config == "P3":
            _phase(job, "Retrieve notes", "Retrieving notes by the words in the task statement. The notes contain no answer key.")
            found = _retrieve(prompt)
            notes = "\n\n".join(f"[{item['source']}]\n{item['text']}" for item in found)
            with JOB_LOCK:
                job["retrieved"] = found
            _push(job, _step("Retrieve notes", "pass", f"{len(found)} notes: " + ", ".join(item["source"] for item in found)))
        _phase(job, "Outline", "Writing an outline; no SysML yet.")
        outlined = chat([
            {"role": "system", "content": "List the parts, ports, connections, and attributes the task requires. Reply with one JSON object. Do not write SysML yet."},
            {"role": "user", "content": prompt if not notes else prompt + "\n\nReference notes:\n" + notes},
        ], max_tokens=1500)
        with JOB_LOCK:
            job["outline"] = outlined["text"]
        _push(job, _step("Outline", "pass", "Outline returned; the model writes from it next."))
        prefix = [{"role": "user", "content": "Outline:\n" + outlined["text"]},
                  {"role": "assistant", "content": "I will follow that outline."}]
    _phase(job, "Write answer", "Calling the model. The prompt still has no answer key.")
    written = _answer(case, prompt, prefix=prefix)
    text = written["text"]
    with JOB_LOCK:
        job["answer"] = text
    _push(job, _step("Write answer", "pass", f"Model {written.get('model') or ''} submitted its answer."))
    syntax = None
    rounds = 0
    run_dir = None
    if case["type"] in {"GEN", "MOD", "ALN"}:
        from agents.solve import companions_of, rounds_for, validate_with_repair
        cap = rounds_for(config)
        scratch = ROOT / "mvp" / "exam-inbox" / f"live-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-{case['id']}"
        scratch.mkdir(parents=True, exist_ok=True)
        _phase(job, "Official syntax", "The official Pilot is parsing model attempt 1.")

        def on_attempt(entry: dict, attempt_text: str, feedback: str) -> None:
            shown = {**entry, "diagnostics": [{"line": item.get("line"), "message": item.get("message") or ""} for item in entry["diagnostics"]],
                     "text": attempt_text[:4000]}
            with JOB_LOCK:
                job.setdefault("attempts", []).append(shown)
                job["answer"] = attempt_text
            if entry["status"] == "PASS" or entry["attempt"] > cap:
                return
            _push(job, _step("Official syntax", "fail", feedback or "The official parse failed."))
            _phase(job, "Repair from errors", f"Repair {entry['attempt']} of at most {cap}: the complete error list goes back to the model, together with every earlier version. Numbers stay as in the task.")

        loop = validate_with_repair(case, prompt, text, scratch, prefix=prefix, label=f"board-{case['id']}",
                                    max_rounds=cap, calls=[], on_attempt=on_attempt, companions=companions_of(case, task_dir))
        text, syntax, run_dir, rounds = loop["text"], loop["sysml_status"], loop["run_dir"], loop["repair_rounds"]
        with JOB_LOCK:
            job["answer"] = text
            job["repair_rounds"] = rounds
            job["max_rounds"] = cap
            job["first_pass_attempt"] = loop["first_pass_attempt"]
        last = loop["attempts"][-1] if loop["attempts"] else {"diagnostics": []}
        from agents.solve import format_diagnostics
        _push(job, _step("Official syntax", "pass" if syntax == "PASS" else "fail",
                         "The official Pilot passed it. That only means the syntax is valid." if syntax == "PASS" else format_diagnostics(last["diagnostics"])))
        if rounds == 0:
            _push(job, _step("Repair from errors", "skip", "No repair this time." if cap else "P0 writes once and is not repaired."))
        else:
            _push(job, _step("Repair from errors", "pass" if syntax == "PASS" else "fail",
                             f"{rounds} repair(s) of at most {cap}; the first passing version was attempt {loop['first_pass_attempt']}." if syntax == "PASS"
                             else f"{rounds} repair(s) made, the cap of {cap}; the official parse still fails. {loop['resubmitted_unchanged']} resubmission(s) were identical to the previous one."))
    else:
        _push(job, _step("Official syntax", "skip", "This task does not take SysML."))
        _push(job, _step("Repair from errors", "skip", "No syntax repair for this task type."))
    numbers = _watts(job.get("answer") or "")
    if numbers:
        _push(job, _step("Read values", "pass", ", ".join(f"{name} {value:g}" for name, value in numbers)))
    else:
        _push(job, _step("Read values", "skip", "No Real wattage values in the answer."))
    _phase(job, "Check against key", "Checking the answer against the answer key. Only this step reads the gold folder.")
    solved = {"text": text, "run_dir": run_dir, "sysml_status": syntax}
    scored = grade(task_dir, solved)
    status = scored["status"]
    if status == "PASS":
        note = "Matches the answer key."
        if scored.get("engineering_status") == "FAIL":
            note = "Design verdict FAIL, as the answer key expects; every kept value is present. Task verdict PASS."
        _push(job, _step("Check against key", "pass", note))
    else:
        reason = scored.get("reason") or scored.get("missing") or ""
        preserve = scored.get("must_preserve") or {}
        if preserve.get("missing"):
            reason = "A value that had to stay was changed: " + "; ".join(f"{item['qualified_name']} should be {item['expected']}, is {item['actual']}" for item in preserve["missing"])
        _push(job, _step("Check against key", "fail", str(reason) or "Does not match the answer key."))
    _push(job, _step("Approval gate", "skip", "Nobody asked to change a limit in this run."))
    _push(job, _step("Archive", "pass", f"Final {status}. Run folder: {run_dir or 'no official run'}"))
    with JOB_LOCK:
        job["status_label"] = status
        job["sysml_status"] = syntax
        job["engineering_status"] = scored.get("engineering_status")
        job["verdict"] = {key: scored[key] for key in VERDICT_KEYS if key in scored} if case["type"] in {"GEN", "MOD"} else scored
        job["phase"] = ""


def _worker(payload: dict, job: dict) -> None:
    global BUSY
    from agents.llm import MODEL_OVERRIDE, USAGE_LOG, usage_summary
    MODEL_OVERRIDE.set(job["model"])
    calls: list[dict] = []
    USAGE_LOG.set(calls)
    try:
        if payload.get("mode") == "new":
            task_dir = _prepare_inbox(payload)
            config = payload.get("configuration") or "P0"
        else:
            task_id = payload.get("task_id") or ""
            task_dir = HELD / task_id
            if not (task_dir / "case.yaml").is_file():
                raise ValueError("No such held-out task.")
            config = payload.get("configuration") or "P0"
        if config not in {"P0", "P1", "P2", "P3"}:
            raise ValueError("The approach must be P0, P1, P2 or P3.")
        _execute(task_dir, config, job)
        with JOB_LOCK:
            if job.get("status") == "running":
                job["status"] = "done"
    except Exception as exc:
        _push(job, _step("Archive", "fail", f"{type(exc).__name__}: {exc}"))
        with JOB_LOCK:
            job["status"] = "error"
            job["error"] = str(exc)
            job["phase"] = ""
    finally:
        with JOB_LOCK:
            job["usage"] = usage_summary(calls)
            BUSY = False


DISCOVER_STEPS = ("brief", "retrieve", "requirements", "source", "design", "syntax", "repair", "align", "simulate", "tradeoff", "readback", "gate")


def _discover_worker(brief: str, job: dict) -> None:
    global BUSY
    def progress(key: str, state: str, detail: str) -> None:
        with JOB_LOCK:
            for item in job["steps"]:
                if item["key"] == key:
                    item["state"] = state
                    item["detail"] = detail
            job["phase"] = key if state == "run" else ""
    try:
        from bench.discover import run
        record = run(brief, progress)
        with JOB_LOCK:
            job["record"] = record
            job["status"] = "done"
    except Exception as exc:
        with JOB_LOCK:
            job["status"] = "error"
            job["error"] = f"{type(exc).__name__}: {exc}"
            for item in job["steps"]:
                if item["state"] == "run":
                    item["state"] = "fail"
                    item["detail"] = job["error"]
    finally:
        with JOB_LOCK:
            BUSY = False


def _start_discover(brief: str) -> tuple[dict | None, str]:
    global BUSY
    brief = (brief or "").strip()
    if len(brief) < 20:
        return None, "Write at least one full sentence for the brief, including the platform and what must be shared."
    with JOB_LOCK:
        if BUSY:
            return None, "The previous run is still going; start the next one when it finishes."
        BUSY = True
        titles = {"brief": "Brief", "retrieve": "① Retrieve from memory", "requirements": "② Write requirements", "source": "Number source check",
                  "design": "② Write designs A / B", "syntax": "③ Official validation", "repair": "Repair from errors", "align": "④ Align",
                  "simulate": "⑤ Budget checks", "tradeoff": "Trade-offs", "readback": "⑤ Read back", "gate": "⑥ Person decides"}
        job = {"id": uuid.uuid4().hex[:12], "kind": "discover", "status": "running", "phase": "requirements",
               "steps": [{"key": key, "title": titles[key], "state": "wait", "detail": "Not reached yet."} for key in DISCOVER_STEPS],
               "brief": brief, "record": None, "error": ""}
        JOBS[job["id"]] = job
    threading.Thread(target=_discover_worker, args=(brief, job), daemon=True).start()
    return job, ""


MOD_TASKS = ("MOD-01", "MOD-02", "MOD-03", "MOD-04", "MOD-05")


def _mvp_case_file(task_id: str) -> Path | None:
    path = ROOT / "analysis" / f"mvp-case-latest-{task_id}.json"
    if path.is_file():
        return path
    legacy = ROOT / "analysis" / "mvp-case-latest.json"
    return legacy if task_id == "MOD-05" and legacy.is_file() else None


def _mvp_case_worker(job: dict, task_id: str) -> None:
    global BUSY
    try:
        import subprocess
        result = subprocess.run([sys.executable, str(ROOT / "bench" / "run_mvp_case.py"), task_id], capture_output=True, text=True, cwd=str(ROOT))
        latest = _mvp_case_file(task_id) or ROOT / "analysis" / f"mvp-case-latest-{task_id}.json"
        with JOB_LOCK:
            if result.returncode == 0 and latest.is_file():
                job["record"] = json.loads(latest.read_text(encoding="utf-8"))
                job["status"] = "done"
            else:
                job["status"] = "error"
                job["error"] = (result.stderr or result.stdout)[-600:]
    except Exception as exc:
        with JOB_LOCK:
            job["status"] = "error"
            job["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        with JOB_LOCK:
            BUSY = False


def _start_mvp_case(task_id: str) -> tuple[dict | None, str]:
    global BUSY
    if task_id not in MOD_TASKS:
        return None, "The task must be one of MOD-01 to MOD-05."
    with JOB_LOCK:
        if BUSY:
            return None, "The previous run is still going; start the next one when it finishes."
        BUSY = True
        job = {"id": uuid.uuid4().hex[:12], "kind": "mvp", "task_id": task_id, "status": "running", "record": None, "error": ""}
        JOBS[job["id"]] = job
    threading.Thread(target=_mvp_case_worker, args=(job, task_id), daemon=True).start()
    return job, ""


CONSOLE_MODELS = ("qwen3.8-flash", "qwen3.8-max")


def _start(payload: dict) -> tuple[dict | None, str]:
    global BUSY
    model = payload.get("model") or CONSOLE_MODELS[0]
    if model not in CONSOLE_MODELS:
        return None, "The model must be qwen3.8-flash or qwen3.8-max."
    with JOB_LOCK:
        if BUSY:
            return None, "The previous run is still going; start the next one when it finishes."
        BUSY = True
        config = payload.get("configuration") or "P0"
        titles = (["Issue task"] + (["Retrieve notes"] if config == "P3" else []) + (["Outline"] if config in {"P2", "P3"} else [])
                  + ["Write answer", "Official syntax", "Repair from errors", "Read values", "Check against key", "Approval gate", "Archive"])
        blank = [_step(title, "wait", "Not reached yet.") for title in titles]
        job = {"id": uuid.uuid4().hex[:12], "status": "running", "steps": blank, "current": 0, "attempts": [], "retrieved": [],
               "requirements": "", "answer": "", "gold": "", "phase": "Issue task",
               "phase_detail": "Reading the task statement.", "error": "", "task_id": payload.get("task_id") or "new task",
               "configuration": payload.get("configuration") or "P0", "type": payload.get("type") or "",
               "cohort": "This run", "repeat": 1, "status_label": "RUNNING", "sysml_status": None,
               "engineering_status": None, "model": model, "verdict": {}, "usage": None}
        JOBS[job["id"]] = job
    threading.Thread(target=_worker, args=(payload, job), daemon=True).start()
    return job, ""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        return

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
            return
        if parsed.path == "/style.css":
            self._send(200, STYLE.read_bytes(), "text/css; charset=utf-8")
            return
        if parsed.path in STATIC:
            name, kind = STATIC[parsed.path]
            self._send(200, (ROOT / "bench" / name).read_bytes(), kind)
            return
        if parsed.path == "/api/memory":
            from bench.discover import load_memory
            self._send(200, json.dumps(load_memory(), ensure_ascii=False).encode(), "application/json; charset=utf-8")
            return
        if parsed.path == "/api/tasks":
            self._send(200, json.dumps(_tasks(), ensure_ascii=False).encode(), "application/json; charset=utf-8")
            return
        if parsed.path == "/api/cells":
            body = json.dumps([_public(row) for row in CELLS], ensure_ascii=False).encode()
            self._send(200, body, "application/json; charset=utf-8")
            return
        if parsed.path == "/api/cell":
            cell_id = parse_qs(parsed.query).get("id", [""])[0]
            row = BY_ID.get(cell_id)
            if not row:
                self._send(404, b"{}", "application/json")
                return
            body = json.dumps(_detail(row), ensure_ascii=False).encode()
            self._send(200, body, "application/json; charset=utf-8")
            return
        if parsed.path == "/api/diagram":
            from bench.model_diagram import DiagramError, render
            query = parse_qs(parsed.query)
            try:
                svg = render(query.get("run", [""])[0], query.get("view", ["connections"])[0])
            except DiagramError as exc:
                self._send(404, json.dumps({"error": str(exc)}, ensure_ascii=False).encode(), "application/json; charset=utf-8")
                return
            self._send(200, svg.read_bytes(), "image/svg+xml")
            return
        if parsed.path == "/api/facts":
            from bench.board_facts import facts
            self._send(200, json.dumps(facts(), ensure_ascii=False).encode(), "application/json; charset=utf-8")
            return
        if parsed.path == "/api/catalog":
            from bench.discover import CATALOG, budgets, brief_from
            query = parse_qs(parsed.query)
            choice = {key: (values[0] if key in {"visible_camera", "ir_camera", "computer", "uplink", "storage"} else float(values[0]))
                      for key, values in query.items() if values and values[0]}
            try:
                body = {"catalog": CATALOG, "budgets": budgets(choice), "brief": brief_from(choice)}
            except KeyError as exc:
                self._send(400, json.dumps({"error": f"Not in the catalog: {exc}"}, ensure_ascii=False).encode(), "application/json; charset=utf-8")
                return
            self._send(200, json.dumps(body, ensure_ascii=False).encode(), "application/json; charset=utf-8")
            return
        if parsed.path == "/api/discover-latest":
            latest = ROOT / "analysis" / "discover-latest.json"
            if not latest.is_file():
                self._send(404, b"{}", "application/json")
                return
            self._send(200, latest.read_bytes(), "application/json; charset=utf-8")
            return
        if parsed.path == "/api/mvp-case":
            task_id = parse_qs(parsed.query).get("task", ["MOD-05"])[0]
            latest = _mvp_case_file(task_id) if task_id in MOD_TASKS else None
            if not latest:
                self._send(404, b"{}", "application/json")
                return
            self._send(200, latest.read_bytes(), "application/json; charset=utf-8")
            return
        if parsed.path == "/api/job":
            job_id = parse_qs(parsed.query).get("id", [""])[0]
            with JOB_LOCK:
                job = JOBS.get(job_id)
                payload = dict(job) if job else None
            if not payload:
                self._send(404, b"{}", "application/json")
                return
            self._send(200, json.dumps(payload, ensure_ascii=False).encode(), "application/json; charset=utf-8")
            return
        self._send(404, b"not found", "text/plain")

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path not in {"/api/run", "/api/discover", "/api/mvp-run", "/api/approve", "/api/review-mapping"}:
            self._send(404, b"not found", "text/plain")
            return
        length = int(self.headers.get("Content-Length") or "0")
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._send(400, '{"error":"Not JSON"}'.encode(), "application/json")
            return
        if parsed.path == "/api/approve":
            from bench.discover import approve
            try:
                with JOB_LOCK:
                    result = approve(str(payload.get("run_id") or ""), str(payload.get("design") or ""))
            except ValueError as exc:
                self._send(409, json.dumps({"error": str(exc)}, ensure_ascii=False).encode(), "application/json; charset=utf-8")
                return
            self._send(200, json.dumps(result, ensure_ascii=False).encode(), "application/json; charset=utf-8")
            return
        if parsed.path == "/api/review-mapping":
            from bench.discover import review_mapping
            try:
                with JOB_LOCK:
                    result = review_mapping(str(payload.get("run_id") or ""), int(payload.get("index", -1)),
                                            str(payload.get("decision") or ""), str(payload.get("note") or ""))
            except (ValueError, TypeError) as exc:
                self._send(409, json.dumps({"error": str(exc)}, ensure_ascii=False).encode(), "application/json; charset=utf-8")
                return
            self._send(200, json.dumps(result, ensure_ascii=False).encode(), "application/json; charset=utf-8")
            return
        if parsed.path == "/api/discover":
            job, error = _start_discover(payload.get("brief") or "")
        elif parsed.path == "/api/mvp-run":
            job, error = _start_mvp_case(str(payload.get("task_id") or "MOD-05"))
        else:
            job, error = _start(payload)
        if error:
            self._send(409, json.dumps({"error": error}, ensure_ascii=False).encode(), "application/json; charset=utf-8")
            return
        self._send(200, json.dumps({"id": job["id"]}, ensure_ascii=False).encode(), "application/json; charset=utf-8")


def main() -> None:
    from bench.vector_index import check
    try:
        check()
    except (ImportError, OSError, RuntimeError) as exc:
        raise SystemExit(f"Not starting: P3 and Part 2 retrieval need the pinned MiniLM + FAISS stack. {exc}")
    server = ThreadingHTTPServer(("127.0.0.1", 8770), Handler)
    print("http://127.0.0.1:8770/", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
