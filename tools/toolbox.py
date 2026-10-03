"""Shared tools for every candidate: check, diff, and query.

validate stays in the official toolchain. These functions read only a completed
run directory. They do not call a model.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bench.power_check import budget  # noqa: E402
from mvp.engine import model_diff  # noqa: E402


def check(run_dir: Path) -> dict:
    measured = budget(run_dir)
    return {"id": "R-POWER-001", "status": measured["budget_status"],
            "total_w": measured.get("total_w"), "limit_w": measured.get("limit_w"),
            "draws_w": measured.get("draws_w"), "sysml_status": measured.get("sysml_status"),
            "reason": measured.get("reason")}


def diff_runs(current_dir: Path, previous_dir: Path) -> dict:
    def elements(folder: Path) -> list[dict]:
        payload = json.loads((folder / "result.json").read_text(encoding="utf-8"))
        return payload.get("model_elements") or []

    structural = model_diff(elements(current_dir), elements(previous_dir))
    current = check(current_dir)
    previous = check(previous_dir)
    structural["power"] = {"current": current, "previous": previous,
                           "same_budget_status": current["status"] == previous["status"]}
    return structural


def query_power(run_dir: Path) -> dict:
    measured = budget(run_dir)
    return {"question": "What are powerLimitW, each drawW, and their sum?",
            "limit_w": measured.get("limit_w"), "draws_w": measured.get("draws_w"),
            "total_w": measured.get("total_w"), "budget_status": measured.get("budget_status")}
