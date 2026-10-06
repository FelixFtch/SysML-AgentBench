"""RTRC Cameo export: writes a run's officially parsed designs as .sysml files for Cameo's SysML v2 edition and says
how to check them. Cameo has no headless command, so a person opens the file; the result is recorded with RTRC Cameo record."""
import json
import os
import re
import urllib.error
import urllib.request

from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, Output
from lfx.schema.message import Message

RUN = re.compile(r"(\d{8}T\d{6})")


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


class RtrcCameoExport(Component):
    display_name = "RTRC Cameo export (when licensed)"
    description = "Exports a run's designs for Cameo's SysML v2 edition. The official Pilot stays the judge; Cameo's result is recorded as agreement."
    icon = "upload"
    name = "RtrcCameoExport"

    inputs = [MessageTextInput(name="run_id", display_name="Run id", value="", info="A run id such as 20261006T211951, or a message that contains it.")]
    outputs = [Output(display_name="Instructions", name="message", method="export")]

    def export(self) -> Message:
        match = RUN.search(str(getattr(self.run_id, "text", self.run_id) or ""))
        if not match:
            raise ValueError("Give a run id")
        body = _call("/cameo/export", {"run": match.group(1)})
        self.status = body["summary"]
        return Message(text=body["summary"])
