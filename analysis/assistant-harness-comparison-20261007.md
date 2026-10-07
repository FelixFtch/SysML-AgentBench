# Outer harness comparison, local Qwen3.8-27B: OpenCode vs Langflow's Agent (2026-10-07)

Two assistants on the same local model (`qwen3.8-27b-q3:64k`, Ollama), the same MCP tools, and the same inner writer
(OpenCode in the sandbox writing the designs). Only the outer layer differs: **RTRC design assistant** (OpenCode chooses
the tools) and **RTRC design assistant · unfolded (local 27B)** (Langflow's Agent component chooses the cards). One
scripted conversation each, same wording, fresh sessions, run through the Workflow API on the superuser copies, results
page stopped. Raw turns: `assistant-harness-comparison-20261007/` (`opencode-outer.jsonl`, `langflow-agent-outer.jsonl`,
`langflow-agent-outer-rerun-after-fix.jsonl`, `runner.py`). The Langflow side's first attempt died on my script's login
rate limit (HTTP 429) and was rerun; that failure is the script's, not the flow's, and is excluded.

| # | Question | OpenCode outer | Langflow Agent outer |
|---|---|---|---|
| 1 | Which projects are in the memory, and each one's power limit? | 20 s, `list_projects`. Both approved designs 60 W, correct; said the list carries no limit for MaritimeISR and offered to read it (did not) | 10 s, `list_projects` + `search_memory`. All three 60 W, correct; also quoted `PowerLimitUnchanged` |
| 2 | "I want to add a sensor to the boat, how would you change it?" | 10 s, no tool. Asked for the draw and data rate before anything; no number invented; no run | 20 s, 6 tool calls. Listed MaritimeISR's 8 Mbps / 128 GB and both precedents correctly, then asked for four numbers; no run |
| 3 | Change 20261003T150116: IR stays 7 W, upload down to 12 Mbps, nothing else; show the brief, do not run | 10 s. Brief correct; named the one change (18 → 12); noted the opening "add a sensor" had no sensor in it | 25 s, `design_status`. Brief correct with a source table; computed the 8 h backlog at 12 vs 18 Mbps |
| 4 | "Confirmed, run." | 255 s. The brief reached the pipeline unchanged. Run 20261007T064005: A and B PASS at parse 1; POWER 49/60 W, LINK 12/20, STORE 64.8/256, TRACE 9/9, all PASS; alignment 6/6 | 370 s. Run 20261007T071503 ran the **default brief of page 2.2** (41 W, 25 W, 12 W, 128 GB, 8 Mbps): POWER 78/60 FAIL, LINK 18/8 FAIL. See below |
| 5 | Do not write; record Send back, reason "comparison test" | 5 s, `record_decision`; also reported the step timings | 5 s, `record_decision` |
| 6 | Replace the 28 W visible camera of 150116 with a 30 W lidar: still within 60 W? Show the arithmetic | 51 W ≤ 60 W, correct; said the 30 W is the engineer's, not the memory's | 51 W ≤ 60 W, correct (`evaluate_expression`) |
| 6 ×2 | Same question, fresh sessions | 3/3 correct; once searched the memory for "LiDAR" and reported nothing there | 3/3 correct; `design_status` + calculator each time |

## Turn 4: not the model, the wiring

The Langflow Agent's tool call carried the right brief: `{"flow_tweak_data": {"brief": "...28 W ... 14 W ... 7 W ... 60 W ... 18 Mbps ... 256 GB ... 12 Mbps ... 20 Mbps"}}`.
Run Flow exposes the sub-flow's input under the generated name `ChatInput-brief~input_value`; the key `brief` was unknown
and ignored, the sub-flow's Chat Input stayed empty, and the Start node fell back to the default brief of the 2.2 design
space (the over-budget demo brief). The pipeline then judged that brief correctly (POWER and LINK FAIL). The agent
returned the review text as it was and did not remark that the brief differed from the one it had shown. The earlier
qwen3.8-max run (20261007T055712) had used the generated key and gone through.

Fixes (decision 034): the pipeline's Start node refuses an empty brief when used as a tool (`require_brief`), so a
misnamed argument fails loudly; the prompt names the exact key; and it asks the agent to compare the returned "Brief:" line
with the confirmed one. **Rerun after the fix** (turns 3 and 4, fresh session): the brief reached the pipeline word for
word; run 20261007T074333: design A PASS at parse 1, all four checks PASS; design B came back from the sandboxed OpenCode
as an empty package after 544 s (Pilot PASS, TRACE 0/9 FAIL, POWER UNKNOWN) and the gate kept it out of memory. That is an
inner-writer weakness of the 27B on a from-scratch design, visible in both assistants' records, not an outer-harness one.

## What the day's numbers support

- Conversation, arithmetic and refusals: close. Langflow's Agent calls more tools and answers more completely; the
  OpenCode outer tends to answer from context. Both refused to invent numbers; both got the 51 W question right 3/3
  (the OpenCode outer had got it wrong once earlier in the evening, in a different session).
- Design runs: one each per harness that reached the pipeline with the right brief, both all-PASS on design A; design B
  PASS in the OpenCode-outer run, degenerate in the rerun. Not enough runs to rank the harnesses on design quality; the
  inner writer is the same in both.
- The one real difference found was a wiring defect in the Run Flow tool, now fixed. For daily use the three-card
  assistant stays the default; the unfolded ones are for showing the structure and for editing the pipeline on the canvas.
