"""MCP tools for the RTRC design assistant: the OpenCode assistant (Langflow node RtrcOpenCodeAssistant and
scripts/assistant.sh, decision 032) and the Langflow-Agent comparison flow (decision 031).

    python3 tools/assistant_mcp.py            # streamable HTTP on 127.0.0.1:8782/mcp

The Agent decides when to call a tool; the tools decide nothing by themselves. Memory search is the results
page's retrieval (MiniLM + FAISS, seeds plus one hop). run_design runs the verified Part 2 pipeline through the
RTRC shell service (bench/shell_service.py): requirements, two designs (by default written by OpenCode in the
sandbox with ./validate in hand, decision 032; or by the model directly), the official SysML v2 Pilot repair
loop, alignment, the four checks, trade-offs, diagram and Cameo export; its record appears on results page 2.3.
Writing a design into memory goes through the same gate as the page: all four checks must pass.
No answer key is reachable from here; nothing under gold/ is read.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp.server.mcpserver import MCPServer  # noqa: E402

SHELL = os.environ.get("RTRC_SHELL_URL", "http://127.0.0.1:8781")
SECRETS = ROOT / ".langflow" / "secrets.env"
MODELS = ("qwen3.8-max", "qwen3.8-flash", "qwen3.8-27b (Ollama)")
RUN_ID = re.compile(r"^\d{8}T\d{6}$")

server = MCPServer(
    "rtrc-assistant",
    instructions=(
        "Tools of the RTRC SysML v2 design assistant. search_memory and list_projects read the memory "
        "(MaritimeISR plus approved designs). run_design runs the verified design pipeline on a brief whose "
        "numbers all come from the engineer; it takes several minutes. validate_sysml_text parses SysML v2 "
        "with the official Pilot. write_to_memory needs the engineer's approval and all four checks passed."
    ),
)


def _token() -> str:
    for line in SECRETS.read_text(encoding="utf-8").splitlines():
        if line.startswith("RTRC_SHELL_TOKEN="):
            return line.split("=", 1)[1].strip().strip("'\"")
    raise RuntimeError("RTRC_SHELL_TOKEN missing from .langflow/secrets.env")


def _shell(path: str, payload: dict, timeout: int = 1800) -> dict:
    request = urllib.request.Request(SHELL + path, data=json.dumps(payload).encode(), method="POST",
                                     headers={"Content-Type": "application/json", "X-RTRC-Token": _token()})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        body = json.loads(exc.read() or b"{}")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"The RTRC shell service is not running at {SHELL} ({exc.reason}); start it with scripts/langflow.sh") from exc
    if not body.get("ok"):
        raise RuntimeError(body.get("error") or f"{path} failed")
    return body


def _run_id(value: str) -> str:
    match = re.search(r"\d{8}T\d{6}", value or "")
    if not match:
        raise ValueError("Give a run id such as 20261006T215846")
    return match.group(0)


def _dump(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=1)


@server.tool(description=(
    "List the projects in the memory: the existing MaritimeISR model and every approved design, with the brief "
    "each approved design answered and its key numbers. Call this when the engineer asks what already exists."))
def list_projects() -> str:
    from bench.discover import load_memory
    body = _shell("/memory", {})
    projects = [{"name": source["name"], "label": source["label"], "cards": source["cards"], "path": source["path"]}
                for source in body["data"]["sources"]]
    briefs = {f"approved {entry['run_id']}·{entry['design']}": {"brief": entry.get("brief", ""), "numbers": entry.get("numbers", {}),
                                                                "approved_at": entry.get("approved_at")} for entry in load_memory()}
    for project in projects:
        project.update(briefs.get(project["name"], {}))
    return _dump({"projects": projects, "note": "MaritimeISR is the existing maritime surveillance model; approved designs were "
                                                "written by the agent flow and approved by a person. Use read_project to see a model's SysML text."})


@server.tool(description=(
    "Search the memory with the results page's retrieval (MiniLM + FAISS, cosine >= 0.30 plus the exact-name bonus, "
    "seeds plus one hop). Returns the matching element cards with their values and connections, and the project "
    "they come from. Use it to find parts, attributes and limits related to what the engineer describes."))
def search_memory(query: str) -> str:
    from bench.discover import retrieve_existing
    found = retrieve_existing(query)
    seeds = [node for node in found.get("nodes", []) if node.get("role") == "seed"]
    return _dump({"library_cards": found.get("library_size"), "matched": len(found.get("nodes", [])), "seeds": len(seeds),
                  "path": found.get("path"), "note": found.get("note"),
                  "cards": [{"text": node.get("text"), "source": node.get("source"), "score": round(node.get("score", 0), 2)}
                            for node in sorted(found.get("nodes", []), key=lambda n: -n.get("score", 0))[:20]]})


@server.tool(description=(
    "Read a project's SysML v2 text from the memory: 'MaritimeISR', or an approved design by its run id such as "
    "'20261003T144529' (as listed by list_projects). Returns the source, truncated at 12000 characters."))
def read_project(name: str) -> str:
    from bench.discover import MARITIME_FILE, load_memory
    wanted = (name or "").strip()
    if wanted.lower() in {"maritimeisr", "maritime", "maritime isr"}:
        path = MARITIME_FILE
    else:
        match = re.search(r"\d{8}T\d{6}", wanted)
        entry = next((item for item in load_memory() if match and item["run_id"] == match.group(0)), None)
        if entry is None or not entry.get("source"):
            raise ValueError(f"No project named {wanted!r}; call list_projects for the names")
        path = ROOT / entry["source"]
    text = path.read_text(encoding="utf-8")
    return _dump({"name": wanted, "file": str(path.relative_to(ROOT)), "characters": len(text), "sysml": text[:12000]})


@server.tool(description=(
    "Run the verified RTRC design pipeline on a brief and return its review. Only call it after the engineer has "
    "confirmed the brief, and only with numbers the engineer gave (device powers in W, the power limit, recording "
    "rate in Mbps, retention hours, storage GB, upload rate and uplink capacity in Mbps). The pipeline searches the "
    "memory, writes numbered requirements, writes design A (adapting a similar project if one exists) and design B, "
    "parses both with the official SysML v2 Pilot and repairs on its errors, aligns A with the memory, computes the "
    "power / upload / storage / trace checks, proposes trade-offs when a check fails, draws the diagram and exports "
    "the passing designs for Cameo. Takes 2 to 10 minutes. model: qwen3.8-max (default), qwen3.8-flash or "
    "'qwen3.8-27b (Ollama)' for the local 3-bit model on this machine. agent: 'opencode' (default) has OpenCode write "
    "each design in the sandbox with the official Pilot as a tool, editing until it parses; 'direct' has the model "
    "write it in one answer with the error-list repair loop. OpenCode needs the results page (port 8770) stopped; if "
    "the tool refuses for that reason, tell the engineer to stop the page and try again, or offer agent 'direct'. "
    "start_from: 'auto' adapts a similar project when the memory has one and starts new otherwise; 'new' always "
    "writes both designs from scratch; 'similar' insists on adapting and fails when nothing similar exists. Use what "
    "the engineer asked for."))
def run_design(brief: str, model: str = "qwen3.8-max", agent: str = "opencode", start_from: str = "auto") -> str:
    if model not in MODELS:
        raise ValueError(f"model must be one of {MODELS}")
    if agent not in {"opencode", "direct"}:
        raise ValueError("agent must be opencode or direct")
    if start_from not in {"auto", "new", "similar"}:
        raise ValueError("start_from must be auto, new or similar")
    if len((brief or "").strip()) < 20:
        raise ValueError("The brief must be a full description with the engineer's numbers")
    started = _shell("/run/start", {"brief": brief, "agent": agent, "model": model})
    run = started["run"]
    retrieve = _shell("/run/retrieve", {"run": run})
    _shell("/run/requirements", {"run": run})
    similar = (retrieve.get("data") or {}).get("similar_project")
    if start_from == "similar" and not similar:
        raise ValueError("The memory has no similar project to adapt; run with start_from 'new' or 'auto'")
    adapt = start_from == "similar" or (start_from == "auto" and retrieve.get("path") == "reuse")
    _shell("/run/adapt" if adapt else "/run/design", {"run": run})
    _shell("/run/validate", {"run": run})
    _shell("/run/align", {"run": run})
    checks = _shell("/run/checks", {"run": run})
    tradeoffs = None
    if str(checks.get("summary", "")).startswith("fail"):
        try:
            tradeoffs = _shell("/run/tradeoffs", {"run": run})["summary"]
        except RuntimeError as exc:
            tradeoffs = f"trade-offs not available: {exc}"
    review = _shell("/run/review", {"run": run})
    return _dump({"run_id": run, "agent": agent, "model": model,
                  "started_from": "the similar project " + similar["name"] if adapt and similar else "scratch",
                  "similar_project": similar, "review": review["summary"], "checks": checks["summary"], "tradeoffs": tradeoffs,
                  "diagrams": (review.get("data") or {}).get("diagrams"), "cameo_exports": (review.get("data") or {}).get("cameo_exports"),
                  "next": "Explain the review to the engineer. If a design passed all four checks and the engineer approves it, "
                          "call write_to_memory; otherwise call record_decision with Reject or Send back."})


@server.tool(description="Show what a saved design run produced: its brief, path (new or reuse), requirements, each design's Pilot result and checks, and the decision if one was recorded.")
def design_status(run_id: str) -> str:
    run = _run_id(run_id)
    path = ROOT / "analysis" / f"discover-{run}.json"
    if not path.is_file():
        path = ROOT / "analysis" / "langflow-runs" / f"{run}.json"
        if not path.is_file():
            raise ValueError(f"No run {run}")
        record = json.loads(path.read_text(encoding="utf-8")).get("record", {})
    else:
        record = json.loads(path.read_text(encoding="utf-8"))
    designs = [{"key": d.get("key"), "pilot": d.get("sysml_status"), "parses": len(d.get("attempts", [])),
                "checks": {c["id"]: c["status"] for c in d.get("checks", []) if c.get("id") != "CONNECT"}} for d in record.get("designs", [])]
    langflow = record.get("langflow", {})
    return _dump({"run_id": run, "brief": record.get("brief"), "path": langflow.get("path"), "similar_project": langflow.get("similar_project"),
                  "requirements": [item.get("text") for item in (record.get("requirements") or {}).get("requirements", [])],
                  "designs": designs, "decision": langflow.get("decision"), "approved": [a for a in langflow.get("approvals", []) if a.get("approved")]})


@server.tool(description=(
    "Parse SysML v2 text with the official SysML v2 Pilot and return PASS or FAIL with the first diagnostics. "
    "package is the package name declared in the text. Use it when the engineer pastes or asks to check SysML."))
def validate_sysml_text(sysml: str, package: str) -> str:
    from mvp.engine import run_submitted_model
    if "package" not in (sysml or ""):
        raise ValueError("The text contains no SysML package")
    folder = ROOT / "mvp" / "exam-inbox" / f"assistant-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')}"
    folder.mkdir(parents=True)
    path = folder / f"{package}.sysml"
    path.write_text(sysml, encoding="utf-8")
    result = run_submitted_model([path], package, label="assistant-validate")
    return _dump({"sysml_status": result["sysml"]["status"], "run_id": result["run_id"],
                  "diagnostics": [{"line": item.get("line"), "message": item.get("message")} for item in result["sysml"].get("diagnostics", [])][:12]})


@server.tool(description=(
    "Write an approved design into the memory so the next search can find it. design is 'A' or 'B'. Call it only "
    "after the engineer explicitly approved that design; the service refuses a design that did not pass all four checks."))
def write_to_memory(run_id: str, design: str = "A") -> str:
    run, key = _run_id(run_id), (design or "A").strip().upper()
    if key not in {"A", "B"}:
        raise ValueError("design must be A or B")
    approval = _shell("/run/approve", {"run": run, "key": key})
    approved = bool((approval.get("data") or {}).get("approved"))
    if not approved:
        # The gate refused (a check failed, the Pilot failed, or a number has no source): nothing is written and no
        # approval is recorded; the engineer may still record Reject or Send back.
        return _dump({"run_id": run, "approved": False, "result": approval["summary"],
                      "next": "Tell the engineer why the gate refused. Record Reject or Send back if they decide so."})
    decision = _shell("/run/decision", {"run": run, "decision": f"Approve design {key}", "note": approval["summary"].splitlines()[-1]})
    return _dump({"run_id": run, "approved": True, "result": approval["summary"], "record": decision["summary"]})


@server.tool(description="Record the engineer's decision on a design run without writing memory: decision is 'Reject' or 'Send back'; note is the reason.")
def record_decision(run_id: str, decision: str, note: str = "") -> str:
    run = _run_id(run_id)
    if decision not in {"Reject", "Send back"}:
        raise ValueError("decision must be 'Reject' or 'Send back'")
    body = _shell("/run/decision", {"run": run, "decision": decision, "note": note})
    return _dump({"run_id": run, "record": body["summary"]})


@server.tool(description="Export a run's designs that passed the Pilot as .sysml files for Cameo's SysML v2 edition and say where they are.")
def export_cameo(run_id: str) -> str:
    body = _shell("/cameo/export", {"run": _run_id(run_id)})
    return _dump({"summary": body["summary"], "files": (body.get("data") or {}).get("files")})


if __name__ == "__main__":
    port = int(os.environ.get("RTRC_ASSISTANT_MCP_PORT", "8782"))
    print(f"rtrc-assistant MCP on http://127.0.0.1:{port}/mcp", file=sys.stderr, flush=True)
    server.run(transport="streamable-http", host="127.0.0.1", port=port)
