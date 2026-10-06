"""Parity between the Langflow flows and the results page.

    python3 bench/langflow_parity.py [--run 20261006T211951]

The Langflow nodes call bench/shell_service.py, which calls the functions the page uses. This checks, on a saved
run and without model calls, that going through the shell changes nothing:
1. Retrieval: the shell's ① Search memory returns exactly retrieve_existing(brief) (identical JSON).
2. Prompts: the design prompt the shell sends equals the page's write_design prompt; the agent prompt, which the
   shell builds itself, is the page's prompt plus the answer.md / ./validate instruction.
3. Official Pilot: the run's saved designs parse again with the same verdict and the same diagnostics.
Needs the shell service running for check 1 (it opens one session that stops after retrieval).
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bench import discover, shell_service  # noqa: E402

SHELL = "http://127.0.0.1:8781"


def _shell(path: str, payload: dict) -> dict:
    request = urllib.request.Request(SHELL + path, data=json.dumps(payload).encode(), method="POST",
                                     headers={"Content-Type": "application/json", "X-RTRC-Token": shell_service._token()})
    with urllib.request.urlopen(request, timeout=600) as response:
        return json.loads(response.read())


def _same(a, b) -> bool:
    return json.dumps(a, sort_keys=True, ensure_ascii=False) == json.dumps(b, sort_keys=True, ensure_ascii=False)


def check_retrieval(brief: str) -> tuple[bool, str]:
    started = _shell("/run/start", {"brief": brief, "agent": "direct", "model": "qwen3.8-flash"})
    shell = _shell("/run/retrieve", {"run": started["run"]})["data"]["retrieval"]
    page = discover.retrieve_existing(brief)
    seeds = sum(1 for node in page.get("nodes", []) if node.get("role") == "seed")
    return _same(shell, page), f"{len(page.get('nodes', []))} elements ({seeds} seeds), {len(page.get('cards', []))} cards, session {started['run']}"


def check_prompts(record: dict) -> tuple[bool, str]:
    captured: list = []

    def fake_chat(messages, **_kwargs):
        captured.append(json.loads(json.dumps(messages)))
        return {"text": "```sysml\npackage DesignA { }\n```", "model": "parity", "usage": {}}

    requirements = record["requirements"]["requirements"]
    cards = record["retrieval"].get("cards")
    real_chat = discover.chat
    discover.chat = fake_chat
    try:
        page = discover.write_design(record["brief"], requirements, "DesignA", discover.VARIANT_A, cards)["messages"]
        session = {"record": {"brief": record["brief"], "requirements": {"requirements": requirements}, "retrieval": {"cards": cards}},
                   "agent": "direct", "model": "qwen3.8-flash"}
        direct = shell_service._write(session, "A", shell_service.VARIANT_A, None)["messages"]
        tasks: list[str] = []
        real_agent = shell_service._agent_design
        shell_service._agent_design = lambda _session, _key, task_text: tasks.append(task_text) or {"text": "", "workspace": ""}
        try:
            shell_service._write(dict(session, agent="opencode"), "A", shell_service.VARIANT_A, None)
        finally:
            shell_service._agent_design = real_agent
    finally:
        discover.chat = real_chat
    agent_ok = bool(tasks) and tasks[0].startswith(page[1]["content"]) and "./validate DesignA" in tasks[0][len(page[1]["content"]):]
    ok = _same(page, direct) and agent_ok and shell_service.VARIANT_A is discover.VARIANT_A
    return ok, f"direct prompt {'identical' if _same(page, direct) else 'DIFFERENT'}; agent prompt {'= page prompt + agent instruction' if agent_ok else 'DIFFERENT'}"


def check_pilot(record: dict) -> tuple[bool, list[str]]:
    from mvp.engine import run_submitted_model
    folder = ROOT / "mvp" / "exam-inbox" / f"parity-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"
    folder.mkdir(parents=True)
    ok, lines = True, []
    for design in record.get("designs", []):
        if not design.get("source"):
            continue
        path = folder / f"Design{design['key']}.sysml"
        path.write_text(design["source"], encoding="utf-8")
        again = run_submitted_model([path], f"Design{design['key']}", label=f"parity-{design['key']}")["sysml"]
        saved = {item["message"] for item in design["attempts"][-1]["diagnostics"]}
        fresh = {item.get("message") for item in again.get("diagnostics", [])}
        same = again["status"] == design["sysml_status"] and saved == fresh
        ok &= same
        lines.append(f"design {design['key']}: saved {design['sysml_status']} ({len(saved)} diagnostics), again {again['status']} "
                     f"({len(fresh)} diagnostics) · {'same' if same else 'DIFFERENT'}")
    return ok, lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", default="20261006T211951", help="a saved run (analysis/discover-<run>.json)")
    args = parser.parse_args()
    discover.load_env()
    record = json.loads((ROOT / "analysis" / f"discover-{args.run}.json").read_text(encoding="utf-8"))
    results = []
    ok, detail = check_retrieval(record["brief"])
    results.append(ok)
    print(f"1. Retrieval through the shell = page retrieval: {'PASS' if ok else 'FAIL'} · {detail}")
    ok, detail = check_prompts(record)
    results.append(ok)
    print(f"2. Design prompts through the shell = page prompts: {'PASS' if ok else 'FAIL'} · {detail}")
    ok, lines = check_pilot(record)
    results.append(ok)
    print(f"3. Same SysML, same official Pilot result: {'PASS' if ok else 'FAIL'}")
    for line in lines:
        print("   " + line)
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
