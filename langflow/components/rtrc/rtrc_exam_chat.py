"""RTRC Exam chat: the chat version of an exam candidate (decision 035). A task text comes in from Chat Input, the
candidate answers it the way it answers an exam cell, and the answer comes out. There is no answer key, so nothing
is scored; the official Pilot still parses a model answer.

Candidates: the direct model with one approach (P0 one-shot; P1 repair from the Pilot's complete error list; P2
outline first; P3 retrieval, then outline), or a coding agent in the sandbox (OpenCode, Claude Code) with AGENTS.md
and ./validate. The shell service runs the same code as the exam cell (bench/shell_service.py /exam/chat)."""
import json
import os
import re
import urllib.error
import urllib.request

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, MessageInput, Output, StrInput
from lfx.schema.data import Data
from lfx.schema.message import Message

CANDIDATES = {
    "Direct model · P0 one-shot": "direct-P0",
    "Direct model · P1 repair from errors": "direct-P1",
    "Direct model · P2 outline first": "direct-P2",
    "Direct model · P3 retrieval then outline": "direct-P3",
    "OpenCode in the sandbox": "opencode",
    "Claude Code in the sandbox": "claude-code",
}
TYPES = ["GEN · generate a new model", "MOD · modify the given model", "ALN · align the two given packages",
         "QRY · answer a question about the given model in JSON", "AMB · ask when a number is missing", "RT · restate the given model in sentences"]
MODELS = ["qwen3.8-flash", "qwen3.8-max", "qwen3.8-27b (Ollama)"]
PACKAGE_LINE = re.compile(r"Package name:\s*([A-Za-z_][A-Za-z0-9_]*)")


def _call(path: str, payload: dict) -> dict:
    url = os.environ.get("RTRC_SHELL_URL", "http://127.0.0.1:8781") + path
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                     headers={"Content-Type": "application/json", "X-RTRC-Token": os.environ.get("RTRC_SHELL_TOKEN", "")})
    try:
        with urllib.request.urlopen(request, timeout=3600) as response:
            body = json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        body = json.loads(exc.read() or b"{}")
    except urllib.error.URLError as exc:
        raise ValueError(f"The RTRC shell service is not reachable at {url} ({exc.reason}); start it with scripts/langflow.sh") from exc
    if not body.get("ok"):
        raise ValueError(body.get("error") or "The RTRC shell service returned an error")
    return body


class RtrcExamChat(Component):
    display_name = "RTRC Exam chat"
    description = "A task text in, an exam candidate's answer out: the direct model with one approach, or a sandboxed coding agent. No answer key, nothing scored."
    icon = "message-square-text"
    name = "RtrcExamChat"

    inputs = [
        MessageInput(name="message", display_name="Task text", info="The task statement, as the exam would give it; for MOD, ALN, QRY and RT tasks paste the given model(s) as fenced sysml blocks after it."),
        DropdownInput(name="candidate", display_name="Candidate", options=list(CANDIDATES), value=list(CANDIDATES)[0]),
        DropdownInput(name="model", display_name="Qwen model", options=MODELS, value=MODELS[0],
                      info="qwen3.8-flash is the model of the frozen exam; qwen3.8-27b (Ollama) is the 3-bit model on this machine (direct or OpenCode)."),
        DropdownInput(name="task_type", display_name="Task type", options=TYPES, value=TYPES[0],
                      info="Decides the rules the direct model gets and whether the official Pilot parses the answer. Sandboxed agents read the task text alone."),
        StrInput(name="package", display_name="Package name (GEN, MOD, ALN)", value="", advanced=True,
                 info="Empty: read from a 'Package name:' line in the task text, else Inbox."),
    ]
    outputs = [
        Output(display_name="Answer", name="answer", method="as_message"),
        Output(display_name="Details", name="details", method="as_data"),
    ]

    def _result(self) -> dict:
        if getattr(self, "_cached", None) is None:
            text = (self.message.text if isinstance(self.message, Message) else str(self.message or "")).strip()
            if not text:
                raise ValueError("Write the task text")
            package = str(self.package or "").strip()
            if not package:
                match = PACKAGE_LINE.search(text)
                package = match.group(1) if match else ""
            self._cached = _call("/exam/chat", {"text": text, "candidate": CANDIDATES[self.candidate], "model": self.model,
                                                "task_type": str(self.task_type).split(" ", 1)[0], "package": package})
            self.status = self._cached["summary"]
        return self._cached

    def as_message(self) -> Message:
        return Message(text=self._result()["data"].get("answer") or "")

    def as_data(self) -> Data:
        return Data(data=self._result()["data"])
