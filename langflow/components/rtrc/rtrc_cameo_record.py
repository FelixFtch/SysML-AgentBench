"""RTRC Cameo record: one node per Human Input branch; stores the person's Cameo check of a design next to the official
Pilot's verdict (interoperability evidence). The Pilot stays the judge."""
import json
import os
import re
import urllib.error
import urllib.request

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, MessageInput, Output, StrInput
from lfx.schema.message import Message

RUN = re.compile(r"run (\d{8}T\d{6})")
RESULTS = ["Opens cleanly", "Errors in Cameo", "Not checked yet"]


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


class RtrcCameoRecord(Component):
    display_name = "RTRC Cameo record"
    description = "Put one after each Human Input branch. Stores the person's Cameo check of a design next to the official Pilot's verdict."
    icon = "clipboard-list"
    name = "RtrcCameoRecord"

    inputs = [
        MessageInput(name="upstream", display_name="From the person's choice", required=False),
        DropdownInput(name="result", display_name="This branch", options=RESULTS, value=RESULTS[-1]),
        DropdownInput(name="key", display_name="Design", options=["A", "B"], value="A"),
        StrInput(name="note", display_name="Note (for example the Cameo error)", value="", required=False),
    ]
    outputs = [Output(display_name="Message", name="message", method="record")]

    def record(self) -> Message:
        text = str(getattr(self.upstream, "text", self.upstream) or "")
        if not text.strip():
            self.status = f"{self.result}: not chosen"
            return Message(text="")
        match = RUN.search(text)
        if not match:
            raise ValueError("No run id in the incoming message")
        body = _call("/cameo/result", {"run": match.group(1), "key": self.key, "result": self.result.lower(), "note": str(self.note or "")})
        self.status = body["summary"]
        return Message(text=body["summary"])
