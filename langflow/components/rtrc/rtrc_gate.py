"""RTRC Gate record: one node per Human Input branch of a stop-and-ask gate (AGENTS.md: a stated limit may only change
with a person's approval). Stores the choice in analysis/langflow-gates.jsonl."""
import json
import os
import urllib.error
import urllib.request

from lfx.custom.custom_component.component import Component
from lfx.io import MessageInput, Output, StrInput
from lfx.schema.message import Message


def _call(path: str, payload: dict) -> dict:
    url = os.environ.get("RTRC_SHELL_URL", "http://127.0.0.1:8781") + path
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                     headers={"Content-Type": "application/json", "X-RTRC-Token": os.environ.get("RTRC_SHELL_TOKEN", "")})
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            body = json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        body = json.loads(exc.read() or b"{}")
    except urllib.error.URLError as exc:
        raise ValueError(f"The RTRC shell service is not reachable at {url} ({exc.reason}); start it with scripts/langflow.sh") from exc
    if not body.get("ok"):
        raise ValueError(body.get("error") or "The RTRC shell service returned an error")
    return body


class RtrcGateRecord(Component):
    display_name = "RTRC Gate record"
    description = "Put one after each Human Input branch of a stop-and-ask gate; records the person's choice."
    icon = "shield-check"
    name = "RtrcGateRecord"

    inputs = [
        MessageInput(name="upstream", display_name="From the person's choice", required=False),
        StrInput(name="gate", display_name="Gate", value="stated limit"),
        StrInput(name="choice", display_name="This branch", value=""),
    ]
    outputs = [Output(display_name="Message", name="message", method="record")]

    def record(self) -> Message:
        text = str(getattr(self.upstream, "text", self.upstream) or "")
        if not text.strip():
            self.status = f"{self.choice}: not chosen"
            return Message(text="")
        body = _call("/gate/decision", {"gate": self.gate, "choice": self.choice, "context": text[:2000]})
        self.status = body["summary"]
        return Message(text=body["summary"])
