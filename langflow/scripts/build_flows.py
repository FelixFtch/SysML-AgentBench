"""Build the RTRC Langflow flows as code and write them as flow files for the Langflow editor.

    LANGFLOW_CONFIG_DIR=.langflow/config .venv-langflow/bin/python langflow/scripts/build_flows.py

Each flow is a Langflow graph of official components (Chat Input / Output, Text Input, If-Else, Human Input) and the
RTRC components in langflow/components/rtrc, built in Python the way Langflow's own starter projects are. This script
then adds what the Python graph API does not express: Human Input's branch outputs, readable positions, and canvas
notes that say who does each step and which paper it applies. Output: langflow/flows/<project folder>/<slug>.json
(catalog.flow_file); import them with langflow/scripts/import_flows.py. Qwen only for now; the Cameo steps are used
once RTRC provides the license.

The flows and the six projects they belong to are listed in langflow/flows/catalog.py (decision 035): each
candidate's exam version and chat version side by side, the shared tool flows, and the rest.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "langflow" / "flows"
sys.path.insert(0, str(ROOT / "langflow" / "components"))
sys.path.insert(0, str(OUT))
from catalog import NAMES, flow_file, tool_name  # noqa: E402

from lfx.components.files_and_knowledge.knowledge import KnowledgeComponent  # noqa: E402
from lfx.components.flow_controls.conditional_router import ConditionalRouterComponent  # noqa: E402
from lfx.components.flow_controls.human_input import HumanInput, _action_id  # noqa: E402
from lfx.components.flow_controls.run_flow import RunFlowComponent  # noqa: E402
from lfx.components.input_output import ChatInput, ChatOutput  # noqa: E402
from lfx.components.models_and_agents.agent import AgentComponent  # noqa: E402
from lfx.components.models_and_agents.mcp_component import MCPToolsComponent  # noqa: E402
from lfx.graph import Graph  # noqa: E402
from rtrc.rtrc_cameo import RtrcCameoExport  # noqa: E402
from rtrc.rtrc_cameo_record import RtrcCameoRecord  # noqa: E402
from rtrc.rtrc_exam_cell import RtrcExamCell  # noqa: E402
from rtrc.rtrc_chat import CANDIDATES as CHAT_CANDIDATES, RtrcChat  # noqa: E402
from rtrc.rtrc_exam_step import RtrcExamStep  # noqa: E402
from rtrc.rtrc_gate import RtrcGateRecord  # noqa: E402
from rtrc.rtrc_memory import RtrcMemory  # noqa: E402
from rtrc.rtrc_mod import RtrcModChange  # noqa: E402
from rtrc.rtrc_mod_step import RtrcModStep  # noqa: E402
from rtrc.rtrc_opencode import RtrcOpenCodeAssistant  # noqa: E402
from rtrc.rtrc_record import RtrcRecord  # noqa: E402
from rtrc.rtrc_results import RtrcResults  # noqa: E402
from rtrc.rtrc_start import RtrcStart  # noqa: E402
from rtrc.rtrc_step import STEPS, RtrcStep  # noqa: E402
from rtrc.rtrc_tool import STEPS as TOOL_STEPS, RtrcTool  # noqa: E402

S = list(STEPS)
T = list(TOOL_STEPS)
KNOWLEDGE_BASE = "rtrc_memory"
sys.path.insert(0, str(ROOT))
from agents.llm_local import OLLAMA_TAG  # noqa: E402

# ---------- the unfolded assistant: Langflow's Agent with one card per RTRC tool and the pipeline as a sub-flow ----------
MCP_SERVER = {"name": "rtrc-assistant", "config": {"url": "http://127.0.0.1:8782/mcp"}}
PIPELINE_TOOL_NAME = NAMES["tool-design-pipeline"]  # Run Flow names the tool "<flow name>_tool" with spaces turned into dashes
PIPELINE_TOOL = tool_name(PIPELINE_TOOL_NAME)
# The single-step tools of tools/assistant_mcp.py stay MCP cards (name, card title, what the card says). search_memory,
# write_to_memory, validate_sysml_text and run_design are sub-flows run as tools instead (decisions 033, 034).
ASSISTANT_TOOLS = [
    ("list_projects", "Tool · list projects", "What is in the memory: MaritimeISR and every approved design, with card counts. Reads analysis/memory/approved.jsonl."),
    ("read_project", "Tool · read a project", "The SysML v2 text of MaritimeISR or of an approved design, from the file itself."),
    ("design_status", "Tool · status of a run", "What a saved run produced (analysis/discover-<run>.json): path, requirements, each design's Pilot result and checks, the decision."),
    ("record_decision", "Tool · record a decision", "Saves Reject or Send back with the engineer's reason on the run's record (page 2.3)."),
    ("export_cameo", "Tool · export for Cameo", "Writes a run's passing designs as .sysml files for Cameo's SysML v2 edition (when RTRC provides the license)."),
]
ASSISTANT_TOOL_NAMES = [name for name, _, _ in ASSISTANT_TOOLS] + ["search_memory", "validate_sysml_text", "write_to_memory", "run_design"]
# The sub-flows the unfolded assistant runs as tools: (slug, flow name, Run Flow tool name, chat-input node id, card title, card text)
TOOL_FLOWS = {
    "search": ("tool-memory-search", NAMES["tool-memory-search"], tool_name(NAMES["tool-memory-search"]), "ChatInput-query",
               "Tool · search memory (a flow) · Paper 2",
               f"Runs the flow \"{NAMES['tool-memory-search']}\": the memory library → MiniLM + FAISS seeds → one hop of neighbours → cards. Open it to see each step."),
    "write": ("tool-write-to-memory", NAMES["tool-write-to-memory"], tool_name(NAMES["tool-write-to-memory"]), "ChatInput-approval",
              "Tool · write to memory (a flow) · approval card · Paper 2",
              f"Pauses for your approval, then runs the flow \"{NAMES['tool-write-to-memory']}\": the gate (Pilot PASS, four checks PASS) → the write → the record → "
              "the knowledge base refreshed with the new cards."),
    "validate": ("tool-validate-sysml", NAMES["tool-validate-sysml"], tool_name(NAMES["tool-validate-sysml"]), "ChatInput-sysml",
                 "Tool · official Pilot on pasted SysML (a flow) · Paper 3",
                 f"Runs the flow \"{NAMES['tool-validate-sysml']}\": the pasted text saved as a file → the official SysML v2 Pilot → PASS or FAIL with the diagnostics."),
}
SEARCH_TOOL, VALIDATE_TOOL, WRITE_TOOL = TOOL_FLOWS["search"][2], TOOL_FLOWS["validate"][2], TOOL_FLOWS["write"][2]
TOOL_OUTPUT = {"allows_loop": False, "cache": True, "display_name": "Toolset", "group_outputs": False, "hidden": None, "loop_types": None,
               "method": "to_toolkit", "name": "component_as_tool", "options": None, "required_inputs": None, "selected": "Tool",
               "tool_mode": True, "types": ["Tool"], "value": "__UNDEFINED__"}
EXAM_MODEL = "qwen3.8-flash"  # the model of the frozen exam; every exam version of an agent uses it, so the columns compare harnesses
# The Langflow-Agent flows: the unfolded chat assistants (decision 033), and the exam versions of decision 035.
# kind "memory": all nine tools, the knowledge base, the pipeline. kind "exam-memory": the exam prompt, memory search and the
# Pilot as the only tools. kind "exam-pilot" / "chat-pilot": the Pilot as the only tool (project 2, no memory at all).
UNFOLDED_VARIANTS = {
    "langflow-agent-memory-chat-max": {"kind": "memory", "model": "qwen3.8-max", "provider": "OpenAI Compatible", "label": "qwen3.8-max",
                                       "where": "Qwen's cloud endpoint"},
    "langflow-agent-memory-chat-local": {"kind": "memory", "model": OLLAMA_TAG, "provider": "Ollama", "label": "local Qwen3.8-27B",
                                         "where": "the 3-bit model on this machine (scripts/qwen38.sh --serve)"},
    "langflow-agent-memory-exam": {"kind": "exam-memory", "model": EXAM_MODEL, "provider": "OpenAI Compatible", "label": EXAM_MODEL,
                                   "where": "Qwen's cloud endpoint"},
    "langflow-agent-pilot-exam": {"kind": "exam-pilot", "model": EXAM_MODEL, "provider": "OpenAI Compatible", "label": EXAM_MODEL,
                                  "where": "Qwen's cloud endpoint"},
    "langflow-agent-pilot-chat": {"kind": "chat-pilot", "model": EXAM_MODEL, "provider": "OpenAI Compatible", "label": EXAM_MODEL,
                                  "where": "Qwen's cloud endpoint"},
}
UNFOLDED_PROMPT = (ROOT / "tools" / "assistant" / "rtrc-assistant.md").read_text(encoding="utf-8").split("\n\nTools:")[0] + f"""

Tools. list_projects and read_project read the memory's files. The knowledge-base search is Langflow's semantic search over the same cards. Four tools are flows; each takes one argument and must be called exactly like this:
- {SEARCH_TOOL}, flow_tweak_data = {{"ChatInput-query~input_value": <a few search words>}}: the memory library → MiniLM + FAISS seeds → one hop of neighbours → the matching cards with values and sources.
- {PIPELINE_TOOL}, flow_tweak_data = {{"ChatInput-brief~input_value": <the confirmed brief, word for word>}} (2 to 10 minutes): memory search, numbered requirements, designs A and B written by OpenCode in a sandbox with the official Pilot as a tool, the Pilot's verdict, alignment with the memory, the power / upload / storage / trace checks, trade-offs when a check fails, diagram and Cameo export; returns the review text with the run id. An empty or misnamed argument is refused. When it returns, compare its "Brief:" line with the brief the engineer confirmed; if they differ, say so and do not present the verdicts as the engineer's design. It needs the results page (port 8770) stopped; if it says so, tell the engineer.
- {VALIDATE_TOOL}, flow_tweak_data = {{"ChatInput-sysml~input_value": <the SysML text the engineer pasted>}}: saves it as a file and runs the official Pilot; PASS or FAIL with the diagnostics.
- {WRITE_TOOL}, flow_tweak_data = {{"ChatInput-approval~input_value": "<run id> A" or "<run id> B"}}: pauses for the person's approval, then checks the gate (Pilot PASS and all four checks PASS), writes the design into the memory, records the approval and refreshes the knowledge base. Call it only after the engineer named the design.
design_status shows a saved run; record_decision (Reject or Send back, with the reason) and export_cameo act on a finished run.

Brief format for the pipeline: the vessel and its devices with power draws in W, the power limit in W, the local recording rate in Mbps, the retention hours, the storage in GB, the upload rate in Mbps and the uplink capacity in Mbps, all from the engineer."""
# The exam prompt of the Langflow-Agent exam flows: the same text as the OpenCode exam workspace, with the two tools named the
# way Run Flow exposes them. The Pilot-only flow of project 2 gets the same prompt without the memory tool.
_VALIDATE_TOOL_TEXT = (f"{VALIDATE_TOOL}, flow_tweak_data = {{\"ChatInput-sysml~input_value\": <the SysML text>}}, parses SysML v2 with the official "
                       "SysML v2 Pilot, the same judge that scores the exam; run it on every model you write and fix what it reports before you reply.")
_SEARCH_TOOL_TEXT = (f" {SEARCH_TOOL}, flow_tweak_data = {{\"ChatInput-query~input_value\": <a few search words>}}, finds elements of the existing "
                     "maritime model and of approved designs; use it for names when the task refers to the existing model.")
PILOT_CHAT_PROMPT = f"""You are a SysML v2 assistant for a synthetic maritime ISR exercise; the numbers are not an RTX specification. You have one tool, the official SysML v2 Pilot: {_VALIDATE_TOOL_TEXT} You have no memory of existing projects and no design pipeline; say so when asked for them. Never invent a number and never change a stated limit. Answer in the language the person writes in."""


def exam_prompt_for(kind: str) -> str:
    """The exam prompt of a Langflow-Agent exam flow (tools/assistant/rtrc-assistant-exam.md with the frozen rules)."""
    sys.path.insert(0, str(ROOT))
    from tools.assistant.workspace import exam_prompt
    return exam_prompt(_VALIDATE_TOOL_TEXT + (_SEARCH_TOOL_TEXT if kind == "exam-memory" else ""))


def _enc(handle: dict, compact: bool = False) -> str:
    return json.dumps(handle, separators=(",", ":") if compact else (", ", ": ")).replace('"', "œ")


def _edge(source: str, target: str, source_handle: dict, target_handle: dict) -> dict:
    return {"source": source, "target": target, "data": {"sourceHandle": source_handle, "targetHandle": target_handle},
            "sourceHandle": _enc(source_handle), "targetHandle": _enc(target_handle),
            "id": f"reactflow__edge-{source}{_enc(source_handle, True)}-{target}{_enc(target_handle, True)}",
            "animated": False, "className": "", "selected": False}


def _graph(start, ends: list) -> Graph:
    """A graph with several outputs; components added after construction need initialize() to appear in dump()."""
    graph = Graph(start=start, end=ends[0])
    for end in ends[1:]:
        graph.add_component(end)
    if len(ends) > 1:
        graph.initialize()
    return graph


def _human_node(node_id: str, decisions: list[str]) -> dict:
    component = HumanInput(_id=node_id)
    frontend = component.to_frontend_node()
    data = frontend["data"]
    node = data["node"]
    node["template"]["decisions"]["value"] = decisions
    base = dict(node["outputs"][0])
    node["outputs"] = [{**base, "name": f"branch_{_action_id(label)}", "display_name": label} for label in decisions]
    return {"id": node_id, "data": {**data, "id": node_id, "type": "HumanInput"}}


def _note_height(text: str, width: int = 460) -> int:
    per_line = width // 8
    lines = sum(max(1, -(-len(paragraph) // per_line)) for paragraph in text.split("\n"))
    return 20 + lines * 36


def _layout(nodes: list[dict], edges: list[dict], top: int = 380) -> None:
    """Layered left-to-right layout: each node one column right of its furthest predecessor."""
    preds = defaultdict(set)
    for edge in edges:
        preds[edge["target"]].add(edge["source"])
    layer: dict[str, int] = {}

    def depth(node_id: str, seen=()) -> int:
        if node_id in layer:
            return layer[node_id]
        value = 0 if not preds[node_id] else 1 + max(depth(p, seen + (node_id,)) for p in preds[node_id] if p not in seen)
        layer[node_id] = value
        return value

    wrap, rows = 8, defaultdict(int)
    for node in nodes:
        if node.get("type") != "noteNode":
            rows[depth(node["id"])] += 1
    band_height = 470 * max(rows[c] for c in range(wrap) if c in rows) + 160 if rows else 0
    placed: dict[int, int] = defaultdict(int)
    for node in nodes:
        if node.get("type") == "noteNode":
            continue
        column = depth(node["id"])
        node["position"] = {"x": 40 + (column % wrap) * 470, "y": top + (column // wrap) * band_height + placed[column] * 470}
        placed[column] += 1


def build(name: str, description: str, graph: Graph, titles: dict, notes: list[tuple[str, str, int, int]],
          humans: list[dict] | None = None, tags: list[str] | None = None) -> dict:
    dump = graph.dump(name=name, description=description)
    nodes, edges = dump["data"]["nodes"], [_edge(e["source"], e["target"], e["data"]["sourceHandle"], e["data"]["targetHandle"])
                                            for e in dump["data"]["edges"]]
    for node in nodes:
        node["type"] = "genericNode"
        title, info = titles.get(node["id"], (None, None))
        if title:
            node["data"]["node"]["display_name"] = title
        if info:
            node["data"]["node"]["description"] = info
    kinds = {node["id"]: node["data"]["type"] for node in nodes}
    for human in humans or []:
        # Each branch target was wired in Python to a placeholder output; the edge is moved onto the branch output.
        hnode = _human_node(human["id"], human["decisions"])
        hnode["type"] = "genericNode"
        hnode["data"]["node"]["display_name"], hnode["data"]["node"]["description"] = human["title"], human["info"]
        nodes.append(hnode)
        src, src_output = human["prompt_from"]
        prompt = hnode["data"]["node"]["template"]["prompt"]
        edges.append(_edge(src, human["id"], {"dataType": kinds[src], "id": src, "name": src_output, "output_types": ["Message"]},
                           {"fieldName": "prompt", "id": human["id"], "inputTypes": prompt.get("input_types") or ["Message"], "type": prompt.get("type", "str")}))
        for label, targets in human["branches"].items():
            for target, field, *placeholder in targets:
                p_src, p_output = placeholder[0] if placeholder else (src, src_output)
                for edge in edges:
                    sh, th = edge["data"]["sourceHandle"], edge["data"]["targetHandle"]
                    if (edge["source"], sh["name"], edge["target"], th["fieldName"]) == (p_src, p_output, target, field):
                        handle = {"dataType": "HumanInput", "id": human["id"], "name": f"branch_{_action_id(label)}", "output_types": ["Message"]}
                        replaced = _edge(human["id"], target, handle, th)
                        edge.clear()
                        edge.update(replaced)
                        break
                else:
                    raise ValueError(f"{name}: no placeholder edge {p_src}.{p_output} → {target}.{field} for branch {label!r}")
    sizes = [_note_height(text) for _, text, _, _ in notes]
    _layout(nodes, edges, top=max([y + h for (_, _, _, y), h in zip(notes, sizes)], default=0) + 80)
    for index, ((note_id, text, x, y), height) in enumerate(zip(notes, sizes)):
        size = {"width": 460, "height": height}
        nodes.append({"id": note_id, "type": "noteNode", "position": {"x": x, "y": y}, **size, "style": dict(size), "measured": dict(size),
                      "data": {"id": note_id, "type": "note",
                               "node": {"description": text, "display_name": "", "documentation": "", "template": {"backgroundColor": "neutral" if index else "blue"}}}})
    return {"name": name, "description": description, "endpoint_name": None, "is_component": False, "tags": tags or [],
            "data": {"nodes": nodes, "edges": edges, "viewport": {"x": 0, "y": 0, "zoom": 0.55}}}


# ---------- the design assistant (for use) ----------

def assistant_flow(exam: bool = False) -> dict:
    """Chat Input -> RTRC OpenCode assistant -> Chat Output: OpenCode over the RTRC MCP tools (project 3).
    Chat: the local Qwen3.8-27B, all nine tools, one OpenCode session per chat session. Exam (decision 035): qwen3.8-flash,
    the exam prompt, memory search and the official Pilot as the only tools, a fresh session per message."""
    from rtrc.rtrc_opencode import MODELS as OPENCODE_MODELS, MODES as OPENCODE_MODES
    chat_in = ChatInput(_id="ChatInput-ask")
    assistant = RtrcOpenCodeAssistant(_id="RtrcOpenCode-assistant")
    assistant.set(message=chat_in.message_response, mode=OPENCODE_MODES[1] if exam else OPENCODE_MODES[0],
                  model=EXAM_MODEL if exam else OPENCODE_MODELS[0])
    chat_out = ChatOutput(_id="ChatOutput-answer")
    chat_out.set(input_value=assistant.turn)
    graph = _graph(chat_in, [chat_out])
    if exam:
        titles = {
            "ChatInput-ask": ("Task statement (one exam task)", "The task text as the exam gives it; bench/langflow_exam.py sends the 27 sealed tasks here, three times each."),
            "RtrcOpenCode-assistant": (f"OpenCode with memory · exam · {EXAM_MODEL}",
                                       "A fresh OpenCode session per task on the exam workspace (~/.rtrc-assistant-exam): the exam prompt with the frozen SysML rules, "
                                       "and two MCP tools, search_memory and validate_sysml_text. No design run, no write to memory. Time and tokens are recorded per task."),
            "ChatOutput-answer": ("Answer (scored outside, by the frozen scorer)", ""),
        }
        notes = [("note-assistant-exam",
                  f"# {NAMES['opencode-memory-exam']}\n\nThe OpenCode-with-memory assistant sitting the 27-task exam (decision 035): the same harness as the chat "
                  "version, on qwen3.8-flash (the model of the frozen exam), with the exam prompt (tools/assistant/rtrc-assistant-exam.md plus the frozen rules of "
                  "agents/solve.py) and two tools only: memory search (paper 2 retrieval over MaritimeISR and the approved designs) and the official Pilot. "
                  "Each message is one task and starts a fresh OpenCode session, so nothing carries over.\n\n"
                  "- Run the whole exam with `python3 bench/langflow_exam.py --flow \"OpenCode with memory exam\"`: 27 tasks × 3 repeats, scored by the frozen "
                  "scorer, a new column on results page 1.3 with time and tokens. The answer keys never enter the prompt.\n"
                  "- One task by hand: paste its statement in the Playground; nothing is scored there.", 40, -20)]
        return build(NAMES["opencode-memory-exam"], "The OpenCode-with-memory assistant on one exam task: answer only, memory search and the official Pilot as tools.",
                     graph, titles, notes, None, ["rtrc", "assistant", "exam"])
    titles = {
        "ChatInput-ask": ("Engineer", "Ask, describe a need, confirm a brief, or decide."),
        "RtrcOpenCode-assistant": ("OpenCode with memory · chat · local Qwen3.8-27B",
                                   "OpenCode is the harness: the model decides which RTRC tool to call and when; the tools decide nothing by themselves. "
                                   "Each chat session continues one OpenCode session."),
        "ChatOutput-answer": ("Answer", ""),
    }
    notes = [("note-assistant",
              f"# {NAMES['opencode-memory-chat']}\n\nTalk to it like a colleague: ask what exists in the memory, describe a need in your own words, "
              "answer its questions about missing numbers, confirm the brief it proposes, and decide on the result.\n\n"
              "- The harness is OpenCode (the exam's pinned binary) on the 3-bit Qwen3.8-27B served by Ollama on this machine; its tools are the RTRC MCP "
              "server (`tools/assistant_mcp.py`, 127.0.0.1:8782): memory search, the verified design pipeline, the official Pilot, the memory gate, decisions, "
              "Cameo export. Its own file and shell tools are off. Nothing leaves this computer.\n"
              "- `run_design` is the same verified pipeline as the design agent flow and the results page (2 to 10 minutes); inside it a second, sandboxed OpenCode "
              "writes the designs with `./validate` in hand, so the results page (8770) must be stopped first. Its record appears on page 2.3.\n"
              "- It never invents numbers, never moves a stated limit, and writes to memory only after you approve a design that passed all four checks.\n"
              "- The same assistant in the terminal: `scripts/assistant.sh`. Its exam version sits next to it in this project.", 40, -20)]
    return build(NAMES["opencode-memory-chat"],
                 "Ask, discuss, confirm requirements, run the verified design pipeline, decide. OpenCode on the local Qwen3.8-27B over the RTRC MCP tools.",
                 graph, titles, notes, None, ["rtrc", "assistant", "local"])


def _mcp_tool_descriptions() -> dict[str, str]:
    """The tool descriptions as Langflow's MCP client sees them; the Actions table of each tool card carries them.
    Needs tools/assistant_mcp.py running (scripts/langflow.sh starts it)."""
    import asyncio

    from lfx.base.mcp.util import MCPStreamableHttpClient
    try:
        tools = asyncio.run(MCPStreamableHttpClient().connect_to_server(MCP_SERVER["config"]["url"]))
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"The RTRC assistant MCP server is not reachable at {MCP_SERVER['config']['url']} ({exc}); start it with scripts/langflow.sh") from exc
    return {tool.name: tool.description for tool in tools}


def _frontend_node(component, node_id: str, x: int, y: int, title: str, info: str, values: dict, *, tool_mode: bool = False) -> dict:
    """A node built from a component's frontend template (for the Agent, the tool cards and the chat ends of the unfolded assistant)."""
    frontend = component.to_frontend_node()
    data = frontend["data"]
    node = data["node"]
    for key, value in values.items():
        if key in node["template"]:
            node["template"][key]["value"] = value
        else:
            node["template"][key] = value
    node["display_name"], node["description"] = title, info
    if tool_mode:
        node["tool_mode"] = True
        node["outputs"] = [dict(TOOL_OUTPUT)]
    return {"id": node_id, "type": "genericNode", "position": {"x": x, "y": y}, "data": {**data, "id": node_id}}


def _tools_metadata(descriptions: dict[str, str], enabled: str) -> dict:
    """The Actions table of one MCP tool card: every tool of the server listed, one enabled; write_to_memory asks for approval."""
    from lfx.base.tools.constants import TOOLS_METADATA_INFO
    from lfx.inputs.inputs import ToolsInput
    rows = [{"name": name, "description": descriptions.get(name, ""), "tags": [name], "status": name == enabled,
             "approval_actions": ["approve", "reject"] if name == enabled == "write_to_memory" else []}
            for name in ASSISTANT_TOOL_NAMES]
    return ToolsInput(name="tools_metadata", display_name="Actions", info=TOOLS_METADATA_INFO, value=rows).to_dict()


def unfolded_flow(slug: str) -> dict:
    """Chat Input -> Langflow's Agent -> Chat Output, with the tools as cards.

    kind "memory" (decision 033): one card per RTRC tool, the knowledge base and the design pipeline as a Run Flow tool;
    the chat assistant. kind "exam-memory" (decision 035): the exam prompt, two Run Flow cards (memory search, the Pilot).
    kind "exam-pilot" / "chat-pilot": the Pilot card alone, no memory at all (project 2)."""
    variant = UNFOLDED_VARIANTS[slug]
    kind = variant["kind"]
    exam = kind.startswith("exam")
    name = NAMES[slug]
    if kind == "memory":
        prompt, who = UNFOLDED_PROMPT, "Engineer"
        ask = "Ask, describe a need, confirm a brief, or decide."
    elif exam:
        prompt, who = exam_prompt_for(kind), "Task statement (one exam task)"
        ask = "The task text as the exam gives it; bench/langflow_exam.py sends the 27 sealed tasks here, three times each."
    else:
        prompt, who = PILOT_CHAT_PROMPT, "Person"
        ask = "Ask for SysML v2 text; the only tool is the official Pilot."
    chat_in = _frontend_node(ChatInput(_id="ChatInput-ask"), "ChatInput-ask", 40, 420, who, ask, {})
    agent = _frontend_node(AgentComponent(_id="Agent-rtrc"), "Agent-rtrc", 640, 300, f"{name} · Langflow Agent · {variant['label']}",
                           f"Langflow's own Agent component: the model decides which card to call and when; the cards decide nothing by themselves. Model: {variant['where']}."
                           + (" Token usage is stored on each answer (time and money per task)." if exam else ""),
                           {"model": [{"name": variant["model"], "provider": variant["provider"], "metadata": {"model_type": "llm", "tool_calling": True}}],
                            "system_prompt": prompt, "n_messages": 30, "max_iterations": 20, "add_current_date_tool": False,
                            "handle_parsing_errors": True})
    chat_out = _frontend_node(ChatOutput(_id="ChatOutput-answer"), "ChatOutput-answer", 1240, 420, "Answer" + (" (scored outside, by the frozen scorer)" if exam else ""), "", {})
    grid = [(40 + (i % 3) * 420, 820 + (i // 3) * 340) for i in range(12)]
    cards: list[dict] = []
    flow_cards = {"memory": ("search", "pipeline", "validate", "write"), "exam-memory": ("validate", "search"),
                  "exam-pilot": ("validate",), "chat-pilot": ("validate",)}[kind]
    # The tools that are flows (decisions 033, 034), first on the canvas; the write card asks for approval.
    for card_kind in flow_cards:
        if card_kind == "pipeline":
            flow_name, card_tool, title, info = PIPELINE_TOOL_NAME, PIPELINE_TOOL, "Tool · run the design pipeline (a flow) · Papers 2, 3, 1", (
                f"Runs the flow \"{PIPELINE_TOOL_NAME}\": ① memory → ② requirements → ③ designs by OpenCode in the sandbox (its rules, template and examples shown as cards) → "
                "④ official Pilot → ⑤ alignment → ⑥ checks → trade-offs → ⑦ review. Open that flow to see every step; edit it and this assistant runs the edited version.")
        else:
            _, flow_name, card_tool, _, title, info = TOOL_FLOWS[card_kind]
        x, y = grid[len(cards)]
        # The flow is found by name for the user running the assistant; import_flows.py fills in the id (an empty-string id
        # would be compared with the loaded flow's id and refused).
        values = {"flow_name_selected": flow_name, "flow_id_selected": None, "cache_flow": False}
        if card_kind == "write":
            values["tools_metadata"] = _flow_tool_metadata(card_tool, approval=True)
        cards.append(_frontend_node(RunFlowComponent(_id=f"RunFlow-{card_kind}"), f"RunFlow-{card_kind}", x, y, title, info, values, tool_mode=True))
    extra: list[dict] = []
    if kind == "memory":
        descriptions = _mcp_tool_descriptions()
        for mcp_name, title, info in ASSISTANT_TOOLS:
            x, y = grid[len(cards)]
            cards.append(_frontend_node(MCPToolsComponent(_id=f"MCPTools-{mcp_name}"), f"MCPTools-{mcp_name}", x, y, title, info,
                                        {"mcp_server": MCP_SERVER, "use_cache": False, "tool_execution_timeout": 1200,
                                         "tools_metadata": _tools_metadata(descriptions, mcp_name)}, tool_mode=True))
        x, y = grid[len(cards)]
        knowledge = _frontend_node(KnowledgeComponent(_id="Knowledge-rtrc"), "Knowledge-rtrc", x, y,
                                   "Memory as knowledge base · Paper 2", "Langflow's semantic search over the same cards (Qwen embeddings, filled by the knowledge-base fill flow and by the write-to-memory flow).",
                                   {"knowledge_base": KNOWLEDGE_BASE, "mode": "Retrieve", "top_k": 8, "include_metadata": True}, tool_mode=True)
        knowledge["data"]["node"]["template"]["knowledge_base"]["options"] = [KNOWLEDGE_BASE]
        extra.append(knowledge)
    agent_template = agent["data"]["node"]["template"]
    tools_handle = {"fieldName": "tools", "id": "Agent-rtrc", "inputTypes": agent_template["tools"]["input_types"], "type": agent_template["tools"]["type"]}
    edges = [_edge("ChatInput-ask", "Agent-rtrc", {"dataType": "ChatInput", "id": "ChatInput-ask", "name": "message", "output_types": ["Message"]},
                   {"fieldName": "input_value", "id": "Agent-rtrc", "inputTypes": agent_template["input_value"]["input_types"], "type": agent_template["input_value"]["type"]}),
             _edge("Agent-rtrc", "ChatOutput-answer", {"dataType": "Agent", "id": "Agent-rtrc", "name": "response", "output_types": ["Message"]},
                   {"fieldName": "input_value", "id": "ChatOutput-answer",
                    "inputTypes": chat_out["data"]["node"]["template"]["input_value"]["input_types"], "type": chat_out["data"]["node"]["template"]["input_value"]["type"]})]
    for node in [*cards, *extra]:
        edges.append(_edge(node["id"], "Agent-rtrc", {"dataType": node["data"]["type"], "id": node["id"], "name": "component_as_tool", "output_types": ["Tool"]}, tools_handle))
    if kind == "memory":
        note_text = (f"# {name}\n\nThe same assistant as **{NAMES['opencode-memory-chat']}**, with its parts on the canvas: Langflow's own Agent in the middle, "
                     "one card per RTRC tool around it, the memory as a knowledge base, and four tools that are flows of their own (project 5).\n\n"
                     f"- Talk to it like a colleague: ask what exists, describe a need, answer its questions about missing numbers, confirm the brief it proposes, decide on the result. Model: {variant['where']}.\n"
                     f"- Flows run as tools, open them to see each step: **{NAMES['tool-memory-search']}** (library → MiniLM + FAISS seeds → one hop → cards, paper 2); **{PIPELINE_TOOL_NAME}** "
                     "(① memory → ② requirements → ③ designs by OpenCode in the sandbox, with the rules, template and examples it was given shown as cards → ④ Pilot → ⑤ alignment → ⑥ checks → trade-offs → ⑦ review; stop the results page 8770 first); "
                     f"**{NAMES['tool-validate-sysml']}** (file → official Pilot, paper 3); **{NAMES['tool-write-to-memory']}** (gate → write → record → knowledge base refreshed). Edit a flow and this assistant runs the edited version.\n"
                     "- **Tool · write to memory** pauses for your approval (its Actions row): the AGENTS.md gate as a card. Every answer shows the tools it called when you expand it in the Playground.\n"
                     "- It never invents numbers and never moves a stated limit; verdicts come from the official Pilot and the checks. Records appear on page 2.3.")
        description = f"The assistant with its parts on the canvas: Langflow's Agent ({variant['label']}), one card per RTRC tool, the memory knowledge base, the design pipeline as a flow run as a tool; write to memory pauses for approval."
    elif kind == "exam-memory":
        note_text = (f"# {name}\n\nLangflow's Agent sitting the 27-task exam with memory (decision 035): the exam prompt (tools/assistant/rtrc-assistant-exam.md plus the frozen "
                     f"rules of agents/solve.py), {EXAM_MODEL} (the model of the frozen exam), and two tools as flows: **{NAMES['tool-validate-sysml']}** and "
                     f"**{NAMES['tool-memory-search']}** (paper 2 retrieval over MaritimeISR and the approved designs). No design pipeline, no write to memory, no knowledge-base card.\n\n"
                     f"- The same prompt and the same two tools as **{NAMES['opencode-memory-exam']}**, so the two columns on results page 1.3 compare the harnesses, not the tools.\n"
                     "- Run the whole exam with `python3 bench/langflow_exam.py --flow \"" + name + "\"`: 27 tasks × 3 repeats, a fresh session per task, scored by the frozen scorer; "
                     "time and tokens (the Agent's usage field) recorded per task. The answer keys never enter the prompt.\n"
                     "- One task by hand: paste its statement in the Playground; nothing is scored there.")
        description = f"Langflow's Agent on one exam task: the exam prompt, {EXAM_MODEL}, memory search and the official Pilot as its only tools."
    elif kind == "exam-pilot":
        note_text = (f"# {name}\n\nLangflow's Agent sitting the 27-task exam without memory (decision 035, project 2): the exam prompt, {EXAM_MODEL}, and one tool, "
                     f"**{NAMES['tool-validate-sysml']}** (the official Pilot). It is the Langflow counterpart of the sandboxed coding agents, which have files and ./validate; "
                     "it has the Pilot and nothing else.\n\n"
                     "- Run the whole exam with `python3 bench/langflow_exam.py --flow \"" + name + "\"`: 27 tasks × 3 repeats, a fresh session per task, scored by the frozen scorer; "
                     "time and tokens recorded per task.\n- One task by hand: paste its statement in the Playground; nothing is scored there.")
        description = f"Langflow's Agent on one exam task: the exam prompt, {EXAM_MODEL}, the official Pilot as its only tool."
    else:
        note_text = (f"# {name}\n\nThe chat version of the Pilot-only Langflow Agent (project 2): ask it for SysML v2 text; its one tool is **{NAMES['tool-validate-sysml']}**, "
                     "the official Pilot. It has no memory of projects and no design pipeline. Its exam version sits next to it.")
        description = f"Langflow's Agent with the official Pilot as its only tool, {EXAM_MODEL}; no memory, no design pipeline."
    note = {"id": "note-unfolded", "type": "noteNode", "position": {"x": 40, "y": -60}, "width": 1240, "height": 320, "style": {"width": 1240, "height": 320},
            "measured": {"width": 1240, "height": 320},
            "data": {"id": "note-unfolded", "type": "note", "node": {"display_name": "", "documentation": "", "template": {"backgroundColor": "blue"}, "description": note_text}}}
    tags = ["rtrc", "langflow-agent"] + (["exam"] if exam else ["assistant"]) + (["local"] if slug.endswith("local") else [])
    return {"name": name, "description": description, "endpoint_name": slug, "is_component": False, "tags": tags,
            "data": {"nodes": [note, chat_in, agent, chat_out, *cards, *extra], "edges": edges, "viewport": {"x": 0, "y": 0, "zoom": 0.5}}}


def _flow_tool_metadata(tool_name: str, *, approval: bool) -> dict:
    """The Actions table of a Run Flow tool card; approval=True makes the Agent pause for the person before running it."""
    from lfx.base.tools.constants import TOOLS_METADATA_INFO
    from lfx.inputs.inputs import ToolsInput
    rows = [{"name": tool_name, "description": "", "tags": [tool_name], "status": True, "approval_actions": ["approve", "reject"] if approval else []}]
    return ToolsInput(name="tools_metadata", display_name="Actions", info=TOOLS_METADATA_INFO, value=rows).to_dict()


def _as_tool(flow: dict, chat_input_id: str) -> dict:
    """Run Flow turns the input component's listed fields into the tool's arguments; only the engineer's text."""
    node = next(node for node in flow["data"]["nodes"] if node["id"] == chat_input_id)
    node["data"]["node"]["field_order"] = ["input_value"]
    return flow


def tool_flow(kind: str) -> dict:
    """One assistant tool unfolded as a flow of cards, run by the unfolded assistant through Run Flow (decision 034)."""
    slug, name, tool_name, chat_id, _, _ = TOOL_FLOWS[kind]
    chat_in = ChatInput(_id=chat_id)
    if kind == "search":
        library, seeds, hop = RtrcTool(_id="RtrcTool-library"), RtrcTool(_id="RtrcTool-seeds"), RtrcTool(_id="RtrcTool-hop")
        library.set(text=chat_in.message_response, step=T[0])
        seeds.set(text=chat_in.message_response, upstream=library.as_message, step=T[1])
        hop.set(text=chat_in.message_response, upstream=seeds.as_message, step=T[2])
        out = ChatOutput(_id="ChatOutput-cards")
        out.set(input_value=hop.as_message)
        graph = _graph(chat_in, [out])
        titles = {chat_id: ("Search words (the tool's argument)", "What the engineer is asking about."),
                  "RtrcTool-library": ("Memory library · Paper 2", "The sources the search reads: MaritimeISR and every approved design (analysis/memory/approved.jsonl), as element cards from the official Pilot parse."),
                  "RtrcTool-seeds": ("MiniLM + FAISS seeds · Paper 2", "bench/vector_index.py (frozen): the query embedded by the pinned MiniLM, searched in a FAISS index of the cards; cosine ≥ 0.30 plus the exact-name bonus. The index is cached by content hash and rebuilt when the memory changes."),
                  "RtrcTool-hop": ("One hop of neighbours · Paper 2", "bench/discover.py retrieve_existing: each seed's linked elements, then the cards the assistant receives, with values and sources."),
                  "ChatOutput-cards": ("Cards (the tool's result)", "")}
        notes = [("note-search", f"# {name}\n\nThe assistant's memory search as cards, in the order the code runs: the library, the vector seeds, the one-hop expansion. Every card calls the same function the results page and the pipeline's ① Search memory use, so the cards here are the cards there. A tool of the memory assistants (projects 3 and 4), chat and exam versions.\n\n- The library is the memory itself: MaritimeISR plus every approved design, re-read on every call, so a newly approved design is searchable at once.\n- The MiniLM + FAISS index is a derived cache keyed by the cards' content; it rebuilds itself when the memory changes (bench/vector_index.py, frozen).\n- The knowledge base rtrc_memory (Qwen embeddings) is a second, separate index for Langflow's own search; the write-to-memory flow refreshes it.", 40, -20)]
        description = "Search the memory for parts, attributes, limits and connections related to the engineer's words: the memory library, MiniLM + FAISS seeds (cosine ≥ 0.30 plus the exact-name bonus), one hop of neighbours; returns the matching cards with values and sources."
    elif kind == "write":
        gate, write, record = RtrcTool(_id="RtrcTool-gate"), RtrcTool(_id="RtrcTool-write"), RtrcTool(_id="RtrcTool-record")
        gate.set(text=chat_in.message_response, step=T[3])
        write.set(text=chat_in.message_response, upstream=gate.as_message, step=T[4])
        record.set(text=chat_in.message_response, upstream=write.as_message, step=T[5])
        memory = RtrcMemory(_id="RtrcMemory-refresh")
        memory.set(after=record.as_message)
        knowledge = KnowledgeComponent(_id="Knowledge-refresh")
        knowledge.set(input_df=memory.as_dataframe, knowledge_base=KNOWLEDGE_BASE, mode="Ingest", allow_duplicates=False, chunk_size=10,
                      column_config=[{"column_name": "text", "vectorize": True, "identifier": False},
                                     {"column_name": "id", "vectorize": False, "identifier": True}])
        out = ChatOutput(_id="ChatOutput-written")
        out.set(input_value=record.as_message)
        graph = _graph(chat_in, [out, knowledge])
        titles = {chat_id: ("'<run id> A' or '<run id> B' (the tool's argument)", "The design the engineer approved."),
                  "RtrcTool-gate": ("Gate · read only", "The page's rule before anything is written: official Pilot PASS, and POWER, LINK, STORE, TRACE all PASS; refuses a design already in memory."),
                  "RtrcTool-write": ("Write into memory · Paper 2", "Appends the design to analysis/memory/approved.jsonl and keeps its SysML file; the same gate refuses when a check failed."),
                  "RtrcTool-record": ("Record the approval", "The decision, grades and times on the run's record (page 2.3); only when the write happened."),
                  "RtrcMemory-refresh": ("Re-read the library · Paper 2", "MaritimeISR plus every approved design, now including the new one, as cards from the official parse."),
                  "Knowledge-refresh": ("Refresh the knowledge base rtrc_memory", "Embeds only the new cards with Qwen (qwen3.7-text-embedding); rows already there are skipped. Langflow's search sees the new design without running F0 by hand."),
                  "ChatOutput-written": ("Result (the tool's result)", "")}
        notes = [("note-write", f"# {name}\n\nThe approval gate of AGENTS.md as cards. The Langflow-Agent chat assistant pauses for the person before running this flow (the Actions row of its card); then: the gate (read only) → the write through the page's gate → the record → the memory re-read and the knowledge base refreshed with the new cards. The exam versions do not have this tool.\n\n- Nothing is written when the gate is closed: a failed check, a failed parse, or an unsourced number.\n- The MiniLM + FAISS index and list/read/search tools see the new design at once (they re-read the memory); this flow also refreshes Langflow's own knowledge base, so the knowledge-base fill flow no longer has to be run by hand after an approval.", 40, -20)]
        description = "Write an approved design into the memory: the gate (official Pilot PASS and all four checks PASS), the write, the record on the run, and the knowledge base refreshed with the new cards. The argument is '<run id> A' or '<run id> B'. Refuses a design that did not pass or is already in memory."
    else:
        save, pilot = RtrcTool(_id="RtrcTool-save"), RtrcTool(_id="RtrcTool-pilot")
        save.set(text=chat_in.message_response, step=T[6])
        pilot.set(upstream=save.as_message, step=T[7])
        out = ChatOutput(_id="ChatOutput-verdict")
        out.set(input_value=pilot.as_message)
        graph = _graph(chat_in, [out])
        titles = {chat_id: ("SysML v2 text (the tool's argument)", "What the engineer pasted."),
                  "RtrcTool-save": ("Save as a file", "The text becomes <package>.sysml under mvp/exam-inbox/; the package name is read from the text."),
                  "RtrcTool-pilot": ("Official SysML v2 Pilot · Paper 3", "mvp/engine.py run_submitted_model: the same Pilot 0.62 that grades the exam; PASS or FAIL with every diagnostic."),
                  "ChatOutput-verdict": ("Verdict (the tool's result)", "")}
        notes = [("note-validate", f"# {name}\n\nThe official Pilot on text the engineer pastes, as two cards: the file, then the parse. The Pilot is the judge here as everywhere else; the assistant only reports what it says. A tool of every Langflow-Agent flow and of the OpenCode-with-memory assistant, chat and exam versions.", 40, -20)]
        description = "Parse SysML v2 text the engineer pasted with the official SysML v2 Pilot: the text is saved as a file and parsed; returns PASS or FAIL with the diagnostics (line and message)."
    return _as_tool(build(name, description, graph, titles, notes, None, ["rtrc", "tool", kind]), chat_id)


# ---------- the main agent flow (F4) ----------

def main_flow(local: bool = False, as_tool: bool = False) -> dict:
    """The agent flow. local=True is the same graph with the Agent node preset to OpenCode on the 3-bit Qwen3.8-27B
    served by Ollama on this machine (decision 032): every model call of the run stays on this computer.
    as_tool=True is the local graph without the person's step: it ends at the review text, so the unfolded assistant
    can run it as a tool (Run Flow) and the person decides in the chat (decision 033)."""
    local = local or as_tool
    chat_in = ChatInput(_id="ChatInput-brief")
    start = RtrcStart(_id="RtrcStart-start")
    if local:
        start.set(brief=chat_in.message_response, agent="OpenCode on Qwen (sandbox)", model="qwen3.8-27b (Ollama)", replay="", require_brief=as_tool)
    else:
        start.set(brief=chat_in.message_response, agent="Qwen direct", model="qwen3.8-flash", replay="", require_brief=False)
    steps = {}
    for key, step_name in (("retrieve", S[0]), ("req", S[1]), ("new", S[2]), ("adapt", S[3]), ("validate", S[4]),
                           ("align", S[5]), ("checks", S[6]), ("trade", S[7]), ("review", S[8])):
        steps[key] = RtrcStep(_id=f"RtrcStep-{key}")
        steps[key].set(step=step_name)
    steps["retrieve"].set(upstream=start.start)
    steps["req"].set(upstream=steps["retrieve"].as_message)
    route = ConditionalRouterComponent(_id="IfElse-similar")
    route.set(input_text=steps["req"].as_message, operator="starts with", match_text="reuse", case_sensitive=True)
    steps["adapt"].set(upstream=route.true_response)
    steps["new"].set(upstream=route.false_response)
    steps["validate"].set(upstream=steps["new"].as_message, upstream_alt=steps["adapt"].as_message)
    steps["align"].set(upstream=steps["validate"].as_message)
    steps["checks"].set(upstream=steps["align"].as_message)
    gate = ConditionalRouterComponent(_id="IfElse-checks")
    gate.set(input_text=steps["checks"].as_message, operator="starts with", match_text="pass", case_sensitive=True)
    steps["trade"].set(upstream=gate.false_response)
    steps["review"].set(upstream=gate.true_response, upstream_alt=steps["trade"].as_message)
    if as_tool:
        out = ChatOutput(_id="ChatOutput-review")
        out.set(input_value=steps["review"].as_message)
        # Read-only cards: what ③ handed to OpenCode (decision 034). They hang off both design branches and feed nothing.
        prompt_cards = []
        for key, step_name in (("rules", T[8]), ("contract", T[9]), ("examples", T[10])):
            card = RtrcTool(_id=f"RtrcTool-prompt-{key}")
            card.set(upstream=steps["adapt"].as_message, upstream_alt=steps["new"].as_message, step=step_name)
            prompt_cards.append(card)
        graph = _graph(chat_in, [out, *prompt_cards])
        titles = {
            "RtrcTool-prompt-rules": ("③ shown · Rules · Paper 3", "The SysML v2 rules OpenCode wrote the designs under (bench/discover.py DESIGN_RULES). Read only."),
            "RtrcTool-prompt-contract": ("③ shown · Attribute template · Paper 3", "The attribute contract: one attribute per requirement, names verbatim, numbers from the brief. Read only."),
            "RtrcTool-prompt-examples": ("③ shown · Similar project or retrieved examples · Paper 2", "What came from the memory: the similar project's model to adapt, or the retrieved element cards. Read only."),
            "ChatInput-brief": ("Brief (the tool's argument)", "The unfolded assistant passes the confirmed brief here."),
            "RtrcStart-start": ("OpenCode on the local Qwen3.8-27B", "Preset: OpenCode in the sandbox, qwen3.8-27b (Ollama). Every model call stays on this machine."),
            "RtrcStep-retrieve": ("① Search memory · Paper 2", "Cards from the official parse of MaritimeISR and approved designs; MiniLM + FAISS; seeds plus one hop."),
            "RtrcStep-req": ("② Requirements", "Numbered requirements; every number must come from the brief. The message starts with reuse or new."),
            "IfElse-similar": ("Similar project found?", "True (reuse): adapt the similar project. False (new): write a new design."),
            "RtrcStep-adapt": ("③ Adapt the similar project · OpenCode in the sandbox", "Design A edits the similar project's model; design B is written new. OpenCode has ./validate (the official Pilot) in hand and edits until it parses."),
            "RtrcStep-new": ("③ New design · OpenCode in the sandbox", "Rules + template + retrieved examples + brief; A literal, B another arrangement; written with ./validate in hand."),
            "RtrcStep-validate": ("④ Official SysML v2 Pilot", "The Pilot is the judge. Every parse attempt is listed."),
            "RtrcStep-align": ("⑤ Align with memory · Paper 1", "The model proposes pairs; code checks both names and writes an alias / allocate package; the Pilot parses it with both sources."),
            "RtrcStep-checks": ("⑥ Checks + read-back", "Power, upload, storage and trace from numbers in the official parse. Starts with pass or fail."),
            "IfElse-checks": ("All four checks pass?", "True: to review. False: trade-offs first."),
            "RtrcStep-trade": ("Trade-offs", "Three proposals from catalog parts only; code recomputes each one; a stated limit never changes."),
            "RtrcStep-review": ("⑦ Diagram · Cameo export · review text", "The review the assistant hands back to the engineer. Saves the run for page 2.3."),
            "ChatOutput-review": ("Review text (the tool's result)", "Returned to the assistant; the person decides in the chat (write to memory pauses for approval)."),
        }
        notes = [("note-tool", f"# {PIPELINE_TOOL_NAME} (a tool of the memory assistants)\n\nThe design pipeline the **{NAMES['langflow-agent-memory-chat-max']}** and its local twin run when the engineer has confirmed a brief: the design agent flow without the person's step. "
                  "It ends at the review text; the decision is made in the chat (write to memory pauses for the person's approval, record decision saves it).\n\n"
                  "- Same nodes and the same shell service as the agent flow, so a run here and a run on the results page give the same retrieval, prompts, Pilot results and checks. The record appears on page 2.3.\n"
                  "- Designs are written by OpenCode in the bubblewrap sandbox on the local Qwen3.8-27B, with `./validate` in hand (decision 032): the Pilot's errors come back as a tool result and the file is edited.\n"
                  "- Stop the results page (8770) before a run. Edit this flow and the assistant runs the edited version.", 40, -20)]
        flow = build(PIPELINE_TOOL_NAME,
                     "Run the verified RTRC design pipeline on a confirmed brief: memory search, numbered requirements, designs A and B written by OpenCode in a sandbox with the official SysML v2 Pilot, the Pilot's verdict, alignment with the memory, the power / upload / storage / trace checks, trade-offs when a check fails, diagram and Cameo export. Returns the review text with the run id. Takes 2 to 10 minutes; the results page (port 8770) must be stopped.",
                     graph, titles, notes, None, ["rtrc", "pipeline", "tool"])
        return _as_tool(flow, "ChatInput-brief")
    # One chain per Human Input branch: Langflow keeps a decision's unchosen branches out of a run, not out of a join.
    branches = {"Approve design A": "A", "Approve design B": "B", "Reject": "reject", "Send back": "sendback"}
    outs = []
    for label, suffix in branches.items():
        record = RtrcRecord(_id=f"RtrcRecord-{suffix}")
        record.set(upstream=steps["review"].as_message, decision=label)
        out = ChatOutput(_id=f"ChatOutput-{suffix}")
        out.set(input_value=record.as_message)
        outs.append(out)
    graph = _graph(chat_in, outs)
    titles = {
        "ChatInput-brief": ("Requirement / brief", "Type the mission brief. Empty: the default brief of the 2.2 design space."),
        "RtrcStart-start": ("Agent: OpenCode on the local Qwen3.8-27B", "OpenCode in the sandbox, on the 3-bit Qwen3.8-27B that Ollama serves on this machine (scripts/qwen38.sh --serve). The other steps use the same local model. Or replay a saved run without model calls.") if local else
                           ("Agent: Qwen only for now", "Qwen direct, or Claude Code / OpenCode on Qwen in the sandbox. Or replay a saved run without model calls."),
        "RtrcStep-retrieve": ("① Search memory · Paper 2", "Cards from the official parse of MaritimeISR and approved designs; MiniLM + FAISS, cosine ≥ 0.30 plus the exact-name bonus; seeds plus one hop."),
        "RtrcStep-req": ("② Requirements", "Numbered requirements; every number must come from the brief. The message starts with reuse or new."),
        "IfElse-similar": ("Similar project found?", "True (reuse): adapt the similar project. False (new): write a new design."),
        "RtrcStep-adapt": ("③ Adapt the similar project · Paper 3 modify", "Design A edits the similar project's model; design B is written new for comparison."),
        "RtrcStep-new": ("③ New design · Paper 3 create", "Rules + template (attribute contract) + retrieved examples + brief and requirements. A literal, B another arrangement."),
        "RtrcStep-validate": ("④ Official SysML v2 Pilot ⇄ repair · Paper 3 loop", "The Pilot is the judge. A failed parse sends the complete error list back in the same conversation, up to 20 times. Every attempt is listed."),
        "RtrcStep-align": ("⑤ Align with memory · Paper 1", "The model proposes pairs; code checks both names and writes an alias / allocate package; the Pilot parses it with both sources."),
        "RtrcStep-checks": ("⑥ Checks + read-back · Paper 3 query", "Power, upload, storage and trace from numbers in the official parse; the model restates its model. Starts with pass or fail."),
        "IfElse-checks": ("All four checks pass?", "True: to review. False: trade-offs first."),
        "RtrcStep-trade": ("Trade-offs", "Three proposals from catalog parts only; code recomputes each one; the 60 W limit never changes."),
        "RtrcStep-review": ("⑦ Model diagram · Cameo export · review", "Diagram drawn from the official parse; the design exported for Cameo (when licensed); the approval text. Saves the run for page 2.3."),
        "RtrcRecord-A": ("Write design A to memory · Paper 2 · ⑨ record", "Refused unless all four checks passed; an approved design becomes retrievable cards. Then saves the decision, grades and times."),
        "RtrcRecord-B": ("Write design B to memory · Paper 2 · ⑨ record", "Refused unless all four checks passed. Then saves the decision, grades and times."),
        "RtrcRecord-reject": ("⑨ Record: rejected", "Saves the decision with every stage's verdict, attempts, seconds, model calls and cost."),
        "RtrcRecord-sendback": ("⑨ Record: sent back", "Saves the decision; change the brief or pick a trade-off and run again."),
        "ChatOutput-A": ("Chat Output: design A", "Grades and times."), "ChatOutput-B": ("Chat Output: design B", "Grades and times."),
        "ChatOutput-reject": ("Chat Output: rejected", "Grades and times."), "ChatOutput-sendback": ("Chat Output: sent back", "Grades and times."),
    }
    human = {"id": "HumanInput-person", "decisions": ["Approve design A", "Approve design B", "Reject", "Send back"],
             "title": "⑧ Person decides · Paper 1 review",
             "info": "The run pauses here with the review text. Approve writes the design to memory; Send back returns the brief with a trade-off.",
             "prompt_from": ("RtrcStep-review", "message"),
             "branches": {label: [(f"RtrcRecord-{suffix}", "upstream")] for label, suffix in branches.items()}}
    local_note = (f"# {NAMES['other-design-agent-flow-local']}\n\nThe design agent flow with every model call on this computer: the 3-bit Qwen3.8-27B served by Ollama (`scripts/qwen38.sh --serve`), and OpenCode in the bubblewrap sandbox writing the designs with `./validate` (the official Pilot) in hand, up to 60 turns per design. Nothing leaves the machine.\n\n- Same nodes, same shell service, same checks as **{NAMES['other-design-agent-flow']}**; only the Agent node's presets differ (OpenCode, qwen3.8-27b (Ollama)).\n- Direct writing with the 27B got stuck on `part usage vessel` for 20 identical repairs (run 20261007T014335); OpenCode gets the Pilot's errors as a tool result and edits the file (decision 032).\n- Stop the results page (8770) before a run: sandboxed agents and the page's answer keys do not run together.\n- Click a node after a run to read what it did; replay a saved run with *Replay a saved run* = `latest` or a run id.")
    notes = [
        ("note-main", local_note if local else f"# {NAMES['other-design-agent-flow']} (Part 2)\n\nA requirement becomes an approvable SysML v2 design. Two cases: **new** (nothing similar in memory, start from scratch) or **reuse** (adapt the similar project found in memory).\n\n- Every RTRC node calls the code behind the results page through the RTRC shell service (`bench/shell_service.py`), so a run here and a run on the page give the same retrieval, prompts, Pilot results and checks.\n- **Qwen only for now** (RTRC has not answered which models may be used).\n- Click a node after a run to read what it did: the retrieved cards, every Pilot attempt and its errors, the alignment pairs, the checks.\n- Replay any saved run without model calls: set *Replay a saved run* in the Agent node to `latest` or a run id.", 40, -20),
        ("note-papers", "## Where the three papers are used\n\n- **Paper 2** (Bader et al., GRAG): ① Search memory and Write to memory. Cards from the official parse, MiniLM + FAISS, seeds + one hop.\n- **Paper 3** (Longshore, Bell, Madachy): ③ create / modify with rules + template + examples; ④ the correction loop, with the Pilot's errors instead of a person; ⑥ read-back is its *query* use.\n- **Paper 1** (Li, Husung, Wang): ⑤ the alias / allocate alignment package, and ⑧ the person's review.\n- **Ours**: the Pilot as judge, the checks, trade-offs recomputed by code, the approval gate, the grades and times.", 540, -20),
        ("note-cameo", f"## Cameo (when RTRC provides the license)\n\n⑦ already writes each passing design to `analysis/cameo-exports/<run>/`. Open it in Cameo's SysML v2 edition and record the result with the flow **{NAMES['other-cameo-check']}**. The Pilot stays the judge; Cameo's result is recorded as agreement (interoperability). Cameo has no headless command, so this is a person's step.", 1040, -20),
    ]
    if local:
        return build(NAMES["other-design-agent-flow-local"],
                     "The design agent flow with every model call on this machine: OpenCode in the sandbox on the 3-bit Qwen3.8-27B served by Ollama; memory search, new or reuse, the official Pilot, alignment, checks, a person's decision, memory, grades and times.",
                     graph, titles, notes, [human], ["rtrc", "agent", "local"])
    return build(NAMES["other-design-agent-flow"],
                 "Part 2 of the results page as a Langflow flow: memory search, new or reuse, the official Pilot loop, alignment, checks, a person's decision, memory, grades and times.",
                 graph, titles, notes, [human], ["rtrc", "agent"])


# ---------- F0 memory ----------

def memory_flow() -> dict:
    memory = RtrcMemory(_id="RtrcMemory-library")
    out = ChatOutput(_id="ChatOutput-memory")
    out.set(input_value=memory.as_message)
    knowledge = KnowledgeComponent(_id="Knowledge-memory")
    knowledge.set(input_df=memory.as_dataframe, knowledge_base=KNOWLEDGE_BASE, mode="Ingest", allow_duplicates=False, chunk_size=10,
                  column_config=[{"column_name": "text", "vectorize": True, "identifier": False},
                                 {"column_name": "id", "vectorize": False, "identifier": True}])
    graph = _graph(memory, [out, knowledge])
    titles = {"RtrcMemory-library": ("F0 Memory · Paper 2", "MaritimeISR plus every approved design, as element cards from the official parse, with their links."),
              "ChatOutput-memory": ("Chat Output", "The memory's sources and size."),
              "Knowledge-memory": ("Knowledge base rtrc_memory", "The cards as Langflow's own knowledge base, embedded by Qwen (qwen3.7-text-embedding). Rows already there are skipped.")}
    notes = [("note-memory", f"# {NAMES['other-memory-knowledge-base']} · what the agent knows\n\nThe memory is the existing MaritimeISR model plus every design a person approved, parsed by the official Pilot into element cards (type, full name, value or connection ends, documentation text) with their links.\n\n- Running this flow fills the Langflow knowledge base **rtrc_memory** (Knowledge page): the card text is embedded by Qwen, the other columns are kept as metadata, and cards already there are skipped. Run it again after a design is approved outside the write-to-memory flow.\n- The design flows' ① Search memory always uses our own retrieval (MiniLM + FAISS, seeds + one hop), so its results match the results page.", 40, -20)]
    flow = build(NAMES["other-memory-knowledge-base"], "The library the agent searches: MaritimeISR and approved designs as cards, mirrored into a Langflow knowledge base.",
                 graph, titles, notes, None, ["rtrc", "memory"])
    for node in flow["data"]["nodes"]:
        if node["id"] == "Knowledge-memory":
            node["data"]["node"]["template"]["knowledge_base"]["options"] = [KNOWLEDGE_BASE]
    return flow


# ---------- the exam versions of projects 1 and 2: one exam cell, the candidate preset ----------

EXAM_CANDIDATES = {
    # slug: (approach or agent, steps shown, what the candidate does)
    "direct-exam-p0": ("P0", ["Issue task", "Write answer", "Official syntax", "Read values", "Check against key", "Approval gate", "Archive"],
                       "P0 one-shot: the model writes once; a failed parse is not repaired."),
    "direct-exam-p1": ("P1", ["Issue task", "Write answer", "Official syntax", "Repair from errors", "Read values", "Check against key", "Approval gate", "Archive"],
                       "P1: a failed parse sends the official Pilot's complete error list back in the same conversation, up to 20 times (paper 3's correction, by the tool)."),
    "direct-exam-p2": ("P2", ["Issue task", "Outline", "Write answer", "Official syntax", "Repair from errors", "Read values", "Check against key", "Approval gate", "Archive"],
                       "P2: an outline of parts, ports and connections first (no SysML yet), then the answer, then repairs as in P1."),
    "direct-exam-p3": ("P3", ["Issue task", "Retrieve notes", "Outline", "Write answer", "Official syntax", "Repair from errors", "Read values", "Check against key", "Approval gate", "Archive"],
                       "P3: MiniLM + FAISS retrieval over the official-examples library (paper 2) into the outline prompt, then the answer, then repairs as in P1."),
    "sandbox-exam-opencode": ("opencode", ["Issue task", "Write answer", "Tool calls (agents)", "Official syntax", "Check against key", "Archive"],
                              "OpenCode in the bubblewrap sandbox with the task, AGENTS.md and ./validate; it repairs inside its own session; the grader parses the final answer once."),
    "sandbox-exam-claude-code": ("claude-code", ["Issue task", "Write answer", "Tool calls (agents)", "Official syntax", "Check against key", "Archive"],
                                 "Claude Code in the same sandbox with the same files and tools as OpenCode (cloud Qwen; the local model is not routed to it)."),
}


def exam_cell_flow(slug: str) -> dict:
    """One exam cell with the candidate preset (decision 035): a sealed task id in (live), or a graded cell replayed; the
    key is used only by the scorer. bench/langflow_exam.py loops the 27 tasks through it; such reruns are saved apart
    from the frozen batches."""
    preset, names, what = EXAM_CANDIDATES[slug]
    agent = preset in {"opencode", "claude-code"}
    cell = RtrcExamCell(_id="RtrcExamCell-cell")
    if agent:
        cell.set(mode="Live: sandboxed agent on Qwen", cell=f"{'opencode' if preset == 'opencode' else 'claude'}:1:MOD-05:P-CODE{'' if preset == 'opencode' else '-2'}",
                 task_id="MOD-05", approach="P1", agent=preset, model=EXAM_MODEL)
    else:
        cell.set(mode="Live: direct Qwen (P0–P3)", cell=f"flash:1:GEN-03:{preset}", task_id="GEN-03", approach=preset, agent="opencode", model=EXAM_MODEL)
    previous, titles = cell.as_data, {}
    nodes = []
    for index, step in enumerate(names):
        node = RtrcExamStep(_id=f"RtrcExamStep-{index:02d}")
        node.set(cell=previous, step=step)
        previous = node.pass_on
        nodes.append(node)
    out = ChatOutput(_id="ChatOutput-exam")
    out.set(input_value=nodes[-1].show)
    graph = Graph(start=cell, end=out)
    papers = {"Retrieve notes": " · Paper 2", "Outline": " · Paper 3", "Write answer": " · Paper 3", "Repair from errors": " · Paper 3 loop"}
    for index, step in enumerate(names):
        titles[f"RtrcExamStep-{index:02d}"] = (step + papers.get(step, ""), "")
    titles["RtrcExamCell-cell"] = (f"Exam cell · {NAMES[slug].replace(' exam', '')} · {EXAM_MODEL}",
                                   what + " Type a sealed task id and run, or switch the mode to replay a graded cell. Time and tokens are recorded. The answer key is used only by the scorer.")
    titles["ChatOutput-exam"] = ("Verdict and record", "")
    text = (f"# {NAMES[slug]}\n\n{what}\n\n- One task: type its id (GEN-01 … RT-05) in the cell node and run; the steps light up with the record and the verdict against the sealed key "
            "(missing items only, never the key). Such a run is saved under analysis/langflow-console/ and is not added to the frozen score.\n"
            f"- The whole exam: `python3 bench/langflow_exam.py --flow \"{NAMES[slug]}\"` runs the 27 tasks three times through this flow and saves a rerun batch next to the frozen one; "
            "the frozen matrix of results page 1.3 does not change.\n"
            "- Replay: set the mode to *Replay a graded cell* and a cell id such as `flash:1:GEN-03:P1` or `opencode:1:MOD-05:P-CODE`."
            + ("\n- Stop the results page (8770) before a live run: sandboxed agents and the page's answer keys do not run together." if agent else ""))
    return build(NAMES[slug], f"One exam cell of {NAMES[slug].replace(' exam', '')}: a sealed task in, the verdict out; or replay a graded cell.",
                 graph, titles, [("note-exam", text, 40, -20)], None, ["rtrc", "exam"])


# ---------- the chat versions of projects 1 and 2 (decision 036): a person's words, a conversation that continues ----------

CHAT_FLOWS = {
    "direct-chat-p0": "Direct model · P0 one answer", "direct-chat-p1": "Direct model · P1 repair from errors",
    "direct-chat-p2": "Direct model · P2 outline first", "direct-chat-p3": "Direct model · P3 retrieval then outline",
    "sandbox-chat-opencode": "OpenCode in the sandbox", "sandbox-chat-claude-code": "Claude Code in the sandbox",
}


def exam_chat_flow(slug: str) -> dict:
    """Chat Input -> RTRC Chat -> Chat Output: the person's message goes to the candidate as written, in the conversation of
    the Langflow session (the lecture's wiring of Chat Input, without its query rewrite). The official Pilot parses a reply
    only when it holds a model; there is no key, so nothing is scored."""
    candidate = CHAT_FLOWS[slug]
    assert candidate in CHAT_CANDIDATES
    chat_in = ChatInput(_id="ChatInput-person")
    node = RtrcChat(_id="RtrcChat-candidate")
    node.set(message=chat_in.message_response, candidate=candidate, model=EXAM_MODEL)
    out = ChatOutput(_id="ChatOutput-reply")
    out.set(input_value=node.as_message)
    graph = _graph(chat_in, [out])
    direct = slug.startswith("direct")
    approach = slug[-2:].upper()  # P0 … P3 of a direct-chat slug
    paths = {"P0": "one answer; a model in it is parsed once and not repaired",
             "P1": "the answer; a model in it is parsed, and the Pilot's complete error list goes back into this conversation until it passes",
             "P2": "an outline first when the message asks for a model, then the answer, then the repair loop",
             "P3": "retrieval from the official examples with your own words, then the outline, the answer and the repair loop"}
    titles = {"ChatInput-person": ("Person", "Write as you would to a colleague. Earlier messages of this session stay in the conversation."),
              "RtrcChat-candidate": (f"{NAMES[slug].replace(' chat', '')} · {EXAM_MODEL}",
                                     (f"Your message, as written, plus the last 30 of this session: {paths[approach]}. The system prompt lets it talk; only a request for a model gets a model.")
                                     if direct else "The agent in a sandbox kept for this session, with ./validate and rules written for a conversation; its own session continues across messages."),
              "ChatOutput-reply": ("Reply (not scored)", "")}
    text = (f"# {NAMES[slug]}\n\nThe chat version of **{NAMES[slug].replace(' chat', ' exam')}**: the same candidate talking to a person. Your words reach it as written, "
            "and the conversation continues across messages, so \"change the last one\" has something to change. Nothing is scored; the official Pilot parses a reply "
            "only when it holds a fenced sysml block.\n\n"
            + ("- What the approach adds happens around your message, not instead of it: P3 retrieves with your own words (no query rewrite), P2 and P3 outline only when you ask for a model, "
               "P1 to P3 repair from the Pilot's complete error list, P0 does not.\n" if direct else
               "- The agent has files and ./validate (the official Pilot) and nothing else; it writes a .sysml file only when you ask for a model. It runs while the results page is up: "
               "a conversation is not scored, so the page's answer keys cannot enter a score.\n")
            + "- Each turn is saved under analysis/langflow-console/ as a chat run; it never enters the frozen matrix. The exam version next to this flow still sits the sealed tasks through the frozen solver.")
    return build(NAMES[slug], f"{NAMES[slug].replace(' chat', '')} in a conversation: your words as written, a reply, the official Pilot on a model in it, nothing scored.",
                 graph, titles, [("note-chat", text, 40, -20)], None, ["rtrc", "chat"])


# ---------- the exam results tables ----------

def results_flow() -> dict:
    results = RtrcResults(_id="RtrcResults-facts")
    out = ChatOutput(_id="ChatOutput-results")
    out.set(input_value=results.as_message)
    graph = Graph(start=results, end=out)
    titles = {"RtrcResults-facts": ("Results (frozen, revision 2)", "Pass rates by task type and approach for the four candidates, the retry run and the cost."),
              "ChatOutput-results": ("Chat Output", "")}
    notes = [("note-results", f"# {NAMES['other-exam-results']} · the headline numbers\n\nThe frozen results of the 27-task exam: direct qwen3.8-flash and qwen3.8-max (P0–P3, three repeats), OpenCode and Claude Code on qwen3.8-flash in the sandbox, and the extra retry run. The matrix (with the Langflow exam columns of decision 035), the cost chart and the model diagrams stay on the results page (`python3 bench/exam_board.py`).", 40, -20)]
    return build(NAMES["other-exam-results"], "The frozen exam results as tables.", graph, titles, notes, None, ["rtrc", "results"])


# ---------- F5 MOD change chain ----------

def mod_flow() -> dict:
    change = RtrcModChange(_id="RtrcModChange-case")
    change.set(task="MOD-05", mode="Replay the latest run")
    views = ["Task and baseline", "Model change", "Official syntax", "Task and design verdicts", "Limit check"]
    previous, nodes = change.as_data, []
    for index, view in enumerate(views):
        node = RtrcModStep(_id=f"RtrcModStep-{index}")
        node.set(case=previous, view=view)
        previous = node.pass_on
        nodes.append(node)
    readback = RtrcModStep(_id="RtrcModStep-readback")
    readback.set(case=nodes[-1].pass_on, view="Read-back")
    out = ChatOutput(_id="ChatOutput-readback")
    out.set(input_value=readback.show)
    route = ConditionalRouterComponent(_id="IfElse-limit")
    route.set(input_text=nodes[-1].show, operator="starts with", match_text="moved", case_sensitive=True)
    gate_outs = []
    for suffix, label in (("keep", "Keep the stated limit"), ("approve", "Approve the new limit")):
        gate = RtrcGateRecord(_id=f"RtrcGateRecord-{suffix}")
        gate.set(upstream=route.true_response, gate="stated limit", choice=label)
        gate_out = ChatOutput(_id=f"ChatOutput-{suffix}")
        gate_out.set(input_value=gate.record)
        gate_outs.append(gate_out)
    graph = _graph(change, [out, *gate_outs])
    titles = {"RtrcModChange-case": ("MOD change · Paper 3 modify", "MOD-01 to MOD-05: the model edits an existing model. Replay the latest run, or run it again on Qwen (two model calls)."),
              "RtrcModStep-0": ("Task and baseline", ""), "RtrcModStep-1": ("Model change", ""), "RtrcModStep-2": ("Official SysML v2 Pilot", ""),
              "RtrcModStep-3": ("Task verdict and design verdict", "Task verdict: the sealed key's checklist. Design verdict: the budget. MOD-05 is over budget by construction; an honest answer passes the task."),
              "RtrcModStep-4": ("Did a stated limit move?", "Starts with moved or unchanged."),
              "RtrcModStep-readback": ("Read-back · Paper 3 query", "The model restates the changed model; code checks every number."),
              "ChatOutput-readback": ("Chat Output: read-back", ""),
              "IfElse-limit": ("Limit moved?", "True: a person must decide before the change is accepted. False: nothing to decide."),
              "RtrcGateRecord-keep": ("Record: limit kept", "The change is not accepted; the stated limit stays."),
              "RtrcGateRecord-approve": ("Record: new limit approved", "Only a person can approve a changed limit (AGENTS.md)."),
              "ChatOutput-keep": ("Chat Output: limit kept", ""), "ChatOutput-approve": ("Chat Output: new limit approved", "")}
    human = {"id": "HumanInput-limit", "decisions": ["Keep the stated limit", "Approve the new limit"], "title": "Person decides on the limit",
             "info": "Only reached when the answer changed a stated limit. In the exam no answer did.",
             "prompt_from": ("IfElse-limit", "true_result"),
             "branches": {"Keep the stated limit": [("RtrcGateRecord-keep", "upstream")], "Approve the new limit": [("RtrcGateRecord-approve", "upstream")]}}
    notes = [("note-mod", f"# {NAMES['other-mod-change-chain']} · changing an existing model (page 2.4)\n\nThe model edits a task's baseline model; the official Pilot judges the syntax; the sealed key gives the task verdict and the budget gives the design verdict; the model reads the edited model back and code checks every number. If the answer moved a stated limit, a person must decide before the change is accepted (AGENTS.md: propose it and stop).", 40, -20)]
    return build(NAMES["other-mod-change-chain"], "One change to an existing model, judged, read back and gated.", graph, titles, notes, [human], ["rtrc", "mod"])


# ---------- Cameo check ----------

def cameo_flow() -> dict:
    run = ChatInput(_id="ChatInput-run")
    export = RtrcCameoExport(_id="RtrcCameoExport-export")
    export.set(run_id=run.message_response)
    results = {"Opens cleanly": "opens", "Errors in Cameo": "errors", "Not checked yet": "notchecked"}
    outs, titles = [], {}
    for label, suffix in results.items():
        record = RtrcCameoRecord(_id=f"RtrcCameoRecord-{suffix}")
        record.set(upstream=export.export, result=label, key="A")
        out = ChatOutput(_id=f"ChatOutput-{suffix}")
        out.set(input_value=record.record)
        outs.append(out)
        titles[f"RtrcCameoRecord-{suffix}"] = (f"Record: {label.lower()}", "Stored next to the official Pilot's verdict as agreement (interoperability).")
        titles[f"ChatOutput-{suffix}"] = (f"Chat Output: {label.lower()}", "")
    graph = _graph(run, outs)
    titles |= {"ChatInput-run": ("Run id", "Type a saved run id, for example 20261006T211951."),
               "RtrcCameoExport-export": ("Export for Cameo (when licensed)", "Writes the run's passing designs as .sysml files for Cameo's SysML v2 edition.")}
    human = {"id": "HumanInput-cameo", "decisions": list(results), "title": "Person opens it in Cameo",
             "info": "Open the exported file in Cameo's SysML v2 edition and pick the result. Until RTRC provides the license: Not checked yet.",
             "prompt_from": ("RtrcCameoExport-export", "message"),
             "branches": {label: [(f"RtrcCameoRecord-{suffix}", "upstream")] for label, suffix in results.items()}}
    notes = [("note-cameo", f"# {NAMES['other-cameo-check']} (when RTRC provides the license)\n\nRTRC works in Cameo. This flow exports a run's officially parsed designs and records whether they open cleanly in Cameo's SysML v2 edition. The official Pilot stays the judge; Cameo's result is recorded as agreement, the interoperability evidence the brief asks for. Cameo has no headless command, so a person opens the file.", 40, -20)]
    return build(NAMES["other-cameo-check"], "Export a run's designs for Cameo and record the person's check.", graph, titles, notes, [human], ["rtrc", "cameo"])


# slug -> builder; the slugs, names and projects are in catalog.py (rtrc-assistant-langchain is built by build_assistant.py)
FLOWS = {
    # 5 · shared tool flows
    "tool-memory-search": lambda: tool_flow("search"), "tool-validate-sysml": lambda: tool_flow("validate"),
    "tool-write-to-memory": lambda: tool_flow("write"), "tool-design-pipeline": lambda: main_flow(as_tool=True),
    # 1 · direct model, P0 to P3: exam and chat
    **{slug: (lambda s=slug: exam_cell_flow(s)) for slug in ("direct-exam-p0", "direct-exam-p1", "direct-exam-p2", "direct-exam-p3")},
    **{slug: (lambda s=slug: exam_chat_flow(s)) for slug in ("direct-chat-p0", "direct-chat-p1", "direct-chat-p2", "direct-chat-p3")},
    # 2 · coding agents without memory: exam and chat
    "sandbox-exam-opencode": lambda: exam_cell_flow("sandbox-exam-opencode"), "sandbox-exam-claude-code": lambda: exam_cell_flow("sandbox-exam-claude-code"),
    "langflow-agent-pilot-exam": lambda: unfolded_flow("langflow-agent-pilot-exam"),
    "sandbox-chat-opencode": lambda: exam_chat_flow("sandbox-chat-opencode"), "sandbox-chat-claude-code": lambda: exam_chat_flow("sandbox-chat-claude-code"),
    "langflow-agent-pilot-chat": lambda: unfolded_flow("langflow-agent-pilot-chat"),
    # 3 · OpenCode with memory
    "opencode-memory-exam": lambda: assistant_flow(exam=True), "opencode-memory-chat": assistant_flow,
    # 4 · Langflow Agent with memory
    "langflow-agent-memory-exam": lambda: unfolded_flow("langflow-agent-memory-exam"),
    "langflow-agent-memory-chat-max": lambda: unfolded_flow("langflow-agent-memory-chat-max"),
    "langflow-agent-memory-chat-local": lambda: unfolded_flow("langflow-agent-memory-chat-local"),
    # 6 · other
    "other-design-agent-flow": main_flow, "other-design-agent-flow-local": lambda: main_flow(local=True),
    "other-memory-knowledge-base": memory_flow, "other-exam-results": results_flow, "other-mod-change-chain": mod_flow,
    "other-cameo-check": cameo_flow,
}


def _stable(value):
    """Same flow, same file: default messages carry the build time, which would change every file on every build."""
    if isinstance(value, dict):
        return {key: "2026-10-06 00:00:00 UTC" if key == "timestamp" and isinstance(item, str) else _stable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_stable(item) for item in value]
    return value


def main() -> None:
    for slug, make in FLOWS.items():
        flow = _stable(make())
        flow["data"]["edges"].sort(key=lambda edge: edge["id"])
        flow["endpoint_name"] = slug
        target = flow_file(slug)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(flow, indent=2, ensure_ascii=False), encoding="utf-8")
        nodes = flow["data"]["nodes"]
        print(f"{target.relative_to(ROOT)}: {sum(1 for n in nodes if n['type'] == 'genericNode')} nodes, {len(flow['data']['edges'])} edges, "
              f"{sum(1 for n in nodes if n['type'] == 'noteNode')} notes")


if __name__ == "__main__":
    main()
