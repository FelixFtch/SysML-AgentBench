# 032 · The Agent-harness assistant is retired; the local Qwen3.8-27B runs through OpenCode in the fixed flow

Date: 2026-10-06. Status: done (user decision of 2026-10-06, after the findings below: drop the Langflow Agent layer, go back to the fixed RTRC nodes, write the designs with OpenCode on the local model). Supersedes decision 031. Affects `agents/external/opencode_run.py`, `agents/llm_local.py`, `bench/shell_service.py`, `langflow/components/rtrc/rtrc_start.py`, `langflow/flows/build_flows.py` (new flow `rtrc-agent-flow-local`), `langflow/flows/import_flows.py`, `langflow/flows/move_to_user.py`, `scripts/langflow.sh`, `scripts/qwen38.sh` and `tools/ollama/qwen3.8-27b-q3-64k.Modelfile` (new); removed: `tools/assistant_mcp.py`, `langflow/flows/build_assistant.py`, `rtrc-assistant*.json`, `setup_assistant.py`. The frozen files are untouched (`bench/freeze.py --check`: unchanged).

## What was found

1. **Direct writing on the 27B gets stuck.** Run 20261007T014335 (Agent-harness assistant on the local model, pipeline `direct`): design A, adapted from MaritimeISR, passed the Pilot at the first parse; design B, written new, opened with `part usage vessel` (the instruction says "one top-level part usage for the vessel", which the 27B wrote literally; `part usage` is not a keyword pair in this toolchain) and the Pilot answered `no viable alternative at input 'vessel'`. The repair loop sends the full error list back in one cumulative conversation (decision 022); the model returned byte-identical text for 20 repairs. The loop only stops on PASS or the cap, so 20 minutes of GPU time went to the same 19 errors.
2. **The Agent harness had no way back into the checks.** The Langflow Agent could validate text with the Pilot (`validate_sysml_text`) and search the memory, but nothing could hand an edited design to the four budget checks and the record; the only path was `run_design`, whose inner loop is the direct one above. Two Agent sessions also retried `run_design` on their own after a failure, so three design runs were sharing the GPU at once.
3. **The 27B was running a third on the CPU.** The published Ollama tag sets `num_ctx 224840`; Ollama reserved the cache for 224k tokens, placed 11.3 of 16.2 GiB of weights on the GPU and the rest on the CPU: 8.1 tokens/s over the first three calls of that run.

## What was decided and built

- **Conversation layer removed.** The two Agent flows, their MCP server (port 8782) and set-up script are deleted from the repository and from Langflow (`import_flows.py` removes them by name when it finds them). The fixed flows are the interface again: a brief in the chat box, the person's decision at ⑧.
- **A derived Ollama tag, `qwen3.8-27b-q3:64k`** (`tools/ollama/qwen3.8-27b-q3-64k.Modelfile`: the same weights, `num_ctx 65536`), built by `scripts/qwen38.sh`, which also starts Ollama (`--serve`, called by `scripts/langflow.sh`) and reports placement (`--status`). Loaded: 13.4 GiB, 100 % on the GPU; 113 tokens/s on a 400-token answer (14× the published tag).
- **OpenCode on the local model.** `agents/external/opencode_run.py` writes an `opencode.json` whose provider is the same `@ai-sdk/openai-compatible` package pointed at `http://127.0.0.1:11434/v1` (no key) with `reasoningEffort: "none"`, which Ollama reads as thinking off; the sandbox of decision 026 shares the network, so nothing else changes. The shell service accepts the local model with `direct` and `opencode`; Claude Code still uses the cloud Qwen (its route is the Anthropic-compatible one, untested against Ollama).
- **A second main flow, `RTRC agent flow · local Qwen3.8-27B via OpenCode`:** the same graph as the agent flow with the Start node preset to OpenCode and `qwen3.8-27b (Ollama)`; every model call of a run stays on this machine (requirements, alignment and read-back through `agents/llm_local.py`; the designs through OpenCode with `./validate` in hand). The results page must be stopped first, as for every sandboxed agent.

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

## What would reverse it

RTRC asking for a conversational layer after all (the removed code is in the history at commit 2569fb3), or OpenCode on the 27B proving no better than direct writing over several briefs (both would show on page 2.3 as parse counts and verdicts).
