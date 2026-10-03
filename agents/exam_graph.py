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
    return {"step": "题面已发出，标准答案未给考生", "agent": case.get("model") or ""}


def write_model(state: State) -> State:
    case = _case()
    return {"step": "考生已写", "agent": case.get("model") or "", "syntax": "pass" if case.get("sysml_status") == "PASS" else "fail"}


def official_syntax(state: State) -> State:
    case = _case()
    syntax: Literal["pass", "fail"] = "pass" if case.get("sysml_status") == "PASS" else "fail"
    return {"step": "官方工具看过语法", "syntax": syntax}


def repair(state: State) -> State:
    return {"step": "这次没有返工", "repairs": state.get("repairs", 0), "syntax": "pass"}


def read_watts(state: State) -> State:
    check = (_case().get("checks") or [{}])[0]
    total = check.get("total_w")
    limit = check.get("limit_w")
    power = f"{total} / {limit}" if total is not None else "未计算"
    return {"step": "从解析结果读出瓦数", "power": power}


def score_list(state: State) -> State:
    case = _case()
    return {"step": f"对照清单：题目判定 {case.get('status') or '待判'}，设计判定 {case.get('engineering_status') or '待判'}",
            "score": case.get("status") or "待判"}


def approval(state: State) -> State:
    limit = _case().get("limit_in_model") or ""
    return {"step": f"上限仍是 {limit}" if limit else "没有这次运行"}


def archive(state: State) -> State:
    case = _case()
    return {"step": "这次运行已存档", "score": case.get("status") or ""}


def after_syntax(state: State) -> Literal["按报错再改", "读瓦数"]:
    if state.get("syntax") == "fail" and state.get("repairs", 0) < 3:
        return "按报错再改"
    return "读瓦数"


def build():
    graph = StateGraph(State)
    graph.add_node("发题面", issue_task)
    graph.add_node("考生写模型", write_model)
    graph.add_node("官方语法", official_syntax)
    graph.add_node("按报错再改", repair)
    graph.add_node("读瓦数", read_watts)
    graph.add_node("对照清单", score_list)
    graph.add_node("审批门", approval)
    graph.add_node("存档", archive)
    graph.add_edge(START, "发题面")
    graph.add_edge("发题面", "考生写模型")
    graph.add_edge("考生写模型", "官方语法")
    graph.add_conditional_edges("官方语法", after_syntax, ["按报错再改", "读瓦数"])
    graph.add_edge("按报错再改", "官方语法")
    graph.add_edge("读瓦数", "对照清单")
    graph.add_edge("对照清单", "审批门")
    graph.add_edge("审批门", "存档")
    graph.add_edge("存档", END)
    return graph.compile()


graph = build()
