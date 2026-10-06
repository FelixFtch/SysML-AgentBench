# FREEZE

Sealed 2026-10-06 17:14 UTC at commit `f4f97ee3587a` after the second review (`bench/tasks/t4_maritime_isr/heldout/REVIEW.md`).
Anything listed here is not edited while a matrix runs; a change means a new freeze and a new batch. `python3 bench/freeze.py --check` verifies the hashes.

## Task bank: 27 sealed tasks (hash over case.yaml, input/, gold/)

| Task | Type | SHA-256 |
|---|---|---|
| GEN-01 | GEN | `db196f783327b147` |
| GEN-02 | GEN | `ca4806d7c02f8987` |
| GEN-03 | GEN | `86231c59c7fda413` |
| GEN-04 | GEN | `ebc30611eca82222` |
| GEN-05 | GEN | `b2ad121599ec8f30` |
| MOD-01 | MOD | `8478eac7de1e5cf7` |
| MOD-02 | MOD | `78b033d37c7bba7c` |
| MOD-03 | MOD | `895dc917cea8fdf4` |
| MOD-04 | MOD | `90d242658d127541` |
| MOD-05 | MOD | `8b5a1d7a088eabbc` |
| QRY-01 | QRY | `1b6750f084510558` |
| QRY-02 | QRY | `7c57180f3e2b30a1` |
| QRY-03 | QRY | `4f883669496895f9` |
| QRY-04 | QRY | `fb0b5c01f26cd701` |
| QRY-05 | QRY | `d5c087d82bf5e235` |
| AMB-01 | AMB | `56da8772259af35e` |
| AMB-02 | AMB | `741dc1a09f047b39` |
| AMB-03 | AMB | `b929b6a75382390f` |
| AMB-04 | AMB | `2d2da6d9681718c5` |
| RT-01 | RT | `06d8e33d9d03a70e` |
| RT-02 | RT | `a93c6fdb4287302a` |
| RT-03 | RT | `19f65d7b37b6b817` |
| RT-04 | RT | `1a567383f9103a6a` |
| RT-05 | RT | `1ccb24519b22f96b` |
| ALN-01 | ALN | `06d46988b750f662` |
| ALN-02 | ALN | `311424d69d2a8c54` |
| ALN-03 | ALN | `c53e1a6524254254` |

## Scoring, prompts, retrieval library, toolchain

| File | SHA-256 |
|---|---|
| `bench/score_task.py` | `b4050dee11751530` |
| `bench/score_answer.py` | `c98fcf5539c7f950` |
| `bench/score_alignment.py` | `5df06a175b208348` |
| `bench/experiment.py` | `f417df508cbc702e` |
| `agents/solve.py` | `979379f3dc59143f` |
| `agents/llm.py` | `ec3c55a31d5e0ae9` |
| `bench/vector_index.py` | `3ceb25d996b173e2` |
| `bench/graph_query.py` | `33f644a0e79cbfbe` |
| `bench/corpus/sysml-syntax.md` | `2fa117caf5c74db2` |
| `bench/corpus/maritime-vocabulary.md` | `e6727de2756b6328` |
| `analysis/vector-index/examples/cards.json` | `cdc2b2cd31e28315` |
| `analysis/vector-index/examples/neighbors.json` | `39620e3c3268416c` |
| `mvp/toolchain/kernel.lock.json` | `a1b1b06dcb6f87ce` |
| `mvp/engine.py` | `82000768d5f90234` |
| `mvp/toolchain/validate.py` | `67637aadb2a6d879` |

## Rules in force

- Official SysML v2 Pilot 0.62.0 (release 2026-08, kernel sha256 `5a015ed3f2b3d2da`); it is the only syntax judge.
- Task verdict and design verdict are separate (decision 019). Judges by model are not used (decision 025).
- Repair loop (decision 022): complete error list, one cumulative conversation, at most 20 repairs, stop after 3 identical resubmissions. P0 never repairs; P1, P2, P3 repair.
- Retrieval (decisions 023, 027): sentence-transformers/all-MiniLM-L6-v2, cosine ≥ 0.3 plus the exact-name bonus, one hop; cards carry each element's documentation text; the exam uses the official-examples library only.
- AMB: an imperative clarification request counts as asking; a number with a unit that the statement does not contain counts as invented only when the answer also writes SysML (decision 028). RT: phrases match after number-word and `.0` normalisation (second review, 2026-10-06).
- Candidates: direct qwen3.8-flash (P0–P3), OpenCode on qwen3.8-flash, Claude Code on qwen3.8-flash, direct qwen3.8-max (P0–P3); 3 repeats each.

## What will be compared (stated before the run)

- Within the direct candidates: P0→P1 isolates repair, P1→P2 the outline, P2→P3 retrieval; first-attempt pass inside each repaired cell is reported next to the final pass.
- Across candidates on the same model: the three ways of running flash, 27 tasks × 3 repeats each.
- No numeric target is pre-registered; the 2026-10-03 matrix (224/288 under its rules) is the archived point of comparison, not a baseline for the new rules.

## History

- **`freeze-2026-10-06`**: sealed 2026-10-06 07:01 UTC at commit `d4a7230958e2` after the second review. The four batches of 2026-10-06 ran under it.
- **`freeze-2026-10-06-a1`**: amendment after the batches. Retrieval lost its word-ranking fallback; the stack and the MiniLM snapshot were pinned (`agents/solve.py`, `bench/vector_index.py`, `bench/graph_query.py`). All 162 scored P3 cells had used hybrid retrieval, and the amended code reproduced their saved retrieval exactly, so no batch changed.
- **`freeze-2026-10-06-r2`** (this file): revision 2, by the user's decisions of 2026-10-06 (decision 028). Retrieval cards carry each element's documentation text (decision 027; `bench/graph_query.py`, the examples library rebuilt from the same official parses). MOD-01's key also checks the radio part and link the statement says to keep. AMB-02 also accepts "maximum power", "power budget" and "limit". An AMB number counts as invented only when the answer also writes SysML (`bench/score_answer.py`). The review fields of every `case.yaml` and key record the second review. The files under `gold/` were edited at the user's explicit decision. Saved answers are re-scored under these keys by `bench/rescore.py` (`results-r2.jsonl` next to each `results.jsonl`, which stays as run), and every P3 cell of both direct batches is rerun (`analysis/heldout-p3doc-*`).
