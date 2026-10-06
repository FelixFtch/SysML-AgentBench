"""RTRC Results: F3, the frozen results (page 1.2) as tables: by task type, by approach, the agents, the side
benchmarks, the retry run and the cost. The matrix, cost chart and diagrams stay on the results page."""
import json
import os
import urllib.error
import urllib.request

from lfx.custom.custom_component.component import Component
from lfx.io import Output
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message

ORDER = ["flash", "max", "opencode", "claude"]
TYPES = ["GEN", "MOD", "ALN", "QRY", "AMB", "RT"]


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


class RtrcResults(Component):
    display_name = "RTRC Results"
    description = "F3: the frozen exam results (revision 2) as tables."
    icon = "table"
    name = "RtrcResults"

    inputs = []
    outputs = [
        Output(display_name="Tables", name="tables", method="as_message"),
        Output(display_name="By task type", name="by_type", method="as_dataframe"),
        Output(display_name="Data", name="data", method="as_data"),
    ]

    def _facts(self) -> dict:
        if getattr(self, "_cached", None) is None:
            self._cached = _call("/facts", {})
            self.status = self._cached["summary"]
        return self._cached["data"]

    def as_message(self) -> Message:
        f = self._facts()
        c = f["cohorts"]
        rows = ["| Task type | " + " | ".join(c[k]["short"] for k in ORDER) + " |", "|---|" + "---:|" * len(ORDER)]
        for t in TYPES:
            rows.append(f"| {t} | " + " | ".join(f"{c[k]['by_type'][t]['pass']}/{c[k]['by_type'][t]['n']}" for k in ORDER) + " |")
        rows.append("| **All** | " + " | ".join(f"**{c[k]['pass']}/{c[k]['n']}**" for k in ORDER) + " |")
        approaches = ["", "| Approach | " + " | ".join(c[k]["label"] for k in ("flash", "max")) + " |", "|---|---:|---:|"]
        for i, cfg in enumerate(c["flash"]["configs"]):
            approaches.append(f"| {cfg['id']} | {cfg['pass']}/{cfg['n']} | {c['max']['configs'][i]['pass']}/{c['max']['configs'][i]['n']} |")
        retry = (f.get("retry") or {}).get("agents") or {}
        extra = ["", "Extra run, the 14 failed tasks retried with agents on qwen3.8-max (not a score): "
                 + "; ".join(f"{a['label']} {a['pass']}/{a['n']}, ${a['usd']:.2f}" for a in retry.values())] if retry else []
        text = "\n".join(["Exam results on the 27 frozen tasks (revision 2)", ""] + rows + approaches + extra
                         + ["", f"Recorded cost about ${f['costs'].get('recorded_usd', 0):.2f} at the list price. The matrix and diagrams are on the results page."])
        return Message(text=text)

    def as_dataframe(self) -> DataFrame:
        c = self._facts()["cohorts"]
        return DataFrame(data=[{"type": t, **{c[k]["short"]: f"{c[k]['by_type'][t]['pass']}/{c[k]['by_type'][t]['n']}" for k in ORDER}} for t in TYPES])

    def as_data(self) -> Data:
        f = self._facts()
        return Data(data={"cohorts": {k: {kk: v for kk, v in f["cohorts"][k].items() if kk in {"label", "pass", "n", "by_type"}} for k in ORDER},
                          "retry": f.get("retry"), "recorded_usd": f["costs"].get("recorded_usd")})
