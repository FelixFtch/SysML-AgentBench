"""RTRC OpenCode assistant: one turn of the conversational design assistant per chat message.

The assistant is OpenCode (the exam's pinned binary) on the local Qwen3.8-27B served by Ollama, with the RTRC MCP
tools (tools/assistant_mcp.py on 127.0.0.1:8782) as its only tools; its file and shell tools are off. The workspace
is prepared by tools/assistant/workspace.py outside the repository. Each Langflow chat session maps to one OpenCode
session, so the conversation continues across messages. Decision 032.
"""
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

from lfx.custom.custom_component.component import Component
from lfx.io import MessageInput, Output
from lfx.schema.message import Message

# Langflow runs component code from a copy, so the repository is found from the environment (RTRC_ROOT, set by
# scripts/langflow.sh) or from the virtual environment, which lives at <repository>/.venv-langflow.
ROOT = Path(os.environ.get("RTRC_ROOT") or Path(sys.prefix).resolve().parent)
OPENCODE = ROOT / "tools" / "opencode" / "opencode"
MCP_URL = os.environ.get("RTRC_ASSISTANT_MCP_URL", "http://127.0.0.1:8782/mcp")


class RtrcOpenCodeAssistant(Component):
    display_name = "RTRC OpenCode assistant"
    description = ("One turn of the RTRC design assistant: OpenCode on the local Qwen3.8-27B with the RTRC tools "
                   "(memory, the verified design pipeline, the official Pilot, the memory gate, decisions, Cameo export).")
    icon = "bot"
    name = "RtrcOpenCodeAssistant"

    inputs = [
        MessageInput(name="message", display_name="Engineer's message",
                     info="Ask what exists, describe a need, confirm the brief it proposes, or decide on a run."),
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
        prepared = subprocess.run(["python3", str(ROOT / "tools" / "assistant" / "workspace.py")], capture_output=True, text=True, timeout=120, check=False)
        if prepared.returncode != 0:
            raise ValueError(f"Could not prepare the assistant workspace: {prepared.stderr.strip()[-400:]}")
        workspace = Path(prepared.stdout.strip())

        session = getattr(self.message, "session_id", None) or getattr(getattr(self, "graph", None), "session_id", None) or "default"
        sessions_file = workspace / "sessions.json"
        sessions = json.loads(sessions_file.read_text(encoding="utf-8")) if sessions_file.is_file() else {}
        argv = [str(OPENCODE), "run", "--format", "json", "--auto", "--dir", str(workspace)]
        argv += ["--session", sessions[session]] if session in sessions else ["--title", f"Langflow {session}"]
        argv.append(text)
        completed = subprocess.run(argv, cwd=workspace, capture_output=True, text=True, timeout=1800, check=False)
        events = [json.loads(line) for line in completed.stdout.splitlines() if line.startswith("{")]
        if events and events[0].get("sessionID"):
            sessions[session] = events[0]["sessionID"]
            sessions_file.write_text(json.dumps(sessions, indent=2), encoding="utf-8")

        texts = [(e["part"].get("messageID"), e["part"].get("text", "")) for e in events if e.get("type") == "text" and e.get("part")]
        tools = [e["part"] for e in events if e.get("type") == "tool_use" and e.get("part")]
        answer = ""
        if texts:
            last = texts[-1][0]
            answer = "\n\n".join(t for m, t in texts if m == last).strip()
        if completed.returncode != 0 or not answer:
            raise ValueError(f"OpenCode returned no answer (exit {completed.returncode}): {completed.stderr.strip()[-600:]}")
        calls = [f"{p.get('tool')} {json.dumps((p.get('state') or {}).get('input'), ensure_ascii=False)[:80]}" for p in tools]
        self.status = f"OpenCode session {sessions.get(session)} · {len(tools)} tool call(s)\n" + "\n".join(calls)
        return Message(text=answer)
