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

## Trial, GEN-03, qwen3.8-flash, P1, cap 20, three repeats (`analysis/trial-repair-20261006T045705/`)

| Repeat | Official syntax | First PASS at attempt | Repairs | Unchanged resubmits | Task verdict |
|---|---|---|---|---|---|
| 1 | PASS | 2 | 1 | 0 | FAIL: the repair changed `fusionLatencyS` from `Real` to `ISQ::TimeValue = 2.0 [SI::s]`; the key's kept value 2.0 is no longer read as a Real |
| 2 | PASS | 4 | 3 | 0 | PASS |
| 3 | PASS | 2 | 1 | 0 | PASS |

All three first attempts were byte-identical (`import ScalarValues::*;` inside the package; the pinned Pilot accepts `private import ScalarValues::*;` and rejects the bare form with `mismatched input 'import' expecting '}'`). Under the old loop this task was 0/3 on P1 with the same text resubmitted four times. The trial cost about 4,600 flash tokens.

The trial changes three things at once (full errors with positions, cumulative memory, an explicit resubmit instruction), so it does not say which one mattered. It does say the "resubmitted unchanged" behaviour was a property of the loop, not a fixed property of the model.

## Open

- `SYSML_RULES` says "Import ScalarValues only when you use Real" and does not say the import needs a visibility keyword in this Pilot. Whether to add that hint is a change to the rules component (paper 3) and is decided before the re-run, not during it.
- The 2026-10-03 matrix stays archived as the old-rule result and is not re-scored; the re-run is a new batch.
