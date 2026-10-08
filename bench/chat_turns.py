"""The chat versions of projects 1 and 2 (decision 036): a person's words go to the model as written, and the
conversation continues across messages.

Until 2026-10-08 these chats fed the person's message into the exam solver (agents/solve.py): the exam's system
prompt ("one fenced sysml block, no prose"), a task type chosen in a dropdown, a fresh conversation per message.
That is the right shape for a sealed task id and the wrong shape for a person. This module is the replacement.
The exam versions are unchanged: bench/langflow_exam.py and the exam cell still use agents/solve.py as frozen.

Direct model (P0 to P3): one conversation per Langflow session, kept under mvp/chat-sessions/. The person's text
is the user turn, word for word. What the approach adds happens around that turn, not instead of it:
- P3 retrieves from the official-examples library with the person's own words (paper 2; no query rewrite) and
  attaches the cards, with sources, as reference notes for this turn.
- P2 and P3 ask the model for an outline first, only when the message asks for a model; the outline is given to
  the writing call as a working note, not as an invented exchange.
- The official Pilot parses the reply only when it contains a fenced sysml block. P1 to P3 then paste the complete
  error list back into the same conversation and ask for the whole file again (paper 3's correction by the tool);
  P0 does not repair. The person sees the final version.

Sandboxed coding agents (OpenCode, Claude Code): one sandbox per Langflow session, kept under mvp/chat-sandbox/,
with ./validate (the official Pilot) and rules written for an assistant, not for an exam. The agent's own session
continues across messages (OpenCode --session, Claude Code --resume), so "change the last one" has something to
change. The results page (8770) does not block these chats: nothing here is scored, so the page's answer keys
cannot leak into a score (user decision of 2026-10-08). The exam path still refuses while the page runs.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.llm import MODEL_OVERRIDE, USAGE_LOG, usage_summary  # noqa: E402
from agents.llm_local import LOCAL_MODELS, chat  # noqa: E402  (routes the local model to Ollama, the rest to agents.llm.chat)

SESSIONS = ROOT / "mvp" / "chat-sessions"
SANDBOXES = ROOT / "mvp" / "chat-sandbox"
APPROACHES = ("P0", "P1", "P2", "P3")
AGENTS = ("opencode", "claude-code")
DEFAULT_ROUNDS = int(os.environ.get("BENCH_REPAIR_ROUNDS", "20"))
IDENTICAL_STOP = 3
HISTORY_LIMIT = 30
FENCED_SYSML = re.compile(r"```sysml\s*\n(.*?)```", re.S | re.I)
PACKAGE_DECL = re.compile(r"\bpackage\s+(?:'[^']+'|[A-Za-z_][A-Za-z0-9_]*)")
SANDBOX_LOCK = threading.Lock()

SYSTEM = """You are a SysML v2 assistant for a synthetic maritime ISR exercise; the numbers are not an RTX specification.
Talk with the person in the language they write in, and answer what they actually asked. A question gets an answer; a remark gets a reply; only a request for a model gets a model.
When they ask for a SysML v2 model, or for a change to one, write SysML v2 textual notation in one fenced code block tagged sysml: exactly one package; when you use Real, `private import ScalarValues::*;` as the first line inside the package (this toolchain requires the visibility keyword, a bare import is rejected); only the names and numbers the person gave. Say briefly what you did around the block.
Never invent a number or a limit. If a value you need is missing, ask for it. Never change a limit the person stated, even to make something fit.
If the person gave you a model earlier in this conversation and asks for a change, change that model and send the whole file again."""
REPAIR_SENTENCE = """
When your reply contains SysML, the official SysML v2 Pilot parses it. If it reports errors, you receive the complete list and must fix the file and send the whole file again in one fenced sysml block."""
REPAIR_NOTE = ("Official validation failed: repair {repair} of at most {cap}. The complete error list from the official "
               "SysML v2 Pilot follows. Fix the model and send the whole file again in one fenced sysml block. "
               "Keep the names and numbers the person gave.")
IDENTICAL_NOTE = "Your last file was byte-identical to the one before it and produced the same errors; change the file."
OUTLINE_SYSTEM = ("A person wrote the message below in a conversation with a SysML v2 assistant. If the message asks for a "
                  "SysML v2 model, or for a change to one, list the parts, ports, connections and attributes it requires as one "
                  "JSON object, using the person's names and no numbers that are not in the message or the notes. If it does "
                  "not ask for a model, reply with the single word NONE.")

# The sandboxed agents' rules, written for a conversation. The exam's AGENTS.md (the repository root file) is not used.
SANDBOX_RULES = """# Rules for this conversation

You are a SysML v2 assistant for a synthetic maritime ISR exercise; the numbers are not an RTX specification. This folder is your workspace. The person talks to you here across several messages; earlier messages and the files you wrote are still here.

1. Answer what the person asked, in the language they write in. A question gets an answer. Only a request for a model gets a model.
2. When they ask for a SysML v2 model or a change to one, write it to a `.sysml` file in this folder (one package per file; `private import ScalarValues::*;` first inside the package when you use Real), run `./validate <PackageName> <file.sysml>`, fix every reported error, then show the final file in your reply in one fenced block tagged sysml and say what you did.
3. Never invent a number or a limit. If a value you need is missing, ask for it. Never change a limit the person stated.
4. Do not edit files under `input/`; they are what the person gave you.
5. Report validation results as the tool printed them, including failures.
"""
CLAUDE_TOOLS = ["Bash", "Read", "Write", "Edit", "Glob", "Grep"]


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", name or "default")[:80]


def _flat_usage(calls: list[dict]) -> dict:
    """Tokens of the turn in the shape the Langflow nodes and the results page read: input, cached, output, calls."""
    summary = usage_summary(calls)
    slots = summary["by_model"].values()
    return {"input": sum(s["prompt_tokens"] for s in slots), "cached": sum(s["cached_tokens"] for s in slots),
            "output": sum(s["completion_tokens"] for s in slots), "calls": summary["calls"], "by_model": summary["by_model"]}


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


# ---------- direct model, P0 to P3 ----------

def _history_file(session: str, approach: str) -> Path:
    return SESSIONS / f"direct-{approach}-{_safe(session)}.json"


def _load_history(session: str, approach: str) -> dict:
    path = _history_file(session, approach)
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"session": session, "approach": approach, "messages": [], "turns": 0}


def _save_history(history: dict, session: str, approach: str, limit: int) -> None:
    history["messages"] = history["messages"][-limit:]
    path = _history_file(session, approach)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


def _retrieve_notes(text: str) -> list[dict]:
    """P3: the official-examples library searched with the person's words (paper 2); never a rewritten query."""
    from agents.solve import _retrieve
    found = _retrieve(text)
    return [{"source": item["source"], "score": round(float(item.get("score") or 0), 3), "text": item["text"]} for item in found]


def _notes_message(notes: list[dict]) -> dict:
    body = "\n\n".join(f"[{item['source']} · score {item['score']}]\n{item['text']}" for item in notes)
    return {"role": "system", "content": "Reference notes for this message only, retrieved from the official SysML v2 example library "
                                         "with the person's own words. Each note names its source. They show notation; they are not facts "
                                         "about the person's system.\n\n" + body}


def _companions(text: str, package: str, folder: Path) -> list[Path]:
    """Fenced sysml blocks in the person's message that declare another package: read-only sources parsed with the answer
    (the two models an alignment package imports, or a model the person pasted and asks to extend)."""
    paths = []
    for block in FENCED_SYSML.findall(text):
        declared = PACKAGE_DECL.search(block)
        if declared:
            name = declared.group(0).split(None, 1)[1].strip("'")
            if name != package:
                path = folder / f"{name}.sysml"
                path.write_text(block.strip() + "\n", encoding="utf-8")
                paths.append(path)
    return paths


def _validate(reply: str, text: str, folder: Path, attempt: int, label: str) -> dict | None:
    """The official Pilot on the last fenced sysml block of the reply; None when the reply holds no model."""
    from agents.solve import format_diagnostics
    from mvp.engine import run_submitted_model
    blocks = FENCED_SYSML.findall(reply)
    if not blocks:
        return None
    source = blocks[-1].strip() + "\n"
    declared = PACKAGE_DECL.search(source)
    if not declared:
        diagnostics = [{"severity": "ERROR", "line": None, "column": None, "message": "The sysml block declares no package."}]
        return {"attempt": attempt, "status": "FAIL", "package": None, "diagnostics": diagnostics, "feedback": format_diagnostics(diagnostics), "source": source}
    package = declared.group(0).split(None, 1)[1].strip("'")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{package}.sysml"
    path.write_text(source, encoding="utf-8")
    companions = _companions(text, package, folder)
    validated = run_submitted_model(companions + [path], package, label=label)
    diagnostics = [{key: item.get(key) for key in ("severity", "line", "column", "message")} for item in validated["sysml"].get("diagnostics", [])]
    return {"attempt": attempt, "status": validated["sysml"]["status"], "package": package, "diagnostics": diagnostics,
            "feedback": format_diagnostics(diagnostics), "source": source, "run_id": validated["run_id"], "run_dir": str(validated["run_dir"])}


def direct_turn(session: str, text: str, approach: str, model: str, *, rounds: int | None = None, history_limit: int = HISTORY_LIMIT) -> dict:
    """One message of a person to the direct model with one approach; the reply, parsed and repaired when it is a model."""
    if approach not in APPROACHES:
        raise ValueError(f"approach must be one of {APPROACHES}")
    text = text.strip()
    if not text:
        raise ValueError("Write a message")
    cap = 0 if approach == "P0" else (DEFAULT_ROUNDS if rounds is None else max(0, rounds))
    history = _load_history(session, approach)
    turn = history["turns"] + 1
    folder = SESSIONS / f"direct-{approach}-{_safe(session)}" / f"turn-{turn:03d}"
    calls: list[dict] = []
    usage_token, model_token = USAGE_LOG.set(calls), MODEL_OVERRIDE.set(model)
    started = time.monotonic()
    steps: list[dict] = []
    notes: list[dict] = []
    outline = ""
    attempts: list[dict] = []
    try:
        system = SYSTEM + (REPAIR_SENTENCE if cap else "")
        turn_notes: list[dict] = []
        if approach == "P3":
            notes = _retrieve_notes(text)
            if notes:
                turn_notes.append(_notes_message(notes))
            steps.append({"title": "Retrieve notes", "state": "pass", "detail": f"{len(notes)} card(s) from the official-examples library, searched with the person's words: "
                                                                                 + ", ".join(item["source"] for item in notes)})
        if approach in {"P2", "P3"}:
            outlined = chat([{"role": "system", "content": OUTLINE_SYSTEM}, *turn_notes, {"role": "user", "content": text}], max_tokens=1500)
            candidate = outlined["text"].strip()
            if candidate and candidate.upper() != "NONE" and "{" in candidate:
                outline = candidate
                turn_notes.append({"role": "system", "content": "Your outline of what this request needs, prepared before writing:\n" + outline})
                steps.append({"title": "Outline", "state": "pass", "detail": "The message asks for a model; an outline of parts, ports, connections and attributes was prepared first."})
            else:
                steps.append({"title": "Outline", "state": "skip", "detail": "The message does not ask for a model; no outline."})
        messages = [{"role": "system", "content": system}, *history["messages"], *turn_notes, {"role": "user", "content": text}]
        written = chat(messages)
        reply = written["text"]
        steps.append({"title": "Answer", "state": "pass", "detail": f"Model {written.get('model') or model} answered the person's message as written."})
        checked = _validate(reply, text, folder, 1, f"chat-{approach}")
        if checked is None:
            steps.append({"title": "Official syntax", "state": "skip", "detail": "The reply holds no fenced sysml block; nothing to parse."})
        else:
            attempts.append({k: checked[k] for k in ("attempt", "status", "package", "diagnostics") if k in checked} | {"run_id": checked.get("run_id")})
            repairs = 0
            identical = 0
            previous = checked["source"]
            while checked["status"] != "PASS" and repairs < cap:
                repairs += 1
                note = REPAIR_NOTE.format(repair=repairs, cap=cap)
                if identical:
                    note += " " + IDENTICAL_NOTE
                messages += [{"role": "assistant", "content": reply}, {"role": "user", "content": note + "\n" + checked["feedback"]}]
                repaired = chat(messages)
                reply = repaired["text"]
                checked = _validate(reply, text, folder, repairs + 1, f"chat-{approach}") or {
                    "attempt": repairs + 1, "status": "FAIL", "package": None, "diagnostics": [{"severity": "ERROR", "line": None, "column": None, "message": "The repair holds no fenced sysml block."}],
                    "feedback": "The repair holds no fenced sysml block.", "source": ""}
                identical = identical + 1 if checked["source"] == previous else 0
                previous = checked["source"]
                attempts.append({k: checked[k] for k in ("attempt", "status", "package", "diagnostics") if k in checked} | {"run_id": checked.get("run_id"), "same_as_previous": bool(identical)})
                if identical >= IDENTICAL_STOP:
                    break
            final = attempts[-1]["status"]
            steps.append({"title": "Official syntax", "state": "pass" if final == "PASS" else "fail",
                          "detail": f"Package {attempts[-1].get('package')}: {final} after {len(attempts)} parse(s)." + ("" if final == "PASS" else " " + checked["feedback"][:400])})
            if cap == 0:
                steps.append({"title": "Repair from errors", "state": "skip", "detail": "P0 writes once and is not repaired."})
            elif repairs:
                steps.append({"title": "Repair from errors", "state": "pass" if final == "PASS" else "fail",
                              "detail": f"{repairs} repair(s) of at most {cap}, in this conversation, with the complete error list each time."})
            else:
                steps.append({"title": "Repair from errors", "state": "skip", "detail": "The first version passed; no repair needed."})
    finally:
        USAGE_LOG.reset(usage_token)
        MODEL_OVERRIDE.reset(model_token)
    history["messages"] += [{"role": "user", "content": text}, {"role": "assistant", "content": reply}]
    history["turns"] = turn
    _save_history(history, session, approach, history_limit)
    return {"candidate": f"direct-{approach}", "approach": approach, "model": model, "session": session, "turn": turn,
            "answer": reply, "sysml_status": attempts[-1]["status"] if attempts else None, "package": attempts[-1].get("package") if attempts else None,
            "attempts": attempts, "repair_rounds": max(0, len(attempts) - 1), "retrieved": notes, "outline": outline,
            "usage": _flat_usage(calls), "seconds": round(time.monotonic() - started, 1), "history_messages": len(history["messages"]), "steps": steps}


def forget(session: str, approach: str | None = None) -> int:
    """Drop the stored conversation(s) of a Langflow session; returns how many were removed."""
    removed = 0
    for item in APPROACHES if approach is None else (approach,):
        path = _history_file(session, item)
        if path.is_file():
            path.unlink()
            removed += 1
        shutil.rmtree(SESSIONS / f"direct-{item}-{_safe(session)}", ignore_errors=True)
    return removed


# ---------- sandboxed coding agents ----------

def _sandbox_dir(agent: str, session: str) -> Path:
    return SANDBOXES / f"{agent}-{_safe(session)}"


def _prepare_sandbox(work: Path, agent: str, model: str) -> tuple[Path, Path]:
    """The persistent workspace and home of one conversation: ./validate, the conversation rules, the provider config."""
    from agents.external.jail import HOME, TOOLCHAIN, VALIDATE
    from agents.external.opencode_run import provider_config
    workspace, home = work / "workspace", work / "home"
    if not workspace.is_dir():
        (workspace / "input").mkdir(parents=True)
        (workspace / "AGENTS.md").write_text(SANDBOX_RULES, encoding="utf-8")
        (workspace / "CLAUDE.md").write_text(SANDBOX_RULES, encoding="utf-8")
        script = workspace / "validate"
        script.write_text(VALIDATE.replace("@VALIDATOR@", str(TOOLCHAIN / "validate.py")), encoding="utf-8")
        script.chmod(0o755)
    if agent == "opencode":
        _, config = provider_config(model)
        (workspace / "opencode.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    if not home.is_dir():
        (home / ".claude-code-router").mkdir(parents=True)
        source = HOME / ".claude-code-router" / "config.sqlite"
        if source.is_file():
            shutil.copy2(source, home / ".claude-code-router" / "config.sqlite")
        (home / "opencode-user-config.jsonc").write_text('{"$schema": "https://opencode.ai/config.json"}\n', encoding="utf-8")
        shutil.copytree(TOOLCHAIN / "build", home / "toolchain-build")
    return workspace, home


def _opencode_answer(events: list[dict]) -> str:
    texts = [(e["part"].get("messageID"), e["part"].get("text", "")) for e in events if e.get("type") == "text" and e.get("part")]
    if not texts:
        return ""
    last = texts[-1][0]
    return "\n\n".join(t for m, t in texts if m == last).strip()


def sandbox_turn(session: str, text: str, agent: str, model: str, *, timeout: int = 900, max_turns: int = 60) -> dict:
    """One message of a person to OpenCode or Claude Code in a persistent sandbox; the agent's own session continues."""
    from agents.external.jail import wrap
    from agents.external.opencode_run import BINARY, provider_config
    if agent not in AGENTS:
        raise ValueError(f"agent must be one of {AGENTS}")
    text = text.strip()
    if not text:
        raise ValueError("Write a message")
    if agent == "claude-code" and model in LOCAL_MODELS:
        raise ValueError("The local 3-bit model runs with OpenCode; Claude Code still uses the cloud Qwen.")
    work = _sandbox_dir(agent, session)
    state_file = work / "session.json"
    state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.is_file() else {"session": session, "agent": agent, "turns": 0, "agent_session": None}
    turn = state["turns"] + 1
    turns_dir = work / "turns"
    turns_dir.mkdir(parents=True, exist_ok=True)
    (turns_dir / f"{turn:03d}-person.md").write_text(text + "\n", encoding="utf-8")
    with SANDBOX_LOCK:
        workspace, home = _prepare_sandbox(work, agent, model)
        if agent == "opencode":
            model_id, _ = provider_config(model)
            argv = [str(BINARY), "run", "--pure", "--auto", "--format", "json", "--dir", str(workspace), "--model", model_id]
            argv += ["--session", state["agent_session"]] if state.get("agent_session") else ["--title", f"Chat {session}"]
            argv.append(text)
        else:
            argv = ["ccr", "default-claude-code", "--", "-p", "--output-format", "json", "--max-turns", str(max_turns),
                    "--allowedTools", *CLAUDE_TOOLS, "--model", f"qwen,{model}"]
            argv += ["--resume", state["agent_session"]] if state.get("agent_session") else []
            argv.append(text)
        started = time.monotonic()
        try:
            completed = subprocess.run(wrap(argv, workspace, home), cwd=workspace, env=os.environ.copy(), text=True, capture_output=True, timeout=timeout)
            stdout, stderr, returncode = completed.stdout, completed.stderr, completed.returncode
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr, returncode = f"timeout after {timeout}s", "timeout"
    seconds = round(time.monotonic() - started, 1)
    (turns_dir / f"{turn:03d}-stdout.{'jsonl' if agent == 'opencode' else 'json'}").write_text(stdout, encoding="utf-8")
    (turns_dir / f"{turn:03d}-stderr.txt").write_text(stderr, encoding="utf-8")
    tools: list[dict] = []
    if agent == "opencode":
        from bench.run_opencode import usage_from_log
        events = []
        for line in stdout.splitlines():
            if line.startswith("{"):
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        if events and events[0].get("sessionID"):
            state["agent_session"] = events[0]["sessionID"]
        answer = _opencode_answer(events)
        for event in events:
            part = event.get("part") or {}
            if part.get("type") == "tool":
                status = part.get("state") if isinstance(part.get("state"), dict) else {}
                tools.append({"tool": part.get("tool"), "status": status.get("status"), "target": str(status.get("title") or "")[:160]})
        usage = usage_from_log(turns_dir / f"{turn:03d}-stdout.jsonl")
    else:
        from bench.run_claude_qwen import usage_of
        try:
            result = json.loads(stdout)
        except json.JSONDecodeError:
            result = {"result": stdout, "is_error": True}
        if result.get("session_id"):
            state["agent_session"] = result["session_id"]
        answer = result.get("result") or ""
        usage = usage_of(result)
        if result.get("num_turns"):
            tools.append({"tool": "turns", "status": "done", "target": f"{result['num_turns']} agent turn(s)"})
    if returncode not in (0, None) and not answer:
        answer = f"The agent returned no answer (exit {returncode}). {stderr.strip()[-600:]}"
    state["turns"] = turn
    state["model"] = model
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    files = sorted(p.name for p in workspace.glob("*.sysml"))
    steps = [{"title": "Message", "state": "pass", "detail": f"Turn {turn} of this conversation; the text went to the agent as written, in its own session."},
             {"title": "Agent", "state": "pass" if answer and returncode in (0, None) else "fail",
              "detail": f"{len(tools)} tool call(s), {usage.get('input', 0)} in / {usage.get('output', 0)} out tokens, {seconds} s" + (f"; files in the workspace: {', '.join(files)}" if files else "")},
             {"title": "Check against key", "state": "skip", "detail": "A conversation has no answer key; nothing is scored."}]
    return {"candidate": agent, "model": model, "session": session, "turn": turn, "agent_session": state.get("agent_session"),
            "answer": answer, "tool_calls": tools, "usage": usage, "seconds": seconds, "returncode": returncode,
            "workspace": str(workspace), "files": files, "steps": steps}
