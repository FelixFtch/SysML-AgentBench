"""RTRC Exam cell: F1 / F2, one exam cell, replayed from the archive or run live on Qwen; the answer key is used
only by the scorer and never returned."""
import json
import os
import urllib.error
import urllib.request

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, Output, StrInput
from lfx.schema.data import Data
from lfx.schema.message import Message

MODES = ["Replay a graded cell", "Live: direct Qwen (P0–P3)", "Live: sandboxed agent on Qwen"]


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


class RtrcExamCell(Component):
    display_name = "RTRC Exam cell"
    description = "One exam cell: replay any graded cell, or run a sealed task live on Qwen (direct or a sandboxed coding agent). Not added to any score."
    icon = "clipboard-check"
    name = "RtrcExamCell"

    inputs = [
        DropdownInput(name="mode", display_name="Mode", options=MODES, value=MODES[0]),
        StrInput(name="cell", display_name="Cell to replay", value="flash:1:GEN-03:P1",
                 info="candidate:repeat:task:approach, e.g. flash:1:GEN-03:P1, max:2:ALN-02:P3, opencode:1:MOD-05:P-CODE, retry-claude:1:ALN-02"),
        StrInput(name="task_id", display_name="Task for a live run", value="GEN-03"),
        # Not named "configuration": Langflow parses any parameter whose name contains "config" as JSON and drops it when
        # that fails (lfx.interface.initialize.loading.convert_kwargs), so a live run always fell back to the default.
        DropdownInput(name="approach", display_name="Approach (direct)", options=["P0", "P1", "P2", "P3"], value="P1"),
        DropdownInput(name="agent", display_name="Agent (sandboxed)", options=["opencode", "claude-code"], value="opencode"),
        DropdownInput(name="model", display_name="Model", options=["qwen3.8-flash", "qwen3.8-max", "qwen3.8-27b (Ollama)"], value="qwen3.8-flash", combobox=True,
                      info="Pick one of the names our runs used, or type any name: a cloud name goes to the endpoint of .env, '<tag> (Ollama)' to a model you pulled "
                           "into Ollama. The frozen columns were run on qwen3.8-flash (docs/langflow/02-keys-and-models.md)."),
    ]
    outputs = [
        Output(display_name="Cell", name="cell_data", method="as_data"),
        Output(display_name="Summary", name="summary", method="as_message"),
    ]

    def _result(self) -> dict:
        if getattr(self, "_cached", None) is None:
            if self.mode == MODES[0]:
                body = _call("/exam/cell", {"id": str(self.cell).strip()})
            elif self.mode == MODES[1]:
                body = _call("/exam/run", {"task_id": str(self.task_id).strip(), "configuration": self.approach, "model": self.model})
            else:
                body = _call("/exam/agent-run", {"task_id": str(self.task_id).strip(), "agent": self.agent, "model": self.model})
            self._cached = body
            self.status = body["summary"]
        return self._cached

    def as_data(self) -> Data:
        return Data(data=self._result()["data"])

    def as_message(self) -> Message:
        return Message(text=self._result()["summary"])
