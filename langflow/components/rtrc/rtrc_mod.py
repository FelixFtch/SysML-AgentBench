"""RTRC MOD change: F5, the MOD change chain (page 2.4): the model edits an existing model, the official tool
judges it, a limit change stops for a person, and the model reads the edited model back. Replayed or run live."""
import json
import os
import urllib.error
import urllib.request

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, Output
from lfx.schema.data import Data
from lfx.schema.message import Message

TASKS = ["MOD-01", "MOD-02", "MOD-03", "MOD-04", "MOD-05"]


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


class RtrcModChange(Component):
    display_name = "RTRC MOD change"
    description = "F5: one change to an existing model (MOD-01 to MOD-05): the latest saved run, or a new run on Qwen (two model calls)."
    icon = "git-compare"
    name = "RtrcModChange"

    inputs = [
        DropdownInput(name="task", display_name="Task", options=TASKS, value="MOD-05"),
        DropdownInput(name="mode", display_name="Mode", options=["Replay the latest run", "Run it again (live)"], value="Replay the latest run"),
    ]
    outputs = [
        Output(display_name="Case", name="case", method="as_data"),
        Output(display_name="Summary", name="summary", method="as_message"),
    ]

    def _result(self) -> dict:
        if getattr(self, "_cached", None) is None:
            path = "/mod/case" if self.mode.startswith("Replay") else "/mod/run"
            self._cached = _call(path, {"task": self.task})
            self.status = self._cached["summary"]
        return self._cached

    def as_data(self) -> Data:
        return Data(data=self._result()["data"])

    def as_message(self) -> Message:
        return Message(text=self._result()["summary"])
