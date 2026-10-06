"""Build the RTRC Langflow flows as code and write them as flow files for the Langflow editor.

    LANGFLOW_CONFIG_DIR=.langflow/config .venv-langflow/bin/python langflow/flows/build_flows.py

Each flow is a Langflow graph of official components (Chat Input / Output, Text Input, If-Else, Human Input) and the
RTRC components in langflow/components/rtrc, built in Python the way Langflow's own starter projects are. This script
then adds what the Python graph API does not express: Human Input's branch outputs, readable positions, and canvas
notes that say who does each step and which paper it applies. Output: langflow/flows/*.json; import them with
langflow/flows/import_flows.py. Qwen only for now; the Cameo steps are used once RTRC provides the license.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "langflow" / "components"))

from lfx.components.flow_controls.conditional_router import ConditionalRouterComponent  # noqa: E402
from lfx.components.flow_controls.human_input import HumanInput, _action_id  # noqa: E402
from lfx.components.input_output import ChatInput, ChatOutput  # noqa: E402
from lfx.graph import Graph  # noqa: E402
from rtrc.rtrc_cameo import RtrcCameoExport  # noqa: E402
from rtrc.rtrc_cameo_record import RtrcCameoRecord  # noqa: E402
from rtrc.rtrc_exam_cell import RtrcExamCell  # noqa: E402
from rtrc.rtrc_exam_step import RtrcExamStep  # noqa: E402
from rtrc.rtrc_gate import RtrcGateRecord  # noqa: E402
from rtrc.rtrc_memory import RtrcMemory  # noqa: E402
from rtrc.rtrc_mod import RtrcModChange  # noqa: E402
from rtrc.rtrc_mod_step import RtrcModStep  # noqa: E402
from rtrc.rtrc_record import RtrcRecord  # noqa: E402
from rtrc.rtrc_results import RtrcResults  # noqa: E402
from rtrc.rtrc_start import RtrcStart  # noqa: E402
from rtrc.rtrc_step import STEPS, RtrcStep  # noqa: E402

S = list(STEPS)


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


# ---------- the main agent flow (F4) ----------

def main_flow() -> dict:
    chat_in = ChatInput(_id="ChatInput-brief")
    start = RtrcStart(_id="RtrcStart-start")
    start.set(brief=chat_in.message_response, agent="Qwen direct", model="qwen3.8-flash", replay="")
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
        "RtrcStart-start": ("Agent: Qwen only for now", "Qwen direct, or Claude Code / OpenCode on Qwen in the sandbox. Or replay a saved run without model calls."),
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
    notes = [
        ("note-main", "# RTRC agent flow (Part 2)\n\nA requirement becomes an approvable SysML v2 design. Two cases: **new** (nothing similar in memory, start from scratch) or **reuse** (adapt the similar project found in memory).\n\n- Every RTRC node calls the code behind the results page through the RTRC shell service (`bench/shell_service.py`), so a run here and a run on the page give the same retrieval, prompts, Pilot results and checks.\n- **Qwen only for now** (RTRC has not answered which models may be used).\n- Click a node after a run to read what it did: the retrieved cards, every Pilot attempt and its errors, the alignment pairs, the checks.\n- Replay any saved run without model calls: set *Replay a saved run* in the Agent node to `latest` or a run id.", 40, -20),
        ("note-papers", "## Where the three papers are used\n\n- **Paper 2** (Bader et al., GRAG): ① Search memory and Write to memory. Cards from the official parse, MiniLM + FAISS, seeds + one hop.\n- **Paper 3** (Longshore, Bell, Madachy): ③ create / modify with rules + template + examples; ④ the correction loop, with the Pilot's errors instead of a person; ⑥ read-back is its *query* use.\n- **Paper 1** (Li, Husung, Wang): ⑤ the alias / allocate alignment package, and ⑧ the person's review.\n- **Ours**: the Pilot as judge, the checks, trade-offs recomputed by code, the approval gate, the grades and times.", 540, -20),
        ("note-cameo", "## Cameo (when RTRC provides the license)\n\n⑦ already writes each passing design to `analysis/cameo-exports/<run>/`. Open it in Cameo's SysML v2 edition and record the result with the flow **RTRC Cameo check**. The Pilot stays the judge; Cameo's result is recorded as agreement (interoperability). Cameo has no headless command, so this is a person's step.", 1040, -20),
    ]
    return build("RTRC agent flow: requirement to approved SysML v2 design",
                 "Part 2 of the results page as a Langflow flow: memory search, new or reuse, the official Pilot loop, alignment, checks, a person's decision, memory, grades and times.",
                 graph, titles, notes, [human], ["rtrc", "agent"])


# ---------- F0 memory ----------

def memory_flow() -> dict:
    memory = RtrcMemory(_id="RtrcMemory-library")
    out = ChatOutput(_id="ChatOutput-memory")
    out.set(input_value=memory.as_message)
    graph = Graph(start=memory, end=out)
    titles = {"RtrcMemory-library": ("F0 Memory · Paper 2", "MaritimeISR plus every approved design, as element cards from the official parse, with their links."),
              "ChatOutput-memory": ("Chat Output", "The memory's sources and size.")}
    notes = [("note-memory", "# F0 · What the agent knows\n\nThe memory is the existing MaritimeISR model plus every design a person approved, parsed by the official Pilot into element cards (type, full name, value or connection ends, documentation text) with their links.\n\n- **Cards** output: one row per card. To browse the memory as a Langflow knowledge base, connect **Cards** to a **Knowledge** node in Ingest mode.\n- The agent flow's ① Search memory always uses our own retrieval (MiniLM + FAISS, seeds + one hop), so its results match the results page.", 40, -20)]
    return build("RTRC F0: memory (what the agent knows)", "The library the agent searches: MaritimeISR and approved designs as cards.", graph, titles, notes, None, ["rtrc", "memory"])


# ---------- F1 / F2 exam cells ----------

def exam_flow(agent: bool) -> dict:
    cell = RtrcExamCell(_id="RtrcExamCell-cell")
    cell.set(mode="Replay a graded cell", cell="opencode:1:MOD-05:P-CODE" if agent else "flash:1:GEN-03:P1",
             task_id="MOD-05" if agent else "GEN-03", configuration="P1", agent="opencode", model="qwen3.8-max" if agent else "qwen3.8-flash")
    names = (["Issue task", "Write answer", "Tool calls (agents)", "Official syntax", "Check against key", "Archive"] if agent else
             ["Issue task", "Retrieve notes", "Outline", "Write answer", "Official syntax", "Repair from errors", "Read values", "Check against key", "Approval gate", "Archive"])
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
    titles["RtrcExamCell-cell"] = ("Exam cell: " + ("sandboxed agent on Qwen" if agent else "direct Qwen, P0–P3"),
                                   "Replay any graded cell, or run a sealed task live (not added to any score). The answer key is used only by the scorer.")
    titles["ChatOutput-exam"] = ("Chat Output", "")
    text = ("# F2 · How a coding agent's answer was graded\n\nClaude Code or OpenCode on Qwen, in the bubblewrap sandbox: it sees the task, AGENTS.md and `./validate`, never the answer key. The steps show its tool calls, the official Pilot result and the verdict. Cells: `opencode:<repeat>:<task>:P-CODE`, `claude:<repeat>:<task>:P-CODE-2`, `retry-opencode:<repeat>:<task>`." if agent else
            "# F1 · How an exam cell gets its score (page 1.1)\n\nPick a cell (`flash:1:GEN-03:P1` = direct qwen3.8-flash, task GEN-03, approach P1, repeat 1), or run a sealed task live. Each node shows its step from the archived record: the task statement, the retrieved notes (P3), the outline (P2/P3), the answer, every official Pilot attempt with its errors, the repair loop, the values read, the verdict against the sealed key (missing items only, never the key), and the archive.")
    return build("RTRC F2: exam cell, sandboxed coding agent" if agent else "RTRC F1: exam cell, direct model",
                 "Replay or run one exam cell step by step.", graph, titles, [("note-exam", text, 40, -20)], None, ["rtrc", "exam"])


# ---------- F3 results ----------

def results_flow() -> dict:
    results = RtrcResults(_id="RtrcResults-facts")
    out = ChatOutput(_id="ChatOutput-results")
    out.set(input_value=results.as_message)
    graph = Graph(start=results, end=out)
    titles = {"RtrcResults-facts": ("F3 Results (frozen, revision 2)", "Pass rates by task type and approach for the four candidates, the retry run and the cost."),
              "ChatOutput-results": ("Chat Output", "")}
    notes = [("note-results", "# F3 · The headline numbers\n\nThe frozen results of the 27-task exam: direct qwen3.8-flash and qwen3.8-max (P0–P3, three repeats), OpenCode and Claude Code on qwen3.8-flash in the sandbox, and the extra retry run. The matrix, the cost chart and the model diagrams stay on the results page (`python3 bench/exam_board.py`).", 40, -20)]
    return build("RTRC F3: results", "The frozen exam results as tables.", graph, titles, notes, None, ["rtrc", "results"])


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
    notes = [("note-mod", "# F5 · Changing an existing model (page 2.4)\n\nThe model edits a task's baseline model; the official Pilot judges the syntax; the sealed key gives the task verdict and the budget gives the design verdict; the model reads the edited model back and code checks every number. If the answer moved a stated limit, a person must decide before the change is accepted (AGENTS.md: propose it and stop).", 40, -20)]
    return build("RTRC F5: MOD change chain", "One change to an existing model, judged, read back and gated.", graph, titles, notes, [human], ["rtrc", "mod"])


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
    notes = [("note-cameo", "# Cameo check (when RTRC provides the license)\n\nRTRC works in Cameo. This flow exports a run's officially parsed designs and records whether they open cleanly in Cameo's SysML v2 edition. The official Pilot stays the judge; Cameo's result is recorded as agreement, the interoperability evidence the brief asks for. Cameo has no headless command, so a person opens the file.", 40, -20)]
    return build("RTRC Cameo check (when licensed)", "Export a run's designs for Cameo and record the person's check.", graph, titles, notes, [human], ["rtrc", "cameo"])


FLOWS = {
    "rtrc-agent-flow": main_flow, "rtrc-f0-memory": memory_flow, "rtrc-f1-exam-direct": lambda: exam_flow(False),
    "rtrc-f2-exam-agent": lambda: exam_flow(True), "rtrc-f3-results": results_flow, "rtrc-f5-mod-change": mod_flow,
    "rtrc-cameo-check": cameo_flow,
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
        (OUT / f"{slug}.json").write_text(json.dumps(flow, indent=2, ensure_ascii=False), encoding="utf-8")
        nodes = flow["data"]["nodes"]
        print(f"{slug}.json: {sum(1 for n in nodes if n['type'] == 'genericNode')} nodes, {len(flow['data']['edges'])} edges, "
              f"{sum(1 for n in nodes if n['type'] == 'noteNode')} notes")


if __name__ == "__main__":
    main()
