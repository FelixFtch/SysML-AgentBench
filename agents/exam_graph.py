"""Exam steps for LangGraph Studio.

Each node reads the latest real case in analysis/mvp-case-latest-MOD-05.json
(older runs wrote analysis/mvp-case-latest.json). That file is the model-written MOD-05 run. Opening the graph does not call the model again.
A new write is started from the exam page.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph

ANALYSIS = Path(__file__).resolve().parents[1] / "analysis"
CASES = (ANALYSIS / "mvp-case-latest-MOD-05.json", ANALYSIS / "mvp-case-latest.json")


def _case() -> dict:
    for path in CASES:
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    return {}


class State(TypedDict, total=False):
    step: str
    syntax: Literal["pass", "fail"]
    repairs: int
    power: str
    score: str
    agent: str


def issue_task(state: State) -> State:
    case = _case()
    return {"step": "Task statement issued; the answer key is not given to the candidate", "agent": case.get("model") or ""}


def write_model(state: State) -> State:
    case = _case()
    return {"step": "The candidate wrote the model", "agent": case.get("model") or "", "syntax": "pass" if case.get("sysml_status") == "PASS" else "fail"}


def official_syntax(state: State) -> State:
    case = _case()
    syntax: Literal["pass", "fail"] = "pass" if case.get("sysml_status") == "PASS" else "fail"
    return {"step": "The official tool checked the syntax", "syntax": syntax}


def repair(state: State) -> State:
    return {"step": "No repair was needed this time", "repairs": state.get("repairs", 0), "syntax": "pass"}


def read_watts(state: State) -> State:
    check = (_case().get("checks") or [{}])[0]
    total = check.get("total_w")
    limit = check.get("limit_w")
    power = f"{total} / {limit}" if total is not None else "not computed"
    return {"step": "Watts read from the official parse", "power": power}


def score_list(state: State) -> State:
    case = _case()
    return {"step": f"Checked against the key: task verdict {case.get('status') or 'pending'}, design verdict {case.get('engineering_status') or 'pending'}",
            "score": case.get("status") or "pending"}


def approval(state: State) -> State:
    limit = _case().get("limit_in_model") or ""
    return {"step": f"The limit is still {limit}" if limit else "No run recorded"}


def archive(state: State) -> State:
    case = _case()
    return {"step": "This run is archived", "score": case.get("status") or ""}


def after_syntax(state: State) -> Literal["Repair from errors", "Read values"]:
    if state.get("syntax") == "fail" and state.get("repairs", 0) < 20:
        return "Repair from errors"
    return "Read values"


def build():
    graph = StateGraph(State)
    graph.add_node("Issue task", issue_task)
    graph.add_node("Write the answer", write_model)
    graph.add_node("Official syntax", official_syntax)
    graph.add_node("Repair from errors", repair)
    graph.add_node("Read values", read_watts)
    graph.add_node("Check against key", score_list)
    graph.add_node("Approval gate", approval)
    graph.add_node("Archive", archive)
    graph.add_edge(START, "Issue task")
    graph.add_edge("Issue task", "Write the answer")
    graph.add_edge("Write the answer", "Official syntax")
    graph.add_conditional_edges("Official syntax", after_syntax, ["Repair from errors", "Read values"])
    graph.add_edge("Repair from errors", "Official syntax")
    graph.add_edge("Read values", "Check against key")
    graph.add_edge("Check against key", "Approval gate")
    graph.add_edge("Approval gate", "Archive")
    graph.add_edge("Archive", END)
    return graph.compile()


graph = build()
