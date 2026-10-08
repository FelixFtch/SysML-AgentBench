"""Sit the 27-task exam through a Langflow flow: one task per run, three repeats, scored by the frozen scorer, time and
tokens recorded. The result is a column of results page 1.3.

    python3 bench/langflow_exam.py --flow "OpenCode with memory exam"            # project 3's column (decision 035), qwen3.8-flash
    python3 bench/langflow_exam.py --flow "Langflow Agent with memory exam"      # project 4's column
    python3 bench/langflow_exam.py --flow "Langflow Agent, Pilot only exam"      # project 2's column
    python3 bench/langflow_exam.py --flow "Langflow Agent, Pilot only exam" --model "qwen3.8-27b (Ollama)"   # the same column on the local model
    python3 bench/langflow_exam.py --flow "My P1 with a checklist" --column my-p1-checklist --login tedi    # your own flow: a new column
    python3 bench/langflow_exam.py --flow "Direct model exam · P1 repair from errors" --repeats 1   # a rerun of a frozen column
    python3 bench/langflow_exam.py --flow "OpenCode in the sandbox exam" --tasks GEN-01,MOD-05       # a rerun, two tasks

Any flow shaped Chat Input → … → Chat Output can sit the exam: the task statement built as the direct candidates get it
(agents.solve._task: requirements plus the given models) is sent as the message, a fresh session per cell, and the reply is
scored here with bench.experiment.validate_and_grade (the official Pilot once, then the frozen scorer). Time is the wall
clock of the run; tokens come from the Agent's usage field on the stored message (Langflow Agent) or from the OpenCode
node's usage file. The repository's six exam-cell flows (RTRC Exam cell → steps) are the other kind: the task id is passed
as a tweak and the shell service scores the cell as it does for the results-page console.

--model puts a model on the flow's model node for this run only (a tweak; the flow file is unchanged): a cloud name, or
"<tag> (Ollama)" for a model pulled into Ollama. Without it, your own flow runs exactly as saved; the three repository
columns default to qwen3.8-flash, the model of the frozen exam. --login runs the flow as the account that owns it
(Langflow shows an account only its own flows); the password is asked for and never stored.

Output: analysis/langflow-exam-<column>-<model tag>-<stamp>/ with results.jsonl, summary.json and the answers. Results page
1.3 lists every such folder as a column (bench.batches.exam_columns), so a finished run appears on the next refresh and,
once committed, on everyone's page. A rerun of a cell flow goes to analysis/langflow-rerun-<slug>-<stamp>/ and is shown
nowhere. The frozen batches are never touched. The results page (8770) must be stopped while a flow runs a sandboxed
coding agent (OpenCode, Claude Code; pass --sandboxed for your own such flow), because the page serves answer keys. The
superuser's login token is cached in .langflow/exam-token (gitignored) because Langflow rate-limits logins.
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
sys.path.insert(0, str(ROOT / "langflow" / "flows"))    # catalog.py: the flow names, projects and files
sys.path.insert(0, str(ROOT / "langflow" / "scripts"))  # import_flows.py: pointing Run Flow cards at the tool flows

from catalog import NAMES, flow_file  # noqa: E402

BASE = f"http://127.0.0.1:{os.environ.get('LANGFLOW_PORT', '7860')}"
DB = ROOT / ".venv-langflow" / "lib" / "python3.12" / "site-packages" / "langflow" / "langflow.db"
HELD = ROOT / "bench" / "tasks" / "t4_maritime_isr" / "heldout"
TOKEN_FILE = ROOT / ".langflow" / "exam-token"
MODEL = "qwen3.8-flash"
# The local 3-bit Qwen3.8-27B (Ollama on this machine) as the model of the same three flows: --model "qwen3.8-27b (Ollama)".
# The flow files keep qwen3.8-flash; the run sends a tweak that sets the model node, so no flow changes. The batch folder is
# named langflow-exam-<column>-local27b-<stamp>, which bench/batches.py LOCAL_MATRIX reads for the local view of page 1.3.
LOCAL_MODEL = "qwen3.8-27b (Ollama)"
LOCAL_FOLDER_TAG = "local27b"
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


_LOGIN: dict = {"username": None, "password": None}  # set by --login; otherwise the superuser of .langflow/secrets.env


def _login() -> str:
    if _LOGIN["username"]:
        username, password = _LOGIN["username"], _LOGIN["password"]
    else:
        secrets = _secrets()
        username, password = secrets["LANGFLOW_SUPERUSER"], secrets["LANGFLOW_SUPERUSER_PASSWORD"]
    token = _request("POST", "/api/v1/login", form={"username": username, "password": password})["access_token"]
    if not _LOGIN["username"]:
        TOKEN_FILE.write_text(token, encoding="utf-8")
        TOKEN_FILE.chmod(0o600)
    _AUTH["token"] = token
    return token


def _token() -> str:
    """A cached login (the login route rate-limits); re-login when the cached token is refused. A --login account is
    never cached on disk."""
    if not _LOGIN["username"] and TOKEN_FILE.is_file():
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
    langflow/scripts/move_to_user.py moves them to the people's account; after that the Agent in a private copy ran with
    an empty key and every cell failed in eight seconds (2026-10-07). Set from .env as setup_assistant.py does.
    The Ollama address (the local model's provider) is checked the same way."""
    names = {item["name"] for item in _request("GET", "/api/v1/variables/", token) or []}
    if set(PROVIDER_VARIABLES) <= names and "OLLAMA_BASE_URL" in names:
        return
    from setup_assistant import MODELS, OLLAMA_URL
    from setup_knowledge import _env, _set_variable
    env = _env()
    if not set(PROVIDER_VARIABLES) <= names:
        _set_variable(token, "OPENAI_COMPATIBLE_BASE_URL", env["MVP_LLM_URL"].rsplit("/chat/completions", 1)[0], "Generic")
        _set_variable(token, "OPENAI_COMPATIBLE_API_KEY", env["MVP_LLM_API_KEY"], "Credential")
    if "OLLAMA_BASE_URL" not in names:
        _set_variable(token, "OLLAMA_BASE_URL", OLLAMA_URL, "Generic")
    _request("POST", "/api/v1/models/enabled_models", token, MODELS)
    print("The runner's login lacked provider variables (move_to_user.py moves them to the people's account); set from .env", flush=True)


def _model_tweaks(flow: dict, model: str | None) -> dict:
    """The tweak that puts `model` on the flow's model node, when a model was asked for. No --model: the flow runs as
    saved (whatever provider and model its cards hold), which is how a person examines a flow they set up on the canvas.
    A local name ("<tag> (Ollama)"): the Langflow Agent gets the Ollama provider and tag (as the local chat variant of
    build_flows.py has them), the OpenCode and RTRC cards get the name. Any other name: the Agent keeps the flow's provider
    (our files: "OpenAI Compatible", the endpoint of the Global Variables) with that model name; the cards get the name."""
    if not model:
        return {}
    from agents.llm_local import local_tag
    tweaks: dict = {}
    tag = local_tag(model)
    for node in flow["data"]["nodes"]:
        node_id, kind = node["id"], node.get("data", {}).get("type")
        template = node.get("data", {}).get("node", {}).get("template", {})
        if kind == "Agent" or node_id == "Agent-rtrc":
            current = (template.get("model") or {}).get("value") or []
            provider = "Ollama" if tag else ((current[0].get("provider") if current and isinstance(current[0], dict) else None) or "OpenAI Compatible")
            tweaks[node_id] = {"model": [{"name": tag or model, "provider": provider, "metadata": {"model_type": "llm", "tool_calling": True}}]}
        elif "model" in template and kind in {"RtrcOpenCodeAssistant", "RtrcChat", "RtrcExamCell", "RtrcStart"}:
            tweaks[node_id] = {"model": model}
    if not tweaks:
        raise SystemExit(f"{flow['name']}: no model node to point at {model!r}; run without --model to examine the flow as saved")
    return tweaks


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
    slug = next((s for s, n in NAMES.items() if n == name), None)
    if slug is None:
        raise SystemExit(f"No flow named {name!r} is visible to this login, and it is not one of the repository's flows. "
                         "Langflow shows an account only its own flows: run again with --login <the account that owns it>.")
    projects = {p["name"]: p for p in _request("GET", "/api/v1/projects/", token) or []}
    project = projects.get(RUNNER_PROJECT) or _request("POST", "/api/v1/projects/", token, {
        "name": RUNNER_PROJECT, "description": "Private copies of the exam flows for bench/langflow_exam.py (the superuser cannot run another user's flows). Same files as the six projects."})
    imported: dict[str, dict] = {}
    for item in NEEDS.get(name, []) + [slug]:
        data = json.loads(flow_file(item).read_text(encoding="utf-8"))
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


def _chat_cell(token: str, flow: dict, task_dir: Path, repeat: int, out: Path, timeout: int, column: str, model: str | None = MODEL) -> dict:
    """One task through a chat flow: the message is the statement the direct candidates get; the reply is scored here."""
    from agents.solve import _task
    from bench.experiment import validate_and_grade
    case, prompt = _task(task_dir)
    session = f"exam-{column}-{case['id']}-r{repeat}-{datetime.now(timezone.utc).strftime('%H%M%S')}"
    started = time.time()
    body = {"flow_id": flow["id"], "input_value": prompt, "mode": "background", "session_id": session}
    tweaks = _model_tweaks(flow, model)
    if tweaks:
        body["tweaks"] = tweaks
    job = _request("POST", "/api/v2/workflows", token, body, timeout=60)
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
    row = {"repeat": repeat, "task_id": case["id"], "type": case["type"], "configuration": "P-LANGFLOW", "model": model or "as saved in the flow",
           "flow": flow["name"], "job_id": job["job_id"], "job_status": final.get("status"), "session": session, "elapsed_s": elapsed,
           "tool_calls": tools, "usage": usage, "answer_file": _rel(answer_file)}
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
    parser.add_argument("--model", default=None,
                        help=f"the model to put on the flow's model node for this run: {MODEL} (the model of the frozen exam; the default for the three "
                             f"columns of decision 035), {LOCAL_MODEL} (the 3-bit model on this machine), '<tag> (Ollama)' for another Ollama model, or any "
                             "cloud model name. Omit it for your own flow to examine the flow exactly as saved (its own provider and model).")
    parser.add_argument("--column", default=None,
                        help="for a flow that is not one of the repository's: the column id it gets on results page 1.3 (letters, digits, dashes), "
                             "e.g. my-p1-checklist. The three repository columns have fixed ids: agent-pilot, opencode-memory, agent-memory.")
    parser.add_argument("--login", default=None,
                        help="the Langflow account that owns the flow (the password is asked for and never stored); default: the superuser of "
                             ".langflow/secrets.env, who sees only its own flows and private copies of the repository's")
    parser.add_argument("--sandboxed", action="store_true",
                        help="your flow runs a sandboxed coding agent (OpenCode / Claude Code card): the results page must be stopped first")
    args = parser.parse_args()
    if args.login:
        import getpass
        _LOGIN["username"], _LOGIN["password"] = args.login, getpass.getpass(f"Langflow password for {args.login}: ")
    own_flow = args.flow not in COLUMNS and args.flow not in CELL_FLOWS
    if own_flow:
        if not args.column:
            raise SystemExit(f"{args.flow!r} is not one of the repository's flows; give it a column id with --column <id> (it becomes a column of results page 1.3)")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*", args.column):
            raise SystemExit("--column: letters, digits and dashes only")
        if args.column in {"agent-pilot", "opencode-memory", "agent-memory"}:
            raise SystemExit(f"--column {args.column} is one of the repository's column ids; choose another")
    elif args.column and args.column != COLUMNS.get(args.flow):
        raise SystemExit(f"{args.flow!r} has the fixed column id {COLUMNS.get(args.flow) or '(a cell flow, no column)'}; --column is for your own flows")
    if args.model and args.flow in CELL_FLOWS:
        raise SystemExit(f"--model is for chat flows; the cell flows {list(CELL_FLOWS)} take their model from the cell node")
    sandboxed = args.sandboxed or "sandbox" in CELL_FLOWS.get(args.flow, "") or args.flow == NAMES["opencode-memory-exam"]
    if sandboxed and _page_running():
        raise SystemExit("The results page (8770) is running and serves answer keys; stop it before an OpenCode or sandboxed run")
    from bench.experiment import load_env
    load_env()
    token = _token()
    _ensure_provider(token)
    flow = _flow(token, args.flow)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    column = COLUMNS.get(args.flow) or (args.column if own_flow else None)
    # The three repository columns default to the frozen exam's model so their folders stay comparable; a person's own
    # flow defaults to "as saved", which is what they built on the canvas.
    model = args.model or (MODEL if args.flow in COLUMNS else None)
    from bench.batches import model_tag as _model_tag
    model_tag = _model_tag(model) if model else "flow"
    out = Path(args.out) if args.out else ROOT / "analysis" / (f"langflow-exam-{column}-{model_tag}-{stamp}" if column else f"langflow-rerun-{CELL_FLOWS[args.flow]}-{stamp}")
    out.mkdir(parents=True, exist_ok=True)
    tasks = _tasks(args.tasks)
    results = out / "results.jsonl"
    done = {(row["task_id"], row["repeat"]) for row in (json.loads(line) for line in results.read_text(encoding="utf-8").splitlines() if line.strip())} if results.is_file() else set()
    summary = {"flow": args.flow, "flow_id": flow["id"], "column": column, "model": model or "as saved in the flow", "model_tag": model_tag,
               "login": args.login or "superuser", "started": stamp, "repeats": args.repeats,
               "tasks": [item["id"] for item in tasks], "scored_by": "bench.experiment.validate_and_grade (frozen scorer)" if column else "the shell service's exam cell",
               "model_tweaks": _model_tweaks(flow, model) if column else {},
               "note": (("Not part of the frozen score (bench/FREEZE.md); a Langflow exam column of decision 035." if not own_flow
                         else "Not part of the frozen score (bench/FREEZE.md); a person's own flow examined with bench/langflow_exam.py --column.") if column
                        else "A rerun of a frozen column through Langflow; shown nowhere.")
                       + (" The model was set on the model node by a run-time tweak; the flow file is unchanged." if model and model != MODEL else "")
                       + (" The flow ran as saved, with its own provider and model." if not model else "")}
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
                    row = _chat_cell(token, flow, task_dir, repeat, out, args.timeout, column, model) if column else _cell_flow_cell(token, flow, task_dir, repeat, out, args.timeout)
                    if _key_failure(row):
                        # A provider variable set moments ago is not always seen by the very next run; one more try, then stop
                        # rather than record a column of empty failures. The batch resumes from this cell when run again.
                        time.sleep(10)
                        row = _chat_cell(token, flow, task_dir, repeat, out, args.timeout, column, model) if column else _cell_flow_cell(token, flow, task_dir, repeat, out, args.timeout)
                        if _key_failure(row):
                            raise SystemExit(f"{item['id']} r{repeat}: the flow's model ran without an API key; the row is not recorded. "
                                             f"Check the runner's login has {' and '.join(PROVIDER_VARIABLES)} (Settings → Model Providers) and run again. "
                                             f"Langflow said: {(row.get('error') or row.get('reason') or '')[:300]}")
                except urllib.error.HTTPError as exc:
                    body = exc.read()[:400].decode("utf-8", "replace")
                    if exc.code == 401:
                        raise SystemExit(f"{item['id']} r{repeat}: Langflow refused the login even after logging in again (HTTP 401 {body}); "
                                         "the row is not recorded. Run again; the batch resumes from this cell.")
                    row = {"repeat": repeat, "task_id": item["id"], "type": item["type"], "configuration": "P-LANGFLOW" if column else None, "model": model,
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
