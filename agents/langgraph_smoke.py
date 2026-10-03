"""Official two-node LangGraph example, then one node that calls qwen3.8."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import TypedDict

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from langgraph.graph import END, START, StateGraph  # noqa: E402

from agents.llm import chat  # noqa: E402
from bench.experiment import load_env  # noqa: E402


class State(TypedDict):
    text: str


def official_a(state: State) -> State:
    return {"text": state["text"] + " -> read"}


def official_b(state: State) -> State:
    return {"text": state["text"] + " -> check"}


def qwen_node(state: State) -> State:
    completed = chat(
        [{"role": "user", "content": "Reply with the single word ok."}],
        max_tokens=20,
        temperature=0,
    )
    return {"text": state["text"] + " -> " + completed["model"] + ":" + completed["text"].strip()}


def main() -> None:
    load_env()
    official = StateGraph(State)
    official.add_node("read", official_a)
    official.add_node("check", official_b)
    official.add_edge(START, "read")
    official.add_edge("read", "check")
    official.add_edge("check", END)
    official_app = official.compile()
    print("OFFICIAL", official_app.invoke({"text": "start"}))
    print("MERMAID")
    print(official_app.get_graph().draw_mermaid())

    live = StateGraph(State)
    live.add_node("ask", qwen_node)
    live.add_edge(START, "ask")
    live.add_edge("ask", END)
    print("QWEN", live.compile().invoke({"text": "start"}))


if __name__ == "__main__":
    main()
