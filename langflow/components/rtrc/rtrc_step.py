"""RTRC Step: one step of the RTRC agent flow, run by the existing pipeline through the RTRC shell service.
The step and the paper it applies are chosen in the Step field; the node passes the run id on in its message."""
import json
import os
import re
import urllib.error
import urllib.request

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, MessageInput, Output
from lfx.schema.data import Data
from lfx.schema.message import Message

STEPS = {
    "① Search memory (paper 2)": "/run/retrieve",
    "② Requirements": "/run/requirements",
    "③ New design (paper 3 create)": "/run/design",
    "③ Adapt the similar project (paper 3 modify)": "/run/adapt",
    "④ Official SysML v2 Pilot ⇄ repair (paper 3 loop)": "/run/validate",
    "⑤ Align with memory (paper 1)": "/run/align",
    "⑥ Checks + read-back (paper 3 query)": "/run/checks",
    "Trade-offs (catalog only, code recomputes)": "/run/tradeoffs",
    "⑦ Model diagram, Cameo export, review": "/run/review",
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


class RtrcStep(Component):
    display_name = "RTRC Step"
    description = "One step of the RTRC agent flow, run by the code behind the results page through the RTRC shell service."
    icon = "workflow"
    name = "RtrcStep"

    inputs = [
        MessageInput(name="upstream", display_name="From the previous step", required=False),
        MessageInput(name="upstream_alt", display_name="Or from the other branch", required=False,
                     info="Where two branches join (new or reuse; checks passed or trade-offs), connect the second branch here."),
        DropdownInput(name="step", display_name="Step", options=list(STEPS), value=list(STEPS)[0]),
    ]
    outputs = [
        Output(display_name="Message", name="message", method="as_message"),
        Output(display_name="Data", name="data", method="as_data"),
    ]

    def _result(self) -> dict:
        if getattr(self, "_cached", None) is None:
            match = RUN.search(_text(self.upstream)) or RUN.search(_text(self.upstream_alt))
            if not match:
                raise ValueError("No run id in the incoming message; connect this step after RTRC Start")
            self._cached = _call(STEPS[self.step], {"run": match.group(1)})
            self.status = self._cached["summary"]
        return self._cached

    def as_message(self) -> Message:
        return Message(text=self._result()["summary"])

    def as_data(self) -> Data:
        data = self._result().get("data")
        return Data(data=data if isinstance(data, dict) else {"items": data})
