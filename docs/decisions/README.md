# Decision records

One short file per significant decision: `NNN-slug.md` with date, options considered, decision, reason, and what would reverse it.

Decisions 001–015 (2026-10-02) are recorded in the execution plan v2.0, section 18: `plans/execution-plan-v2.md`. New decisions go here as separate files and are also summarized in that table.

| # | Decision |
|---|---|
| 001 | Project centre moves from "upgrade workbench product" to "agent benchmark" |
| 002 | Keep official toolchain, engine checks, evidence packs; drop Workbench-as-product |
| 003 | Langflow not a system component (optional demo shell only). Correction 2026-10-06: its "no native approval gate" reason no longer holds (Human Input and agent tool approval since Langflow 1.11); the other reasons stand. Plan for the shell: `plans/langflow-shell-plan.md` |
| 004 | Agent layer: LangGraph (fallback plain Python); not Pydantic AI |
| 005 | Off-the-shelf agent baseline: OpenCode primary, Claude Code optional |
| 006 | External benchmarks are calibration/seed only, not the main line |
| 007 | Evaluation framework: Inspect AI (superseded by 017) |
| 008 | Not using AutoGen / CrewAI / Swarm / AutoGPT |
| 009 | Project statement wording corrected: evaluations exist; ours is "first" only for the stated intersection |
| 010 | Repository root moved to `/data/robotics/RTRC`; original folder kept as read-only archive; `vendor/` symlinked |
| 011 | Primary model: existing Qwen cloud API (qwen3.8-flash dev / qwen3.8-max experiments); local Ollama optional |
| 012 | Model visualization: Cameo SysML v2 Community Edition (free) primary, SysON fallback; second checker: Syside CLI (trial/academic) primary, Cameo fallback; official Pilot remains the adjudicator |
| 013 | Conditional configuration P-VENDOR: CATIA Magic 2026x built-in AI Assistant as a black-box agent, if the license permits |
| 014 | No RSI; the LLM validator is an object of evaluation, never an adjudicator |
| 015 | Superseded plans (2026-09-22 ×2, v1.0) archived under `research/archive/plans-2026-09/`; plan v2.0 is the single authority |
| [016](016-plain-python-agents-langgraph-view.md) | P0–P3 run as plain Python; LangGraph is a read-only view of a saved run (settles 004) |
| [017](017-inspect-ai-not-adopted.md) | Inspect AI not adopted; own runner, JSON results, exam page and report as viewers (supersedes 007) |
| [018](018-main-matrix-model-qwen38-flash.md) | The 288-cell matrix and OpenCode use qwen3.8-flash; console model selectable, flash by default |
| [019](019-task-verdict-vs-design-verdict.md) | Task verdict and design verdict are separate; saved answers re-scored without new model calls |
| [020](020-part2-blank-task-prototype.md) | Part 2 prototype: blank brief → requirements → two designs → Pilot → alignment → checks → human approval → memory |
| [021](021-cost-at-list-price.md) | Cost reported in USD at official list price; every new run records usage |
| [022](022-repair-loop-full-errors-cumulative.md) | Repair loop sends the complete error list in one cumulative conversation, cap 20; P1–P3 all repair |
| [023](023-vector-retrieval-paper2.md) | Paper 2's retrieval implemented: MiniLM + FAISS over Pilot-parsed cards, connections included; exam P3 uses a leak-free official-examples library. Amended 2026-10-06: no fallback, pinned stack and MiniLM snapshot |
| [024](024-paper1-alignment-tasks.md) | Paper 1 replicated on its own example (mappings transfer, packages fail the Pilot); alignment becomes scored task type ALN, three sealed tasks, 27 in the bank |
| [025](025-no-model-judges.md) | Model judges dropped; second review of the 27 keys done and recorded; bank frozen (`bench/FREEZE.md`, tag `freeze-2026-10-06`) |
| [026](026-agent-sandbox.md) | Agents run in a bubblewrap sandbox with the same workspace, rules, tools and `./validate`; the first two agent batches of 2026-10-06 are discarded (OpenCode read keys, Claude Code had tools denied); `./validate` passes files in the scorer's order after the Pilot's order dependence was found, and the agents' ALN runs were rerun |
| [027](027-paper2-replication.md) | Paper 2 replicated on its own EV model: the published notebook passes an empty context (one-line fix); precision matches the paper at 0.35, the 0.904 F1 at 0.45 does not; our retrieval matches the fixed pipeline once cards carry documentation (applied in 028) |
| [029](029-retry-failed-tasks-agents-max.md) | The 14 tasks that failed anywhere retried with OpenCode and Claude Code on qwen3.8-max (≤50 `./validate` calls, 60 min, stop on first pass): 41/42 and 40/42; not a score |
| [028](028-freeze-revision-2.md) | Freeze revision 2: retrieval cards carry documentation text; MOD-01 checks the radio it says to keep; AMB-02 accepts more ways to ask for the limit; an AMB number counts as invented only with SysML; saved answers re-scored (6 cells change), every direct P3 cell rerun |
| [030](030-langflow-shell.md) | The agent flows in Langflow 1.12.5 over the existing pipeline: seven flows, new or reuse of a similar project, the person's decision as a Human Input node, Cameo export and check, the memory as a Langflow knowledge base (Qwen embeddings); a live run through Langflow shows on page 2.3, parity with the page checked |
| [031](031-design-assistant.md) | A conversational design assistant: Langflow's Agent harness (qwen3.8-max) over an MCP server exposing our memory search, the verified design pipeline, the official Pilot and the memory gate; a four-turn test (ask, change request, run, send back); the local 3-bit Qwen3.8-27B as a model option. Harness replaced by 032 |
| [032](032-opencode-harness-local-model.md) | OpenCode is the harness outside and inside: the assistant is one Langflow node (and a terminal script) running OpenCode on the local Qwen3.8-27B over the same MCP tools; `run_design` writes the designs with the sandboxed OpenCode; a 64k-context Ollama tag puts the whole model on the GPU (113 tokens/s instead of 8); the 27B written directly had repeated the same broken `part usage` text for 20 repairs; the Langflow-Agent flow of 031 kept for comparison |
| [033](033-unfolded-assistant.md) | The assistant unfolded on the canvas, added next to the others: Langflow's Agent with one card per RTRC tool, the design pipeline as a 14-card flow run as a tool (edit it and the assistant runs the edit), write to memory as an approval card; a Max and a local-27B version; one run through the tool passed both designs and all checks; the approval card paused and a Reject wrote nothing |
