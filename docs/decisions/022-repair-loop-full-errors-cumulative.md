# 022 · Repair loop: complete error list, one cumulative conversation, cap of 20

Date: 2026-10-06. Status: accepted. Affects `agents/solve.py`, `bench/experiment.py`, `bench/exam_board.py`, `bench/discover.py`.

## What was wrong

The P1 repair loop used in the 2026-10-03 matrix had three limits that were ours, not the tool's:

1. Only the first 8 diagnostic messages went back to the model, without line or column.
2. Every repair opened a new conversation holding only the previous version and that round's errors. Earlier versions and earlier error lists were dropped.
3. At most 3 repairs. Only P1 repaired; P2 and P3 did not, so P3 measured "retrieval without repair" and the four approaches were not cumulative.

In that matrix all 10 P1 generate-task failures used the 3 repairs and resubmitted the previous text unchanged at least once; GEN-03's three repeats and GEN-04's third resubmitted the same text all four times.

## Rule now

- The complete diagnostic list from the official Pilot goes back, each line as `[SEVERITY] line L, column C: message`.
- One submission is one conversation: rules, task, version 1, full errors 1, version 2, full errors 2, … until the parse passes or the cap is reached. `conversation.json` and every `attempts/attempt-NN.sysml` with its `.diagnostics.json` are saved in the run folder.
- Cap: `BENCH_REPAIR_ROUNDS`, default 20 repairs; `bench/experiment.py --rounds N` overrides it. P0 never repairs. P1, P2 and P3 all repair, so P0→P1 isolates repair, P1→P2 isolates the outline, P2→P3 isolates retrieval.
- Each record carries `attempts`, `repair_rounds`, `max_rounds`, `first_pass_attempt` and `resubmitted_unchanged`. The first-attempt result inside a repaired cell is what P0 used to measure.
- The exam console (1.5) and the Part 2 design validation use the same function and the same cap.

## Trials, GEN-03, P1, cap 20, three repeats each

Correction: the first trial ran on **qwen3.8-max**, not flash. `bench/experiment.load_env()` used to let `.env` override a model set on the command line; fixed the same day (environment wins). Both trials are kept.

qwen3.8-max (`analysis/trial-repair-max-20261006T045705/`):

| Repeat | Official syntax | First PASS at attempt | Repairs | Unchanged resubmits | Task verdict |
|---|---|---|---|---|---|
| 1 | PASS | 2 | 1 | 0 | FAIL: the repair changed `fusionLatencyS` from `Real` to `ISQ::TimeValue = 2.0 [SI::s]`; the key's kept value 2.0 is no longer read as a Real |
| 2 | PASS | 4 | 3 | 0 | PASS |
| 3 | PASS | 2 | 1 | 0 | PASS |

qwen3.8-flash, the matrix model (`analysis/trial-repair-flash-20261006T055816/`):

| Repeat | Official syntax | First PASS at attempt | Repairs | Unchanged resubmits | Task verdict |
|---|---|---|---|---|---|
| 1 | FAIL | — | 20 (cap) | 18 | FAIL: from attempt 4 on it resubmitted the same file (bare `import ScalarValues::Real;` and `part fusion : Processor in commandShip;`) against the same 8 errors |
| 2 | PASS | 4 | 3 | 1 | PASS |
| 3 | PASS | 5 | 4 | 2 | PASS |

Every first attempt failed on the same line: `import ScalarValues::*;` inside the package. The pinned Pilot accepts `private import` / `public import` and rejects the bare form with `mismatched input 'import' expecting '}'` (probe in the conversation record of 2026-10-06). The rules did not mention the keyword; the P3 notes did, but they reached only the outline prompt. Under the old loop this task was 0/3 on flash P1 with the same text resubmitted four times. With memory and full errors flash passes 2/3 and still locks onto one wrong file in 1/3; max passes syntax 3/3.

Guard added after the flash trial: after three consecutive byte-identical resubmissions the loop stops (`BENCH_REPAIR_IDENTICAL_STOP`, default 3, 0 disables) and records `stop_reason`; the first identical resubmission gets one extra sentence in the feedback saying the text did not change. A stop by this guard is a failure like a stop at the cap.

## Open

- `SYSML_RULES` says "Import ScalarValues only when you use Real" and does not say the import needs a visibility keyword in this Pilot. Whether to add that hint is a change to the rules component (paper 3) and is decided before the re-run, not during it.
- The 2026-10-03 matrix stays archived as the old-rule result and is not re-scored; the re-run is a new batch.
