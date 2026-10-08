# 035 · Six Langflow projects: each candidate's exam version next to its chat version; the agent flows sit the exam; three new columns on page 1.3

Date: 2026-10-07. Status: done (user decisions of 2026-10-07: one project per candidate with an exam version and a chat version side by side, full names and no codes; the shared tool flows and the rest in projects of their own; a Pilot-only Langflow Agent next to the sandboxed coding agents; exam results read on results page 1.3 as pass / fail / not run yet; time and tokens recorded). Affects `langflow/flows/catalog.py` (new), `build_flows.py`, `import_flows.py`, `move_to_user.py`, `setup_assistant.py`, `build_assistant.py`, `langflow/components/rtrc/rtrc_exam_chat.py` (new), `rtrc_opencode.py`, `rtrc_exam_cell.py`, `tools/assistant/workspace.py`, `tools/assistant/rtrc-assistant-exam.md` (new), `bench/shell_service.py` (`/exam/chat`), `bench/langflow_exam.py` (new), `bench/batches.py`, `bench/exam_board.py`, `bench/board_facts.py`, `bench/board.js`, `bench/board.css`, `bench/exam_board.html`, `scripts/langflow.sh`, `langflow/README.md`. Frozen files untouched (`bench/freeze.py --check`: unchanged).

## Why

The frozen exam scores four candidates (direct flash and max with P0–P3; OpenCode and Claude Code in the sandbox). The assistants of decisions 031 to 034 had never sat it: they answered design briefs, with tools the exam candidates do not have. A comparison of harnesses needs the same 27 tasks, the same model and an answer format the frozen scorer can read; and the user wanted the Langflow side arranged by candidate, each with a version that sits the exam and a version that talks, instead of one project of sixteen flows with codes (F0 … F5).

## What was built

**Six projects** (`langflow/flows/catalog.py`; the flow file name is the slug, the name is what Langflow shows):

| Project | Exam version | Chat version |
|---|---|---|
| 1 · Direct model, approaches P0 to P3 | `Direct model exam · P0 one-shot` … `· P3 retrieval then outline`: the exam cell with the approach preset | `Direct model chat · P0 … P3`: the same fixed path (P3 retrieval, P2/P3 outline, the answer, the Pilot with the repair loop for P1–P3) on a typed task; no key, nothing scored |
| 2 · Coding agents without memory | `OpenCode in the sandbox exam`, `Claude Code in the sandbox exam`; `Langflow Agent, Pilot only exam` | `OpenCode in the sandbox chat`, `Claude Code in the sandbox chat`, `Langflow Agent, Pilot only chat` |
| 3 · OpenCode with memory | `OpenCode with memory exam` | `OpenCode with memory chat` (the design assistant of 032) |
| 4 · Langflow Agent with memory | `Langflow Agent with memory exam` | the two unfolded assistants of 033 and the one-MCP-card flow of 031 |
| 5 · Shared tool flows | `Memory search`, `Validate SysML with the official Pilot`, `Write to memory`, `Design pipeline` | |
| 6 · Other | the design agent flow with a person's decision (cloud and local), the knowledge-base fill, the results tables, the MOD change chain, the Cameo check | |

**The exam versions.** Every one uses qwen3.8-flash, the model of the frozen exam, so a column compares a harness, not a model.
- Projects 1 and 2 (cell flows): the existing exam cell node with the candidate preset; a task id in, the shell service scores it as the page console does.
- Projects 2 (Pilot only), 3 and 4 (chat-style exam flows): the task statement, as the direct candidates get it (`agents.solve._task`), goes in through Chat Input; the reply is scored outside Langflow by `bench.experiment.validate_and_grade` (the official Pilot once, then the frozen key). The prompt is `tools/assistant/rtrc-assistant-exam.md` with the frozen rules of `agents/solve.py` appended: answer in the task's form and nothing else; ask only when the task says a number is missing; never invent a limit; the Pilot tool on every model written. Tools: the official Pilot (`Validate SysML with the official Pilot` as a Run Flow card; `validate_sysml_text` over MCP for OpenCode), plus memory search for projects 3 and 4. No design pipeline, no write to memory, no knowledge-base card. OpenCode runs in a second workspace (`~/.rtrc-assistant-exam`, `workspace.py --mode exam`) with the other seven MCP tools switched off and a fresh session per task.
- `bench/langflow_exam.py --flow "<name>"` loops the 27 tasks three times through a flow (a fresh session per cell), scores, and records wall time, tool calls and tokens: the Langflow Agent's usage field on its stored message; the OpenCode node's per-session usage file; the direct and sandboxed runs' usage from the shell's console record (OpenCode's from its event log, as the frozen batches read it). Output: `analysis/langflow-exam-<column>-qwen3.8-flash-<stamp>/` for the three columns, `analysis/langflow-rerun-*` for a rerun of a frozen column (shown nowhere).

**Results page 1.3** gains three column groups after Claude Code: `Langflow Agent, Pilot only`, `OpenCode with memory`, `Langflow Agent with memory`, three repeats each, grey "not run yet" until a batch exists (`bench/batches.py` `LANGFLOW_COHORTS`, read by `exam_board.py` and `board_facts.py` under `langflow_cohorts`, apart from the four frozen cohorts; STATUS.md and the report do not read them). A cell's tooltip carries its time, tool calls and tokens; the header's tooltip the column's pass count, tokens, USD and total time.

**The chat versions of projects 1 and 2** were one new node, `RTRC Exam chat`, over a new shell endpoint `/exam/chat`: the direct approaches on a typed task (package from a `Package name:` line, task type chosen on the node; for an alignment task the fenced sysml blocks of the text become the companion files), or a sandboxed agent on a fresh task folder made from the text. Nothing is scored; each run is saved under `analysis/langflow-console/`. **Superseded on 2026-10-08 by decision 036**: this fed a person's words into the exam solver, so every message came back as an exam answer; the chat versions now take the person's words as written and keep the conversation (`RTRC Chat`, `/chat/turn`, `bench/chat_turns.py`). The exam versions are as described here.

## Found while building

- **Langflow drops any component parameter whose name contains `config` or `kwargs`** when its value is not JSON (`lfx.interface.initialize.loading.convert_kwargs`): the exam cell's `configuration` dropdown had been ignored in every live run, so F1 "live" always ran P1 whatever was chosen. Renamed `approach` (the shell still receives `configuration`). The frozen batches did not go through this node.
- Langflow registers component code at start and refuses code it does not know (`LANGFLOW_ALLOW_CUSTOM_COMPONENTS=False`): a new or edited RTRC component needs a Langflow restart before an import of flows that carry it.
- `GET /api/v2/workflows?job_id=` answers 500 while a background run is in flight; the runner polls Langflow's job table and reads the route once the job has ended.
- A Run Flow tool stores its sub-flow's Chat Output under the caller's session; the caller's own message (and the Agent's usage field) is found by flow id.
- The superuser cannot run flows owned by the account people use; the runner imports a private copy of the flow file into `RTRC exam runner (admin)` when needed. The same JSON, so the same flow.

## Evidence (2026-10-07, smoke runs on one or two tasks each, saved outside the repository)

- `Direct model chat · P1 repair from errors` on the GEN-03 statement: the FusionNode package back in 8 s (official Pilot PASS inside the shell).
- `Langflow Agent, Pilot only exam`: GEN-03 PASS in 36 s (1 Pilot call, 2971 in / 1904 out tokens); QRY-02 PASS in 4 s.
- `Langflow Agent with memory exam`: GEN-03 PASS in 32 s (1 tool call); QRY-02 PASS in 8 s after one `Memory-search_tool` call, the qualified name written in full.
- `OpenCode with memory exam`: GEN-03 PASS in 28 s (`rtrc_validate_sysml_text` once; 6010 in / 1192 out tokens, 5632 cached); QRY-02 PASS in 8 s.
- `Direct model exam · P0 one-shot` through the runner on GEN-03: the console record now says P0 (before the rename it said P1); 245 in / 104 out tokens, 8 s.
- `OpenCode in the sandbox exam` through the runner on QRY-02: FAIL ("does not match the answer key"), 104 s, 16 tool calls; the mechanism works, the answer did not.
- `OpenCode in the sandbox chat` and `Langflow Agent, Pilot only chat` on a small typed task: both returned a parsed package with the Pilot's PASS.

No full column has been run yet: the three Langflow columns of page 1.3 show "not run yet" until `bench/langflow_exam.py` is run for each (27 × 3 cells; the OpenCode column needs the results page stopped).

## What would reverse it

A full column disagreeing with its smoke runs (for example the memory assistants reaching for the design pipeline despite the exam prompt), or the per-cell time and token record proving unreliable (the Agent's usage field missing on some providers), would send the exam versions back to a scripted candidate outside Langflow.
