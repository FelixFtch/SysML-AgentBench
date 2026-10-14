# 038 — The approval gate also blocks on an open question and on a design number the brief never gave

Date: 2026-10-10.

## What was found

The first run of the whole-flow benchmark (`plans/part2-flow-benchmark.md`, direct writer on qwen3.8-flash, 100
briefs) included 13 briefs with one value removed, for example "The vessel power limit is still to be confirmed."
In every one of them the requirements step did what it should: it wrote a question and left the quantity out. The
flow then went on as if the question had been answered. In 9 of the 13 runs a design was eligible for approval:

- in some, the design writer filled the missing value itself (`powerLimitW = 60`, a number that appears nowhere in
  the brief); the four gated checks read the design's own numbers, so POWER passed, TRACE passed because no
  requirement carried that quantity, and nothing compared the design's numbers with the brief;
- in others the design simply left the unknown device or rate out, and the POWER or LINK check passed on what was
  left (LINK falls back to the recording rate when no upload rate is stated).

The requirements' number-source check (`unsourced`) never fires in these cases, because the invented or omitted
number is in the design, not in the requirements. The benchmark's scorer caught it; the tool did not.

## Decision

Two rules are added to the gate (`bench/discover.py`, `approval_block` and `gate_for`, used by the page, the shell
service and the MCP):

1. **An open value blocks approval.** The requirements step now returns `missing_values`: the quantities a check needs
   that the brief does not state, each with the question to ask (the prompt says never to fill such a value in). When
   that list is not empty the gate answers `needs-person` with no eligible design, as for a number of unknown origin.
   The person answers and runs the brief again. This is the exam's AMB rule applied to the flow: ask, do not guess,
   do not proceed on a guess. `questions` stays a free field for remarks and conflicts and does not block: the first
   attempt at this rule blocked on any question and would have blocked three of the twenty saved runs, including an
   approved one, on remarks such as "the upload rate exceeds the uplink; should it be reduced?", which the LINK check
   already judges. For records written before `missing_values` existed, a requirement without a value whose text says
   the value is unspecified ("to be confirmed", "shall be defined", "TBD" …) counts as an open value (`open_values`).
2. **A fifth gated check, SOURCE.** Every literal number in the officially parsed design must appear in the brief
   or in a requirement value that itself came from the brief. `simulate()` takes the brief for this; without it the
   check is UNKNOWN, which also blocks. The comparison is on the number alone, as the requirements' check is, so a
   coincidence (an invented 8 Mbps when the brief has an 8 somewhere else) still slips through; that limit is stated.

`GATED_CHECKS` is now `POWER, LINK, STORE, TRACE, SOURCE`. The page, the Langflow pipeline card and the MCP say
"every gated check" instead of "all four checks". The example in the requirements prompt no longer shows `60` as a
sample value; a sample number in the prompt is a number the model can echo when the brief gives none.

## Checked

- The 20 saved runs of the design flow (page, Langflow, MCP): no gate changes. Every design's numbers come from its
  brief; no run reported an open value.
- A live run on the brief above with the direct writer on qwen3.8-max: the requirements step reported
  `missing_values = [powerLimitW]` and left the quantity null; both designs nevertheless carried `powerLimitW = 60`
  (the value of the existing MaritimeISR model, which memory retrieval had shown to the writer); SOURCE failed both
  with "not in the brief: powerLimitW = 60"; the gate answered `needs-person`. Both layers were needed: the writer
  filled the value even after the requirements step had asked for it.
- The benchmark's 13 missing-value records, re-gated from the saved records: 7 become `needs-person` through the
  unspecified-value wording of their requirements; the rest need the checks recomputed with the brief (SOURCE) or a
  fresh run under the new prompt. Benchmark runs started before this change should be run again so every writer is
  measured under the same requirements prompt and gate.
- The static four checks keep their meaning; the time-domain rows (REQS, MISSION) stay informational.

## What would reverse it

A brief whose author wants the flow to proceed on a stated default when a value is missing. Then the default must be
written into the brief, not guessed by the model; the gate rule stays.
