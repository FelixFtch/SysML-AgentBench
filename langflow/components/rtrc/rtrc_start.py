"""RTRC Start: begins one run of the RTRC agent flow (Part 2) through the RTRC shell service (bench/shell_service.py)."""
import json
import os
import urllib.error
import urllib.request

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, MultilineInput, Output, StrInput
from lfx.schema.message import Message

AGENTS = {"Qwen direct": "direct", "Claude Code on Qwen (sandbox)": "claude-code", "OpenCode on Qwen (sandbox)": "opencode"}


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


class RtrcStart(Component):
    display_name = "RTRC Start"
    description = "Starts one run of the RTRC agent flow: the brief, the agent and the Qwen model, or a replay of a saved run without model calls."
    icon = "play"
    name = "RtrcStart"

    inputs = [
        MultilineInput(name="brief", display_name="Requirement / brief",
                       info="Everything the agent receives. Empty: the default brief of the 2.2 design space on the results page."),
        DropdownInput(name="agent", display_name="Agent (Qwen only for now)", options=list(AGENTS), value="Qwen direct",
                      info="Qwen directly, or Claude Code / OpenCode running on Qwen inside the bubblewrap sandbox."),
        DropdownInput(name="model", display_name="Qwen model", options=["qwen3.8-flash", "qwen3.8-max"], value="qwen3.8-flash"),
        StrInput(name="replay", display_name="Replay a saved run", value="",
                 info="Empty for a live run. 'latest' or a run id such as 20261006T211951 replays that run without model calls."),
    ]
    outputs = [Output(display_name="Run", name="run", method="start")]

    def start(self) -> Message:
        body = _call("/run/start", {"brief": str(self.brief or ""), "agent": AGENTS.get(self.agent, "direct"),
                                    "model": self.model, "replay": str(self.replay or "").strip()})
        self.status = body["summary"]
        return Message(text=body["summary"])
