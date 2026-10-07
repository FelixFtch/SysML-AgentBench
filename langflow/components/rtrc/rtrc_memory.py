"""RTRC Memory: F0, the library the agent searches (paper 2): MaritimeISR plus every approved design, as cards
built from the official Pilot parse. The DataFrame output can be ingested into a Langflow knowledge base for browsing."""
import json
import os
import urllib.error
import urllib.request

from lfx.custom.custom_component.component import Component
from lfx.io import MessageInput, Output
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message


def _call(path: str, payload: dict) -> dict:
    url = os.environ.get("RTRC_SHELL_URL", "http://127.0.0.1:8781") + path
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                     headers={"Content-Type": "application/json", "X-RTRC-Token": os.environ.get("RTRC_SHELL_TOKEN", "")})
    try:
        with urllib.request.urlopen(request, timeout=1800) as response:
            body = json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        body = json.loads(exc.read() or b"{}")
    except urllib.error.URLError as exc:
        raise ValueError(f"The RTRC shell service is not reachable at {url} ({exc.reason}); start it with scripts/langflow.sh") from exc
    if not body.get("ok"):
        raise ValueError(body.get("error") or "The RTRC shell service returned an error")
    return body


class RtrcMemory(Component):
    display_name = "RTRC Memory (paper 2)"
    description = "F0: MaritimeISR and every approved design as element cards from the official parse, with their links."
    icon = "database"
    name = "RtrcMemory"

    inputs = [
        MessageInput(name="after", display_name="After (optional)", required=False, advanced=True,
                     info="Connect the card that changes the memory (the write card of the write-to-memory tool) so the "
                          "library is read after the write; F0 leaves it empty."),
    ]
    outputs = [
        Output(display_name="Summary", name="summary", method="as_message"),
        Output(display_name="Cards", name="cards", method="as_dataframe"),
        Output(display_name="Data", name="data", method="as_data"),
    ]

    def _result(self) -> dict:
        if getattr(self, "_cached", None) is None:
            self._cached = _call("/memory", {})
            self.status = self._cached["summary"]
        return self._cached

    def as_message(self) -> Message:
        return Message(text=self._result()["summary"])

    def as_dataframe(self) -> DataFrame:
        rows = self._result()["data"]["rows"]
        return DataFrame(data=[{key: row[key] for key in ("id", "type", "name", "source", "links", "documentation", "text")} for row in rows])

    def as_data(self) -> Data:
        return Data(data={"sources": self._result()["data"]["sources"]})
