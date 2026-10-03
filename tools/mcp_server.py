"""MCP tools for OpenCode: official validation, power check, diff, and query.

Gold directories are refused. The server does not call a language model.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp.server.mcpserver import MCPServer  # noqa: E402

from mvp.engine import run_submitted_model  # noqa: E402
from tools.toolbox import check, diff_runs, query_power  # noqa: E402

server = MCPServer("rtrc-tools", instructions="Validate SysML with the official pilot. Do not edit files under gold/.")


def _refuse(path: str) -> None:
    resolved = Path(path).resolve()
    if "gold" in resolved.parts:
        raise ValueError("Refusing a path inside a gold directory")


@server.tool(description="Validate a .sysml file with the official SysML v2 pilot. Returns the run id and syntax status.")
def validate_sysml(path: str, package: str) -> str:
    _refuse(path)
    result = run_submitted_model([path], package, label="mcp-validate")
    return json.dumps({"run_id": result["run_id"], "run_dir": result["run_dir"],
                       "sysml_status": result["sysml"]["status"],
                       "diagnostics": [item.get("message") for item in result["sysml"].get("diagnostics", [])][:8]},
                      ensure_ascii=False)


@server.tool(description="Read powerLimitW and drawW from an official parse and compare their sum with the limit.")
def check_budget(run_dir: str) -> str:
    _refuse(run_dir)
    return json.dumps(check(Path(run_dir)), ensure_ascii=False)


@server.tool(description="Compare named elements and the power check between two official run directories.")
def diff_sysml_runs(current_run_dir: str, previous_run_dir: str) -> str:
    _refuse(current_run_dir)
    _refuse(previous_run_dir)
    result = diff_runs(Path(current_run_dir), Path(previous_run_dir))
    brief = {"added": [item.get("qualifiedName") for item in result.get("added", [])],
             "removed": [item.get("qualifiedName") for item in result.get("removed", [])],
             "changed": [item.get("element") for item in result.get("changed", [])],
             "same_budget_status": result.get("power", {}).get("same_budget_status")}
    return json.dumps(brief, ensure_ascii=False)


@server.tool(description="Return the power limit, each draw, and their sum from an official parse.")
def query_budget(run_dir: str) -> str:
    _refuse(run_dir)
    return json.dumps(query_power(Path(run_dir)), ensure_ascii=False)


if __name__ == "__main__":
    server.run(transport="stdio")
