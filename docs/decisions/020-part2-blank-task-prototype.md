# 020 — Part 2 prototype: blank brief to approved design, with memory

Date: 2026-10-03.

## What was added

`bench/discover.py`, run from section 2.3 of the exam page. One run:

1. Retrieve elements from memory by the brief's words and numbers, then one hop of neighbours (paper 2, Bader et al., without vectors). Memory = the existing `MaritimeISR` model plus every design a person approved.
2. Write numbered requirements from the brief; code rejects any number not in the brief.
3. Write two designs (paper 3, Longshore et al.: rules, attribute contract, retrieved examples) and validate each with the official Pilot; repair from diagnostics at most three times.
4. Propose a mapping from design A to `MaritimeISR` and validate the alignment package with both source files (paper 1, Li et al.). Neither source model is edited.
5. Compute power, uplink, storage and traceability from the official parse.
6. If a check fails, the model proposes trade-offs from a synthetic catalog; code recomputes each one.
7. The model reads its own design back as sentences; code checks every brief number.
8. A person approves a design or not. Approved designs go to `analysis/memory/approved.jsonl` and are retrieved by the next run.

All parts and numbers are synthetic, not RTX specifications.

## Decisions taken with it

- The first approval (run 20261003T144529, design A) was made by the assistant while testing the page. The team decided on 2026-10-03 to keep it as a formal approval. The second (20261003T150116, design A) was made from the page.
- Budgets are static sums, not time-domain simulation.

## Status

Five runs in the current format on 2026-10-03 (six earlier-format runs are in `analysis/archive/2026-10-03-superseded/`). The default brief failed power (78/60 W) and uplink (18/8 Mbps); the three proposed trade-offs were all feasible when recomputed, and the run that used one of them passed all four checks. Later runs retrieved 4 of 7 elements from the approved design. There is no answer key for this part yet, so it has no score.

## What would reverse it

Advisors preferring that Part 2 is only described in the report, or a scored task set for it replacing the free-form brief.
