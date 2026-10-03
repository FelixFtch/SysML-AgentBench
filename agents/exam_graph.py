"""The exam flow as a LangGraph, so Studio can draw it.

Nodes record which step ran. They do not score and they do not call a model.
The repair edge is the only loop: syntax failure goes back, at most three times.
"""
from __future__ import annotations

from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph


class State(TypedDict, total=False):
    step: str
    syntax: Literal["pass", "fail"]
    repairs: int
    power: str
    score: str
    agent: str


def issue_task(state: State) -> State:
    return {"step": "题面已发出，标准答案未给考生"}


def write_model(state: State) -> State:
    from agents.llm import chat
    from bench.experiment import load_env
    load_env()
    completed = chat(
        [{"role": "user", "content": "用一句话说明你是写 SysML 的考生。不要写代码。"}],
        max_tokens=80,
        temperature=0,
    )
    reply = completed["model"] + "：" + completed["text"].strip()
    return {"step": "考生已写", "agent": reply}


def official_syntax(state: State) -> State:
    # The picture shows the branch. A real run fills syntax from the pilot.
    syntax = state.get("syntax", "pass")
    return {"step": "官方工具看过语法", "syntax": syntax}


def repair(state: State) -> State:
    count = state.get("repairs", 0) + 1
    syntax: Literal["pass", "fail"] = "pass" if count >= 3 else state.get("syntax", "fail")
    return {"step": f"按报错修改，第 {count} 次", "repairs": count, "syntax": syntax}


def read_watts(state: State) -> State:
    return {"step": "从解析结果读出瓦数", "power": state.get("power", "未计算")}


def score_list(state: State) -> State:
    return {"step": "对照清单。超过 60 W 记失败", "score": state.get("score", "待判")}


def approval(state: State) -> State:
    return {"step": "没有人批准改上限"}


def archive(state: State) -> State:
    return {"step": "这次运行已存档"}


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
