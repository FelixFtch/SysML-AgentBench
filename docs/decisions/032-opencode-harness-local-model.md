# 032 · OpenCode is the harness, outside and inside, on the local Qwen3.8-27B; Langflow's Agent flow stays as a comparison

Date: 2026-10-06. Status: done (user decisions of 2026-10-06, after the findings below: the designs are written by OpenCode, not by the model directly; the conversation layer is OpenCode too, with the RTRC tools, in Langflow as one node and in the terminal; everything on the local model; the Agent-component flow of 031 kept next to it for comparison, with `direct` inside). The tools and the rules of 031 stay. Affects `agents/external/opencode_run.py`, `agents/llm_local.py`, `bench/shell_service.py`, `tools/assistant_mcp.py` (`run_design` gets `agent`, default `opencode`), `tools/assistant/` (new: the prompt and the workspace), `scripts/assistant.sh` (new), `langflow/components/rtrc/rtrc_opencode.py` (new node) and `rtrc_start.py`, `langflow/flows/build_flows.py` (flows `rtrc-assistant`, `rtrc-agent-flow-local`), `langflow/flows/build_assistant.py` and `setup_assistant.py` (the comparison flow `rtrc-assistant-langchain`), `langflow/flows/import_flows.py`, `langflow/flows/move_to_user.py`, `scripts/langflow.sh`, `scripts/qwen38.sh` and `tools/ollama/qwen3.8-27b-q3-64k.Modelfile` (new). The frozen files are untouched (`bench/freeze.py --check`: unchanged).

## What was found

1. **Direct writing on the 27B gets stuck.** Run 20261007T014335 (Agent-harness assistant on the local model, pipeline `direct`): design A, adapted from MaritimeISR, passed the Pilot at the first parse; design B, written new, opened with `part usage vessel` (the instruction says "one top-level part usage for the vessel", which the 27B wrote literally; `part usage` is not a keyword pair in this toolchain) and the Pilot answered `no viable alternative at input 'vessel'`. The repair loop sends the full error list back in one cumulative conversation (decision 022); the model returned byte-identical text for 20 repairs. The loop only stops on PASS or the cap, so 20 minutes of GPU time went to the same 19 errors.
2. **The Agent harness had no way back into the checks.** The Langflow Agent could validate text with the Pilot (`validate_sysml_text`) and search the memory, but nothing could hand an edited design to the four budget checks and the record; the only path was `run_design`, whose inner loop is the direct one above. Two Agent sessions also retried `run_design` on their own after a failure, so three design runs were sharing the GPU at once.
3. **The 27B was running a third on the CPU.** The published Ollama tag sets `num_ctx 224840`; Ollama reserved the cache for 224k tokens, placed 11.3 of 16.2 GiB of weights on the GPU and the rest on the CPU: 8.1 tokens/s over the first three calls of that run.

## What was decided and built

- **The conversation layer stays; its harness is OpenCode.** Same shape as 031, Chat Input → harness → Chat Output, but the middle node (`RtrcOpenCodeAssistant`) runs the exam's pinned OpenCode on the local model with the RTRC MCP server (`tools/assistant_mcp.py`, 127.0.0.1:8782) as its only tools; OpenCode's own file and shell tools are switched off in the workspace configuration (`tools/assistant/workspace.py`, written to `~/.rtrc-assistant`, outside the repository). The prompt of 031 moved to `tools/assistant/rtrc-assistant.md` with one addition: the pipeline's default agent and the results-page rule. Each Langflow chat session maps to one OpenCode session, so the conversation continues across messages. The same workspace opens in the terminal with `scripts/assistant.sh`. Gone with the Agent component: the provider and credential set-up in Langflow, the MCP registration in Langflow, the knowledge-base node (`search_memory` reads the same cards) and their per-user migration. Session titles use the same local model (`small_model`), so no request leaves the machine.
- **`run_design` writes the designs with OpenCode.** The tool gained `agent` (`opencode` by default, `direct` on request); inside, the shell service runs the sandboxed OpenCode of decision 026 with `./validate` in hand, so the Pilot's errors come back as a tool result and the file gets edited, instead of the same text being resubmitted.
- **A derived Ollama tag, `qwen3.8-27b-q3:64k`** (`tools/ollama/qwen3.8-27b-q3-64k.Modelfile`: the same weights, `num_ctx 65536`), built by `scripts/qwen38.sh`, which also starts Ollama (`--serve`, called by `scripts/langflow.sh`) and reports placement (`--status`). Loaded: 13.4 GiB, 100 % on the GPU; 113 tokens/s on a 400-token answer (14× the published tag).
- **OpenCode on the local model.** `agents/external/opencode_run.py` writes an `opencode.json` whose provider is the same `@ai-sdk/openai-compatible` package pointed at `http://127.0.0.1:11434/v1` (no key) with `reasoningEffort: "none"`, which Ollama reads as thinking off; the sandbox of decision 026 shares the network, so nothing else changes. The shell service accepts the local model with `direct` and `opencode`; Claude Code still uses the cloud Qwen (its route is the Anthropic-compatible one, untested against Ollama).
- **A second main flow, `RTRC agent flow · local Qwen3.8-27B via OpenCode`,** for measuring: the same graph as the agent flow with the Start node preset to OpenCode and `qwen3.8-27b (Ollama)`; every model call of a run stays on this machine (requirements, alignment and read-back through `agents/llm_local.py`; the designs through OpenCode with `./validate` in hand). The fixed flows are for measuring and replay; the assistant is for use. The results page must be stopped before either runs a sandboxed agent.

## Evidence

- OpenCode smoke test in the sandbox on the local model (workspace `mvp/agent-runs/20261007T021708-ff99-P-CODE-rtrc-smoke`): 21 steps, tools `bash` ×17, `write` ×2, `read` ×1, no reasoning events, `./validate` PASS written to `answer.md`, 164 s.
- Full flow run: see the "Run" section below, filled in from the record on page 2.3.

## Run

The same brief as the stuck run, through the new flow in the Langflow server (Workflow API, background mode; run 20261007T022418, on page 2.3), agent `opencode`, model `qwen3.8-27b (Ollama)`, every model call on this machine:

| Step | Seconds | Result |
|---|---|---|
| ① retrieve | 0.2 | reuse path: MaritimeISR is the similar project |
| ② requirements | 6.6 | 9 requirements, no unsourced number (the published tag had taken 75 s and 114 s for this step) |
| ③ designs, OpenCode | 173.4 | A (adapt MaritimeISR): 21 tool calls (bash 15, read 3, write 3), 58 s; B (new arrangement): 35 tool calls (bash 23, read 5, write 5, glob 2), 115 s. B routes both cameras through a recorder part, then the edge computer, then a shore link; `part vessel`, not `part usage vessel` |
| ④ official Pilot | 7.8 | A PASS at parse 1, B PASS at parse 1, no diagnostics |
| ⑤ align | 9.0 | 5/5 pairs verified; alignment package PASS |
| ⑥ checks | 2.8 | A and B: POWER 49 ≤ 60 W PASS, LINK 12 ≤ 20 Mbps PASS, STORE 43.2 ≤ 128 GB PASS, TRACE 9/9 PASS |
| ⑧ person | — | the job reported `suspended` with the review text; resumed with *Send back* to finish the test, so nothing was written to memory |

Local model usage for the direct steps: 4 calls, 2615 prompt and 1168 completion tokens. The 60 W limit and every other number are the brief's. One run is one run: it says OpenCode on the 27B can get through this brief, not what its pass rate is.

## Assistant conversation

Through the Langflow node, headless (`lfx run --session-id test-oc-1`, the node's own code), on the local model, every turn with the same OpenCode session:

1. "What projects are in the memory, and which approved design has the highest upload rate?" → `rtrc_list_projects`; a table of the three projects with card counts, the 18 Mbps design named, the two briefs summarised; 7 s.
2. A change request on the 18 Mbps design (infrared camera to 7 W, upload back to 12 Mbps, nothing else) with "show me the brief first" → it noted that the camera already draws 7 W in that design, wrote the brief with every number's source, flagged the one open point (keep the recording rate at 18 Mbps, or lower it too?), and stated the run it would make (`opencode`, `qwen3.8-27b (Ollama)`, `start_from similar`) without running; 9 s.
3. "Keep 18 Mbps; confirmed, run." → `run_design(agent opencode, model qwen3.8-27b (Ollama), start_from similar)`; the call died after about a minute: OpenCode bounds an MCP tool call by the server's `timeout` (the documentation describes it as the tool-listing timeout; the binary passes it to `callTool`), and the default is far below a design run. The assistant reported the failure, checked `list_projects` for a saved result, found none, and asked whether to rerun or use agent `direct`; nothing was invented. The orphaned pipeline run (20261007T025954) was stopped with the shell service. Fix: `mcp.rtrc.timeout` and `experimental.mcp_timeout` set to 30 minutes in the workspace configuration.
4. "8770 is stopped, Ollama is running. Run again." → run 20261007T030531, every model call local: requirements 5.0 s; designs by OpenCode 483 s (A 63 s; B 6 min, written new); Pilot: A and B PASS at parse 1; alignment 5/5, package PASS; checks on both: POWER 49 ≤ 60 W, LINK 12 ≤ 20 Mbps, STORE 64.8 ≤ 256 GB, TRACE 9/9, all PASS; no trade-off needed. The assistant reported the table with the run id, re-did the arithmetic, gave the diagram links, pointed at the review's `read-back: missing 60` line and said it could not interpret it on the pipeline's behalf, and asked for the decision (approve A or B, send back, reject). One slip: it quoted the Cameo export path as `analysis/cameo/…`; the files are under `analysis/cameo-exports/20261007T030531/`.

In the terminal, the same first question through `opencode run` took 11 s with the same tool call and the same numbers.

## The Langflow-Agent flow, kept for comparison

On the user's request the assistant of 031 is back as **RTRC design assistant (Langflow Agent, qwen3.8-max)** (`langflow/flows/build_assistant.py`, `rtrc-assistant-langchain.json`, `setup_assistant.py`): Langflow's own Agent component outside, `run_design` with agent `direct` inside, exactly as in 031, over the same MCP server and rules, so the two harnesses can be compared on the same brief. Its Langflow-side needs (the Qwen credential, the MCP registration, the knowledge base, all per user) are set up by `setup_assistant.py` and moved to the account people use by `move_to_user.py`. It was rebuilt and imported on 2026-10-06; its MCP node built, its knowledge-base node could not be exercised under the superuser (the knowledge base belongs to the user account), so the first conversation under that account is the check.

## What would reverse it

The comparison flow winning on several briefs (fewer parses, fewer failed checks, shorter conversations), or OpenCode on the 27B proving no better than direct writing over several briefs; both would show on page 2.3 as parse counts and verdicts.
