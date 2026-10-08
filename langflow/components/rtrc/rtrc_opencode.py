"""RTRC OpenCode assistant: one turn of the conversational design assistant per chat message, or one exam answer.

The assistant is OpenCode (the exam's pinned binary) with the RTRC MCP tools (tools/assistant_mcp.py on
127.0.0.1:8782) as its only tools; its file and shell tools are off. The workspace is prepared by
tools/assistant/workspace.py outside the repository. Decision 032.

Chat mode: the local Qwen3.8-27B served by Ollama (or a cloud Qwen), all nine tools, and each Langflow chat session
maps to one OpenCode session, so the conversation continues across messages.
Exam mode (decision 035): the exam workspace, qwen3.8-flash, the exam prompt, memory search and the official Pilot as
the only tools, and a fresh OpenCode session for every message, so one task cannot see another.
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, MessageInput, Output
from lfx.schema.message import Message

# Langflow runs component code from a copy, so the repository is found from the environment (RTRC_ROOT, set by
# scripts/langflow.sh) or from the virtual environment, which lives at <repository>/.venv-langflow.
ROOT = Path(os.environ.get("RTRC_ROOT") or Path(sys.prefix).resolve().parent)
OPENCODE = ROOT / "tools" / "opencode" / "opencode"
MCP_URL = os.environ.get("RTRC_ASSISTANT_MCP_URL", "http://127.0.0.1:8782/mcp")
MODES = ["Chat: one OpenCode session per Langflow session, all nine tools",
         "Exam: a fresh session per message, answer only, memory search and the official Pilot as the only tools"]
MODELS = ["qwen3.8-27b (Ollama)", "qwen3.8-max", "qwen3.8-flash"]


def _env() -> dict:
    """The process environment plus .env (the cloud Qwen endpoint and key for OpenCode's provider; never printed)."""
    env = os.environ.copy()
    dotenv = ROOT / ".env"
    if dotenv.is_file():
        for line in dotenv.read_text(encoding="utf-8").splitlines():
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    return env


class RtrcOpenCodeAssistant(Component):
    display_name = "RTRC OpenCode assistant"
    description = ("One turn of the RTRC design assistant: OpenCode with the RTRC tools (memory, the verified design "
                   "pipeline, the official Pilot, the memory gate, decisions, Cameo export); or, in exam mode, one exam answer.")
    icon = "bot"
    name = "RtrcOpenCodeAssistant"

    inputs = [
        MessageInput(name="message", display_name="Engineer's message",
                     info="Ask what exists, describe a need, confirm the brief it proposes, or decide on a run. In exam mode: one task statement."),
        DropdownInput(name="mode", display_name="Mode", options=MODES, value=MODES[0], advanced=True),
        DropdownInput(name="model", display_name="Model", options=MODELS, value=MODELS[0], advanced=True, combobox=True,
                      info="Pick one of the names our runs used, or type any name: a cloud name goes to the endpoint of .env (or to OpenCode's own provider when "
                           "OPENCODE_MODEL is set), '<tag> (Ollama)' to a model you pulled into Ollama. The exam flows used qwen3.8-flash."),
    ]
    outputs = [Output(display_name="Answer", name="answer", method="turn")]

    def turn(self) -> Message:
        text = (self.message.text if isinstance(self.message, Message) else str(self.message or "")).strip()
        if not text:
            raise ValueError("Write a message for the assistant")
        if not OPENCODE.is_file():
            raise ValueError(f"Missing the pinned OpenCode binary {OPENCODE}; set RTRC_ROOT to the repository")
        try:
            urllib.request.urlopen(urllib.request.Request(MCP_URL, method="GET"), timeout=3).read(1)
        except Exception as exc:  # noqa: BLE001 - any failure means the tools are not there
            if "HTTP Error" not in str(exc):
                raise ValueError(f"The RTRC assistant MCP server is not running at {MCP_URL}; start it with scripts/langflow.sh or scripts/assistant.sh") from exc
        exam = str(self.mode or MODES[0]).startswith("Exam")
        model = str(self.model or MODELS[0])
        env = _env()
        prepared = subprocess.run(["python3", str(ROOT / "tools" / "assistant" / "workspace.py"), "--mode", "exam" if exam else "chat", "--model", model],
                                  capture_output=True, text=True, timeout=120, check=False, env=env)
        if prepared.returncode != 0:
            raise ValueError(f"Could not prepare the assistant workspace: {prepared.stderr.strip()[-400:]}")
        workspace = Path(prepared.stdout.strip().splitlines()[-1])

        session = getattr(self.message, "session_id", None) or getattr(getattr(self, "graph", None), "session_id", None) or "default"
        sessions_file = workspace / "sessions.json"
        sessions = json.loads(sessions_file.read_text(encoding="utf-8")) if sessions_file.is_file() and not exam else {}
        argv = [str(OPENCODE), "run", "--format", "json", "--auto", "--dir", str(workspace)]
        if exam:
            argv += ["--title", f"Exam {session}"]  # never --session: each task starts clean
        else:
            argv += ["--session", sessions[session]] if session in sessions else ["--title", f"Langflow {session}"]
        argv.append(text)
        started = time.monotonic()
        completed = subprocess.run(argv, cwd=workspace, capture_output=True, text=True, timeout=1800, check=False, env=env)
        events = [json.loads(line) for line in completed.stdout.splitlines() if line.startswith("{")]
        if events and events[0].get("sessionID") and not exam:
            sessions[session] = events[0]["sessionID"]
            sessions_file.write_text(json.dumps(sessions, indent=2), encoding="utf-8")

        texts = [(e["part"].get("messageID"), e["part"].get("text", "")) for e in events if e.get("type") == "text" and e.get("part")]
        tools = [e["part"] for e in events if e.get("type") == "tool_use" and e.get("part")]
        usage = _usage(events)
        seconds = round(time.monotonic() - started, 1)
        answer = ""
        if texts:
            last = texts[-1][0]
            answer = "\n\n".join(t for m, t in texts if m == last).strip()
        if completed.returncode != 0 or not answer:
            raise ValueError(f"OpenCode returned no answer (exit {completed.returncode}): {completed.stderr.strip()[-600:]}")
        calls = [f"{p.get('tool')} {json.dumps((p.get('state') or {}).get('input'), ensure_ascii=False)[:80]}" for p in tools]
        opened = events[0].get("sessionID") if events else None
        # Time and tokens of this turn, for the exam runner (bench/langflow_exam.py) and the results page: a sidecar
        # file per Langflow session next to the workspace, and the message's own usage field.
        record = {"session": session, "opencode_session": opened, "model": model, "mode": "exam" if exam else "chat", "seconds": seconds,
                  "tool_calls": [p.get("tool") for p in tools], **usage}
        usage_dir = workspace / "usage"
        usage_dir.mkdir(exist_ok=True)
        (usage_dir / f"{re.sub(r'[^A-Za-z0-9_.-]', '_', session)}.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
        self.status = (f"OpenCode {'exam' if exam else 'chat'} · {model} · session {opened if exam else sessions.get(session)} · {len(tools)} tool call(s) · "
                       f"{seconds} s · {usage['input']} in / {usage['output']} out tokens\n" + "\n".join(calls))
        return Message(text=answer, properties={"usage": {"input_tokens": usage["input"], "output_tokens": usage["output"],
                                                          "total_tokens": usage["input"] + usage["output"]}, "build_duration": seconds})


def _usage(events: list[dict]) -> dict:
    """Tokens of one OpenCode run, from the step events that carry a tokens block (as bench/run_opencode.usage_from_log reads them)."""
    total = {"input": 0, "cached": 0, "cache_write": 0, "output": 0, "calls": 0}
    for event in events:
        tokens = (event.get("part") or {}).get("tokens") or {}
        if not tokens:
            continue
        cache = tokens.get("cache") or {}
        total["input"] += (tokens.get("input") or 0) + (cache.get("read") or 0) + (cache.get("write") or 0)
        total["cached"] += cache.get("read") or 0
        total["cache_write"] += cache.get("write") or 0
        total["output"] += (tokens.get("output") or 0) + (tokens.get("reasoning") or 0)
        total["calls"] += 1
    return total
