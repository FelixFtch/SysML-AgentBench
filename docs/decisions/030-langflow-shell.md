# 030 · The agent flows in Langflow, over the existing pipeline

Date: 2026-10-06. Status: done (user decisions of 2026-10-06: build the plan; memory stays in the flow and is browsable as a Langflow knowledge base, embedded by Qwen; Qwen only for now; Cameo where it is needed). Affects `langflow/` (new), `bench/shell_service.py` (new), `bench/langflow_parity.py` (new), `scripts/langflow.sh` (new), `scripts/langflow_secrets.py` (new), `requirements-langflow.txt` (new), `bench/discover.py` (variant texts shared; trade-off reply limit 1200 → 2500 tokens), `bench/exam_board.html` (link from 2.1), `.gitignore`. Plan: `plans/langflow-shell-plan.md` §12–§15. Guide: `langflow/README.md`.

## Question

Can everything we show RTRC, above all the Part 2 agent flow (requirement → memory search → new design or adapt a similar project → official Pilot loop → checks → a person's decision → memory, with grades and times), run and be shown in Langflow, without a second implementation that could drift from the results page?

## What was built

- **A shell, not a port.** Langflow nodes are thin clients of a local JSON API (`bench/shell_service.py`, 127.0.0.1:8781, token from `.langflow/secrets.env`). Each endpoint calls the code the page uses: `bench/discover.py` for retrieval, requirements, designs, validation, alignment, checks, trade-offs and approval; `bench/exam_board.py` for exam cells (without the key text); `bench/model_diagram.py` for diagrams; `agents/external` for the sandboxed agents.
- **Seven flows** (`langflow/flows/build_flows.py`, built in Python like Langflow's starter projects): the agent flow, F0 memory, F1/F2 exam cells (replay or live), F3 results, F5 MOD change chain, and the Cameo check. Official components carry the control flow: If-Else for new vs reuse and for "all four checks pass", Human Input for the person's decision. Canvas notes name the paper each step applies.
- **New in the agent flow:** the reuse branch. When ① finds a similar project (an approved design, else MaritimeISR), design A adapts its model (paper 3's modify) and design B is written new; with nothing similar, both are new as on the page.
- **Cameo:** ⑦ exports each design that passes the Pilot; the Cameo check flow records a person's result on the run's record. The Pilot stays the judge.
- **Memory as Langflow's own knowledge base** (the user's option A): F0 ingests the 152 memory cards into the knowledge base "rtrc memory", embedded by Qwen (`qwen3.7-text-embedding`, through Langflow's "OpenAI Compatible" provider; `langflow/flows/setup_knowledge.py`). RTRC can search and filter the cards on Langflow's Knowledge page; rerunning F0 adds only new cards. The agent flow's ① Search memory still uses our retrieval, so its results match the results page.

## Evidence

- Every flow runs in the server, and every flow except F0 (whose Knowledge node needs the server's provider settings) also headless with `lfx run`. F0 filled the knowledge base with 152 cards; a second run left it at 152. The Human Input pause and resume were tested from the terminal, through the v2 Workflow API (background run → `suspended` → resume), and by clicking the decision card in the editor.
- A live run through the Langflow server, default brief, direct qwen3.8-flash (run 20261006T215846): reuse path (similar project MaritimeISR); design A passed the Pilot on the first parse, POWER FAIL 78/60 W and LINK FAIL as the brief forces, STORE and TRACE PASS; design B failed all 21 parses; alignment 5/5 pairs; decision "Send back"; 311 s, 26 model calls, about $0.015. The record is on page 2.3.
- `bench/langflow_parity.py` on run 20261006T211951: retrieval through the shell identical to `retrieve_existing`; the design prompt identical to the page's, the agent prompt the page's plus the sandbox instruction; both saved designs parse again with the same verdict and diagnostics.

## Rules kept

Login on, local only, CORS limited to the local origin; `LANGFLOW_ALLOW_CUSTOM_COMPONENTS=False`, so only built-in components and `langflow/components` run (the plan's category blocklist does not exist in 1.12.5; this setting covers it and also disables the built-in code-execution components); the only key in Langflow is the Qwen key for the knowledge base's embeddings, stored as an encrypted credential (user decision; the agent flow's model calls go through the shell service); no answer key served; sandboxed agents refused while the results page runs; approval into memory only through the same gate as the page.

## Found on the way

- Human Input in Langflow 1.12.5 skips the unchosen branches but cannot be joined again: a node fed by two branches gets the review text on both, and a node after two branch nodes fails. Each choice therefore has its own record node.
- Part 2's repair loop has no stop on identical resubmissions: in both live runs design B used all 20 repairs, and 16 of its 21 attempts repeated the previous text. The exam's loop stops after three identical answers. Kept as is so the flow matches the page; changing it is a separate decision.

## What would reverse it

RTRC asking for Langflow's own agent and retrieval components instead of ours (the page's results could then no longer be reproduced in Langflow), or a Langflow release that makes the shell service unnecessary, for example durable Human Input joins plus an allow-listed component that can call the pipeline in-process.
