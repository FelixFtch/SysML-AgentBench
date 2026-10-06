"""Import langflow/flows/*.json into the Langflow project "RTRC SysML-AgentBench" (create or update; safe to repeat).

    .venv-langflow/bin/python langflow/flows/import_flows.py

Logs in as the superuser from .langflow/secrets.env (never printed) and prints each flow's editor link.
"""
from __future__ import annotations

import gzip
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = f"http://127.0.0.1:{os.environ.get('LANGFLOW_PORT', '7860')}"
PROJECT = "RTRC SysML-AgentBench"
ORDER = ["rtrc-agent-flow", "rtrc-f0-memory", "rtrc-f1-exam-direct", "rtrc-f2-exam-agent", "rtrc-f3-results",
         "rtrc-f5-mod-change", "rtrc-cameo-check"]


def _secrets() -> dict:
    values = {}
    for line in (ROOT / ".langflow" / "secrets.env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("'\"")
    return values


def _request(method: str, path: str, token: str | None = None, body=None, form: dict | None = None):
    headers = {"Accept": "application/json"}
    data = None
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    with urllib.request.urlopen(request, timeout=120) as response:
        raw = response.read()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return json.loads(raw) if raw else None


def main() -> None:
    secrets = _secrets()
    token = _request("POST", "/api/v1/login", form={"username": secrets["LANGFLOW_SUPERUSER"],
                                                    "password": secrets["LANGFLOW_SUPERUSER_PASSWORD"]})["access_token"]
    project = next((p for p in _request("GET", "/api/v1/projects/", token) if p["name"] == PROJECT), None)
    if project is None:
        project = _request("POST", "/api/v1/projects/", token, {
            "name": PROJECT, "description": "The RTRC SysML v2 agent flows: the Part 2 agent flow, memory, exam cells, results, MOD change, Cameo check."})
    existing = {f["name"]: f for f in _request("GET", f"/api/v1/flows/?folder_id={project['id']}&get_all=true&header_flows=true", token) or []
                if f.get("folder_id") == project["id"]}
    for slug in ORDER:
        flow = json.loads((ROOT / "langflow" / "flows" / f"{slug}.json").read_text(encoding="utf-8"))
        payload = {"name": flow["name"], "description": flow["description"], "data": flow["data"],
                   "endpoint_name": slug, "tags": flow.get("tags") or [], "folder_id": project["id"]}
        if flow["name"] in existing:
            saved = _request("PATCH", f"/api/v1/flows/{existing[flow['name']]['id']}", token, payload)
            action = "updated"
        else:
            saved = _request("POST", "/api/v1/flows/", token, payload)
            action = "created"
        print(f"{action}: {flow['name']}\n    {BASE}/flow/{saved['id']}")


if __name__ == "__main__":
    main()
