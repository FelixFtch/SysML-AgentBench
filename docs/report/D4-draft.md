# D4 report: benchmarking AI agents that translate requirements into SysML v2

RTRC 2706 · UConn Senior Design · frozen exam through 2026-10-06, later measurements through 2026-10-13, acceptance notes 2026-10-14. Every maritime number is synthetic and is not an RTX specification. This is the report. It is not a signed acceptance: no advisor has signed it, and there is no separate PDF. The frozen exam figures are generated from saved runs in `STATUS.md` and `analysis/report/exam-20261006/index.html`. `STATUS.md` itself still describes the side benchmarks as they stood on 2026-10-06; sections 6 to 8 below replace that description. The process and the practical lessons are collected in the knowledge base, `docs/knowledge-base/` (D7).

## Summary

- **Feasibility.** On 27 sealed maritime ISR tasks scored only by the official SysML v2 Pilot 0.62 and answer keys written in advance, direct qwen3.8-max passes 313 of 324 cells (96.6%) and direct qwen3.8-flash 270 of 324 (83.3%). Two off-the-shelf coding agents on flash, run in a sandbox with nothing but the task, a rules file and the official validator, pass 78 of 81 each (96.3%, OpenCode and Claude Code).
- **A validator in the loop lifts the cheap model.** As an agent, flash reaches 96% against 86% for its best direct approach, at 15–80× the cost; direct max with the repair loop passes 79 of 81 for less ($0.12 for 81 tasks).
- **The model matters more than the workflow.** With the same model, the four approaches (one-shot, repair loop, outline first, retrieval) differ by at most 5 of 81 cells on flash and 2 of 81 on max, within the repeat-to-repeat spread. The repair loop is the one step with a clear effect: it raises flash's final official parse from 33–37 to 36–39 of 39 SysML answers per approach. Max parses all 39 at the first attempt in every approach.
- **Weakest skill: aligning two models (paper 1).** It is the lowest task type for flash and both agents and the second lowest for max: flash passes 19 of 36 alignment cells, max 33 of 36, OpenCode 8 of 9, Claude Code 7 of 9. Query and clarification tasks follow for the direct calls: flash's most common misses are a right query answer written with a differently qualified name and a missing alignment pair, and both direct models sometimes ask about the wrong missing quantity.
- **Safety holds.** No candidate changed a value the task said to keep or wrote a model with a number the task did not give, and on the over-budget task (MOD-05, 78 W against a 60 W limit) all 30 answers (24 direct cells, 6 agent runs) report the overrun instead of raising the limit.
- **The official tool has an order dependence.** The Pilot can pass an alignment package when it is listed before its source models and fail the same files in the other order. The scorer uses one fixed order; the agents' validator now uses the same order, and their alignment runs were rerun.
- **Scored under freeze revision 2.** After the batches, three keys were fixed and the retrieval cards gained documentation text (decision 028). The saved answers were re-scored with the batches' own scoring code, which changed six cells, all from FAIL to PASS, and every direct P3 cell was rerun.
- **The same exam on the local model, and three Langflow columns.** The frozen matrix rerun on the local 3-bit Qwen3.8-27B passes 196 of 324 direct cells, 60 of 81 as OpenCode and 68 of 81 as Claude Code. Three Langflow chat flows sat the same 27 tasks: on flash, Pilot only 81/81, OpenCode with memory 81/81, Agent with memory 79/81; on the local 27B, 71/81, 64/81 and 80/81. These columns are scored by the frozen scorer and are not part of the frozen total.
- **External validity does not repeat the exam.** On the full SysEngBench file (1,144 questions × 3) every line lands between 86% and 97%. On PURE, turned into SysML v2 rather than copied as sentences, the official parse is near ceiling and the passage-level pass is about half, because one wrong requirement fails the passage. The maritime exam is what separates the lines.
- **The design tool can be scored end to end.** On 100 catalogue briefs, writers that call the official validator pass about 83–85% of runs (OpenCode 249/300, OpenCode with memory 255/300, Langflow Agent with memory 251/300, Pilot only 246/298). The direct writer on flash passes 19 of 100, almost entirely because it does not emit legal SysML. Briefs that omit a number are failed by every writer except one run: they fill the gap instead of asking, and the gate blocks the invented number (decision 038).
- **Cost.** At the China (Beijing) list price, 81 cells cost $0.0087 on flash P0 and $0.12 on max P0 (14×); an agent run on flash costs about $0.006–0.008 on average (81 runs: OpenCode $0.68, Claude Code at least $0.51). The frozen exam plus the side benchmarks as they stood on 2026-10-06 cost $2.45; everything recorded by that date, including discarded and superseded runs, about $3.97. Later PURE, SysEngBench, local-27B and Part 2 runs are not folded into those two totals.

## 1. What was built

**Task bank.** 27 tasks on one synthetic maritime ISR scenario (unmanned surface vessel, UAV, command ship, shore station): generate a model (GEN, 5), modify a model (MOD, 5), align two models (ALN, 3), query a model (QRY, 5), ask when a number is missing (AMB, 4), restate a model as requirements (RT, 5). Each task has an answer key written before any run: required names and connections, values that must not change, required and forbidden alignment pairs, expected query results, the quantity a clarification must ask about, required phrases. A second person reviewed all 27 keys (`bench/tasks/t4_maritime_isr/heldout/REVIEW.md`); the bank, scorers, prompts, retrieval library and toolchain are frozen with hashes in `bench/FREEZE.md` (tag `freeze-2026-10-06-r2`, with the history of the freeze).

**Revision 2** (decision 028), made after the batches by the user's decisions: MOD-01's key also checks the radio part and link its statement says to keep (no verdict changed); AMB-02's key accepts "maximum power", "power budget" and "limit" as asking for the limit (three direct answers that asked in those words now pass); an AMB number counts as invented only when the answer also writes SysML (three agent clarifications that showed an example format or arithmetic now pass); retrieval cards carry each element's documentation text, as in paper 2 (every direct P3 cell rerun). Every changed verdict is listed in `analysis/rescore-r2.json`; the original results files stay as run.

**Adjudicator.** The official OMG SysML v2 Pilot 0.62 is the only syntax judge. A task passes when the official parse passes (GEN, MOD, ALN), every required name, connection or mapping is present, no number was invented, every value to keep is unchanged, and every engineering check comes out as the key expects. Whether a design meets its budget is a separate design verdict (decision 019). No model judges: two were tried on the 2026-10-03 answers and agreed with the tool on 226 and 157 of 288 cells, passing models that do not even parse (decision 025).

**Candidates.** Direct calls to qwen3.8-flash and qwen3.8-max, each with four approaches and three repeats (27 × 4 × 3 = 324 cells each):

| Approach | What it adds |
|---|---|
| P0 | One answer, no feedback |
| P1 | Repair loop: the complete official error list goes back after every version, in one conversation, up to 20 repairs; it stops after three identical resubmissions (decision 022) |
| P2 | An outline (parts, ports, connections) before the SysML, then P1's loop |
| P3 | Retrieval (MiniLM + FAISS over official SysML v2 example models and notes, decision 023), then P2 |

OpenCode 1.18.27 and Claude Code 2.1.278 on qwen3.8-flash ran the 27 tasks three times each (81 runs each) in a bubblewrap sandbox: the task statement, `AGENTS.md` and `./validate` (the official Pilot) are the only things visible; the repository, answer keys, earlier runs and transcripts are not (decision 026). The help differs by design: the direct prompts carry the SysML rules (and the alignment rules for ALN) and the harness runs the repair loop; the agents get no rules and run the validator themselves.

## 2. Feasibility: four candidates by task type

| Task type | Direct flash | Direct max | OpenCode (flash) | Claude Code (flash) |
|---|---|---|---|---|
| GEN generate | 53/60 | 60/60 | 14/15 | 15/15 |
| MOD modify | 60/60 | 60/60 | 14/15 | 14/15 |
| ALN align | 19/36 | 33/36 | 8/9 | 7/9 |
| QRY query | 46/60 | 58/60 | 15/15 | 15/15 |
| AMB ask | 39/48 | 42/48 | 12/12 | 12/12 |
| RT restate | 53/60 | 60/60 | 15/15 | 15/15 |
| **All** | **270/324** | **313/324** | **78/81** | **78/81** |

How the failures split (one class per failing cell from its saved evidence, `bench/classify_failures.py`; examples in `docs/failure_taxonomy.md`):

- Flash, 54 failures: a right answer with a differently qualified name (14), a missing alignment pair (14), a question about the wrong quantity (9), a missing phrase in the restatement (7), an illegal connection (6), a missing part (2), an unresolved name in an alignment package (2).
- Max, 11 failures: a question about the wrong quantity (6), a missing alignment pair (3), a differently qualified name (2).
- OpenCode, 3 failures: two runs hit the 900 s limit before writing `answer.md` (GEN-05, ALN-02; in both the model in the workspace had passed `./validate`), and one MOD answer described the edit instead of returning the model (MOD-02).
- Claude Code, 3 failures: two ALN-02 runs hit the 900 s limit, and one MOD answer returned only the added line (MOD-03).

## 3. Performance: the same model with four approaches

| Approach | Flash pass (of 81) | Flash parse, 1st attempt → final (of 39) | Flash USD | Max pass (of 81) | Max USD |
|---|---|---|---|---|---|
| P0 one-shot | 65 | 34 → 34 | $0.0087 | 77 | $0.1199 |
| P1 repair loop | 68 | 33 → 36 | $0.0123 | 79 | $0.1188 |
| P2 outline + repair | 67 | 37 → 39 | $0.0242 | 78 | $0.3372 |
| P3 retrieval + outline + repair | 70 | 35 → 39 | $0.0254 | 79 | $0.3616 |

- **Repair** is cheap and works for the weaker model: flash's final parse rises by 3, 2 and 4 answers in P1–P3, for 17, 2 and 4 repairs in all. No cell reached the 20-repair cap; 3 stopped after three identical resubmissions, with the complete error list and every earlier version in the conversation. Before the loop was rebuilt (2026-10-03: 3 repairs, only the first 8 error lines, a fresh conversation each time), all 10 failing P1 generate cells had resubmitted unchanged text at least once.
- **The outline and retrieval** add tokens (P3 costs 2.9× P0 on flash, 3.0× on max) without a pass-rate difference that survives the spread between runs. Flash's three repeats disagree in 23 of 108 (task, approach) groups, max's in 8. The P3 rerun measured the spread directly: on the 25 tasks whose P3 prompts were byte-identical in both runs, 9 of 75 flash cells and 2 of 75 max cells changed verdict.
- **Model choice** is the large effect: max passes 43 more cells than flash at about 13× the cost.

No confidence intervals or significance tests were computed; with three repeats per cell, differences of a few cells should not be read as rankings.

## 4. The two agents

Both agents ran each task three times on qwen3.8-flash in the sandbox. Both pass 78 of 81 runs (96.3%): well above direct flash at its best approach (P3, 70 of 81) and level with direct max (96.6%). They get there through the validator, which they run themselves: OpenCode called `./validate` 151 times in 68 runs, Claude Code 134 times in 69 runs. Every SysML answer either agent wrote into `answer.md` passes the official parse, and none changed a kept value; both report MOD-05's overrun in all three runs.

Their failures are of a different kind from the direct calls': running out of time (two each; in three of the four the model in the workspace had already passed `./validate`) and answering a modify task with a description of the edit instead of the model (one each). Their three repeats disagree on 3 (OpenCode) and 2 (Claude Code) of 27 tasks.

The cost is in the loop: every step re-sends the workspace, mostly as cached input. OpenCode used 23.3 million input tokens (21.5 million cached) and 0.46 million output tokens for 81 runs, $0.68; Claude Code at least 17.4 million (16.3 million cached) and 0.41 million, at least $0.51 (Claude Code reports usage only when a run ends, so the two runs that hit the limit are missing). For the same 81 tasks, direct max with the repair loop (P1) passes 79 for $0.12 and direct flash P3 passes 70 for $0.03.

One Claude Code run (ALN-03, repeat 2) put its answer in its final message instead of `answer.md`; the runner takes the final output when `answer.md` is missing, for both agents, so it was scored.

**The same 27 tasks, other columns.** These are scored by the frozen scorer and are not inside the 270/324 and 78/81 totals above. On qwen3.8-flash, three Langflow flows sat the exam: Langflow Agent, Pilot only 81/81; OpenCode with memory 81/81; Langflow Agent with memory 79/81 (`analysis/langflow-exam-*-qwen3.8-flash-20261007T*/summary.json`). The same matrix on the local 3-bit Qwen3.8-27B, served by Ollama: direct 196/324, OpenCode 60/81, Claude Code 68/81, and the three Langflow flows 71/81, 64/81 and 80/81 (`README.md`, `analysis/langflow-exam-*-local27b-*/summary.json`). The local direct run is the weak one. The sandboxed agents and the Langflow agent with memory recover most of it.

Two earlier agent batches of the same morning are discarded and kept on disk with the reason: OpenCode, working in a folder inside the repository, read the answer key of the task it was solving in several runs; Claude Code had every Bash and Write call denied, so it never ran the validator. Neither is in any score above.

**Validator order.** In the first sandboxed batch both agents checked their alignment packages with their own file listed before the two source models. In that order the Pilot passes a package that writes a nested usage as `Pkg::part::sub`; in the scorer's order (sources first) the same files fail with `Must be an accessible feature (use dot notation for nesting)`. All 8 alignment answers the agents submitted and the scorer failed had passed the agents' own check this way. Re-validating every graded alignment answer in both orders changed none of the direct answers, the answers of the agents' rerun or the three gold packages (`bench/check_validator_order.py`, `analysis/validator-order-20261006.json`). `./validate` now passes files in the scorer's order and all 18 agent alignment runs were rerun; the first batch's alignment rows are kept and listed as superseded.

## 5. The three papers in practice

| Paper | What we use | What the evidence says |
|---|---|---|
| 1 · Li, Husung, Wang, cross-organization model alignment (arXiv 2508.16181) | ALN tasks; Part 2 step ④ Align | Replicated on the authors' own example with their seven-stage prompt: the mapping stage transfers (7 of their 11 pairs proposed), but the alignment package, theirs and ours, fails the official Pilot. So the model only proposes pairs; code checks both names, classifies each pair from the two official parses and writes the package; a person accepts or rejects each pair. Alignment is the lowest task type for flash and both agents, and the second lowest for max. |
| 2 · Bader et al., GRAG retrieval over SysML v2 (ISSE 2025) | P3 retrieval; Part 2 step ① Retrieve; graph-retrieval queries | MiniLM embeddings in a FAISS index over Pilot-parsed element cards, seeds plus one hop, as in the paper, with an exact-name bonus of ours. On the five query tasks it finds 13 of 15 key elements against 11 for the earlier word ranking; with only the retrieved cards as context, max answers 5 of 5 query tasks (4 of 5 with the word ranking). In the exam, P3 versus P2 is +3 cells on flash and +1 on max, within the spread between runs. Replicated on the authors' own EV model with their code (decision 027): the published notebook passes an empty context to the model (0 of 3 answers right); with one fix it answers 3 of 3 and matches the paper's precision at threshold 0.35 (0.177 against 0.180), while the 0.904 F1 at 0.45 depends on unpublished wording and labels. Ours answered 2 of 3 with a tenth of the context while the cards lacked documentation text, and 3 of 3 with it; the cards now carry it (revision 2). |
| 3 · Longshore, Bell, Madachy, NPS (SYM-AM-24-048/-138) | Rules + template + examples in the writing prompt; the repair loop | The rules carry most of the effect: once they stated the Pilot's `private import` convention, the import and `Real` errors that were 22 of 64 failures in the 2026-10-03 matrix disappeared. The paper's human correction step is replaced by the official error list; it lifts flash's parse rate and is not needed by max. |

## 6. Side benchmarks named in the brief (not in the exam score)

The brief names two public collections. Both were first tried on a small slice, and that slice is not the result reported here. On 2026-10-06 a 100-question SysEngBench subset (seed 20261006, always answering B would score 51 of 100) and two PURE excerpts scored 6 of 6 for every candidate (`STATUS.md`). Those folders remain on disk. The measurements below use the full public file and the requirements-to-SysML protocol.

**SysEngBench** (rabell/SysEngBench, MIT), all 1,144 questions of `test.csv` × 3 repeats = 3,432 answers, qwen3.8-flash, four options scored against the published key. Always answering B scores 557 of 1,144 on the full file.

| Line | Correct |
|---|---|
| Claude Code | 3316/3432 (96.6%) |
| Langflow Agent with memory | 3305/3432 (96.3%) |
| Direct P0 | 3288/3432 (95.8%) |
| Direct | 3287/3432 (95.8%) |
| Direct P2 | 3286/3432 (95.7%) |
| Direct P3 | 3277/3432 (95.5%) |
| Langflow Agent, Pilot only | 3244/3432 (94.5%) |
| Direct P1 | 3240/3432 (94.4%) |
| OpenCode | 3217/3432 (93.7%) |
| OpenCode with memory | 2959/3432 (86.2%) |

The file does not separate the lines the way the maritime exam does. OpenCode with memory is the weak line on this file and on PURE.

**PURE** (Zenodo 7118517, the collection behind nlreqdataset.isti.cnr.it, CC BY 4.0). Six XML documents mark their requirements (1,004 requirements). `bench/build_pure_tasks.py` cuts them into 175 passages of up to 12 units (headings, explanatory text and requirements). The candidate writes one SysML v2 package; a passage passes when the official Pilot parses it, every marked requirement appears inside its own `requirement def`, no explanatory paragraph does, there is no extra requirement def, and no number appears that the passage does not contain. An earlier protocol asked the model to copy the requirement sentences. Most of its failures were the right text cut at a different boundary, and no approach of ours was involved. That protocol is superseded and is not in the table. qwen3.8-flash, three repeats.

| Line | Passage pass | Official Pilot | Marked requirements found |
|---|---|---|---|
| OpenCode | 299/525 | 523/525 | 2815/3012 |
| Claude Code | 297/517 | 510/517 | 2862/2976 |
| Direct P3 | 283/525 | 520/525 | 2912/3012 |
| Direct P1 | 268/525 | 514/525 | 2809/2985 |
| Direct P2 | 267/525 | 522/525 | 2904/3002 |
| Direct P0 | 259/525 | 523/525 | 2811/3012 |
| Direct | 254/525 | 525/525 | 2910/3012 |
| Langflow Agent, Pilot only | 248/523 | 522/523 | 2757/2990 |
| Langflow Agent with memory | 242/524 | 522/524 | 2737/3003 |
| OpenCode with memory | 176/525 | 480/525 | 2477/2930 |

Syntax is no longer what separates them. A passage fails when a marked requirement is left out or an explanatory paragraph is written as a requirement. Claude Code finished 517 rows, Pilot only 523 and Agent with memory 524; the others finished 525. The passage-level pass is the strict score. Coverage of the marked requirements stays above 90% except for OpenCode with memory (84.5%).

## 7. What the pipeline can decide (verification and validation)

- **Syntax:** the official Pilot gives a definite verdict with line and column. Flash's final answers parse in 148 of 156 SysML cells, max's in all 156.
- **Task:** the written key gives a definite verdict on names, connections, mappings, kept values, invented numbers and questions.
- **Design:** budgets are computed from the officially parsed numbers. MOD-05 asks for a 12 W camera while forbidding a change to the 60 W limit, so any correct answer is over budget (41 + 25 + 12 = 78 W). All 12 flash and 12 max cells and all 6 agent runs report it: task PASS, design FAIL. Raising the limit or lowering another draw to fit fails the task (`bench/test_score_pwr01.py`).
- **Safety and interoperability:** a person approves any requirement change and which design enters memory; no candidate changed a value it was told to keep; alignment declares links between models without editing either source.

The exam's design verdict is still that static budget. The design flow now also integrates each design's parsed rates over the mission (60 s steps, duration equal to the stated retention, constant rates) and cross-checks the integral with OpenModelica 1.27.1 (`bench/simulate_design.py`). On the 20 real design runs saved before the scored benchmark, the two integrators agree on every run. Four of the 20 have requirements that contradict each other on power and on the link. Five have a design B with no numeric attributes, so its mission check is unknown. This is a check of the flow's own requirements and designs. It is not a hardware test, and it is not one of the gated checks that decide whether a design may enter memory.

## 8. Part 2: from a blank brief to an approvable design

A brief goes through retrieval over the existing MaritimeISR model and approved designs (paper 2), numbered requirements whose numbers must come from the brief, two SysML v2 designs (paper 3), the official Pilot with repair, alignment with MaritimeISR (paper 1, the model proposes pairs and code writes the package), power, uplink, storage and traceability checks from the parsed numbers, a source check that every design literal appears in the brief or in a sourced requirement (decision 038), a mission-timeline check (section 7), a read-back of the parsed model as sentences, and a person's decision. An approved design joins memory and later runs retrieve it. Two designs are in memory (20261003T144529-A and 20261003T150116-A). P0, P1, P2 and P3 are exam prompts. They are not writers of this step: the flow always repairs from the Pilot's errors and does not outline first.

The same 100 briefs, drawn from the flow's own parts catalogue and scored by code (`bench/run_part2_bench.py`, scorer v2, decision 038), were run on qwen3.8-flash. A correct infeasible brief is a task pass with a design fail. Direct is 100 runs. The other writers are 100 briefs × 3, except Pilot only, which stopped at 298 when its run budget ended. Adapting an approved design was not in this round.

| Writer | Task pass | Both designs parse | Feasible | Over power | Over link | Missing value | Preview |
|---|---|---|---|---|---|---|---|
| OpenCode with memory | 255/300 | 297/300 | 39/39 | 123/129 | 33/33 | 0/39 | 60/60 |
| Langflow Agent with memory | 251/300 | 298/300 | 39/39 | 122/129 | 31/33 | 0/39 | 59/60 |
| OpenCode | 249/300 | 299/300 | 39/39 | 120/129 | 31/33 | 0/39 | 59/60 |
| Langflow Agent, Pilot only | 246/298 | 291/298 | 38/38 | 119/129 | 28/32 | 1/39 | 60/60 |
| Claude Code | 112/300 | 140/300 | 15/39 | 71/129 | 9/33 | 0/39 | 17/60 |
| Direct writer | 19/100 | 25/100 | 2/13 | 11/43 | 3/11 | 0/13 | 3/20 |

The direct writer's failures are syntactic: it submits `part definition` and `port definition`, which the Pilot rejects, and then resubmits the same file until the repair cap. Writers that hold `./validate` fix that. The missing-value briefs are the other systematic failure. The correct behaviour is to ask and to leave the design ineligible. Five of the six writers never do this (0 passes); Pilot only does it once in 39. They fill in a number, often the 60 W power limit from memory, and the source check then blocks approval. That is the gate working. It is not a high score.

The catalogue cannot make storage fail. Its smaller drive is 128 GB, and the largest recording it can ask for is 18 Mbps for 8 h, which is 64.8 GB. A 64 GB option was not added in order to manufacture a failure.

One later live run, after this table, is recorded as `20261013T155413`: a fixed-wing UAV brief on the local 27B through OpenCode. Both designs pass the official Pilot and every gated check. The gate is awaiting a person. The script does not choose. Cameo export files are written next to the run; Cameo itself is not in the brief's software list and is not installed here.

## 9. Cost

Prices: Alibaba Cloud Model Studio, China (Beijing) list price checked 2026-10-03, per million tokens: qwen3.8-flash input $0.113, cached input $0.014, output $0.382; qwen3.8-max $1.65, $0.206, $4.951. Cached input is billed at about an eighth of fresh input, which is what keeps the agents affordable.

| Item | Runs or cells | USD |
|---|---|---|
| Direct flash, P0 / P1 / P2 / P3 | 81 each | $0.0087 / $0.0123 / $0.0242 / $0.0254 |
| Direct max, P0 / P1 / P2 / P3 | 81 each | $0.1199 / $0.1188 / $0.3372 / $0.3616 |
| OpenCode on flash | 81 | $0.6817 |
| Claude Code on flash | 81 | at least $0.5143 |
| Side benchmarks, four candidates | SysEngBench 300 answers, PURE 6 each | $0.2438 |
| Scored batches and side benchmarks | | $2.45 |
| Discarded and superseded runs | agents 81 + 81 + 9 + 9, P3 cells 81 + 81 | $1.40 |

Everything recorded, including the discarded and superseded runs, graph retrieval, the Part 2 prototype and the MOD change chain, comes to about $3.97. The paper 1 and paper 2 replications and the trial runs are recorded in their own folders and not summed. The discarded Claude Code batch is priced from Claude Code's own per-model usage, because its runner recorded the cached input apart from the input.

## 10. Limits

- 27 synthetic tasks on one scenario, keys by one author and one reviewer; no human blind review or inter-rater agreement yet.
- Three repeats per cell and no confidence intervals; the scored models are Qwen models; one pinned version of each agent. The local 27B was run on the maritime exam and not on PURE or on the full SysEngBench file.
- The agents and the direct calls get different help (rules in the prompt versus a validator they run themselves), so the comparison is between setups, not between pure abilities.
- The Pilot's verdict can depend on input order; the scorer fixes the order, but other order effects were not searched for.
- The keys were revised once after the batches (decision 028); the revision changed six verdicts, all to PASS, and no second human reviewer has checked it.
- Claude Code's cost on the frozen exam is a lower bound: it reports usage only when a run ends. The $2.45 and $3.97 totals stop at 2026-10-06.
- SysEngBench's published key is concentrated on a few letters, so a high score there is weak evidence. PURE's passage-level pass fails a whole passage for one mistake; coverage and the official parse should be read beside it.
- In the design-flow benchmark the direct writer is one pass over the 100 briefs, not three, and Pilot only finished 298 of 300. Storage cannot fail in the catalogue used to build those briefs. The missing-value case shows that the writers invent a number and the gate blocks it; it does not show that they ask.
- `STATUS.md` is generated from the frozen exam and still describes the superseded 100-question and two-excerpt side runs. Sections 6 to 8 of this report are the later measurements.

## 11. Recommended next steps

1. Keep the official Pilot as the syntax judge and fixed answer keys as the task judge; do not use a model as judge. Validate multi-file packages in one fixed order: the sources first, the package last.
2. Report the task verdict and the design verdict separately; an over-budget design is a design failure, and raising the limit is never a pass.
3. Spend on the model before the workflow: on this bank a stronger model gains far more than any added step. Keep the repair loop (cheap, helps weaker models, no cell needed more than a few repairs); treat the outline and retrieval as optional until a larger bank shows an effect.
4. For alignment, let the model propose pairs, let code write the package and let a person accept each pair; do not let a model write the package unchecked.
5. An off-the-shelf coding agent with the official validator in its loop lifts a cheap model to the strong one's level (flash: 86% at its best direct approach, 96% as an agent), at roughly 15–80× the direct cost of flash and above the cost of calling max directly. Give a fixed, cheap model the validator in a loop; when the budget allows, a stronger model with the repair loop is cheaper and as good. Ask the agent to write its answer file early: three of the four agent timeouts had a model that already passed the validator.
6. The Part 2 prototype now has a scored set (section 8). What it does not yet have is the adapt-an-approved-design branch, a storage option small enough to fail, and a writer that asks when a number is missing. Those are findings, not open scaffolding.
7. Still open, and not required to close the brief's question: a human blind review with Cohen's κ, confidence intervals, a frontier model outside the Qwen family, the local 27B on PURE and on the full SysEngBench file, the vendor assistant (Cameo AI) and a second checker (Syside), interface tasks in the UMAA style, and a reproduction on a clean machine. Regenerating `STATUS.md` so it no longer quotes the superseded side-benchmark slice. Asking RTRC to confirm that Pilot 0.62.0 is the software package they meant (section 12).

## 12. Acceptance against the brief

The brief's required work is the decision-support question: can an agent turn natural-language requirements into SysML v2, on a maritime ISR scenario, with evidence of feasibility, performance, limits and next steps, checked on PURE and SysEngBench. Sections 1 to 8 are that evidence. The ten activities and the capability checkboxes are written as "may" and "suggested, but not required."

Two records that look like the same review are not.

- The 27 held-out answer keys were read by a second reviewer on 2026-10-06 and frozen (`bench/tasks/t4_maritime_isr/heldout/REVIEW.md`, decision 028, tag `freeze-2026-10-06-r2`).
- `scenario/maritime-isr/` is the reference model those tasks start from. Its checklist, `assertions.yaml`, still has one author. Its engineering acceptance stays UNKNOWN because no domain budget checker was applied to that model on 2026-10-02. That file was not signed in the held-out review, and this report does not sign it.

The brief's "required software package" field does not name a package or a version. It lists three papers and two datasets (PURE / nlreqdataset, SysEngBench). The project pins the official OMG SysML v2 Pilot 0.62.0 (kernel sha256 `5a015ed3f2b3d2da` in `bench/FREEZE.md`) as the only syntax judge. Whether RTRC accepts that pin as the required package is still an open confirmation. It is not recorded here as confirmed.

What this report does not contain, because the work was not done: a human blind review and Cohen's κ, a confidence interval, a non-Qwen frontier model, Cameo AI, a second checker (Syside), UMAA-style interface tasks, a clean-machine reproduction, and the adapt-an-approved-design branch of the design flow. Interoperability here is SysML v2 text plus an alignment package plus a Cameo export file. Reliability here is repeated runs and a frozen toolchain. Safety here is the approval gate, not a hardware safety case. The mission simulation is a constant-rate integral of the design's own numbers, cross-checked with OpenModelica, not a trial at sea.
