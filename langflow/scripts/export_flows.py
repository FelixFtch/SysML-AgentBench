"""Export flows from a running Langflow back into the repository's flow files, keys scrubbed.

    .venv-langflow/bin/python langflow/scripts/export_flows.py                       # every catalog flow this login owns
    .venv-langflow/bin/python langflow/scripts/export_flows.py "Direct model chat · P1 repair from errors"
    .venv-langflow/bin/python langflow/scripts/export_flows.py --login FelixFang       # the flows of the account people use
    .venv-langflow/bin/python langflow/scripts/export_flows.py --login FelixFang --new "My P1 with a checklist" --project 1-direct-model

This closes the loop that Langflow's own Share -> Export opens: edit a flow on the canvas, export it here, commit the
file, open a pull request. The file lands where catalog.flow_file() says (a flow in the catalog) or in the project
folder you name (--new; the script prints the line to add to catalog.PROJECTS). What is written is the same JSON that
Langflow's export writes, with three differences made on purpose:
- every field whose name says key, token, password or secret is emptied unless it is a Global Variable reference
  (load_from_db), so a file can never carry a credential;
- the ids of Run Flow targets are dropped (they belong to one Langflow instance; the import fills them in by name);
- message timestamps are pinned, so an unchanged flow gives an unchanged file.
Langflow shows a login only its own flows, so pass --login for the account that owns the flow; the password is asked
for on the terminal and never printed (the superuser's comes from .langflow/secrets.env).
"""
from __future__ import annotations

import argparse
import getpass
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "langflow" / "flows"))
sys.path.insert(0, str(ROOT / "langflow" / "scripts"))
from catalog import FLOWS_DIR, FOLDERS, NAMES, SLUG_OF, flow_file  # noqa: E402
from import_flows import _request, _secrets  # noqa: E402

SECRET_FIELD = re.compile(r"api[_-]?key|token|password|secret", re.I)


def _login(username: str | None) -> str:
    if username:
        password = getpass.getpass(f"Langflow password for {username}: ")
    else:
        secrets = _secrets()
        username, password = secrets["LANGFLOW_SUPERUSER"], secrets["LANGFLOW_SUPERUSER_PASSWORD"]
    return _request("POST", "/api/v1/login", form={"username": username, "password": password})["access_token"]


def _scrub(flow: dict) -> int:
    """Empty every credential-looking field that is not a Global Variable reference; drop Run Flow ids. Returns how many fields were emptied."""
    emptied = 0
    for node in flow["data"]["nodes"]:
        data = node.get("data", {})
        template = data.get("node", {}).get("template", {})
        for name, field in template.items():
            if not isinstance(field, dict):
                continue
            if SECRET_FIELD.search(name) and field.get("value") and not field.get("load_from_db"):
                field["value"] = ""
                emptied += 1
        if data.get("type") == "RunFlow":
            if "flow_id_selected" in template:
                template["flow_id_selected"]["value"] = None
            for key in ("options_metadata", "selected_metadata"):
                template.get("flow_name_selected", {}).pop(key, None)
    return emptied


def _stable(value):
    if isinstance(value, dict):
        return {key: "2026-10-06 00:00:00 UTC" if key == "timestamp" and isinstance(item, str) else _stable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_stable(item) for item in value]
    return value


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("names", nargs="*", help="flow names as Langflow shows them (default: every catalog flow this login owns)")
    parser.add_argument("--login", default=None, help="the Langflow account that owns the flows (default: the superuser of .langflow/secrets.env)")
    parser.add_argument("--new", default=None, help="a flow that is not in the catalog yet: its name in Langflow")
    parser.add_argument("--project", default=None, choices=sorted(FOLDERS.values()), help="with --new: the project folder to write it into")
    args = parser.parse_args()
    if args.new and not args.project:
        parser.error("--new needs --project <folder>")
    token = _login(args.login)
    visible = {f["name"]: f for f in _request("GET", "/api/v1/flows/?get_all=true&header_flows=true", token) or []}
    wanted = [args.new] if args.new else (args.names or [name for name in NAMES.values() if name in visible])
    for name in wanted:
        if name not in visible:
            print(f"not visible to this login: {name}  (try --login <owner>)", file=sys.stderr)
            continue
        full = _request("GET", f"/api/v1/flows/{visible[name]['id']}", token)
        if args.new:
            slug = _slug(name)
            target = FLOWS_DIR / args.project / f"{slug}.json"
        else:
            slug = SLUG_OF[name]
            target = flow_file(slug)
        flow = {"name": full["name"], "description": full.get("description") or "", "endpoint_name": slug, "is_component": False,
                "tags": full.get("tags") or [], "data": full["data"]}
        emptied = _scrub(flow)
        flow = _stable(flow)
        flow["data"]["edges"].sort(key=lambda edge: edge["id"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(flow, indent=2, ensure_ascii=False), encoding="utf-8")
        nodes = flow["data"]["nodes"]
        print(f"{target.relative_to(ROOT)}: {sum(1 for n in nodes if n['type'] == 'genericNode')} nodes, {len(flow['data']['edges'])} edges"
              + (f", {emptied} credential field(s) emptied" if emptied else ""))
        if args.new:
            project = next(p for p, folder in FOLDERS.items() if folder == args.project)
            print(f'add to catalog.PROJECTS under "{project}":  ("{slug}", "{name}"),')


if __name__ == "__main__":
    main()
