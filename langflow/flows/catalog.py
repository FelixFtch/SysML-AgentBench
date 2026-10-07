"""The RTRC flows and the six Langflow projects they live in (decision 035). One place for the names.

Each project holds one candidate's exam version and chat version side by side, so the same canvas can sit the
27-task exam (one task in, one answer out, scored outside) or talk to a person:

1. Direct model, approaches P0 to P3: the fixed paths of the exam, no tools; one flow per approach.
2. Sandboxed coding agents: OpenCode and Claude Code with files and ./validate (the official Pilot), nothing else.
3. OpenCode with memory: the conversational assistant (OpenCode over the RTRC tools).
4. Langflow Agent with memory: the same tools on Langflow's own Agent, each tool a card.
5. Shared tool flows: memory search, validate, write to memory, the design pipeline; run as tools by 3 and 4.
6. Other: the design agent flow with a person's decision, the knowledge-base fill, the results tables, the MOD
   change chain, the Cameo check.

A slug is the flow file name (langflow/flows/<slug>.json) and the flow's endpoint name; the name is what Langflow
shows. Run Flow names a tool "<flow name with spaces as dashes>_tool", so the shared tool flows keep short names.
RETIRED lists names of earlier versions of these flows that an import removes.
"""
from __future__ import annotations

PROJECTS: list[tuple[str, str, list[tuple[str, str]]]] = [
    ("5 · Shared tool flows",
     "Flows the memory assistants run as tools: memory search (paper 2), the official Pilot on pasted SysML, write to memory (gate, write, record, knowledge base), the design pipeline. Imported first; projects 3 and 4 point at them.",
     [("tool-memory-search", "Memory search"),
      ("tool-validate-sysml", "Validate SysML with the official Pilot"),
      ("tool-write-to-memory", "Write to memory"),
      ("tool-design-pipeline", "Design pipeline")]),
    ("1 · Direct model, approaches P0 to P3",
     "The exam's fixed paths, one flow per approach: P0 writes once; P1 repairs from the official Pilot's complete error list; P2 outlines first; P3 retrieves examples (paper 2) before the outline. The model has no tools. Exam: a sealed task id in, scored against its key. Chat: a task text in, the answer out, nothing scored.",
     [("direct-exam-p0", "Direct model exam · P0 one-shot"),
      ("direct-exam-p1", "Direct model exam · P1 repair from errors"),
      ("direct-exam-p2", "Direct model exam · P2 outline first"),
      ("direct-exam-p3", "Direct model exam · P3 retrieval then outline"),
      ("direct-chat-p0", "Direct model chat · P0 one-shot"),
      ("direct-chat-p1", "Direct model chat · P1 repair from errors"),
      ("direct-chat-p2", "Direct model chat · P2 outline first"),
      ("direct-chat-p3", "Direct model chat · P3 retrieval then outline")]),
    ("2 · Coding agents without memory: OpenCode, Claude Code, Langflow Agent",
     "Agents that choose their own steps but have no memory tools and no design pipeline. OpenCode and Claude Code run in the bubblewrap sandbox with the task, AGENTS.md and ./validate (the official Pilot). The Langflow Agent has the official Pilot as its only tool. Exam: a sealed task in, scored, time and tokens recorded. Chat: a task text in, the answer out.",
     [("sandbox-exam-opencode", "OpenCode in the sandbox exam"),
      ("sandbox-exam-claude-code", "Claude Code in the sandbox exam"),
      ("langflow-agent-pilot-exam", "Langflow Agent, Pilot only exam"),
      ("sandbox-chat-opencode", "OpenCode in the sandbox chat"),
      ("sandbox-chat-claude-code", "Claude Code in the sandbox chat"),
      ("langflow-agent-pilot-chat", "Langflow Agent, Pilot only chat")]),
    ("3 · OpenCode with memory",
     "OpenCode as the conversational harness over the RTRC tools (memory search, read a project, the design pipeline, the official Pilot, the memory gate, decisions, Cameo export). Chat: the design assistant. Exam: a fresh session per task, answer only, memory search and the Pilot as the only tools, qwen3.8-flash.",
     [("opencode-memory-exam", "OpenCode with memory exam"),
      ("opencode-memory-chat", "OpenCode with memory chat")]),
    ("4 · Langflow Agent with memory",
     "Langflow's own Agent over the same tools, one card per tool, four tools as flows. Chat: the unfolded assistant on qwen3.8-max or the local Qwen3.8-27B. Exam: the same exam rules and the same two tools as project 3, qwen3.8-flash.",
     [("langflow-agent-memory-exam", "Langflow Agent with memory exam"),
      ("langflow-agent-memory-chat-max", "Langflow Agent with memory chat · qwen3.8-max"),
      ("langflow-agent-memory-chat-local", "Langflow Agent with memory chat · local Qwen3.8-27B"),
      ("rtrc-assistant-langchain", "Langflow Agent with memory chat · qwen3.8-max · one MCP card (decision 031)")]),
    ("6 · Other",
     "The design agent flow with the person's decision at ⑧ (cloud Qwen, and the local Qwen3.8-27B via OpenCode), the knowledge-base fill, the exam results tables, the MOD change chain, the Cameo check.",
     [("other-design-agent-flow", "Design agent flow with a person's decision"),
      ("other-design-agent-flow-local", "Design agent flow · local Qwen3.8-27B via OpenCode"),
      ("other-memory-knowledge-base", "Memory knowledge base fill"),
      ("other-exam-results", "Exam results tables"),
      ("other-mod-change-chain", "MOD change chain"),
      ("other-cameo-check", "Cameo check")]),
]

NAMES: dict[str, str] = {slug: name for _, _, flows in PROJECTS for slug, name in flows}
PROJECT_OF: dict[str, str] = {slug: project for project, _, flows in PROJECTS for slug, _ in flows}
ORDER: list[str] = [slug for _, _, flows in PROJECTS for slug, _ in flows]

# The single project of decisions 030 to 034 and the flow names it held; an import moves everything into the six
# projects above and removes these.
OLD_PROJECT = "RTRC SysML-AgentBench"
RETIRED = [
    "RTRC design assistant", "RTRC design assistant (Langflow Agent, qwen3.8-max)", "RTRC design assistant (local Qwen3.8-27B)",
    "RTRC design assistant · unfolded (qwen3.8-max)", "RTRC design assistant · unfolded (local 27B)",
    "RTRC memory search", "RTRC write to memory", "RTRC validate SysML", "RTRC design pipeline", "RTRC design pipeline (as a tool)",
    "RTRC agent flow: requirement to approved SysML v2 design", "RTRC agent flow · local Qwen3.8-27B via OpenCode",
    "RTRC F0: memory (what the agent knows)", "RTRC F1: exam cell, direct model", "RTRC F2: exam cell, sandboxed coding agent",
    "RTRC F3: results", "RTRC F5: MOD change chain", "RTRC Cameo check (when licensed)",
]


def tool_name(flow_name: str) -> str:
    """Run Flow's name for a flow used as a tool."""
    return flow_name.replace(" ", "-") + "_tool"
