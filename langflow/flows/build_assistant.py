"""Build the conversational flow "RTRC design assistant" (Langflow's Agent harness over our tools).

    LANGFLOW_CONFIG_DIR=.langflow/config .venv-langflow/bin/python langflow/flows/build_assistant.py

Chat Input -> Agent (qwen3.8-max through the "OpenAI Compatible" provider) -> Chat Output. The Agent's tools are the
RTRC assistant MCP server (tools/assistant_mcp.py: memory search, read a project, run the verified design pipeline,
validate SysML, write to memory, record a decision, export for Cameo) and the Langflow knowledge base rtrc_memory
in Retrieve mode. The Agent decides when to call a tool; the official Pilot and the checks decide the verdicts.
Output: langflow/flows/rtrc-assistant.json; import with langflow/flows/import_flows.py.
"""
from __future__ import annotations

import json
from pathlib import Path

from lfx.components.files_and_knowledge.knowledge import KnowledgeComponent
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.components.models_and_agents.agent import AgentComponent
from lfx.components.models_and_agents.mcp_component import MCPToolsComponent

OUT = Path(__file__).resolve().parent
MODEL = "qwen3.8-max"
PROVIDER = "OpenAI Compatible"
KNOWLEDGE_BASE = "rtrc_memory"
MCP_SERVER = {"name": "rtrc-assistant", "config": {"url": "http://127.0.0.1:8782/mcp"}}

SYSTEM_PROMPT = """You are the RTRC design assistant for early-stage systems engineering in SysML v2. The scenario is a synthetic maritime ISR exercise; the numbers are not an RTX specification.

What you do: help an engineer see what already exists in the memory, turn a vague need into numbered requirements, run the verified design pipeline once the engineer confirms the brief, explain the results plainly, and record the engineer's decision.

Rules:
1. Never invent a number. Every power draw, rate, capacity, duration or limit must come from the engineer or from the memory, and you say which. If a number needed for the power, upload, storage or trace checks is missing, ask for it before running a design.
2. A stated limit (for example a 60 W power limit) is never changed to make a check pass. If a design exceeds it, say so and offer trade-offs from the memory; changing the limit is the engineer's decision, not yours.
3. Before calling run_design, show the engineer the exact brief you will send (one paragraph with all the numbers and units) and wait for an explicit confirmation.
4. Verdicts come from tools, not from you: the official SysML v2 Pilot decides syntax, the checks decide the budget. Report them as they are, including failures, with the run id.
5. Writing into memory needs the engineer's explicit approval of a named design (A or B) that passed all four checks. Otherwise record Reject or Send back with the engineer's reason.
6. Answer in the language the engineer writes in. Be concrete and brief; quote values with units; do not repeat the whole tool output.

Tools: list_projects, search_memory and read_project read the memory with the results page's own retrieval. The knowledge-base search is Langflow's semantic search over the same cards. run_design runs the verified pipeline (3 to 8 minutes; default model qwen3.8-max). design_status shows a saved run. validate_sysml_text parses SysML the engineer pastes. write_to_memory, record_decision and export_cameo act on a finished run.

Brief format for run_design: the vessel and its devices with power draws in W, the power limit in W, the local recording rate in Mbps, the retention hours, the storage in GB, the upload rate in Mbps and the uplink capacity in Mbps, all from the engineer."""

TOOL_OUTPUT = {"allows_loop": False, "cache": True, "display_name": "Toolset", "group_outputs": False, "hidden": None, "loop_types": None,
               "method": "to_toolkit", "name": "component_as_tool", "options": None, "required_inputs": None, "selected": "Tool",
               "tool_mode": True, "types": ["Tool"], "value": "__UNDEFINED__"}


def _enc(handle: dict, compact: bool = False) -> str:
    return json.dumps(handle, separators=(",", ":") if compact else (", ", ": ")).replace('"', "œ")


def _edge(source: str, source_handle: dict, target: str, target_handle: dict) -> dict:
    return {"source": source, "target": target, "data": {"sourceHandle": source_handle, "targetHandle": target_handle},
            "sourceHandle": _enc(source_handle), "targetHandle": _enc(target_handle),
            "id": f"reactflow__edge-{source}{_enc(source_handle, True)}-{target}{_enc(target_handle, True)}",
            "animated": False, "className": "", "selected": False}


def _node(component, node_id: str, x: int, y: int, title: str, info: str, values: dict, *, tool_mode: bool = False) -> dict:
    frontend = component.to_frontend_node()
    data = frontend["data"]
    node = data["node"]
    for key, value in values.items():
        node["template"][key]["value"] = value
    node["display_name"], node["description"] = title, info
    if tool_mode:
        node["tool_mode"] = True
        node["outputs"] = [dict(TOOL_OUTPUT)]
    return {"id": node_id, "type": "genericNode", "position": {"x": x, "y": y}, "data": {**data, "id": node_id}}


def build() -> dict:
    chat_in = _node(ChatInput(_id="ChatInput-ask"), "ChatInput-ask", 40, 420, "Engineer", "Ask, describe a need, confirm a brief, or decide.", {})
    agent = _node(AgentComponent(_id="Agent-rtrc"), "Agent-rtrc", 560, 300, "RTRC design assistant · qwen3.8-max",
                  "Langflow's Agent harness: the model decides which tool to call and when; the tools decide nothing by themselves.",
                  {"model": [{"name": MODEL, "provider": PROVIDER, "metadata": {"model_type": "llm", "tool_calling": True}}],
                   "system_prompt": SYSTEM_PROMPT, "n_messages": 30, "max_iterations": 20, "add_current_date_tool": False,
                   "handle_parsing_errors": True})
    mcp = _node(MCPToolsComponent(_id="MCPTools-rtrc"), "MCPTools-rtrc", 40, 820, "RTRC tools (MCP)",
                "tools/assistant_mcp.py: memory search and projects, the verified design pipeline, the official Pilot, memory write, decisions, Cameo export.",
                {"mcp_server": MCP_SERVER, "use_cache": False, "tool_execution_timeout": 1200}, tool_mode=True)
    knowledge = _node(KnowledgeComponent(_id="Knowledge-rtrc"), "Knowledge-rtrc", 40, 1180, "Memory as knowledge base",
                      "Langflow's semantic search over the same 152 cards (Qwen embeddings).",
                      {"knowledge_base": KNOWLEDGE_BASE, "mode": "Retrieve", "top_k": 8, "include_metadata": True}, tool_mode=True)
    knowledge["data"]["node"]["template"]["knowledge_base"]["options"] = [KNOWLEDGE_BASE]
    chat_out = _node(ChatOutput(_id="ChatOutput-answer"), "ChatOutput-answer", 1080, 420, "Answer", "", {})

    agent_template = agent["data"]["node"]["template"]
    tools_handle = {"fieldName": "tools", "id": "Agent-rtrc", "inputTypes": agent_template["tools"]["input_types"], "type": agent_template["tools"]["type"]}
    edges = [
        _edge("ChatInput-ask", {"dataType": "ChatInput", "id": "ChatInput-ask", "name": "message", "output_types": ["Message"]},
              "Agent-rtrc", {"fieldName": "input_value", "id": "Agent-rtrc", "inputTypes": agent_template["input_value"]["input_types"], "type": agent_template["input_value"]["type"]}),
        _edge("MCPTools-rtrc", {"dataType": "MCPTools", "id": "MCPTools-rtrc", "name": "component_as_tool", "output_types": ["Tool"]}, "Agent-rtrc", tools_handle),
        _edge("Knowledge-rtrc", {"dataType": "Knowledge", "id": "Knowledge-rtrc", "name": "component_as_tool", "output_types": ["Tool"]}, "Agent-rtrc", tools_handle),
        _edge("Agent-rtrc", {"dataType": "Agent", "id": "Agent-rtrc", "name": "response", "output_types": ["Message"]},
              "ChatOutput-answer", {"fieldName": "input_value", "id": "ChatOutput-answer",
                                    "inputTypes": chat_out["data"]["node"]["template"]["input_value"]["input_types"], "type": chat_out["data"]["node"]["template"]["input_value"]["type"]}),
    ]
    note = {"id": "note-assistant", "type": "noteNode", "position": {"x": 40, "y": -40}, "width": 980, "height": 300,
            "style": {"width": 980, "height": 300}, "measured": {"width": 980, "height": 300},
            "data": {"id": "note-assistant", "type": "note", "node": {"display_name": "", "documentation": "", "template": {"backgroundColor": "blue"},
                     "description": (
                         "# RTRC design assistant\n\nTalk to it like a colleague: ask what exists in the memory, describe a need in your own words, "
                         "answer its questions about missing numbers, confirm the brief it proposes, and decide on the result.\n\n"
                         "- The Agent (qwen3.8-max) chooses the tools; the official SysML v2 Pilot and the budget checks give the verdicts.\n"
                         "- `run_design` is the same verified pipeline as the fixed flow and the results page (3 to 8 minutes); its record appears on page 2.3.\n"
                         "- It never invents numbers, never moves a stated limit, and writes to memory only after you approve a design that passed all four checks.\n"
                         "- The seven fixed flows stay as the benchmark; this one is for use.")}}}
    return {"name": "RTRC design assistant", "description": "Ask, discuss, confirm requirements, run the verified design pipeline, decide. Langflow Agent (qwen3.8-max) over the RTRC MCP tools and the memory knowledge base.",
            "endpoint_name": "rtrc-assistant", "is_component": False, "tags": ["rtrc", "assistant"],
            "data": {"nodes": [note, chat_in, agent, mcp, knowledge, chat_out], "edges": edges, "viewport": {"x": 0, "y": 0, "zoom": 0.7}}}


def _stable(value):
    if isinstance(value, dict):
        return {key: "2026-10-06 00:00:00 UTC" if key == "timestamp" and isinstance(item, str) else _stable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_stable(item) for item in value]
    return value


if __name__ == "__main__":
    flow = _stable(build())
    (OUT / "rtrc-assistant.json").write_text(json.dumps(flow, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"rtrc-assistant.json: {sum(1 for n in flow['data']['nodes'] if n['type'] == 'genericNode')} nodes, {len(flow['data']['edges'])} edges")
