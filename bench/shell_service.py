"""The RTRC shell service: the existing pipeline behind a small local JSON API for the Langflow nodes
(plans/langflow-shell-plan.md). Each step calls the code the results page uses (bench/discover.py,
bench/exam_board.py, bench/model_diagram.py, agents/external), so a Langflow run and a page run give the same
retrieval, prompts, Pilot results and checks, and write the same records.

    python3 bench/shell_service.py            # 127.0.0.1:8781, token from .langflow/secrets.env

No answer key is served: exam details are the page's cell detail without the key text. Every request except
GET /health and GET /diagram needs the header X-RTRC-Token; the token is read from the secrets file and never
put into the environment, so sandboxed agents started from here cannot see it. Sandboxed agents are refused
while the results page (127.0.0.1:8770, which serves answer keys) is running.

Main flow (run = the record id, as on page 2.3): /run/start, /run/retrieve, /run/requirements, /run/design
(new: A literal, B alternative) or /run/adapt (reuse: A adapts the similar project, B is written new),
/run/validate, /run/align, /run/checks, /run/tradeoffs, /run/review (diagrams, Cameo export, approval text;
saves the record), /run/approve, /run/decision. /run/start with "replay" replays a saved run without model calls.
Other flows: /memory, /exam/cells, /exam/cell, /exam/run, /exam/agent-cell, /exam/agent-run, /chat/turn (the chat
versions of projects 1 and 2: a person's words, a conversation that continues; bench/chat_turns.py), /chat/forget, /facts,
/mod/case, /mod/run, /cameo/export, /cameo/result, /gate/decision, /diagram.
"""
from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bench.discover import VARIANT_A, VARIANT_B  # noqa: E402
from bench.experiment import load_env  # noqa: E402

HOST, PORT = "127.0.0.1", 8781
PAGE_PORT = 8770
SECRETS = ROOT / ".langflow" / "secrets.env"
SESSIONS_DIR = ROOT / "analysis" / "langflow-runs"
CONSOLE_DIR = ROOT / "analysis" / "langflow-console"
CAMEO_DIR = ROOT / "analysis" / "cameo-exports"
HELD = ROOT / "bench" / "tasks" / "t4_maritime_isr" / "heldout"
MODELS = ("qwen3.8-flash", "qwen3.8-max", "qwen3.8-27b (Ollama)", "qwen3.8-27b local")
AGENTS = ("direct", "claude-code", "opencode")
LOCAL_MODELS = {"qwen3.8-27b (Ollama)", "qwen3.8-27b local"}  # served by Ollama on this machine; direct or OpenCode (decision 032)
LOCAL_REFUSED = "The local 3-bit model runs with Qwen direct or OpenCode; a Claude Code exam still uses the cloud Qwen."
VARIANT_ADAPT = ("Design A: adapt the similar existing project. Start from its model: keep its structure, part names and port names "
                 "where they fit the brief; change only what the requirements need; add what is missing; leave out what the brief does not need. "
                 "Every number must come from the requirements, and a stated limit is never changed.")
SESSIONS: dict[str, dict] = {}
LOCK = threading.Lock()
AGENT_LOCK = threading.Lock()


def _token() -> str:
    if not SECRETS.is_file():
        raise SystemExit("Missing .langflow/secrets.env; run python3 scripts/langflow_secrets.py")
    for line in SECRETS.read_text(encoding="utf-8").splitlines():
        if line.startswith("RTRC_SHELL_TOKEN="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("RTRC_SHELL_TOKEN is missing from .langflow/secrets.env")


class StepError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _page_running() -> bool:
    with socket.socket() as probe:
        probe.settimeout(0.3)
        return probe.connect_ex(("127.0.0.1", PAGE_PORT)) == 0


# ---------- sessions (one per main-flow run) ----------

def _save_session(session: dict) -> None:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    (SESSIONS_DIR / f"{session['id']}.json").write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")


def _session(run_id: str) -> dict:
    if not re.fullmatch(r"\d{8}T\d{6}", run_id or ""):
        raise StepError(f"Not a run id: {run_id!r}")
    with LOCK:
        if run_id not in SESSIONS:
            path = SESSIONS_DIR / f"{run_id}.json"
            if not path.is_file():
                raise StepError(f"No such run: {run_id}")
            SESSIONS[run_id] = json.loads(path.read_text(encoding="utf-8"))
        return SESSIONS[run_id]


def _step(session: dict, name: str, work):
    """Time one step, collect its model usage, store the session, and return work()'s result."""
    from agents.llm import MODEL_OVERRIDE, USAGE_LOG
    calls: list[dict] = []
    started, wall = time.monotonic(), _now()
    usage_token = USAGE_LOG.set(calls)
    model_token = MODEL_OVERRIDE.set(session["model"])
    try:
        result = work()
    finally:
        USAGE_LOG.reset(usage_token)
        MODEL_OVERRIDE.reset(model_token)
        session["calls"].extend(calls)
        session["record"].setdefault("langflow", {}).setdefault("timings", {})[name] = {
            "started": wall, "seconds": round(time.monotonic() - started, 1), "model_calls": len(calls)}
        _save_session(session)
    return result


def _replayed(session: dict, key: str):
    return (session.get("source_record") or {}).get(key)


def run_start(body: dict) -> dict:
    from bench.discover import CATALOG, brief_from
    replay = (body.get("replay") or "").strip()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    while (SESSIONS_DIR / f"{stamp}.json").exists() or (ROOT / "analysis" / f"discover-{stamp}.json").exists():
        time.sleep(1)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    session = {"id": stamp, "mode": "live", "calls": [], "written": {}, "log": []}
    if replay:
        name = "discover-latest.json" if replay == "latest" else f"discover-{replay}.json"
        path = ROOT / "analysis" / name
        if not path.is_file():
            raise StepError(f"No saved run {replay!r} to replay")
        source = json.loads(path.read_text(encoding="utf-8"))
        session.update({"mode": "replay", "source_record": source, "agent": "replay", "model": "replay"})
        session["record"] = {"id": stamp, "brief": source.get("brief", ""), "synthetic": True,
                             "langflow": {"replay_of": source.get("id"), "mode": "replay"}}
    else:
        agent = body.get("agent") or "direct"
        model = body.get("model") or MODELS[0]
        if agent not in AGENTS or model not in MODELS:
            raise StepError(f"Agent must be one of {AGENTS} and model one of {MODELS} (Qwen only for now)")
        if model in LOCAL_MODELS and agent == "claude-code":
            raise StepError(LOCAL_REFUSED)
        brief = (body.get("brief") or "").strip() or brief_from(CATALOG["default"])
        if len(brief) < 20:
            raise StepError("Write at least one full sentence for the brief")
        session.update({"agent": agent, "model": model})
        session["record"] = {"id": stamp, "brief": brief, "synthetic": True,
                             "langflow": {"mode": "live", "agent": agent, "model": model, "started": _now()}}
    folder = ROOT / "mvp" / "exam-inbox" / f"discover-{stamp}"
    folder.mkdir(parents=True, exist_ok=True)
    session["folder"] = str(folder)
    with LOCK:
        SESSIONS[stamp] = session
    _save_session(session)
    record = session["record"]
    mode = "replay of " + record["langflow"]["replay_of"] if session["mode"] == "replay" else f"live · agent {session['agent']} · {session['model']}"
    return {"run": stamp, "summary": f"run {stamp} · {mode}\n\nBrief:\n{record['brief']}", "data": {"brief": record["brief"], "mode": session["mode"]}}


def _similar_project(retrieval: dict) -> dict | None:
    """The project the reuse branch starts from: the best-scoring approved design among the retrieved seeds,
    otherwise MaritimeISR when the retrieval found reusable values there."""
    from bench.discover import MARITIME_FILE, load_memory
    seeds = sorted((node for node in retrieval.get("nodes", []) if node.get("role") == "seed"), key=lambda node: -node.get("score", 0))
    memory = {f"approved {entry['run_id']}·{entry['design']}": entry for entry in load_memory()}
    for node in seeds:
        entry = memory.get(node.get("source", ""))
        if entry and entry.get("source") and (ROOT / entry["source"]).is_file():
            return {"name": node["source"], "path": entry["source"], "package": entry["package"], "brief": entry.get("brief", "")}
    if retrieval.get("path") == "reuse":
        return {"name": "MaritimeISR", "path": str(MARITIME_FILE.relative_to(ROOT)), "package": "MaritimeISR", "brief": ""}
    return None


def run_retrieve(body: dict) -> dict:
    from bench.discover import retrieve_existing
    session = _session(body.get("run"))
    record = session["record"]

    def work():
        if session["mode"] == "replay":
            return _replayed(session, "retrieval") or {}
        try:
            return retrieve_existing(record["brief"])
        except Exception as exc:  # same fallback as bench.discover.run: the run continues as a new design
            return {"nodes": [], "edges": [], "cards": [], "numbers": {}, "path": "new", "sources": [],
                    "error": f"{type(exc).__name__}: {exc}", "note": "Retrieval did not finish."}

    retrieval = _step(session, "retrieve", work)
    record["retrieval"] = retrieval
    similar = _similar_project(retrieval)
    path = "reuse" if similar else "new"
    record["langflow"]["path"] = path
    record["langflow"]["similar_project"] = similar
    _save_session(session)
    seeds = [node for node in retrieval.get("nodes", []) if node.get("role") == "seed"]
    lines = [f"{path} · run {session['id']}",
             f"① Memory: {retrieval.get('library_size', 0)} cards; {len(retrieval.get('nodes', []))} retrieved "
             f"({len(seeds)} seeds, {len(retrieval.get('nodes', [])) - len(seeds)} one-hop neighbours); {retrieval.get('note', '')}"]
    if similar:
        lines.append(f"Similar project: {similar['name']} ({similar['path']})")
    lines += [f"  seed {node['short']} · {node['type']} · score {node.get('score', 0):.2f} · {node.get('source')}" for node in seeds[:6]]
    return {"run": session["id"], "summary": "\n".join(lines), "path": path,
            "data": {"path": path, "similar_project": similar, "retrieval": retrieval}}


def run_requirements(body: dict) -> dict:
    from bench.discover import write_requirements
    session = _session(body.get("run"))
    record = session["record"]
    req = _step(session, "requirements", lambda: _replayed(session, "requirements") if session["mode"] == "replay" else write_requirements(record["brief"]))
    record["requirements"] = req
    _save_session(session)
    path = record.get("langflow", {}).get("path") or "new"
    similar = record.get("langflow", {}).get("similar_project")
    lines = [f"{path} · run {session['id']}" + (f" · similar project {similar['name']}" if similar else " · no similar project: a new design"),
             f"② {len(req.get('requirements', []))} requirements, {len(req.get('questions', []))} questions; "
             + (f"{len(req['unsourced'])} carry numbers that are not in the brief (blocks approval)" if req.get("unsourced") else "every number is in the brief")]
    lines += [f"  {item.get('id')}: {item.get('text')}" for item in req.get("requirements", [])]
    lines += [f"  question: {item}" for item in req.get("questions", [])]
    return {"run": session["id"], "summary": "\n".join(lines), "data": req}


def _agent_design(session: dict, key: str, task_text: str) -> dict:
    """One design written by a sandboxed coding agent on Qwen (agents/external): the scored batches' sandbox,
    AGENTS.md and ./validate; the answer is answer.md, else the final message."""
    if _page_running():
        raise StepError("The results page is running and serves answer keys; stop it before running a sandboxed agent")
    folder = Path(session["folder"]) / f"agent-{key}"
    (folder / "input").mkdir(parents=True, exist_ok=True)
    (folder / "input" / "requirements.md").write_text(task_text, encoding="utf-8")
    with AGENT_LOCK:
        if session["agent"] == "opencode":
            from agents.external.opencode_run import run_opencode
            previous = os.environ.get("MVP_LLM_MODEL")
            os.environ["MVP_LLM_MODEL"] = session["model"]
            try:
                solved = run_opencode(folder)
            finally:
                if previous is None:
                    os.environ.pop("MVP_LLM_MODEL", None)
                else:
                    os.environ["MVP_LLM_MODEL"] = previous
            text, workspace = solved["text"], solved["workspace"]
        else:
            from bench.run_claude_qwen import run_claude
            run = run_claude(folder, model=session["model"], max_turns=60, timeout=900, label="langflow")
            text, workspace = run["text"], str(run["workspace"])
    return {"text": text, "workspace": workspace}


def _write(session: dict, key: str, variant: str, baseline: dict | None) -> dict:
    from bench.discover import DESIGN_RULES, write_design
    from agents.llm_local import chat  # dispatches to agents.llm.chat for the cloud models, to Ollama for the local one
    record = session["record"]
    requirements = record["requirements"]["requirements"]
    cards = record["retrieval"].get("cards")
    if baseline is None and session["agent"] == "direct":
        return write_design(record["brief"], requirements, f"Design{key}", variant, cards)
    listing = "\n".join(f"{item.get('id')}: {item.get('text')}" for item in requirements)
    contract = "\n".join(f"attribute {q['name']} : Real = {float(q['value']):g};  // {item.get('id')}"
                         for item in requirements for q in [item.get("quantity") or {}] if q.get("name") and q.get("value") is not None) or "(none)"
    base_text = (ROOT / baseline["path"]).read_text(encoding="utf-8") if baseline else ""
    instruction = (f"Package name: Design{key}. Write one SysML v2 package that satisfies these requirements. "
                   "Structure: one top-level part usage for the vessel; inside it one part usage per device; ports and connect statements between devices. "
                   "The checker reads only these exact attribute declarations, each placed inside the part usage it belongs to "
                   "(powerLimitW, uplinkMbps, uploadMbps, storageGB, dataRateMbps, retentionHours on the vessel part; drawW on each powered device part):\n"
                   f"{contract}\nUse these attribute names verbatim. Do not rename them. Do not write attributes inside requirement usages. "
                   f"Add one requirement def per requirement id with a doc comment quoting that id. Variant: {variant}")
    body = f"Mission brief:\n{record['brief']}\n\nRequirements:\n{listing}\n\n"
    if baseline:
        body += (f"The similar existing project to start from ({baseline['name']}, package {baseline['package']}; "
                 f"rename the package to Design{key}; do not import the original):\n```sysml\n{base_text}\n```\n\n")
    elif cards:
        body += "Related elements already in the existing maritime model (for naming consistency; do not import them):\n" + "\n".join(cards) + "\n\n"
    messages = [{"role": "system", "content": DESIGN_RULES}, {"role": "user", "content": body + instruction}]
    parts = [{"key": "rules", "label": "Rules", "paper": "p3", "text": DESIGN_RULES},
             {"key": "contract", "label": "Template · attribute contract", "paper": "p3", "text": contract},
             ({"key": "baseline", "label": f"Similar project to adapt · {baseline['name']}", "paper": "p2", "text": base_text} if baseline else
              {"key": "examples", "label": "Examples · retrieved existing elements", "paper": "p2", "text": "\n".join(cards or []) or "(no retrieval results)"}),
             {"key": "task", "label": "Brief + requirements", "paper": "", "text": f"{record['brief']}\n\n{listing}"},
             {"key": "variant", "label": "What this variant must do", "paper": "", "text": variant}]
    if session["agent"] == "direct":
        reply = chat(messages)
        return {"text": reply["text"], "model": reply.get("model"), "usage": reply.get("usage"), "messages": messages, "prompt_parts": parts}
    task_text = (body + instruction + f"\n\nWrite the package Design{key} in a ```sysml block in answer.md. "
                 f"Before answering, check it with ./validate Design{key} <your file>.")
    produced = _agent_design(session, key, task_text)
    return {"text": produced["text"], "model": f"{session['agent']} on {session['model']}", "usage": None,
            "messages": messages, "prompt_parts": parts, "agent_workspace": produced["workspace"]}


def _designs(body: dict, adapt: bool) -> dict:
    session = _session(body.get("run"))
    record = session["record"]
    if "requirements" not in record or "retrieval" not in record:
        raise StepError("Run ① Search memory and ② Requirements first")
    similar = record["langflow"].get("similar_project") if adapt else None
    if adapt and not similar:
        raise StepError("No similar project was found; the new-design branch applies")

    def work():
        if session["mode"] == "replay":
            return {item["key"]: {"replayed": True} for item in _replayed(session, "designs") or []}
        plan = [("A", VARIANT_ADAPT, similar), ("B", VARIANT_B, None)] if adapt else [("A", VARIANT_A, None), ("B", VARIANT_B, None)]
        return {key: _write(session, key, variant, base) for key, variant, base in plan}

    written = _step(session, "adapt" if adapt else "design", work)
    session["written"] = written
    record["langflow"]["branch"] = "reuse" if adapt else "new"
    _save_session(session)
    lines = [f"run {session['id']}", "③ " + ("A adapts " + similar["name"] + "; B is written new" if adapt else "A follows the brief literally; B uses another arrangement")
             + f" · agent {session.get('agent')} · {session.get('model')}"]
    for key, item in written.items():
        if item.get("replayed"):
            lines.append(f"  Design {key}: replayed from run {record['langflow'].get('replay_of')}")
        else:
            lines.append(f"  Design {key}: {len(item.get('text', ''))} characters written by {item.get('model')}")
    return {"run": session["id"], "summary": "\n".join(lines),
            "data": {key: {k: v for k, v in item.items() if k != "messages"} for key, item in written.items()}}


def run_validate(body: dict) -> dict:
    from bench.discover import _validate_design, parsed_numbers, simulate
    session = _session(body.get("run"))
    record = session["record"]

    def progress(key: str, state: str, detail: str) -> None:
        session["log"].append({"at": _now(), "step": key, "state": state, "detail": detail})

    def work():
        if session["mode"] == "replay":
            return _replayed(session, "designs") or []
        designs = []
        for key, written in sorted(session["written"].items()):
            design = _validate_design(key, written, Path(session["folder"]), progress)
            if design["sysml_status"] == "PASS":
                numbers, connections, names = parsed_numbers(Path(design["run_dir"]))
                design.update({"numbers": numbers, "connections": connections, "elements": names,
                               "checks": simulate(numbers, connections, [dict(item) for item in record["requirements"]["requirements"]])})
            else:
                design["checks"] = [{"id": "SYNTAX", "label": "Official syntax", "status": "FAIL", "detail": "The parse failed, so nothing was computed."}]
            if written.get("agent_workspace"):
                design["agent_workspace"] = written["agent_workspace"]
            designs.append(design)
        return designs

    designs = _step(session, "validate", work)
    record["designs"] = designs
    _save_session(session)
    lines = [f"run {session['id']}", "④ Official SysML v2 Pilot, with repair from errors (≤ 20)"]
    for design in designs:
        lines.append(f"  Design {design['key']}: {design['sysml_status']} after {len(design.get('attempts', []))} parse(s), "
                     f"{design.get('repair_rounds', 0)} repair(s)")
        for attempt in design.get("attempts", []):
            first = (attempt.get("diagnostics") or [{}])[0].get("message", "") if attempt["status"] != "PASS" else ""
            lines.append(f"    attempt {attempt['attempt']}: {attempt['status']}{' · ' + first[:140] if first else ''}"
                         f"{' · same as the previous version' if attempt.get('same_as_previous') else ''}")
    return {"run": session["id"], "summary": "\n".join(lines),
            "data": [{k: v for k, v in design.items() if k not in {"source"}} for design in designs]}


def run_align(body: dict) -> dict:
    from bench.discover import align
    session = _session(body.get("run"))
    record = session["record"]
    designs = record.get("designs") or []

    def work():
        if session["mode"] == "replay":
            return _replayed(session, "alignment") or {}
        first = designs[0] if designs else {}
        if first.get("sysml_status") == "PASS" and record["retrieval"].get("nodes"):
            try:
                return align(session["id"], first, Path(first["path"]), record["retrieval"])
            except Exception as exc:
                return {"mappings": [], "verified": 0, "proposed": 0, "error": f"{type(exc).__name__}: {exc}"}
        return {"mappings": [], "verified": 0, "proposed": 0, "note": "Design A failed the parse or retrieval found nothing; alignment skipped."}

    alignment = _step(session, "align", work)
    record["alignment"] = alignment
    _save_session(session)
    package = alignment.get("package") or {}
    lines = [f"run {session['id']}", f"⑤ Alignment with MaritimeISR (paper 1): {alignment.get('proposed', 0)} pairs proposed, "
             f"{alignment.get('verified', 0)} with both names present, {alignment.get('declared', 0)} declared; "
             f"package {package.get('name', '—')} official Pilot {package.get('sysml_status', 'not generated')}"]
    lines += [f"  {row.get('design')} → {row.get('existing')} · {row.get('construct') or 'not declared'}"
              + (f" · {row['refused']}" if row.get("refused") else "") for row in alignment.get("mappings", [])]
    if alignment.get("note") or alignment.get("error"):
        lines.append("  " + (alignment.get("note") or alignment.get("error")))
    return {"run": session["id"], "summary": "\n".join(lines), "data": alignment}


def run_checks(body: dict) -> dict:
    from bench.discover import approval_block, numbers_in, read_back
    session = _session(body.get("run"))
    record = session["record"]
    designs = record.get("designs") or []

    def work():
        if session["mode"] == "replay":
            return designs
        brief_numbers = numbers_in(record["brief"])
        for design in designs:
            if design["sysml_status"] == "PASS":
                design["read_back"] = read_back(design["source"])["text"]
                design["read_back_numbers"] = {value: value in numbers_in(design["read_back"]) for value in sorted(brief_numbers, key=float)}
        return designs

    _step(session, "checks", work)
    failing = sorted({check["label"] for design in designs for check in design.get("checks", []) if check["status"] == "FAIL"})
    eligible = [design["key"] for design in designs if not approval_block(record, design)]
    record["langflow"]["failing"] = failing
    record["langflow"]["eligible"] = eligible
    _save_session(session)
    verdict = "pass" if eligible and not failing else "fail"
    lines = [f"{verdict} · run {session['id']}", f"⑥ Checks on numbers read from the official parse; read-back (paper 3 query)"]
    for design in designs:
        lines.append(f"  Design {design['key']}: " + ", ".join(f"{check['id']} {check['status']}" + (f" ({check.get('actual')} / {check.get('limit')} {check.get('unit', '')})" if check.get("limit") is not None else "")
                                                       for check in design.get("checks", []) if check["id"] != "CONNECT"))
        missed = [value for value, said in (design.get("read_back_numbers") or {}).items() if not said]
        if design.get("read_back"):
            lines.append(f"    read-back: {'every brief number restated' if not missed else 'missing ' + ', '.join(missed)}")
    lines.append(f"  eligible for approval: {', '.join(eligible) or 'none'}" + (f" · failing: {', '.join(failing)}" if failing else ""))
    return {"run": session["id"], "summary": "\n".join(lines), "verdict": verdict,
            "data": {"failing": failing, "eligible": eligible,
                     "designs": [{k: design.get(k) for k in ("key", "checks", "read_back", "read_back_numbers", "numbers")} for design in designs]}}


def run_tradeoffs(body: dict) -> dict:
    from bench.discover import propose_tradeoffs
    session = _session(body.get("run"))
    record = session["record"]
    failing = record["langflow"].get("failing") or []

    def work():
        if session["mode"] == "replay":
            return _replayed(session, "tradeoffs") or {"proposals": []}
        if not failing:
            return {"proposals": []}
        try:
            return propose_tradeoffs(record["brief"], failing)
        except Exception as exc:
            return {"proposals": [], "error": f"{type(exc).__name__}: {exc}"}

    tradeoffs = _step(session, "tradeoffs", work)
    record["tradeoffs"] = tradeoffs
    _save_session(session)
    lines = [f"run {session['id']}", f"Trade-offs for: {', '.join(failing) or 'nothing failed'} (catalog parts only; code recomputes each)"]
    for index, item in enumerate(tradeoffs.get("proposals", []), 1):
        lines.append(f"  {index}. {item.get('title') or json.dumps(item.get('choice', {}))} · "
                     f"{'feasible' if item.get('feasible') else 'not feasible'} when code recomputes it · {item.get('rationale', '')[:160]}")
    if tradeoffs.get("error"):
        lines.append(f"  No proposals: {tradeoffs['error']}")
    return {"run": session["id"], "summary": "\n".join(lines), "data": tradeoffs}


def _diagram_link(run_id: str | None, view: str = "connections") -> str:
    return f"http://{HOST}:{PORT}/diagram?run={run_id}&view={view}" if run_id else ""


def _cameo_export(session: dict, design: dict) -> str | None:
    if design.get("sysml_status") != "PASS" or not design.get("source"):
        return None
    folder = CAMEO_DIR / session["id"]
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"Design{design['key']}.sysml"
    path.write_text(design["source"], encoding="utf-8")
    return str(path.relative_to(ROOT))


def run_review(body: dict) -> dict:
    """Diagrams, the Cameo export and the approval text; saves the record so page 2.3 shows it and approval works."""
    from agents.llm import usage_summary
    from bench.discover import approval_block
    from bench.model_diagram import DiagramError, render
    session = _session(body.get("run"))
    record = session["record"]
    designs = record.get("designs") or []
    record["usage"] = usage_summary(session["calls"])
    eligible = record["langflow"].get("eligible") or []
    req = record.get("requirements") or {}
    if req.get("unsourced"):
        record["gate"] = {"answer": "needs-person", "eligible": [], "effect": "The requirements contain numbers that are not in the brief. Nothing can go into memory until a person supplies them."}
    elif eligible:
        record["gate"] = {"answer": "awaiting-person", "eligible": eligible,
                          "effect": f"Design{'s' if len(eligible) > 1 else ''} {', '.join(eligible)} pass{'' if len(eligible) > 1 else 'es'} all four checks and may be approved into memory by a person."}
    else:
        record["gate"] = {"answer": "awaiting-person", "eligible": [],
                          "effect": "No design passes all four checks, so none can go into memory. Pick a trade-off and send the brief back."}
    lines = [f"run {session['id']} · review for a person", f"Brief: {record['brief']}", ""]
    for design in designs:
        last = (design.get("attempts") or [{}])[-1]
        link = ""
        if design.get("sysml_status") == "PASS" and last.get("run_id"):
            try:
                render(last["run_id"], "connections")
                link = _diagram_link(last["run_id"])
            except DiagramError as exc:
                link = f"(diagram not drawn: {exc})"
        design["diagram"] = link
        design["cameo_export"] = _cameo_export(session, design) if session["mode"] == "live" else None
        reason = approval_block(record, design)
        lines.append(f"Design {design['key']}: official Pilot {design['sysml_status']} after {len(design.get('attempts', []))} parse(s); "
                     + ", ".join(f"{check['id']} {check['status']}" for check in design.get("checks", []) if check["id"] != "CONNECT"))
        lines.append(f"  approval: {'eligible' if not reason else reason}")
        if link:
            lines.append(f"  ⑦ diagram: {link}")
        if design.get("cameo_export"):
            lines.append(f"  Cameo: export ready at {design['cameo_export']} (open it in Cameo's SysML v2 when RTRC provides the license)")
    alignment = record.get("alignment") or {}
    lines.append(f"Alignment: {alignment.get('verified', 0)}/{alignment.get('proposed', 0)} pairs verified; package {(alignment.get('package') or {}).get('sysml_status', 'not generated')}")
    for index, item in enumerate((record.get("tradeoffs") or {}).get("proposals", []), 1):
        lines.append(f"Trade-off {index}: {item.get('title') or ''} · {'feasible' if item.get('feasible') else 'not feasible'} when code recomputes it")
    lines.append(f"Gate: {record['gate']['effect']}")
    record["langflow"]["review"] = {"at": _now(), "text": "\n".join(lines)}
    if session["mode"] == "live":
        text = json.dumps(record, ensure_ascii=False, indent=2)
        (ROOT / "analysis" / f"discover-{session['id']}.json").write_text(text, encoding="utf-8")
        (ROOT / "analysis" / "discover-latest.json").write_text(text, encoding="utf-8")
    _save_session(session)
    return {"run": session["id"], "summary": "\n".join(lines),
            "data": {"gate": record["gate"], "diagrams": {d["key"]: d.get("diagram") for d in designs},
                     "cameo_exports": {d["key"]: d.get("cameo_export") for d in designs}}}


def run_approve(body: dict) -> dict:
    from bench.discover import approve
    session = _session(body.get("run"))
    key = (body.get("key") or "").upper()
    if session["mode"] != "live":
        return {"run": session["id"], "summary": f"run {session['id']} · replay: approving design {key} changes no memory", "data": {"approved": False}}
    try:
        result = approve(session["id"], key)
        outcome = {"approved": True, "memory_size": len(result["memory"])}
        text = f"Design {key} approved into memory ({len(result['memory'])} designs now); the next run's retrieval can find it."
    except ValueError as exc:
        outcome = {"approved": False, "reason": str(exc)}
        text = f"Design {key} not approved: {exc}"
    session["record"]["langflow"].setdefault("approvals", []).append({"design": key, **outcome, "at": _now()})
    _save_session(session)
    return {"run": session["id"], "summary": f"run {session['id']}\n{text}", "data": outcome}


def run_decision(body: dict) -> dict:
    """⑨ The person's decision, the grades and the times: one record per run (the same record page 2.3 shows)."""
    session = _session(body.get("run"))
    record = session["record"]
    decision = body.get("decision") or "unknown"
    lf = record["langflow"]
    lf["decision"] = {"action": decision, "note": (body.get("note") or "")[:500], "at": _now()}
    lf["finished"] = _now()
    timings = lf.get("timings", {})
    designs = record.get("designs") or []
    lf["grades"] = {
        "branch": lf.get("branch"), "path": lf.get("path"),
        "designs": {d["key"]: {"official_pilot": d.get("sysml_status"), "parses": len(d.get("attempts", [])),
                               "first_pass_attempt": d.get("first_pass_attempt"),
                               "checks": {c["id"]: c["status"] for c in d.get("checks", []) if c["id"] != "CONNECT"},
                               "read_back_complete": all((d.get("read_back_numbers") or {"-": False}).values())} for d in designs},
        "alignment": {"proposed": (record.get("alignment") or {}).get("proposed"), "verified": (record.get("alignment") or {}).get("verified"),
                      "package": ((record.get("alignment") or {}).get("package") or {}).get("sysml_status")},
        "eligible": lf.get("eligible"), "approved": [a["design"] for a in lf.get("approvals", []) if a.get("approved")],
        "seconds": round(sum(item["seconds"] for item in timings.values()), 1),
        "model_calls": sum(item.get("model_calls", 0) for item in timings.values()),
    }
    from agents.llm import usage_summary
    record["usage"] = usage_summary(session["calls"])
    usd = 0.0
    try:
        from bench.board_facts import PRICES
        for name, slot in (record["usage"].get("by_model") or {}).items():
            price = PRICES["models"].get(name.split(",")[-1]) or PRICES["models"].get(session.get("model"), {})
            if price:
                fresh = max((slot.get("prompt_tokens") or 0) - (slot.get("cached_tokens") or 0), 0)
                usd += (fresh * price["input"] + (slot.get("cached_tokens") or 0) * price["cache"] + (slot.get("completion_tokens") or 0) * price["output"]) / 1e6
    except Exception:
        pass
    lf["grades"]["usd"] = round(usd, 4)
    if session["mode"] == "live":
        text = json.dumps(record, ensure_ascii=False, indent=2)
        path = ROOT / "analysis" / f"discover-{session['id']}.json"
        if path.is_file():
            saved = json.loads(path.read_text(encoding="utf-8"))
            for key in ("approvals", "cameo"):
                if saved.get(key):
                    record[key] = saved[key]
            text = json.dumps(record, ensure_ascii=False, indent=2)
        path.write_text(text, encoding="utf-8")
        latest = ROOT / "analysis" / "discover-latest.json"
        if not latest.is_file() or json.loads(latest.read_text(encoding="utf-8")).get("id") == session["id"]:
            latest.write_text(text, encoding="utf-8")
    _save_session(session)
    where = (f"saved; page 2.3 shows run {session['id']}" if session["mode"] == "live"
             else f"replay of run {lf.get('replay_of')}; kept in analysis/langflow-runs, not on page 2.3")
    lines = [f"run {session['id']} · decision: {decision}", f"⑨ Grades and times ({where})"]
    for key, grade in lf["grades"]["designs"].items():
        lines.append(f"  Design {key}: Pilot {grade['official_pilot']} (parses {grade['parses']}) · "
                     + ", ".join(f"{k} {v}" for k, v in grade["checks"].items()) + f" · read-back {'complete' if grade['read_back_complete'] else 'incomplete'}")
    lines.append(f"  approved into memory: {', '.join(lf['grades']['approved']) or 'none'}")
    lines += [f"  {name}: {item['seconds']} s, {item.get('model_calls', 0)} model call(s)" for name, item in timings.items()]
    lines.append(f"  total {lf['grades']['seconds']} s, {lf['grades']['model_calls']} model calls, about ${lf['grades']['usd']:.4f} at the list price")
    return {"run": session["id"], "summary": "\n".join(lines), "data": lf["grades"]}


def _saved_record(run_id: str) -> tuple[Path, dict]:
    if not re.fullmatch(r"\d{8}T\d{6}", run_id or ""):
        raise StepError(f"Not a run id: {run_id!r}")
    path = ROOT / "analysis" / f"discover-{run_id}.json"
    if not path.is_file():
        raise StepError(f"No saved run {run_id}; a run is saved at its review step")
    return path, json.loads(path.read_text(encoding="utf-8"))


def cameo_export(body: dict) -> dict:
    """Writes a saved run's officially parsed designs as .sysml files for Cameo's SysML v2 edition."""
    path, record = _saved_record(body.get("run"))
    folder = CAMEO_DIR / record["id"]
    folder.mkdir(parents=True, exist_ok=True)
    lines, files = [f"run {record['id']} · Cameo export"], {}
    for design in record.get("designs", []):
        if design.get("sysml_status") == "PASS" and design.get("source"):
            target = folder / f"Design{design['key']}.sysml"
            target.write_text(design["source"], encoding="utf-8")
            files[design["key"]] = str(target.relative_to(ROOT))
            lines.append(f"  Design {design['key']}: {files[design['key']]} (official Pilot PASS)")
        else:
            lines.append(f"  Design {design['key']}: not exported, the official parse did not pass")
    lines += ["Open each file in Cameo's SysML v2 edition and check that it loads without errors; then pick the result.",
              "Until RTRC provides the license, pick \"Not checked yet\". The official Pilot stays the judge."]
    return {"run": record["id"], "summary": "\n".join(lines), "data": {"files": files}}


def gate_decision(body: dict) -> dict:
    """A person's choice at a stop-and-ask gate (a stated limit may only change with a person's approval)."""
    entry = {"gate": str(body.get("gate") or "")[:100], "choice": str(body.get("choice") or "")[:100],
             "context": str(body.get("context") or "")[:2000], "at": _now()}
    with (ROOT / "analysis" / "langflow-gates.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return {"summary": f"Gate \"{entry['gate']}\": {entry['choice']} (a person's decision, recorded at {entry['at']})", "data": entry}


def cameo_result(body: dict) -> dict:
    """Stores a person's Cameo check on the saved run (and on its Langflow session, if there is one)."""
    path, record = _saved_record(body.get("run"))
    entry = {"design": (body.get("key") or "A").upper(), "result": body.get("result") or "", "note": (body.get("note") or "")[:500], "at": _now()}
    record.setdefault("cameo", []).append(entry)
    text = json.dumps(record, ensure_ascii=False, indent=2)
    path.write_text(text, encoding="utf-8")
    latest = ROOT / "analysis" / "discover-latest.json"
    if latest.is_file() and json.loads(latest.read_text(encoding="utf-8")).get("id") == record["id"]:
        latest.write_text(text, encoding="utf-8")
    if (SESSIONS_DIR / f"{record['id']}.json").is_file():
        session = _session(record["id"])
        session["record"].setdefault("cameo", []).append(entry)
        _save_session(session)
    return {"run": record["id"], "summary": f"run {record['id']} · Cameo check of design {entry['design']}: {entry['result']}"
            + (f" · {entry['note']}" if entry["note"] else ""), "data": entry}


# ---------- other flows ----------

def memory(_: dict) -> dict:
    """F0: the library the agent searches: MaritimeISR plus every approved design, as cards from the official parse."""
    from bench.discover import _library, load_memory
    cards, neighbors, kinds, source_of, sources = _library()
    rows = []
    for ident, text in cards.items():
        parts = text.split(" ")
        doc = text.split("doc: ", 1)[1] if "doc: " in text else ""
        rows.append({"id": ident, "type": parts[0], "name": parts[1] if len(parts) > 1 else "", "source": source_of.get(ident, ""),
                     "links": len(neighbors.get(ident, ())), "documentation": doc, "text": text})
    lines = [f"F0 memory: {len(cards)} cards in {len(sources)} source(s); {sum(len(v) for v in neighbors.values()) // 2} links",
             *[f"  {source['label']}: {source['cards']} cards ({source['path']})" for source in sources],
             f"Approved designs in memory: {len(load_memory())}"]
    return {"summary": "\n".join(lines), "data": {"sources": sources, "rows": rows}}


def _strip_keys(detail: dict) -> dict:
    return {key: value for key, value in detail.items() if key not in {"gold"}}


def _board():
    import bench.exam_board as board
    return board


def _retry_rows() -> list[dict]:
    rows = []
    for folder in sorted((ROOT / "analysis").glob("retry-*-qwen3.8-max-*")):
        results = folder / "results.jsonl"
        if not results.is_file():
            continue
        agent = "opencode" if "-opencode-" in folder.name else "claude"
        for line in results.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                row.update({"id": f"retry-{agent}:{row['repeat']}:{row['task_id']}", "cohort": f"Retry · {agent} · qwen3.8-max",
                            "cohort_id": f"retry-{agent}", "batch": folder.name, "model": "qwen3.8-max"})
                rows.append(row)
    return rows


def exam_cells(_: dict) -> dict:
    board = _board()
    rows = list(board.CELLS) + _retry_rows()
    cells = [{"id": row["id"], "cohort": row.get("cohort"), "task_id": row["task_id"], "configuration": row.get("configuration"),
              "repeat": row.get("repeat"), "status": row.get("status")} for row in rows]
    return {"summary": f"{len(cells)} graded cells: " + ", ".join(f"{name} {sum(1 for c in cells if c['cohort'] == name)}" for name in dict.fromkeys(c["cohort"] for c in cells)),
            "data": cells}


def _find_cell(cell_id: str) -> dict:
    board = _board()
    row = board.BY_ID.get(cell_id) or next((row for row in _retry_rows() if row["id"] == cell_id), None)
    if not row:
        raise StepError(f"No such cell: {cell_id!r}")
    return row


def _tool_trace(workspace: str | None) -> list[dict]:
    """The agent's tool calls, from OpenCode's step events or Claude Code's stream-json, in order."""
    if not workspace:
        return []
    work = Path(workspace).parent
    steps = []
    for name in ("stdout.jsonl", "stdout.json"):
        path = work / name
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            part = event.get("part") or {}
            if part.get("type") == "tool":
                state = part.get("state") if isinstance(part.get("state"), dict) else {}
                steps.append({"tool": part.get("tool"), "status": state.get("status"), "target": str(state.get("title") or "")[:160]})
            for block in ((event.get("message") or {}).get("content") or []) if event.get("type") == "assistant" else []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    target = json.dumps(block.get("input"), ensure_ascii=False)[:160]
                    steps.append({"tool": block.get("name"), "status": "called", "target": target})
        break
    return steps


def exam_cell(body: dict) -> dict:
    board = _board()
    row = _find_cell(body.get("id") or "")
    detail = _strip_keys(board._detail(row))
    detail["tool_trace"] = _tool_trace(row.get("workspace"))
    detail["validate_calls"] = row.get("validate_calls")
    detail["elapsed_s"] = row.get("elapsed_s")
    attempts = detail.get("attempts") or []
    lines = [f"{row['id']} · {row.get('cohort')} · task verdict {row.get('status')} · official syntax {row.get('sysml_status') or 'n/a'}"]
    lines += [f"  {step.get('title')}: {step.get('state')} · {str(step.get('detail') or '')[:160]}" for step in detail.get("steps", [])]
    if attempts:
        lines.append(f"  {len(attempts)} official parse(s); last {attempts[-1].get('status')}; diagram {_diagram_link(attempts[-1].get('run_id'))}")
    if detail["tool_trace"]:
        lines.append(f"  {len(detail['tool_trace'])} tool call(s) by the agent")
    return {"summary": "\n".join(lines), "data": detail}


def exam_run(body: dict) -> dict:
    """F1 live: one sealed task with one approach, exactly as the page console runs it; the key is used only to score."""
    from agents.llm import MODEL_OVERRIDE, USAGE_LOG, usage_summary
    board = _board()
    task_id, config, model = body.get("task_id") or "", body.get("configuration") or "P0", body.get("model") or MODELS[0]
    task_dir = HELD / task_id
    if not (task_dir / "case.yaml").is_file() or config not in {"P0", "P1", "P2", "P3"} or model not in MODELS:
        raise StepError("Need a sealed task id, an approach P0–P3 and a Qwen model")
    job = {"id": "langflow", "status": "running", "steps": [], "current": 0, "attempts": [], "retrieved": [], "requirements": "",
           "answer": "", "gold": "", "phase": "", "phase_detail": "", "error": "", "task_id": task_id, "configuration": config,
           "type": "", "cohort": "Langflow run", "repeat": 1, "status_label": "RUNNING", "sysml_status": None,
           "engineering_status": None, "model": model, "verdict": {}, "usage": None}
    calls: list[dict] = []
    usage_token, model_token = USAGE_LOG.set(calls), MODEL_OVERRIDE.set(model)
    started = time.monotonic()
    try:
        board._execute(task_dir, config, job)
    finally:
        USAGE_LOG.reset(usage_token)
        MODEL_OVERRIDE.reset(model_token)
    job["usage"] = usage_summary(calls)
    job["seconds"] = round(time.monotonic() - started, 1)
    result = _strip_keys(job)
    CONSOLE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    (CONSOLE_DIR / f"{stamp}-{task_id}-{config}-{model}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [f"{task_id} · {config} · {model} · task verdict {job.get('status_label')} · {job['seconds']} s (not added to any score)"]
    lines += [f"  {step.get('title')}: {step.get('state')} · {str(step.get('detail') or '')[:160]}" for step in job.get("steps", [])]
    return {"summary": "\n".join(lines), "data": result}


def exam_agent_run(body: dict) -> dict:
    """F2 live: one sealed task by a sandboxed coding agent on Qwen, with the scored batches' limits (15 min; Claude Code 60 turns)."""
    from bench.experiment import validate_and_grade
    task_id, agent, model = body.get("task_id") or "", body.get("agent") or "opencode", body.get("model") or MODELS[1]
    task_dir = HELD / task_id
    if model in LOCAL_MODELS and agent == "claude-code":
        raise StepError(LOCAL_REFUSED)
    if not (task_dir / "case.yaml").is_file() or agent not in {"opencode", "claude-code"} or model not in MODELS:
        raise StepError("Need a sealed task id, agent opencode or claude-code, and a Qwen model")
    if _page_running():
        raise StepError("The results page is running and serves answer keys; stop it before running a sandboxed agent")
    started = time.monotonic()
    with AGENT_LOCK:
        if agent == "opencode":
            from agents.external.opencode_run import run_opencode
            previous = os.environ.get("MVP_LLM_MODEL")
            os.environ["MVP_LLM_MODEL"] = model
            try:
                solved = run_opencode(task_dir)
            finally:
                if previous is None:
                    os.environ.pop("MVP_LLM_MODEL", None)
                else:
                    os.environ["MVP_LLM_MODEL"] = previous
            from bench.run_opencode import usage_from_log
            text, workspace, returncode = solved["text"], solved["workspace"], solved["returncode"]
            usage = usage_from_log(Path(workspace).parent / "stdout.jsonl")  # tokens of the run, as the scored batches read them
        else:
            from bench.run_claude_qwen import run_claude, usage_of
            run = run_claude(task_dir, model=model, max_turns=60, timeout=900, label="langflow-agent")
            text, workspace, returncode, usage = run["text"], str(run["workspace"]), run["returncode"], usage_of(run["result"])
    scored = validate_and_grade(task_dir, text, label=f"langflow-{agent}-{task_id}", workspace=Path(workspace).parent / "graded")
    board = _board()
    configuration = "P-CODE" if agent == "opencode" else "P-CODE-2"
    row = {"id": f"langflow-{agent}:1:{task_id}:{configuration}", "cohort": "Langflow run", "model": model, "task_id": task_id,
           "type": next((task["type"] for task in board._tasks() if task["id"] == task_id), None), "configuration": configuration,
           "repeat": 1, "status": scored.get("status"), "engineering_status": scored.get("engineering_status"),
           "sysml_status": scored.get("sysml_status"), "engine_run": scored.get("engine_run"), "workspace": workspace, "usage": usage}
    result = _strip_keys(board._detail(row))
    result.update({"agent": agent, "returncode": returncode, "seconds": round(time.monotonic() - started, 1),
                   "reason": scored.get("reason"), "tool_trace": _tool_trace(workspace)})
    CONSOLE_DIR.mkdir(parents=True, exist_ok=True)
    saved = CONSOLE_DIR / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-{task_id}-{agent}-{model}.json"
    for step in result.get("steps", []):
        if step.get("title") == "Archive":
            step["detail"] = f"Saved in {saved.relative_to(ROOT)} (a Langflow run, not added to any score)."
    saved.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [f"{task_id} · {agent} on {model} · task verdict {result['status']} · official syntax {result['sysml_status'] or 'n/a'} · {result['seconds']} s",
             f"  {len(result['tool_trace'])} tool call(s) in the sandbox (not added to any score)"]
    lines += [f"  {step.get('title')}: {step.get('state')} · {str(step.get('detail') or '')[:160]}" for step in result.get("steps", [])]
    return {"summary": "\n".join(lines), "data": result}


# ---------- the chat versions of projects 1 and 2 (decision 036): a person's words, a conversation that continues ----------

def chat_turn(body: dict) -> dict:
    """One message of a person to a direct approach (P0 to P3) or to a sandboxed coding agent, in the conversation of the
    Langflow session; the reply, parsed by the official Pilot only when it holds a model. Nothing is scored."""
    from bench import chat_turns
    text = str(body.get("text") or "").strip()
    candidate, model = str(body.get("candidate") or "direct-P1"), body.get("model") or MODELS[0]
    session = str(body.get("session") or "default")
    if not text:
        raise StepError("Write a message")
    if model not in MODELS:
        raise StepError(f"model must be one of {MODELS}")
    if candidate.startswith("direct-"):
        approach = candidate[len("direct-"):]
        if approach not in chat_turns.APPROACHES:
            raise StepError(f"candidate must be direct-P0 … direct-P3, opencode or claude-code")
        rounds = body.get("rounds")
        result = chat_turns.direct_turn(session, text, approach, model, rounds=None if rounds in (None, "") else int(rounds),
                                        history_limit=int(body.get("history") or chat_turns.HISTORY_LIMIT))
    elif candidate in chat_turns.AGENTS:
        result = chat_turns.sandbox_turn(session, text, candidate, model, timeout=int(body.get("timeout") or 900),
                                          max_turns=int(body.get("max_turns") or 60))
    else:
        raise StepError("candidate must be direct-P0 … direct-P3, opencode or claude-code")
    CONSOLE_DIR.mkdir(parents=True, exist_ok=True)
    saved = CONSOLE_DIR / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-chat-{candidate}-{model}.json"
    saved.write_text(json.dumps({**result, "text": text}, ensure_ascii=False, indent=2), encoding="utf-8")
    syntax = result.get("sysml_status")
    if candidate in chat_turns.AGENTS:
        tail = " · the agent runs ./validate in its sandbox" + (f"; files: {', '.join(result['files'])}" if result.get("files") else "")
    else:
        tail = f" · official syntax {syntax}" if syntax else " · no model in this reply"
    lines = [f"{candidate} · {model} · turn {result['turn']} · {result['seconds']} s" + tail + " (a conversation: nothing scored)"]
    lines += [f"  {step['title']}: {step['state']} · {str(step['detail'])[:160]}" for step in result["steps"]]
    return {"summary": "\n".join(lines), "data": result}


def chat_forget(body: dict) -> dict:
    """Drop the stored direct-model conversation(s) of a Langflow session (the sandboxes keep their folders)."""
    from bench import chat_turns
    session = str(body.get("session") or "")
    if not session:
        raise StepError("Need the session id")
    approach = body.get("approach") or None
    removed = chat_turns.forget(session, approach)
    return {"summary": f"{removed} conversation(s) forgotten for session {session}", "data": {"removed": removed}}


def facts(_: dict) -> dict:
    from bench.board_facts import facts as board_facts
    data = board_facts()
    cohorts = data["cohorts"]
    lines = ["F3 results on the 27 frozen tasks (revision 2):"]
    for key in ("flash", "max", "opencode", "claude"):
        c = cohorts[key]
        lines.append(f"  {c['label']}: {c['pass']}/{c['n']}")
    retry = (data.get("retry") or {}).get("agents") or {}
    for agent in retry.values():
        lines.append(f"  Extra run, failed tasks retried · {agent['label']}: {agent['pass']}/{agent['n']} (not a score)")
    lines.append(f"  Recorded cost about ${data['costs'].get('recorded_usd', 0):.2f} at the list price")
    return {"summary": "\n".join(lines), "data": data}


def mod_case(body: dict) -> dict:
    task = body.get("task") or "MOD-05"
    path = ROOT / "analysis" / f"mvp-case-latest-{task}.json"
    if not path.is_file():
        raise StepError(f"No saved change run for {task}")
    case = json.loads(path.read_text(encoding="utf-8"))
    return {"summary": _mod_summary(case), "data": {k: v for k, v in case.items() if k != "gold"}}


def _mod_summary(case: dict) -> str:
    gate = case.get("approval") or {}
    lines = [f"{case.get('task_id')} change run {case.get('id')} · model {case.get('model')}",
             f"  Official Pilot: {case.get('sysml_status')}", f"  Task verdict: {case.get('status')} · design verdict: {case.get('engineering_status')}",
             f"  Limit in the baseline {case.get('limit_in_baseline')} → in the answer {case.get('limit_in_model')}: "
             + ("the limit moved, a person must decide" if gate.get("answer") not in {None, "not-needed"} and case.get("limit_in_model") != case.get("limit_in_baseline") else "unchanged")]
    mentions = case.get("round_trip_mentions") or {}
    lines.append(f"  Read-back restates {sum(mentions.values())} of {len(mentions)} numbers in the model")
    return "\n".join(lines)


def mod_run(body: dict) -> dict:
    task = body.get("task") or "MOD-05"
    if task not in {"MOD-01", "MOD-02", "MOD-03", "MOD-04", "MOD-05"}:
        raise StepError("The task must be one of MOD-01 to MOD-05")
    done = subprocess.run([sys.executable, str(ROOT / "bench" / "run_mvp_case.py"), task], capture_output=True, text=True, cwd=str(ROOT), timeout=1800)
    if done.returncode != 0:
        raise StepError((done.stderr or done.stdout)[-600:])
    return mod_case({"task": task})


# ---------- the unfolded assistant's tool sub-flows (decision 034): one card per step, all stateless ----------

def _tool_text(body: dict, key: str) -> str:
    value = body.get(key)
    return str(value or "").strip()


def tool_memory_library(_: dict) -> dict:
    """Card 1 of memory search: what the library is made of (the same sources the search reads)."""
    body = memory({})
    return {"summary": body["summary"], "data": {"sources": body["data"]["sources"]}}


def tool_memory_seeds(body: dict) -> dict:
    """Card 2 of memory search: the MiniLM + FAISS seeds for the query (paper 2's first step)."""
    from bench.discover import retrieve_existing
    query = _tool_text(body, "query")
    if len(query) < 3:
        raise StepError("Give the search a few words")
    found = retrieve_existing(query)
    seeds = [node for node in found["nodes"] if node.get("role") == "seed"]
    lines = [f"Seeds for \"{query[:80]}\": {len(seeds)} of {found['library_size']} cards · {found['embedding_model']} · cosine ≥ {found['threshold']}"
             f" plus the exact-name bonus {found['name_bonus']}",
             *[f"  {node['score']:.2f} · {node['text']}  [{node['source']}]" for node in seeds]]
    return {"summary": "\n".join(lines), "data": {"query": query, "seeds": seeds, "method": found["method"], "threshold": found["threshold"]}}


def tool_memory_hop(body: dict) -> dict:
    """Card 3 of memory search: each seed's one-hop neighbours, then the cards handed to the assistant."""
    from bench.discover import retrieve_existing
    query = _tool_text(body, "query")
    if len(query) < 3:
        raise StepError("Give the search a few words")
    found = retrieve_existing(query)
    hops = [node for node in found["nodes"] if node.get("role") == "neighbor"]
    short = {node["id"]: node.get("short") or node.get("name") or node["id"] for node in found["nodes"]}
    lines = [f"One hop from the seeds: {len(hops)} neighbour(s); {len(found['cards'])} cards in all · {found['note']}",
             *[f"  via {short.get(node['via'], node['via'])} → {node['text']}  [{node['source']}]" for node in hops],
             "Cards returned to the assistant:", *[f"  {card}" for card in found["cards"]]]
    return {"summary": "\n".join(lines), "data": {"query": query, "cards": found["cards"], "numbers": found["numbers"], "path": found["path"]}}


def _run_and_key(body: dict) -> tuple[str, str]:
    text = _tool_text(body, "request")
    run = re.search(r"\d{8}T\d{6}", text)
    key = re.search(r"\b([AB])\b", text.upper().replace(run.group(0), "") if run else text.upper())
    if not run or not key:
        raise StepError("Say which run and which design: '<run id> A' or '<run id> B'")
    return run.group(0), key.group(1)


def tool_gate(body: dict) -> dict:
    """Card 1 of write to memory: the gate, read only. The same rule as the page: Pilot PASS and all four checks PASS."""
    from bench.discover import approval_block, load_memory
    run, key = _run_and_key(body)
    path = ROOT / "analysis" / f"discover-{run}.json"
    if not path.is_file():
        raise StepError(f"No such run: {run}")
    record = json.loads(path.read_text(encoding="utf-8"))
    design = next((item for item in record.get("designs", []) if item.get("key") == key), None)
    if not design:
        raise StepError(f"Run {run} has no design {key}")
    reason = approval_block(record, design)
    already = any(entry["run_id"] == run and entry["design"] == key for entry in load_memory())
    checks = {c["id"]: c["status"] for c in design.get("checks", []) if c["id"] != "CONNECT"}
    verdict = "already in memory" if already else ("gate open" if not reason else f"gate closed: {reason}")
    lines = [f"run {run} · design {key} · {verdict}",
             f"  official Pilot {design.get('sysml_status')} after {len(design.get('attempts', []))} parse(s)",
             *[f"  {name} {status}" for name, status in checks.items()]]
    return {"summary": "\n".join(lines), "data": {"run": run, "key": key, "open": not reason and not already, "reason": reason, "already": already}}


def _has_session(run: str) -> bool:
    return run in SESSIONS or (SESSIONS_DIR / f"{run}.json").is_file()


def tool_write(body: dict) -> dict:
    """Card 2 of write to memory: the write itself, through the page's gate (refuses when the gate is closed).
    Runs made before the Langflow shell have no session; they go through the page's approve() directly."""
    run, key = _run_and_key(body)
    if _has_session(run):
        result = run_approve({"run": run, "key": key})
    else:
        from bench.discover import approve
        try:
            outcome = approve(run, key)
            result = {"run": run, "summary": f"run {run}\nDesign {key} approved into memory ({len(outcome['memory'])} designs now); the next search can find it.",
                      "data": {"approved": True, "memory_size": len(outcome["memory"])}}
        except ValueError as exc:
            result = {"run": run, "summary": f"run {run}\nDesign {key} not approved: {exc}", "data": {"approved": False, "reason": str(exc)}}
    return _with_upstream(result, body)


def _with_upstream(result: dict, body: dict) -> dict:
    """The write and record cards repeat the cards before them, so the flow's last message tells the whole story."""
    upstream = _tool_text(body, "upstream")
    if upstream:
        result["summary"] = upstream.rstrip() + "\n" + result["summary"]
    return result


def tool_record_approval(body: dict) -> dict:
    """Card 3 of write to memory: the decision on the run's record, only when the write happened."""
    run, key = _run_and_key(body)
    written_now = "approved into memory" in _tool_text(body, "upstream")
    if not _has_session(run):
        result = {"run": run, "summary": f"Record: run {run} · design {key} · " + ("approval kept on the run's record (a run from before the Langflow shell: no grades and times to add)"
                                                                                  if written_now else "nothing written this time, so no approval is recorded"),
                  "data": {"recorded": written_now}}
        return _with_upstream(result, body)
    session = _session(run)
    approvals = session["record"]["langflow"].get("approvals", [])
    if not written_now or not any(a.get("design") == key and a.get("approved") for a in approvals):
        return _with_upstream({"run": run, "summary": f"Record: run {run} · design {key} · nothing written this time, so no approval is recorded", "data": {"recorded": False}}, body)
    result = run_decision({"run": run, "decision": f"Approve design {key}", "note": "approved in the assistant's chat"})
    result["summary"] = "Record: " + result["summary"]
    return _with_upstream(result, body)


def tool_validate_save(body: dict) -> dict:
    """Card 1 of validate: the pasted text becomes a file, the package name is read from it."""
    sysml = _tool_text(body, "sysml")
    match = re.search(r"\bpackage\s+(\w+)", sysml)
    if not match:
        raise StepError("The text declares no package")
    package = match.group(1)
    folder = ROOT / "mvp" / "exam-inbox" / f"assistant-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')}"
    folder.mkdir(parents=True)
    path = folder / f"{package}.sysml"
    path.write_text(sysml, encoding="utf-8")
    return {"summary": f"file: {path.relative_to(ROOT)}\npackage: {package}\n  {len(sysml.splitlines())} line(s), {len(sysml)} characters",
            "data": {"file": str(path.relative_to(ROOT)), "package": package}}


def tool_validate_pilot(body: dict) -> dict:
    """Card 2 of validate: the official SysML v2 Pilot on that file."""
    from mvp.engine import run_submitted_model
    text = _tool_text(body, "saved")
    file_match = re.search(r"file:\s*(\S+)", text)
    package_match = re.search(r"package:\s*(\w+)", text)
    if not file_match or not package_match:
        raise StepError("Connect this card after the save card")
    path = ROOT / file_match.group(1)
    result = run_submitted_model([path], package_match.group(1), label="assistant-validate")
    diagnostics = result["sysml"].get("diagnostics", [])[:12]
    lines = [f"official Pilot {result['sysml']['status']} · package {package_match.group(1)} · run {result['run_id']}",
             *[f"  line {item.get('line')}: {item.get('message')}" for item in diagnostics]]
    return {"summary": "\n".join(lines), "data": {"sysml_status": result["sysml"]["status"], "diagnostics": diagnostics}}


def tool_prompt_part(body: dict) -> dict:
    """Read-only card of the pipeline: one part of the prompt the designs were written from (rules, template, examples)."""
    session = _session(body.get("run"))
    part_key = _tool_text(body, "part")
    written = session["record"].get("written") or session.get("written") or {}
    for key in ("A", "B"):
        parts = (written.get(key) or {}).get("prompt_parts") or []
        part = next((p for p in parts if p.get("key") == part_key), None)
        if part:
            return {"run": session["id"], "summary": f"run {session['id']} · {part['label']} (design {key}, paper {part.get('paper') or '-'})\n{part['text']}",
                    "data": {"key": part_key, "text": part["text"]}}
    return {"run": session["id"], "summary": f"run {session['id']} · no {part_key} part on this run", "data": {"key": part_key}}


ROUTES = {
    "/tool/memory/library": tool_memory_library, "/tool/memory/seeds": tool_memory_seeds, "/tool/memory/hop": tool_memory_hop,
    "/tool/gate": tool_gate, "/tool/write": tool_write, "/tool/record-approval": tool_record_approval,
    "/tool/validate/save": tool_validate_save, "/tool/validate/pilot": tool_validate_pilot, "/tool/prompt-part": tool_prompt_part,
    "/run/start": run_start, "/run/retrieve": run_retrieve, "/run/requirements": run_requirements,
    "/run/design": lambda body: _designs(body, adapt=False), "/run/adapt": lambda body: _designs(body, adapt=True),
    "/run/validate": run_validate, "/run/align": run_align, "/run/checks": run_checks, "/run/tradeoffs": run_tradeoffs,
    "/run/review": run_review, "/run/approve": run_approve, "/run/decision": run_decision,
    "/cameo/export": cameo_export, "/cameo/result": cameo_result, "/gate/decision": gate_decision,
    "/memory": memory, "/exam/cells": exam_cells, "/exam/cell": exam_cell, "/exam/run": exam_run,
    "/exam/agent-cell": exam_cell, "/exam/agent-run": exam_agent_run, "/chat/turn": chat_turn, "/chat/forget": chat_forget, "/facts": facts, "/mod/case": mod_case, "/mod/run": mod_run,
}


def _markdown(text: str) -> str:
    """Summary lines as Markdown for Langflow's cards and chat: indented lines become list items, the rest paragraphs.
    The first line stays first; the If-Else nodes route on it."""
    out: list[str] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        if line.startswith("  ") and out:
            out.append("- " + line.strip())
        else:
            if out:
                out.append("")
            out.append(line)
    return "\n".join(out)


def _readable(handler):
    def wrapped(body: dict) -> dict:
        result = handler(body)
        if isinstance(result.get("summary"), str):
            result["summary"] = _markdown(result["summary"])
        return result
    return wrapped


ROUTES |= {path: _readable(handler) for path, handler in ROUTES.items() if path.startswith(("/run/", "/cameo/", "/gate/", "/tool/"))}


class Handler(BaseHTTPRequestHandler):
    token = ""

    def log_message(self, fmt: str, *args) -> None:
        return

    def _send(self, code: int, body: bytes, kind: str = "application/json; charset=utf-8") -> None:
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, payload: dict) -> None:
        self._send(code, json.dumps(payload, ensure_ascii=False, default=str).encode())

    def _authorized(self) -> bool:
        return bool(self.token) and self.headers.get("X-RTRC-Token") == self.token

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._json(200, {"ok": True, "service": "rtrc-shell", "page_running": _page_running()})
            return
        if parsed.path == "/diagram":
            from bench.model_diagram import DiagramError, render
            query = parse_qs(parsed.query)
            try:
                svg = render(query.get("run", [""])[0], query.get("view", ["connections"])[0])
            except DiagramError as exc:
                self._json(404, {"error": str(exc)})
                return
            self._send(200, svg.read_bytes(), "image/svg+xml")
            return
        if not self._authorized():
            self._json(401, {"error": "missing or wrong X-RTRC-Token"})
            return
        handler = ROUTES.get(parsed.path)
        if parsed.path not in {"/exam/cells", "/facts"} or not handler:
            self._json(404, {"error": "use POST for this path"})
            return
        self._dispatch(handler, {})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if not self._authorized():
            self._json(401, {"error": "missing or wrong X-RTRC-Token"})
            return
        handler = ROUTES.get(parsed.path)
        if not handler:
            self._json(404, {"error": f"no such path {parsed.path}"})
            return
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        except json.JSONDecodeError:
            self._json(400, {"error": "the body must be JSON"})
            return
        self._dispatch(handler, body)

    def _dispatch(self, handler, body: dict) -> None:
        try:
            self._json(200, {"ok": True, **handler(body)})
        except StepError as exc:
            self._json(400, {"ok": False, "error": str(exc)})
        except Exception as exc:
            self._json(500, {"ok": False, "error": f"{type(exc).__name__}: {exc}", "trace": traceback.format_exc()[-1500:]})


def main() -> None:
    load_env()
    from agents.llm_local import install
    from bench.vector_index import check
    install()  # the local Qwen (Ollama) as a model option; the frozen agents/llm.py stays as it is
    check()
    Handler.token = _token()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"RTRC shell service on http://{HOST}:{PORT} (token from {SECRETS.relative_to(ROOT)})", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
