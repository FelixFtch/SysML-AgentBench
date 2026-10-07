# 031 · A conversational design assistant on Langflow's Agent harness, over the verified pipeline

Date: 2026-10-06. Status: the assistant for use is now the one of [032](032-opencode-harness-local-model.md) (OpenCode on the local Qwen3.8-27B as the harness, OpenCode writing the designs); this flow stays as **RTRC design assistant (Langflow Agent, qwen3.8-max)** for comparison, with `run_design` on `direct` as described here. Built under the user decisions of 2026-10-06: build it now; Langflow's Agent as the harness, OpenCode later if needed; qwen3.8-max for the conversation. Affects `tools/assistant_mcp.py` (new), `langflow/flows/build_assistant.py` and `rtrc-assistant.json` (new), `langflow/flows/setup_assistant.py` (new), `langflow/flows/move_to_user.py` (new), `scripts/langflow.sh`, `agents/llm_local.py` (new) and `bench/shell_service.py` (the local 3-bit Qwen3.8-27B as a model option; the frozen `agents/llm.py` is untouched), `langflow/README.md`.

## Question

The fixed flows (decision 030) take a complete brief and run a fixed sequence: good for measuring, not how an engineer works. RTRC's statement asks for decision support in early-stage work, where the need is incomplete and a person confirms requirements before anything is built. Can the engineer ask, discuss and confirm in natural language, and still get a design whose verdicts come from the official Pilot and the budget checks?

## What was built

- **Harness:** Langflow's Agent component (LangChain `create_agent` on LangGraph: the model chooses tools in a loop, with chat history and `max_iterations`). Model `qwen3.8-max` through the "OpenAI Compatible" provider. OpenCode and Claude Code stay available as sandboxed tools of the fixed flows; they were equal in the exam (78/81 each on flash; 41/42 and 40/42 on max), OpenCode faster and cheaper.
- **Tools:** an MCP server (`tools/assistant_mcp.py`, streamable HTTP on 127.0.0.1:8782) exposing our code: `list_projects`, `search_memory` (the page's retrieval), `read_project`, `run_design` (the verified Part 2 pipeline through the shell service; its record appears on page 2.3), `design_status`, `validate_sysml_text` (official Pilot), `write_to_memory` (the page's gate), `record_decision`, `export_cameo`; plus the Langflow knowledge base `rtrc memory` in Retrieve mode.
- **Rules in the system prompt:** never invent a number; never move a stated limit; show the brief and wait for confirmation before `run_design`; verdicts come from tools; memory writes need an explicit approval of a design that passed all four checks; answer in the engineer's language.
- **Local model option:** the 3-bit Qwen3.8-27B (Unsloth `UD-Q3_K_XL`, Ollama `smtek/Qwen3.8-27B:Q3_K_XL`, about 14 GB on the RTX 4090) is selectable as `qwen3.8-27b (Ollama)` in the fixed flows and in `run_design`; direct calls only, not in the sandbox. The routing lives in `agents/llm_local.py`, installed by the shell service at start-up, so the frozen `agents/llm.py` keeps its hash (`bench/freeze.py --check` unchanged). Thinking is switched off with `reasoning_effort: none`, the parameter Ollama's OpenAI-compatible endpoint honours. Its requirements step took 34 s on a new brief.

## Evidence

A four-turn conversation on 2026-10-06 (session `test-assistant-1`): (1) "what is in the memory" → `list_projects`, correct projects and numbers, 12 s; (2) a change request on an approved design → it searched the memory, computed the budgets by hand, found the upload rate (18 Mbps) would exceed the new 8 Mbps uplink, offered three options without touching the limits, and showed the brief, 42 s; (3) "option 1, run" (written in Chinese) → `run_design`, run 20261007T002947: reuse path, designs A and B PASS on the first parse, all four checks PASS, alignment 6/6, and it pointed out an uncovered issue (64.8 GB at 8 Mbps takes 18 hours), 70 s; (4) "Send back" with a reason → `record_decision`, nothing written to memory.

Then every tool through the Agent (sessions `test-assistant-4` and `-5`, admin copy without the knowledge-base node): a brainstorm with no numbers (it called `list_projects`, `search_memory` and the calculator, found the 18 W headroom and the 20 Mbps uplink bottleneck, offered four sensor directions and five trade-offs, ran nothing); `read_project` on MaritimeISR's radio chain, which also surfaced a conflict between MaritimeISR (8 Mbps, 128 GB) and the approved designs (20 Mbps, 256 GB); `validate_sysml_text` on a snippet missing a semicolon (FAIL, then PASS after it added the semicolon); `design_status` and `export_cameo`; a request to approve the failing design A of run 20261006T215846, which it declined by rule, and which the service gate also refused when the tool was called directly; a from-scratch run (`start_from="new"`, run 20261007T005632, both designs PASS, all checks PASS, 52 s). A refused approval no longer records an "Approve" decision (fixed during these tests). Every answer stores the tools it called with inputs, outputs and durations (Langflow's `message.content_blocks`), visible in the Playground.

## Found on the way

- Langflow keeps provider credentials, knowledge bases and MCP servers per user. The flows, the Qwen credential, the knowledge base (row, runs and files under `~/.langflow/knowledge_bases/<username>/`) and the MCP registration were moved to the account people log in with (`move_to_user.py`).
- With `LANGFLOW_ALLOW_CUSTOM_COMPONENTS=False`, stdio MCP servers are restricted to administrators; the server therefore runs over HTTP on localhost.
- The checks do not cover transfer time; the assistant noticed it from the numbers. Whether to add such a check to the pipeline is a separate decision.

## What would reverse it

RTRC preferring a coding agent (OpenCode) as the conversational layer, or the Agent harness proving unreliable in longer sessions (tool misuse, invented numbers slipping past the pipeline's unsourced-number check). Both would be visible in the saved runs and the chat transcripts.
