"""RTRC Chat: the chat version of an exam candidate (decision 036). The person's message goes to the candidate as
written, in the conversation of this Langflow session, and the reply comes back. Nothing is scored.

Candidates: the direct model with one approach (P0 one answer; P1 the official Pilot's complete error list back for
repair; P2 an outline first; P3 retrieval from the official examples with the person's words, then the outline), or a
coding agent in a persistent sandbox (OpenCode, Claude Code) with ./validate and its own session continued across
messages. The shell service runs it (bench/shell_service.py /chat/turn, bench/chat_turns.py)."""
import json
import os
import urllib.error
import urllib.request

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, IntInput, MessageInput, Output
from lfx.schema.data import Data
from lfx.schema.message import Message

CANDIDATES = {
    "Direct model · P0 one answer": "direct-P0",
    "Direct model · P1 repair from errors": "direct-P1",
    "Direct model · P2 outline first": "direct-P2",
    "Direct model · P3 retrieval then outline": "direct-P3",
    "OpenCode in the sandbox": "opencode",
    "Claude Code in the sandbox": "claude-code",
}
MODELS = ["qwen3.8-flash", "qwen3.8-max", "qwen3.8-27b (Ollama)"]


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


class RtrcChat(Component):
    display_name = "RTRC Chat"
    description = ("A person's message to an exam candidate, as written, in a conversation that continues: the direct model with one "
                   "approach, or a coding agent in its sandbox. The official Pilot parses a reply only when it holds a model. Nothing is scored.")
    icon = "message-square-text"
    name = "RtrcChat"

    inputs = [
        MessageInput(name="message", display_name="Message", info="Whatever the person writes. A question gets an answer; a request for a model gets a model."),
        DropdownInput(name="candidate", display_name="Candidate", options=list(CANDIDATES), value=list(CANDIDATES)[1]),
        DropdownInput(name="model", display_name="Qwen model", options=MODELS, value=MODELS[0],
                      info="qwen3.8-flash is the model of the frozen exam; qwen3.8-27b (Ollama) is the 3-bit model on this machine (direct, OpenCode, or Claude Code through its router)."),
        IntInput(name="rounds", display_name="Repair rounds (P1 to P3)", value=20, advanced=True,
                 info="How many times the official Pilot's error list goes back to the model in this conversation. P0 never repairs."),
        IntInput(name="history", display_name="Messages kept", value=30, advanced=True,
                 info="How many earlier messages of this session the direct model sees. The sandboxed agents keep their own session."),
    ]
    outputs = [
        Output(display_name="Reply", name="reply", method="as_message"),
        Output(display_name="Details", name="details", method="as_data"),
    ]

    def _result(self) -> dict:
        if getattr(self, "_cached", None) is None:
            text = (self.message.text if isinstance(self.message, Message) else str(self.message or "")).strip()
            if not text:
                raise ValueError("Write a message")
            session = getattr(self.message, "session_id", None) or getattr(getattr(self, "graph", None), "session_id", None) or "default"
            self._cached = _call("/chat/turn", {"text": text, "candidate": CANDIDATES[self.candidate], "model": self.model, "session": str(session),
                                                "rounds": self.rounds, "history": self.history})
            self.status = self._cached["summary"]
        return self._cached

    def as_message(self) -> Message:
        data = self._result()["data"]
        usage = data.get("usage") or {}
        return Message(text=data.get("answer") or "",
                       properties={"usage": {"input_tokens": usage.get("input") or 0, "output_tokens": usage.get("output") or 0,
                                             "total_tokens": (usage.get("input") or 0) + (usage.get("output") or 0)},
                                   "build_duration": data.get("seconds")})

    def as_data(self) -> Data:
        return Data(data=self._result()["data"])
