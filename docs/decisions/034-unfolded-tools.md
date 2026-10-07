# 034 · The assistant's tools unfolded into flows: memory search, write to memory (knowledge base refreshed), validate, the pipeline's prompt cards

Date: 2026-10-07. Status: done (user decision of 2026-10-07: unfold the four tools whose logic has steps, keep the single-step tools as cards, make the knowledge base update itself; add, do not change). Adds three flows and cards to one; nothing existing was removed. Affects `bench/shell_service.py` (nine stateless `/tool/...` endpoints over the existing functions), `langflow/components/rtrc/rtrc_tool.py` (new card), `rtrc_memory.py` (an optional "after" input), `rtrc_start.py` (`require_brief`), `langflow/flows/build_flows.py`, `import_flows.py`, `langflow/README.md`.

## Why

On the unfolded canvas of 033 the tools were still one card each: the engineer could see that the assistant searches the memory, not how. RTRC asked for the reasoning as steps. Langflow's way is a flow per tool, run through Run Flow; the Agent calls the flow, the flow's cards run in order.

## What was built

| Flow (a tool of the unfolded assistants) | Cards | Paper |
|---|---|---|
| **RTRC memory search** | search words → memory library (MaritimeISR + approved designs as Pilot-parsed cards) → MiniLM + FAISS seeds (cosine ≥ 0.30, exact-name bonus; `bench/vector_index.py`, frozen, called not changed) → one hop of neighbours → cards | 2 |
| **RTRC write to memory** | `<run id> A/B` → gate, read only (Pilot PASS and four checks PASS; refuses a design already in memory) → write through the page's gate → record on the run → the library re-read → **knowledge base `rtrc_memory` refreshed** (Qwen embeds the new cards only). The unfolded assistant pauses for the person's approval before this flow runs (the Actions row of its Run Flow card) | 2 |
| **RTRC validate SysML** | pasted text → saved as `<package>.sysml` → official SysML v2 Pilot → PASS or FAIL with diagnostics | 3 |
| **RTRC design pipeline** (033) | three read-only cards added after ③: the rules, the attribute template and the similar project or retrieved examples OpenCode was given | 3, 2 |

Each card is `RtrcTool`, stateless, calling a `/tool/...` endpoint of the shell service that runs the same function the results page runs; the write and record cards repeat the cards before them, so the flow's last message carries the whole story (gate, write, record) back to the agent. The single-step tools (list projects, read a project, status of a run, record a decision, export for Cameo) stay MCP cards: each is one file read or one line written.

The knowledge base no longer needs F0 by hand after an approval: the write flow ends with the same ingest F0 does (duplicates skipped; about 45 cards per design, a few seconds). The MiniLM + FAISS index and the list/read/search tools already re-read the memory on every call.

Found while building: a flow becomes a tool only when its Chat Input lists its fields in `field_order`; the generated argument name is `<ChatInput id>~input_value`, which a 27B simplifies unless the prompt spells it out; the Start node of the pipeline now refuses an empty brief as a tool (`require_brief`) instead of running the page's default brief; approval on a Run Flow card works through the same `approval_actions` metadata as on an MCP card; runs from before the Langflow shell have no session, so the write card calls the page's `approve()` directly for them.

## Evidence (2026-10-07, unfolded (local 27B), superuser copy before the move)

- "Search the memory for cards about uplink and upload rates" → `RTRC-memory-search_tool` → the hop card's text: 2 neighbours, 6 cards, the R9 requirement cards and `Uplink` parts of both approved designs with sources; 20 s.
- "Validate this SysML with the official Pilot: package Probe {…}" → `RTRC-validate-SysML_tool` → `official Pilot PASS · package Probe`; 10 s.
- "Write design A of 20261003T150116 into the memory" (a design already in memory, so every card runs and nothing changes) → the job paused with the approval card for `RTRC-write-to-memory_tool`; Approve → gate: already in memory, Pilot PASS, four checks PASS; write: "not approved: This design is already in memory."; record: nothing written; the library re-read and the knowledge base ingest ran with no new rows; `approved.jsonl` still two lines; 15 s. Before the echo was added, the agent had summarised the last card alone as "written"; with the whole story returned it cannot.
- The outer-harness comparison and the Run Flow argument-name defect it exposed: `analysis/assistant-harness-comparison-20261007.md`.

## What would reverse it

The unfolded flows drifting from the page's code (the parity check `bench/langflow_parity.py` would show it, since the cards call the same functions), or the Run Flow tool calls proving unreliable on the 27B (misnamed arguments now fail loudly and would show in the chat).
