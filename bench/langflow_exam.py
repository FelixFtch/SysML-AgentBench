"""Sit the 27-task exam through a Langflow flow (decision 035): one task per run, three repeats, scored by the frozen
scorer, time and tokens recorded.

    python3 bench/langflow_exam.py --flow "OpenCode with memory exam"            # project 3, a new column on page 1.3
    python3 bench/langflow_exam.py --flow "Langflow Agent with memory exam"      # project 4, a new column
    python3 bench/langflow_exam.py --flow "Langflow Agent, Pilot only exam"      # project 2, a new column
    python3 bench/langflow_exam.py --flow "Direct model exam · P1 repair from errors" --repeats 1   # a rerun of a frozen column
    python3 bench/langflow_exam.py --flow "OpenCode in the sandbox exam" --tasks GEN-01,MOD-05       # a rerun, two tasks

Two kinds of flow:
- a chat flow (Chat Input → agent → Chat Output): the task statement built as the direct candidates get it (agents.solve._task:
  requirements plus the given models) is sent as the message, a fresh session per cell, and the reply is scored here with
  bench.experiment.validate_and_grade (the official Pilot once, then the frozen scorer). Time is the wall clock of the run;
  tokens come from the Agent's usage field on the stored message (Langflow Agent) or from the OpenCode node's usage file.
- an exam-cell flow (RTRC Exam cell → steps): the task id is passed as a tweak and the shell service scores the cell as it
  does for the results-page console; the row it returns is kept.

Output: analysis/langflow-exam-<column>-qwen3.8-flash-<stamp>/ (a new column of results page 1.3, read by bench/batches.py
LANGFLOW_COHORTS) or analysis/langflow-rerun-<slug>-<stamp>/ (a rerun of a frozen column; shown nowhere, kept as a record).
Each folder holds results.jsonl, summary.json and the answers. The frozen batches are never touched. The results page
(8770) must be stopped while a sandboxed or OpenCode flow runs; the runner refuses to start otherwise. The login token is
cached in .langflow/exam-token (gitignored) because Langflow rate-limits logins.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import socket
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "langflow" / "flows"))

from catalog import NAMES  # noqa: E402

BASE = f"http://127.0.0.1:{os.environ.get('LANGFLOW_PORT', '7860')}"
DB = ROOT / ".venv-langflow" / "lib" / "python3.12" / "site-packages" / "langflow" / "langflow.db"
HELD = ROOT / "bench" / "tasks" / "t4_maritime_isr" / "heldout"
TOKEN_FILE = ROOT / ".langflow" / "exam-token"
MODEL = "qwen3.8-flash"
# Chat flows that are columns of page 1.3: flow name -> (column id, folder prefix)
COLUMNS = {NAMES["langflow-agent-pilot-exam"]: "agent-pilot", NAMES["opencode-memory-exam"]: "opencode-memory", NAMES["langflow-agent-memory-exam"]: "agent-memory"}
CELL_FLOWS = {NAMES[s]: s for s in ("direct-exam-p0", "direct-exam-p1", "direct-exam-p2", "direct-exam-p3", "sandbox-exam-opencode", "sandbox-exam-claude-code")}
USAGE_DIR = Path(os.environ.get("RTRC_ASSISTANT_EXAM_HOME", Path.home() / ".rtrc-assistant-exam")) / "usage"


def _secrets() -> dict:
    values = {}
    for line in (ROOT / ".langflow" / "secrets.env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("'\"")
    return values


_AUTH: dict = {"token": None}  # the live login; replaced on a 401, since Langflow's access token expires during a run of hours


def _request(method: str, path: str, token: str | None = None, body=None, form: dict | None = None, timeout: int = 120, retry: bool = True):
    headers = {"Accept": "application/json"}
    data = None
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {_AUTH['token'] or token}"
    request = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        # The access token expired in the middle of a run (2026-10-07: thirty cells recorded as "HTTP 401 Token has
        # expired"); log in again once and repeat the request. The probe in _token() runs before a login is held and
        # must see its 401 itself.
        if exc.code == 401 and token and retry and _AUTH["token"] is not None:
            _login()
            return _request(method, path, token, body, form, timeout, retry=False)
        raise
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return json.loads(raw) if raw else None


def _login() -> str:
    secrets = _secrets()
    token = _request("POST", "/api/v1/login", form={"username": secrets["LANGFLOW_SUPERUSER"], "password": secrets["LANGFLOW_SUPERUSER_PASSWORD"]})["access_token"]
    TOKEN_FILE.write_text(token, encoding="utf-8")
    TOKEN_FILE.chmod(0o600)
    _AUTH["token"] = token
    return token


def _token() -> str:
    """A cached login (the login route rate-limits); re-login when the cached token is refused."""
    if TOKEN_FILE.is_file():
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
        try:
            _request("GET", "/api/v1/users/whoami", token)
            _AUTH["token"] = token
            return token
        except urllib.error.HTTPError:
            pass
    return _login()


RUNNER_PROJECT = "RTRC exam runner (admin)"
# What a private copy of an exam flow needs imported first: the shared tool flows its Run Flow cards point at.
NEEDS = {NAMES["langflow-agent-pilot-exam"]: ["tool-validate-sysml"], NAMES["langflow-agent-memory-exam"]: ["tool-validate-sysml", "tool-memory-search"]}
PROVIDER_VARIABLES = ("OPENAI_COMPATIBLE_BASE_URL", "OPENAI_COMPATIBLE_API_KEY")
# What Langflow's Agent reports when its provider variable is missing: the "OpenAI Compatible" provider allows no key and
# sends the placeholder EMPTY, so the endpoint refuses and the job ends in seconds with no reply.
KEY_ERRORS = ("Incorrect API key", "API key is required")


def _ensure_provider(token: str) -> None:
    """The runner's login needs the Qwen provider variables of its own. Langflow keeps them per user, and
    langflow/flows/move_to_user.py moves them to the people's account; after that the Agent in a private copy ran with
    an empty key and every cell failed in eight seconds (2026-10-07). Set from .env as setup_assistant.py does."""
    names = {item["name"] for item in _request("GET", "/api/v1/variables/", token) or []}
    if set(PROVIDER_VARIABLES) <= names:
        return
    from setup_assistant import MODELS, OLLAMA_URL
    from setup_knowledge import _env, _set_variable
    env = _env()
    _set_variable(token, "OPENAI_COMPATIBLE_BASE_URL", env["MVP_LLM_URL"].rsplit("/chat/completions", 1)[0], "Generic")
    _set_variable(token, "OPENAI_COMPATIBLE_API_KEY", env["MVP_LLM_API_KEY"], "Credential")
    _set_variable(token, "OLLAMA_BASE_URL", OLLAMA_URL, "Generic")
    _request("POST", "/api/v1/models/enabled_models", token, MODELS)
    print("The runner's login had no Qwen provider variables (move_to_user.py moves them to the people's account); set from .env", flush=True)


def _key_failure(row: dict) -> bool:
    text = f"{row.get('error') or ''} {row.get('reason') or ''}"
    return row.get("status") != "PASS" and any(marker in text for marker in KEY_ERRORS)


def _flow(token: str, name: str) -> dict:
    """The flow by name as this login sees it. Langflow shows a user only its own flows, and the superuser the runner logs
    in as cannot run a flow owned by the account people use (FLOW_NOT_FOUND), so when the flow is not visible a private copy
    of the same flow file is imported into the superuser's project RUNNER_PROJECT and run there; it is the same JSON."""
    visible = {f["name"]: f for f in _request("GET", "/api/v1/flows/?get_all=true&header_flows=true", token) or []}
    if name in visible:
        return _request("GET", f"/api/v1/flows/{visible[name]['id']}", token)
    from import_flows import _point_run_flow_cards
    slug = next(s for s, n in NAMES.items() if n == name)
    projects = {p["name"]: p for p in _request("GET", "/api/v1/projects/", token) or []}
    project = projects.get(RUNNER_PROJECT) or _request("POST", "/api/v1/projects/", token, {
        "name": RUNNER_PROJECT, "description": "Private copies of the exam flows for bench/langflow_exam.py (the superuser cannot run another user's flows). Same files as the six projects."})
    imported: dict[str, dict] = {}
    for item in NEEDS.get(name, []) + [slug]:
        data = json.loads((ROOT / "langflow" / "flows" / f"{item}.json").read_text(encoding="utf-8"))
        _point_run_flow_cards(data, imported)
        payload = {"name": data["name"], "description": data["description"], "data": data["data"], "endpoint_name": None,
                   "tags": data.get("tags") or [], "folder_id": project["id"]}
        saved = _request("PATCH", f"/api/v1/flows/{visible[data['name']]['id']}", token, payload) if data["name"] in visible else _request("POST", "/api/v1/flows/", token, payload)
        imported[data["name"]] = saved
        visible[data["name"]] = saved
        print(f"private copy in {RUNNER_PROJECT}: {data['name']}", flush=True)
    return _request("GET", f"/api/v1/flows/{imported[name]['id']}", token)


def _page_running() -> bool:
    with socket.socket() as probe:
        probe.settimeout(0.3)
        return probe.connect_ex(("127.0.0.1", 8770)) == 0


def _tasks(selected: str) -> list[dict]:
    items = [json.loads(line) for line in (HELD / "index.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    if selected and selected != "all":
        wanted = {t.strip() for t in selected.split(",") if t.strip()}
        items = [item for item in items if item["id"] in wanted]
        missing = wanted - {item["id"] for item in items}
        if missing:
            raise SystemExit(f"Unknown task id(s): {sorted(missing)}")
    return items


def _job_status(job_id: str) -> tuple[str | None, str | None]:
    """The job's status and error from Langflow's own database (read-only); the status route answers 500 while a run is
    in flight, so the table is polled and the route is read once the job has ended."""
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    row = con.execute("SELECT status, error FROM job WHERE job_id = ?", (job_id.replace("-", ""),)).fetchone()
    con.close()
    return (row[0], row[1]) if row else (None, None)


def _wait(token: str, job_id: str, limit: int) -> dict:
    started = time.time()
    while time.time() - started < limit:
        time.sleep(4)
        status, error = _job_status(job_id)
        if status in {"completed", "failed", "cancelled", "suspended"}:
            try:
                job = _request("GET", f"/api/v2/workflows?job_id={job_id}", token, timeout=60)
            except urllib.error.HTTPError as exc:
                job = {"status": status, "errors": [{"error": f"status route HTTP {exc.code}"}] + ([{"error": str(error)[:600]}] if error else [])}
            job.setdefault("status", status)
            if error and not job.get("errors"):
                job["errors"] = [{"error": str(error)[:600]}]
            return job
    return {"status": "timeout"}


def _stored_message(session: str, flow_id: str) -> dict:
    """The AI message of the flow in a session from Langflow's database (read-only): its text, tool calls and the Agent's
    usage field. A sub-flow run as a tool stores its own message under the same session, so the flow id is required."""
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    row = con.execute("SELECT text, content_blocks, properties FROM message WHERE session_id=? AND sender='Machine' AND replace(flow_id, '-', '')=? "
                      "ORDER BY timestamp DESC LIMIT 1", (session, flow_id.replace("-", ""))).fetchone()
    con.close()
    if not row:
        return {"text": "", "tool_calls": [], "usage": {}}
    tools = []
    for block in json.loads(row[1] or "[]"):
        for content in block.get("contents", []):
            if content.get("type") == "tool_use":
                tools.append(content.get("name"))
    properties = json.loads(row[2] or "{}") if isinstance(row[2], str) else (row[2] or {})
    usage = properties.get("usage") or {}
    return {"text": row[0] or "", "tool_calls": tools,
            "usage": {"input": usage.get("input_tokens") or 0, "cached": 0, "output": usage.get("output_tokens") or 0} if usage else {}}


def _opencode_usage(session: str) -> dict:
    path = USAGE_DIR / f"{re.sub(r'[^A-Za-z0-9_.-]', '_', session)}.json"
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {"usage": {"input": data.get("input") or 0, "cached": data.get("cached") or 0, "output": data.get("output") or 0, "calls": data.get("calls") or 0},
            "tool_calls": data.get("tool_calls") or [], "opencode_seconds": data.get("seconds")}


def _rel(path: Path) -> str:
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def _chat_cell(token: str, flow: dict, task_dir: Path, repeat: int, out: Path, timeout: int, column: str) -> dict:
    """One task through a chat flow: the message is the statement the direct candidates get; the reply is scored here."""
    from agents.solve import _task
    from bench.experiment import validate_and_grade
    case, prompt = _task(task_dir)
    session = f"exam-{column}-{case['id']}-r{repeat}-{datetime.now(timezone.utc).strftime('%H%M%S')}"
    started = time.time()
    job = _request("POST", "/api/v2/workflows", token, {"flow_id": flow["id"], "input_value": prompt, "mode": "background", "session_id": session}, timeout=60)
    final = _wait(token, job["job_id"], timeout)
    elapsed = round(time.time() - started, 1)
    stored = _stored_message(session, flow["id"])
    text = stored["text"] or ((final.get("output") or {}).get("text") or "")
    extra = _opencode_usage(session) if column == "opencode-memory" else {}
    usage = extra.get("usage") or stored["usage"]
    tools = extra.get("tool_calls") or stored["tool_calls"]
    answer_file = out / "answers" / f"{case['id']}-r{repeat}.md"
    answer_file.parent.mkdir(parents=True, exist_ok=True)
    answer_file.write_text(text, encoding="utf-8")
    row = {"repeat": repeat, "task_id": case["id"], "type": case["type"], "configuration": "P-LANGFLOW", "model": MODEL, "flow": flow["name"],
           "job_id": job["job_id"], "job_status": final.get("status"), "session": session, "elapsed_s": elapsed, "tool_calls": tools, "usage": usage,
           "answer_file": _rel(answer_file)}
    if final.get("status") != "completed" or not text:
        row.update({"status": "FAIL", "sysml_status": None, "engineering_status": "FAIL",
                    "reason": f"The Langflow job ended {final.get('status')} " + ("with no reply." if not text else "."), "error": json.dumps((final.get("errors") or [])[:2])[:600]})
        return row
    scored = validate_and_grade(task_dir, text, label=f"langflow-{column}-{case['id']}", workspace=out / "graded" / f"{case['id']}-r{repeat}")
    row.update({key: scored.get(key) for key in ("status", "sysml_status", "engineering_status", "engine_run", "reason", "run_dir")})
    row["run_dir"] = str(row["run_dir"]) if row.get("run_dir") else None
    return row


def _cell_flow_cell(token: str, flow: dict, task_dir: Path, repeat: int, out: Path, timeout: int) -> dict:
    """One task through an exam-cell flow: the task id as a tweak; the shell service scores it and the step nodes show it."""
    started = time.time()
    # A tweak on the cell node replaces its values, so every preset of the flow file is sent with the task id (a tweak of the
    # task id alone ran the component's defaults).
    cell = next(node for node in flow["data"]["nodes"] if node["id"] == "RtrcExamCell-cell")["data"]["node"]["template"]
    tweaks = {"RtrcExamCell-cell": {**{key: cell[key]["value"] for key in ("mode", "cell", "approach", "agent", "model")}, "task_id": task_dir.name}}
    job = _request("POST", "/api/v2/workflows", token, {"flow_id": flow["id"], "input_value": "", "mode": "background", "tweaks": tweaks,
                                                        "session_id": f"rerun-{task_dir.name}-r{repeat}-{datetime.now(timezone.utc).strftime('%H%M%S')}"}, timeout=60)
    final = _wait(token, job["job_id"], timeout)
    elapsed = round(time.time() - started, 1)
    # The shell service saves the scored cell under analysis/langflow-console/<stamp>-<task>-...json; the newest one for this
    # task written after the job started is the record (the flow's terminal output is only the last step's text).
    record = {}
    console = ROOT / "analysis" / "langflow-console"
    for path in sorted(console.glob(f"*-{task_dir.name}-*.json"), reverse=True):
        if path.stat().st_mtime >= started - 1:
            record = json.loads(path.read_text(encoding="utf-8"))
            record["console_file"] = _rel(path)
            break
    answer_file = out / "answers" / f"{task_dir.name}-r{repeat}.md"
    answer_file.parent.mkdir(parents=True, exist_ok=True)
    answer_file.write_text(str(record.get("answer") or ""), encoding="utf-8")
    usage = record.get("usage") or {}
    if usage.get("by_model"):  # the direct run's usage summary: per-model prompt/completion tokens
        slots = usage["by_model"].values()
        usage = {"input": sum(s.get("prompt_tokens") or 0 for s in slots), "cached": sum(s.get("cached_tokens") or 0 for s in slots),
                 "output": sum(s.get("completion_tokens") or 0 for s in slots), "calls": usage.get("calls") or 0}
    return {"repeat": repeat, "task_id": task_dir.name, "type": record.get("type"), "configuration": record.get("configuration"), "model": record.get("model") or MODEL,
            "flow": flow["name"], "job_id": job["job_id"], "job_status": final.get("status"), "elapsed_s": elapsed,
            "status": record.get("status_label") or record.get("status") or ("FAIL" if final.get("status") != "completed" else None),
            "sysml_status": record.get("sysml_status"), "engineering_status": record.get("engineering_status"), "repair_rounds": record.get("repair_rounds"),
            "usage": usage, "seconds_in_shell": record.get("seconds"), "tool_calls": [t.get("tool") for t in record.get("tool_trace") or []],
            "console_file": record.get("console_file"),
            "reason": (record.get("reason") or (record.get("verdict") or {}).get("reason")
                       or next((step.get("detail") for step in record.get("steps") or [] if step.get("state") == "fail"), None)) if record
            else f"The Langflow job ended {final.get('status')} without the cell record.",
            "answer_file": _rel(answer_file)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--flow", required=True, help="the Langflow flow name, e.g. 'OpenCode with memory exam'")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--tasks", default="all", help="all, or a comma-separated list of task ids")
    parser.add_argument("--timeout", type=int, default=1800, help="seconds to wait for one run")
    parser.add_argument("--out", default=None, help="the batch folder (default: a new one under analysis/)")
    args = parser.parse_args()
    if args.flow not in COLUMNS and args.flow not in CELL_FLOWS:
        raise SystemExit(f"--flow must be one of {list(COLUMNS) + list(CELL_FLOWS)}")
    sandboxed = "sandbox" in CELL_FLOWS.get(args.flow, "") or args.flow == NAMES["opencode-memory-exam"]
    if sandboxed and _page_running():
        raise SystemExit("The results page (8770) is running and serves answer keys; stop it before an OpenCode or sandboxed run")
    from bench.experiment import load_env
    load_env()
    token = _token()
    _ensure_provider(token)
    flow = _flow(token, args.flow)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    column = COLUMNS.get(args.flow)
    out = Path(args.out) if args.out else ROOT / "analysis" / (f"langflow-exam-{column}-{MODEL}-{stamp}" if column else f"langflow-rerun-{CELL_FLOWS[args.flow]}-{stamp}")
    out.mkdir(parents=True, exist_ok=True)
    tasks = _tasks(args.tasks)
    results = out / "results.jsonl"
    done = {(row["task_id"], row["repeat"]) for row in (json.loads(line) for line in results.read_text(encoding="utf-8").splitlines() if line.strip())} if results.is_file() else set()
    summary = {"flow": args.flow, "flow_id": flow["id"], "column": column, "model": MODEL, "started": stamp, "repeats": args.repeats,
               "tasks": [item["id"] for item in tasks], "scored_by": "bench.experiment.validate_and_grade (frozen scorer)" if column else "the shell service's exam cell",
               "note": "Not part of the frozen score (bench/FREEZE.md); a Langflow exam column of decision 035." if column else "A rerun of a frozen column through Langflow; shown nowhere."}
    (out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    shown = str(out.relative_to(ROOT)) if out.is_relative_to(ROOT) else str(out)
    print(f"{args.flow}: {len(tasks)} task(s) × {args.repeats} → {shown}", flush=True)
    with results.open("a", encoding="utf-8") as handle:
        for repeat in range(1, args.repeats + 1):
            for item in tasks:
                if (item["id"], repeat) in done:
                    continue
                task_dir = ROOT / item["path"]
                try:
                    row = _chat_cell(token, flow, task_dir, repeat, out, args.timeout, column) if column else _cell_flow_cell(token, flow, task_dir, repeat, out, args.timeout)
                    if _key_failure(row):
                        # A provider variable set moments ago is not always seen by the very next run; one more try, then stop
                        # rather than record a column of empty failures. The batch resumes from this cell when run again.
                        time.sleep(10)
                        row = _chat_cell(token, flow, task_dir, repeat, out, args.timeout, column) if column else _cell_flow_cell(token, flow, task_dir, repeat, out, args.timeout)
                        if _key_failure(row):
                            raise SystemExit(f"{item['id']} r{repeat}: the flow's model ran without an API key; the row is not recorded. "
                                             f"Check the runner's login has {' and '.join(PROVIDER_VARIABLES)} (Settings → Model Providers) and run again. "
                                             f"Langflow said: {(row.get('error') or row.get('reason') or '')[:300]}")
                except urllib.error.HTTPError as exc:
                    body = exc.read()[:400].decode("utf-8", "replace")
                    if exc.code == 401:
                        raise SystemExit(f"{item['id']} r{repeat}: Langflow refused the login even after logging in again (HTTP 401 {body}); "
                                         "the row is not recorded. Run again; the batch resumes from this cell.")
                    row = {"repeat": repeat, "task_id": item["id"], "type": item["type"], "configuration": "P-LANGFLOW" if column else None, "model": MODEL,
                           "flow": args.flow, "status": "FAIL", "sysml_status": None, "engineering_status": "FAIL", "error": f"HTTP {exc.code} {body}", "elapsed_s": None}
                row.setdefault("cohort_id", column)
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                handle.flush()
                usage = row.get("usage") or {}
                print(f"  r{repeat} {item['id']}: {row.get('status')} · {row.get('elapsed_s')} s · {usage.get('input', 0)} in / {usage.get('output', 0)} out · {len(row.get('tool_calls') or [])} tool call(s)"
                      + (f" · {row.get('reason') or row.get('error')}" if row.get("status") != "PASS" else ""), flush=True)
    rows = [json.loads(line) for line in results.read_text(encoding="utf-8").splitlines() if line.strip()]
    passed = sum(1 for row in rows if row.get("status") == "PASS")
    summary.update({"finished": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S"), "n": len(rows), "pass": passed,
                    "seconds_total": round(sum(row.get("elapsed_s") or 0 for row in rows), 1),
                    "tokens": {"input": sum((row.get("usage") or {}).get("input") or 0 for row in rows), "output": sum((row.get("usage") or {}).get("output") or 0 for row in rows)}})
    (out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"done: {passed}/{len(rows)} pass · {summary['seconds_total']} s · {summary['tokens']['input']} in / {summary['tokens']['output']} out tokens → {shown}")


if __name__ == "__main__":
    main()
