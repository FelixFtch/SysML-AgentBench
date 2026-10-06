# 025 · Model judges are dropped from the page and the scoring; the second review and the freeze

Date: 2026-10-06. Status: accepted (user decision). Affects `bench/exam_board.py`, `bench/board.js`, `bench/board_facts.py`, `scripts/make_status.py`, the report builder; `bench/review_gold.py`, `bench/freeze.py`, `bench/FREEZE.md`, `bench/tasks/t4_maritime_isr/heldout/REVIEW.md`.

## Judges

Two models were tried as second readers of the 288 answers (Jev 1.13: agrees with the tool on 226/288, 32 false passes all on generate tasks; qwen3.8-max: 157/288, 70 false passes). Neither ever changed a score. The conclusion stands as one line in the report: a model judge is worse than the official tool and the keys, so there is none. The judge columns, the "Is Jev right?" matrix colouring, the judge rows in the cell view and the Jev cost item come off the page; the saved judge files move to `analysis/archive/`. Jev cannot be a candidate either: its interface returns choices and scores, not text, so it cannot write a model.

SysEngBench (20 multiple-choice questions, answered by Jev) is replaced by the same questions put to the four candidates in a separate appendix batch; the Jev file is archived.

## Second review and freeze

The user delegated the second review of the 27 keys to the assistant. `bench/review_gold.py` runs the mechanical checks (27/27) and `REVIEW.md` records the reading: two leniencies noted for the next key revision (MOD-01 does not check the radio connection it says to keep; AMB-02's word list misses "power consumption"), no key edited. Two scorer rules were decided in the review: an imperative clarification request counts as asking, with unit-bearing numbers not in the statement counted as invented; RT phrases match after number-word and `.0` normalisation. `bench/freeze.py` writes `bench/FREEZE.md` with the hash of every task directory, scorer, prompt, retrieval library and the toolchain lock; the git tag `freeze-2026-10-06` marks the commit. `python3 bench/freeze.py --check` must print `unchanged` before any batch is reported.

## Rules in force for the new batches

Same as FREEZE.md: four candidates on flash (direct P0–P3, OpenCode, Claude Code) plus direct max, 27 tasks × 3 repeats; the repair loop of decision 022; retrieval of decision 023; separate task and design verdicts of decision 019; cost at list price of decision 021.
