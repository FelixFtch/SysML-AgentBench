"""Import langflow/flows/*.json into the six Langflow projects of catalog.py (create or update; safe to repeat).

    .venv-langflow/bin/python langflow/flows/import_flows.py

Logs in as the superuser from .langflow/secrets.env (never printed), creates the projects, imports the shared tool
flows first (the Run Flow cards of projects 3 and 4 point at them by name and need their ids), then the rest, in the
order of catalog.ORDER. Flows that still carry a retired name (the single project of decisions 030 to 034) are removed,
and that project is deleted once it is empty. If people log in with another account, run move_to_user.py afterwards.
Prints each flow's editor link.
"""
from __future__ import annotations

import gzip
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from catalog import OLD_PROJECT, PROJECT_OF, PROJECTS, RETIRED  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
BASE = f"http://127.0.0.1:{os.environ.get('LANGFLOW_PORT', '7860')}"
ORDER = [slug for _, _, flows in PROJECTS for slug, _ in flows]


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


def _point_run_flow_cards(flow: dict, imported: dict[str, dict]) -> None:
    """A Run Flow card holds the sub-flow's name in the flow file; the id exists only after the import. Fill it in,
    with the metadata the editor reads when it refreshes the card, so opening the flow does not report
    "Error building graph" and the run path compares the id with the flow it loads."""
    for node in flow["data"]["nodes"]:
        template = node.get("data", {}).get("node", {}).get("template", {})
        name = (template.get("flow_name_selected") or {}).get("value")
        if node.get("data", {}).get("type") != "RunFlow" or not name:
            continue
        target = imported.get(name)
        if target is None:
            raise SystemExit(f"{flow['name']}: its Run Flow card points at {name!r}, which must be imported first (catalog.PROJECTS order)")
        meta = {"id": target["id"], "updated_at": target.get("updated_at")}
        template["flow_id_selected"]["value"] = target["id"]
        template["flow_name_selected"]["options"] = [name]
        template["flow_name_selected"]["options_metadata"] = [meta]
        template["flow_name_selected"]["selected_metadata"] = meta


def _projects(token: str) -> dict[str, dict]:
    return {p["name"]: p for p in _request("GET", "/api/v1/projects/", token) or []}


def main() -> None:
    secrets = _secrets()
    token = _request("POST", "/api/v1/login", form={"username": secrets["LANGFLOW_SUPERUSER"],
                                                    "password": secrets["LANGFLOW_SUPERUSER_PASSWORD"]})["access_token"]
    projects = _projects(token)
    for name, description, _ in PROJECTS:
        if name not in projects:
            projects[name] = _request("POST", "/api/v1/projects/", token, {"name": name, "description": description})
            print(f"project created: {name}")
    flows_by_name = {f["name"]: f for f in _request("GET", "/api/v1/flows/?get_all=true&header_flows=true", token) or []
                     if f.get("folder_id") in {p["id"] for p in projects.values()}}
    imported: dict[str, dict] = {}
    for slug in ORDER:
        flow = json.loads((ROOT / "langflow" / "flows" / f"{slug}.json").read_text(encoding="utf-8"))
        _point_run_flow_cards(flow, imported)
        project = projects[PROJECT_OF[slug]]
        payload = {"name": flow["name"], "description": flow["description"], "data": flow["data"],
                   "endpoint_name": slug, "tags": flow.get("tags") or [], "folder_id": project["id"]}
        if flow["name"] in flows_by_name:
            saved = _request("PATCH", f"/api/v1/flows/{flows_by_name[flow['name']]['id']}", token, payload)
            action = "updated" if flows_by_name[flow["name"]].get("folder_id") == project["id"] else "moved"
        else:
            saved = _request("POST", "/api/v1/flows/", token, payload)
            action = "created"
        imported[flow["name"]] = saved
        print(f"{action}: {PROJECT_OF[slug]} / {flow['name']}\n    {BASE}/flow/{saved['id']}")
    for name in RETIRED:
        if name in flows_by_name:
            _request("DELETE", f"/api/v1/flows/{flows_by_name[name]['id']}", token)
            print(f"removed: {name}")
    old = projects.get(OLD_PROJECT)
    if old:
        left = [f for f in _request("GET", f"/api/v1/flows/?folder_id={old['id']}&get_all=true&header_flows=true", token) or [] if f.get("folder_id") == old["id"]]
        if not left:
            _request("DELETE", f"/api/v1/projects/{old['id']}", token)
            print(f"project removed (empty): {OLD_PROJECT}")
        else:
            print(f"project kept, {len(left)} flow(s) still in it: {OLD_PROJECT}")


if __name__ == "__main__":
    main()
