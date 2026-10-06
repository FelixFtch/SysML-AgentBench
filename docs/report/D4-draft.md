# D4 report draft: benchmarking AI agents that translate requirements into SysML v2

RTRC 2706 · UConn Senior Design · data through 2026-10-06. Every maritime number is synthetic and is not an RTX specification. Current figures are generated from saved runs in `STATUS.md` and `analysis/report/exam-20261006/index.html`; this draft explains them. The process and the practical lessons are collected in the knowledge base, `docs/knowledge-base/` (D7).

## Summary

- **Feasibility.** On 27 sealed maritime ISR tasks scored only by the official SysML v2 Pilot 0.62 and answer keys written in advance, direct qwen3.8-max passes 312 of 324 cells (96.3%) and direct qwen3.8-flash 267 of 324 (82.4%). Two off-the-shelf coding agents on flash, run in a sandbox with nothing but the task, a rules file and the official validator, pass 77 of 81 (95.1%, OpenCode) and 76 of 81 (93.8%, Claude Code).
- **A validator in the loop lifts the cheap model.** As an agent, flash reaches 94–95% against 85% for its best direct approach, at 15–80× the cost; direct max with the repair loop passes 79 of 81 for less ($0.12 for 81 tasks).
- **The model matters more than the workflow.** With the same model, the four approaches (one-shot, repair loop, outline first, retrieval) differ by at most 6 of 81 cells on flash and 2 of 81 on max, within the repeat-to-repeat spread. The repair loop is the one step with a clear effect: it raises flash's final official parse from 31–37 to 36–39 of 39 SysML answers per approach. Max parses all 39 at the first attempt in every approach.
- **Weakest skill: aligning two models (paper 1).** It is the lowest task type for flash and both agents and the second lowest for max: flash passes 20 of 36 alignment cells, max 33 of 36, OpenCode 8 of 9, Claude Code 7 of 9. Query and clarification tasks follow for the direct calls: flash's most common miss is a right query answer written with a differently qualified name, and both direct models sometimes ask about the wrong missing quantity.
- **Safety holds.** No candidate changed a value the task said to keep, and on the over-budget task (MOD-05, 78 W against a 60 W limit) all 30 answers (24 direct cells, 6 agent runs) report the overrun instead of raising the limit. The scorer fails three agent clarifications for invented numbers; all three stop and ask, and the numbers are an example format or arithmetic from the statement (a key revision is proposed, not applied).
- **The official tool has an order dependence.** The Pilot can pass an alignment package when it is listed before its source models and fail the same files in the other order. The scorer uses one fixed order; the agents' validator now uses the same order, and their alignment runs were rerun.
- **Cost.** At the China (Beijing) list price, 81 cells cost $0.0087 on flash P0 and $0.12 on max P0 (14×); an agent run on flash costs about $0.006–0.008 on average (81 runs: OpenCode $0.68, Claude Code at least $0.51). Everything scored, including the side benchmarks, cost $2.46; everything recorded, including discarded runs, about $3.54.

## 1. What was built

**Task bank.** 27 tasks on one synthetic maritime ISR scenario (unmanned surface vessel, UAV, command ship, shore station): generate a model (GEN, 5), modify a model (MOD, 5), align two models (ALN, 3), query a model (QRY, 5), ask when a number is missing (AMB, 4), restate a model as requirements (RT, 5). Each task has an answer key written before any run: required names and connections, values that must not change, required and forbidden alignment pairs, expected query results, the quantity a clarification must ask about, required phrases. A second person reviewed all 27 keys (`bench/tasks/t4_maritime_isr/heldout/REVIEW.md`); the bank, scorers, prompts, retrieval library and toolchain are frozen with hashes in `bench/FREEZE.md` (tag `freeze-2026-10-06`).

**Adjudicator.** The official OMG SysML v2 Pilot 0.62 is the only syntax judge. A task passes when the official parse passes (GEN, MOD, ALN), every required name, connection or mapping is present, no number was invented, every value to keep is unchanged, and every engineering check comes out as the key expects. Whether a design meets its budget is a separate design verdict (decision 019). No model judges: two were tried on the 2026-10-03 answers and agreed with the tool on 226 and 157 of 288 cells, passing models that do not even parse (decision 025).

**Candidates.** Direct calls to qwen3.8-flash and qwen3.8-max, each with four approaches and three repeats (27 × 4 × 3 = 324 cells each):

| Approach | What it adds |
|---|---|
| P0 | One answer, no feedback |
| P1 | Repair loop: the complete official error list goes back after every version, in one conversation, up to 20 repairs; it stops after three identical resubmissions (decision 022) |
| P2 | An outline (parts, ports, connections) before the SysML, then P1's loop |
| P3 | Retrieval (MiniLM + FAISS over official SysML v2 example models and notes, decision 023), then P2 |

OpenCode 1.18.27 and Claude Code on qwen3.8-flash ran the 27 tasks three times each (81 runs each) in a bubblewrap sandbox: the task statement, `AGENTS.md` and `./validate` (the official Pilot) are the only things visible; the repository, answer keys, earlier runs and transcripts are not (decision 026). The help differs by design: the direct prompts carry the SysML rules (and the alignment rules for ALN) and the harness runs the repair loop; the agents get no rules and run the validator themselves.

## 2. Feasibility: four candidates by task type

| Task type | Direct flash | Direct max | OpenCode (flash) | Claude Code (flash) |
|---|---|---|---|---|
| GEN generate | 52/60 | 60/60 | 14/15 | 15/15 |
| MOD modify | 60/60 | 60/60 | 14/15 | 14/15 |
| ALN align | 20/36 | 33/36 | 8/9 | 7/9 |
| QRY query | 45/60 | 58/60 | 15/15 | 15/15 |
| AMB ask | 38/48 | 41/48 | 11/12 | 10/12 |
| RT restate | 52/60 | 60/60 | 15/15 | 15/15 |
| **All** | **267/324** | **312/324** | **77/81** | **76/81** |

How the failures split (one class per failing cell from its saved evidence, `bench/classify_failures.py`; examples in `docs/failure_taxonomy.md`):

- Flash, 57 failures: a right answer with a differently qualified name (15), a missing alignment pair (12), a question about the wrong quantity (10), a missing phrase in the restatement (8), an illegal connection (6), a missing part (3), an unresolved name in an alignment package (3).
- Max, 12 failures: a question about the wrong quantity (7), a missing alignment pair (3), a differently qualified name (2).
- OpenCode, 4 failures: two runs hit the 900 s limit before writing `answer.md` (GEN-05, ALN-02; in both the model in the workspace had passed `./validate`), one MOD answer described the edit instead of returning the model (MOD-02), and one correct clarification that showed an example format (`e.g. <= 450 W`) counts as an invented number (AMB-02).
- Claude Code, 5 failures: two ALN-02 runs hit the 900 s limit, one MOD answer returned only the added line (MOD-03), and two correct clarifications that showed arithmetic from the statement (128 GB / 30 days ≈ 4.27 GB/day, which the answers themselves say must not be used) count as invented numbers (AMB-03).

## 3. Performance: the same model with four approaches

| Approach | Flash pass (of 81) | Flash parse, 1st attempt → final (of 39) | Flash USD | Max pass (of 81) | Max USD |
|---|---|---|---|---|---|
| P0 one-shot | 63 | 34 → 34 | $0.0087 | 77 | $0.1199 |
| P1 repair loop | 68 | 33 → 36 | $0.0123 | 79 | $0.1188 |
| P2 outline + repair | 67 | 37 → 39 | $0.0242 | 77 | $0.3372 |
| P3 retrieval + outline + repair | 69 | 31 → 38 | $0.0320 | 79 | $0.3698 |

- **Repair** is cheap and works for the weaker model: flash's final parse rises by 3, 2 and 7 answers in P1–P3, for 17, 2 and 13 repairs in all. No cell reached the 20-repair cap; 4 stopped after three identical resubmissions, with the complete error list and every earlier version in the conversation. Before the loop was rebuilt (2026-10-03: 3 repairs, only the first 8 error lines, a fresh conversation each time), all 10 failing P1 generate cells had resubmitted unchanged text at least once.
- **The outline and retrieval** add tokens (P3 costs 3.7× P0 on flash, 3.1× on max) without a pass-rate difference that survives the repeat spread: flash's three repeats disagree in 24 of 108 (task, approach) groups, max's in 8.
- **Model choice** is the large effect: max passes 45 more cells than flash at about 12× the cost.

No confidence intervals or significance tests were computed; with three repeats per cell, differences of a few cells should not be read as rankings.

## 4. The two agents

Both agents ran each task three times on qwen3.8-flash in the sandbox. OpenCode passes 77 of 81 runs (95.1%) and Claude Code 76 of 81 (93.8%): well above direct flash at its best approach (P3, 69 of 81) and close to direct max (96.3%). They get there through the validator, which they run themselves: OpenCode called `./validate` 151 times in 68 runs, Claude Code 134 times in 69 runs. Every SysML answer either agent wrote into `answer.md` passes the official parse, and none changed a kept value; both report MOD-05's overrun in all three runs.

Their failures are of a different kind from the direct calls': running out of time (two each; in three of the four the model in the workspace had already passed `./validate`), answering a modify task with a description of the edit instead of the model (one each), and the strict invented-number rule on correct clarifications (three, see section 2). Their three repeats disagree on 4 (OpenCode) and 3 (Claude Code) of 27 tasks.

The cost is in the loop: every step re-sends the workspace, mostly as cached input. OpenCode used 23.3 million input tokens (21.5 million cached) and 0.46 million output tokens for 81 runs, $0.68; Claude Code at least 17.4 million (16.3 million cached) and 0.41 million, at least $0.51 (Claude Code reports usage only when a run ends, so the two runs that hit the limit are missing). For the same 81 tasks, direct max with the repair loop (P1) passes 79 for $0.12 and direct flash P3 passes 69 for $0.03.

One Claude Code run (ALN-03, repeat 2) put its answer in its final message instead of `answer.md`; the runner takes the final output when `answer.md` is missing, for both agents, so it was scored.

Two earlier agent batches of the same morning are discarded and kept on disk with the reason: OpenCode, working in a folder inside the repository, read the answer key of the task it was solving in several runs; Claude Code had every Bash and Write call denied, so it never ran the validator. Neither is in any score above.

**Validator order.** In the first sandboxed batch both agents checked their alignment packages with their own file listed before the two source models. In that order the Pilot passes a package that writes a nested usage as `Pkg::part::sub`; in the scorer's order (sources first) the same files fail with `Must be an accessible feature (use dot notation for nesting)`. All 8 alignment answers the agents submitted and the scorer failed had passed the agents' own check this way. Re-validating every graded alignment answer in both orders changed none of the 72 direct answers, the 16 answers of the agents' rerun or the three gold packages (`bench/check_validator_order.py`, `analysis/validator-order-20261006.json`). `./validate` now passes files in the scorer's order and all 18 agent alignment runs were rerun; the first batch's alignment rows are kept and listed as superseded.

## 5. The three papers in practice

| Paper | What we use | What the evidence says |
|---|---|---|
| 1 · Li, Husung, Wang, cross-organization model alignment (arXiv 2508.16181) | ALN tasks; Part 2 step ④ Align | Replicated on the authors' own example with their seven-stage prompt: the mapping stage transfers (7 of their 11 pairs proposed), but the alignment package, theirs and ours, fails the official Pilot. So the model only proposes pairs; code checks both names, classifies each pair from the two official parses and writes the package; a person accepts or rejects each pair. Alignment is the lowest task type for flash and both agents, and the second lowest for max. |
| 2 · Bader et al., GRAG retrieval over SysML v2 (ISSE 2025) | P3 retrieval; Part 2 step ① Retrieve; graph-retrieval queries | MiniLM embeddings in a FAISS index over Pilot-parsed element cards, seeds plus one hop, as in the paper, with an exact-name bonus of ours. On the five query tasks it finds 13 of 15 key elements against 11 for the earlier word ranking; with only the retrieved cards as context, max answers 5 of 5 query tasks (4 of 5 with the word ranking). In the exam, P3 versus P2 is +2 cells on flash and +2 on max, within noise. Replicated on the authors' own EV model with their code (decision 027): the published notebook passes an empty context to the model (0 of 3 answers right); with one fix it answers 3 of 3 and matches the paper's precision at threshold 0.35 (0.177 against 0.180), while the 0.904 F1 at 0.45 depends on unpublished wording and labels. Ours answers 2 of 3 with a tenth of the context, and 3 of 3 once cards carry documentation text, a change proposed for the next freeze. |
| 3 · Longshore, Bell, Madachy, NPS (SYM-AM-24-048/-138) | Rules + template + examples in the writing prompt; the repair loop | The rules carry most of the effect: once they stated the Pilot's `private import` convention, the import and `Real` errors that were 22 of 64 failures in the 2026-10-03 matrix disappeared. The paper's human correction step is replaced by the official error list; it lifts flash's parse rate and is not needed by max. |

## 6. Side benchmarks named in the brief (not in the exam score)

| Candidate | SysEngBench, 100 questions × 3 | PURE, 2 excerpts × 3 |
|---|---|---|
| Direct flash | 283/300 | 6/6 |
| Direct max | 291/300 | 6/6 |
| OpenCode (flash) | 272/300 | 6/6 |
| Claude Code (flash) | 291/300 | 6/6 |

SysEngBench (rabell/SysEngBench, MIT): 100 questions fixed with seed 20261006, 10 per prompt. Answering B every time scores 51 of 100 on this subset because the dataset's key is mostly B and C, so these scores say little about systems engineering judgement. PURE (nlreqdataset, CC BY 4.0): two sealed excerpts; the extracted requirement sentences must equal the key. Both are saturated for these candidates and do not separate them; the maritime exam does.

## 7. What the pipeline can decide (verification and validation)

- **Syntax:** the official Pilot gives a definite verdict with line and column. Flash's final answers parse in 147 of 156 SysML cells, max's in all 156.
- **Task:** the written key gives a definite verdict on names, connections, mappings, kept values, invented numbers and questions.
- **Design:** budgets are computed from the officially parsed numbers. MOD-05 asks for a 12 W camera while forbidding a change to the 60 W limit, so any correct answer is over budget (41 + 25 + 12 = 78 W). All 12 flash and 12 max cells and all 6 agent runs report it: task PASS, design FAIL. Raising the limit or lowering another draw to fit fails the task (`bench/test_score_pwr01.py`).
- **Safety and interoperability:** a person approves any requirement change and which design enters memory; no candidate changed a value it was told to keep; alignment declares links between models without editing either source.

It cannot replace a hardware test: the budgets are static sums, not time-domain simulation.

## 8. Part 2 prototype: from a blank brief to an approvable design

A brief goes through retrieval over the existing MaritimeISR model and approved designs (paper 2), numbered requirements whose numbers must come from the brief, two designs (paper 3), the official Pilot with repair, alignment with MaritimeISR (paper 1, code writes the package), power, uplink, storage and traceability checks from the parsed numbers, a read-back of the design as sentences, and a person's decision. An approved design joins memory and later runs retrieve it. The latest run proposed 5 alignment pairs, verified all 5 and declared them in a package the Pilot accepts. Two designs are in memory. This part has no scored task set yet.

## 9. Cost

Prices: Alibaba Cloud Model Studio, China (Beijing) list price checked 2026-10-03, per million tokens: qwen3.8-flash input $0.113, cached input $0.014, output $0.382; qwen3.8-max $1.65, $0.206, $4.951. Cached input is billed at about an eighth of fresh input, which is what keeps the agents affordable.

| Item | Runs or cells | USD |
|---|---|---|
| Direct flash, P0 / P1 / P2 / P3 | 81 each | $0.0087 / $0.0123 / $0.0242 / $0.0320 |
| Direct max, P0 / P1 / P2 / P3 | 81 each | $0.1199 / $0.1188 / $0.3372 / $0.3698 |
| OpenCode on flash | 81 | $0.6817 |
| Claude Code on flash | 81 | at least $0.5143 |
| Side benchmarks, four candidates | SysEngBench 300 answers, PURE 6 each | $0.2438 |
| Scored batches and side benchmarks | | $2.46 |
| Discarded and superseded agent runs | 81 + 81 + 9 + 9 | $0.9607 |

Everything recorded, including the discarded runs, graph retrieval, the Part 2 prototype and the MOD change chain, comes to about $3.54. The paper 1 replication (4 calls) and the trial runs are recorded in their own folders and not summed.

## 10. Limits

- 27 synthetic tasks on one scenario, keys by one author and one reviewer; no human blind review or inter-rater agreement yet.
- Three repeats per cell and no confidence intervals; only Qwen models; one pinned version of each agent.
- The agents and the direct calls get different help (rules in the prompt versus a validator they run themselves), so the comparison is between setups, not between pure abilities.
- The Pilot's verdict can depend on input order; the scorer fixes the order, but other order effects were not searched for.
- Two keys are known to be imperfect and are left for the next revision: MOD-01 does not check the radio connection it says to keep; AMB-02 accepts only "watt", "power limit" or "how many watts" as asking about the limit. The invented-number rule also fails three correct agent clarifications that show an example format or arithmetic from the statement; a change is proposed, not applied.
- Claude Code's cost is a lower bound: it reports usage only when a run ends.

## 11. Recommended next steps

1. Keep the official Pilot as the syntax judge and fixed answer keys as the task judge; do not use a model as judge. Validate multi-file packages in one fixed order: the sources first, the package last.
2. Report the task verdict and the design verdict separately; an over-budget design is a design failure, and raising the limit is never a pass.
3. Spend on the model before the workflow: on this bank a stronger model gains far more than any added step. Keep the repair loop (cheap, helps weaker models, no cell needed more than a few repairs); treat the outline and retrieval as optional until a larger bank shows an effect.
4. For alignment, let the model propose pairs, let code write the package and let a person accept each pair; do not let a model write the package unchecked.
5. An off-the-shelf coding agent with the official validator in its loop lifts a cheap model close to a strong one (flash: 85% at its best direct approach, 94–95% as an agent), at roughly 15–80× the direct cost of flash and above the cost of calling max directly. Give a fixed, cheap model the validator in a loop; when the budget allows, a stronger model with the repair loop is cheaper and as good. Ask the agent to write its answer file early: three of the four agent timeouts had a model that already passed the validator.
6. Next measurements: a human blind review with Cohen's κ, confidence intervals, a frontier model outside the Qwen family, the vendor assistant (Cameo AI) and a second checker (Syside), tasks that must trigger the approval gate, interface tasks in the UMAA style, a scored task set for the Part 2 prototype, and a reproduction on a clean machine. Under the next freeze, put documentation text into the retrieval cards and rerun P3 (decision 027).
