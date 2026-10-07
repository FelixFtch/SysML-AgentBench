"""RTRC Tool step: one card of an assistant tool unfolded into a sub-flow (decision 034): memory search (library,
MiniLM + FAISS seeds, one hop), write to memory (gate, write, record), validate pasted SysML (save, official Pilot),
and the read-only prompt-part cards of the design pipeline. Every card is stateless and calls the RTRC shell service,
which runs the same code as the results page; the chain order on the canvas is kept by the "From the previous card"
input. The engineer's text (query, "<run id> A", or SysML) comes from the sub-flow's Chat Input."""
import json
import os
import re
import urllib.error
import urllib.request

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, MessageInput, Output
from lfx.schema.data import Data
from lfx.schema.message import Message

# card name -> (endpoint, what the payload carries)
STEPS = {
    "Memory library (paper 2): MaritimeISR + approved designs as cards": ("/tool/memory/library", "none"),
    "MiniLM + FAISS seeds (paper 2): cosine ≥ 0.30 + exact-name bonus": ("/tool/memory/seeds", "query"),
    "One hop of neighbours (paper 2) → cards for the assistant": ("/tool/memory/hop", "query"),
    "Gate: Pilot PASS and all four checks PASS? (read only)": ("/tool/gate", "request"),
    "Write the design into memory (through the page's gate)": ("/tool/write", "request"),
    "Record the approval on the run (page 2.3)": ("/tool/record-approval", "request"),
    "Save the pasted SysML as a file": ("/tool/validate/save", "sysml"),
    "Official SysML v2 Pilot on that file": ("/tool/validate/pilot", "saved"),
    "Prompt part · rules (paper 3)": ("/tool/prompt-part", "run:rules"),
    "Prompt part · attribute template (paper 3)": ("/tool/prompt-part", "run:contract"),
    "Prompt part · retrieved examples or similar project (paper 2)": ("/tool/prompt-part", "run:examples"),
}
RUN = re.compile(r"run (\d{8}T\d{6})")


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


def _text(value) -> str:
    if isinstance(value, list):
        return "\n".join(_text(item) for item in value)
    return str(getattr(value, "text", value) or "")


class RtrcTool(Component):
    display_name = "RTRC Tool step"
    description = "One card of an assistant tool unfolded on the canvas; runs the code behind the results page through the RTRC shell service."
    icon = "wrench"
    name = "RtrcTool"

    inputs = [
        MessageInput(name="text", display_name="Engineer's text", required=False,
                     info="From the sub-flow's Chat Input: the search words, '<run id> A' or '<run id> B', or the pasted SysML."),
        MessageInput(name="upstream", display_name="From the previous card", required=False,
                     info="Keeps the cards in order; the Pilot card reads the saved file from here, the prompt-part cards read the run id."),
        MessageInput(name="upstream_alt", display_name="Or from the other branch", required=False),
        DropdownInput(name="step", display_name="Card", options=list(STEPS), value=list(STEPS)[0]),
    ]
    outputs = [
        Output(display_name="Message", name="message", method="as_message"),
        Output(display_name="Data", name="data", method="as_data"),
    ]

    def _result(self) -> dict:
        if getattr(self, "_cached", None) is None:
            path, kind = STEPS[self.step]
            text, upstream = _text(self.text), _text(self.upstream) or _text(self.upstream_alt)
            if kind == "none":
                payload = {}
            elif kind in ("query", "request", "sysml"):
                payload = {kind: text, "upstream": upstream}  # the write and record cards echo the cards before them
            elif kind == "saved":
                payload = {"saved": upstream}
            else:  # run:<part>
                match = RUN.search(upstream)
                if not match:
                    raise ValueError("No run id in the incoming message; connect this card after a pipeline step")
                payload = {"run": match.group(1), "part": kind.split(":", 1)[1]}
            self._cached = _call(path, payload)
            self.status = self._cached["summary"]
        return self._cached

    def as_message(self) -> Message:
        return Message(text=self._result()["summary"])

    def as_data(self) -> Data:
        data = self._result().get("data")
        return Data(data=data if isinstance(data, dict) else {"items": data})
