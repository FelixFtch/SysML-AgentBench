"""RTRC Record: ⑨ one node per Human Input branch. Approve writes the design into memory (paper 2); every branch saves
the person's decision with the grades and the times, the record page 2.3 shows."""
import json
import os
import re
import urllib.error
import urllib.request

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, MessageInput, Output, StrInput
from lfx.schema.data import Data
from lfx.schema.message import Message

RUN = re.compile(r"run (\d{8}T\d{6})")
DECISIONS = {"Approve design A": "A", "Approve design B": "B", "Reject": None, "Send back": None}


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


class RtrcRecord(Component):
    display_name = "RTRC Record the decision"
    description = ("⑨ Put one after each Human Input branch. Approve writes the design into memory (paper 2; refused unless all four "
                   "checks passed). Every branch saves the decision with each stage's verdict, attempts, seconds, model calls and cost.")
    icon = "clipboard-list"
    name = "RtrcRecord"

    inputs = [
        MessageInput(name="upstream", display_name="From the person's choice", required=False),
        DropdownInput(name="decision", display_name="This branch", options=list(DECISIONS), value="Reject"),
        StrInput(name="note", display_name="Note", value="", required=False),
    ]
    outputs = [
        Output(display_name="Message", name="message", method="as_message"),
        Output(display_name="Data", name="data", method="as_data"),
    ]

    def _result(self) -> dict:
        if getattr(self, "_cached", None) is None:
            text = str(getattr(self.upstream, "text", self.upstream) or "")
            if not text.strip():
                self.status = f"{self.decision}: not chosen"
                self._cached = {"summary": "", "data": {}}
                return self._cached
            match = RUN.search(text)
            if not match:
                raise ValueError("No run id in the incoming message")
            key, note, lines = DECISIONS.get(self.decision), str(self.note or ""), []
            if key:
                approval = _call("/run/approve", {"run": match.group(1), "key": key})
                lines.append(approval["summary"].splitlines()[-1])
                note = (note + " " + lines[-1]).strip()
            body = _call("/run/decision", {"run": match.group(1), "decision": self.decision, "note": note})
            self._cached = {"summary": "\n".join(lines + [body["summary"]]), "data": body.get("data") or {}}
            self.status = self._cached["summary"]
        return self._cached

    def as_message(self) -> Message:
        return Message(text=self._result()["summary"])

    def as_data(self) -> Data:
        return Data(data=self._result()["data"])
