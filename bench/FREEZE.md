# FREEZE

Sealed 2026-10-06 07:01 UTC at commit `d4a7230958e2` after the second review (`bench/tasks/t4_maritime_isr/heldout/REVIEW.md`).
Anything listed here is not edited while a matrix runs; a change means a new freeze and a new batch. `python3 bench/freeze.py --check` verifies the hashes.

## Task bank: 27 sealed tasks (hash over case.yaml, input/, gold/)

| Task | Type | SHA-256 |
|---|---|---|
| GEN-01 | GEN | `188e7c9399f5b95a` |
| GEN-02 | GEN | `4f7caed99bf978cf` |
| GEN-03 | GEN | `f2e20a70a68710b8` |
| GEN-04 | GEN | `06b0896e3d4f0582` |
| GEN-05 | GEN | `bb32fdf15a287644` |
| MOD-01 | MOD | `1b2437bbde3ba27e` |
| MOD-02 | MOD | `71ebe3e7cf779c3c` |
| MOD-03 | MOD | `ac183989ef867fc3` |
| MOD-04 | MOD | `87b631ba642bd9db` |
| MOD-05 | MOD | `a14ac06d67c86f15` |
| QRY-01 | QRY | `e58f73cfb8265158` |
| QRY-02 | QRY | `99d7d4bb3dd9d2cc` |
| QRY-03 | QRY | `a429ee0a7659b0c7` |
| QRY-04 | QRY | `57213dca541bee4d` |
| QRY-05 | QRY | `ef34f4c870f6da04` |
| AMB-01 | AMB | `8ee0003ebbc034b6` |
| AMB-02 | AMB | `a6e3bfc503e821ef` |
| AMB-03 | AMB | `c5550171906f37bd` |
| AMB-04 | AMB | `6bd1496d36fe1400` |
| RT-01 | RT | `5cfdd12573bd8a21` |
| RT-02 | RT | `207d6731cd59eced` |
| RT-03 | RT | `045d92e7d915c002` |
| RT-04 | RT | `9b3bd9ce253ade24` |
| RT-05 | RT | `14d1d8f0bed8b708` |
| ALN-01 | ALN | `f0e2e2b79aa0c664` |
| ALN-02 | ALN | `b94ed8f7d59ebbd8` |
| ALN-03 | ALN | `550e418575470c93` |

## Scoring, prompts, retrieval library, toolchain

| File | SHA-256 |
|---|---|
| `bench/score_task.py` | `b4050dee11751530` |
| `bench/score_answer.py` | `c4d4b46d50a4aeed` |
| `bench/score_alignment.py` | `5df06a175b208348` |
| `bench/experiment.py` | `f417df508cbc702e` |
| `agents/solve.py` | `979379f3dc59143f` |
| `agents/llm.py` | `ec3c55a31d5e0ae9` |
| `bench/vector_index.py` | `3ceb25d996b173e2` |
| `bench/graph_query.py` | `fd18be0d387b69bb` |
| `bench/corpus/sysml-syntax.md` | `2fa117caf5c74db2` |
| `bench/corpus/maritime-vocabulary.md` | `e6727de2756b6328` |
| `analysis/vector-index/examples/cards.json` | `66990cda5682d8f6` |
| `analysis/vector-index/examples/neighbors.json` | `f0af2ba24b09b71f` |
| `mvp/toolchain/kernel.lock.json` | `a1b1b06dcb6f87ce` |
| `mvp/engine.py` | `82000768d5f90234` |
| `mvp/toolchain/validate.py` | `67637aadb2a6d879` |

## Rules in force

- Official SysML v2 Pilot 0.62.0 (release 2026-08, kernel sha256 `5a015ed3f2b3d2da`); it is the only syntax judge.
- Task verdict and design verdict are separate (decision 019). Judges by model are not used (decision 025).
- Repair loop (decision 022): complete error list, one cumulative conversation, at most 20 repairs, stop after 3 identical resubmissions. P0 never repairs; P1, P2, P3 repair.
- Retrieval (decision 023): sentence-transformers/all-MiniLM-L6-v2, cosine ≥ 0.3 plus the exact-name bonus, one hop; the exam uses the official-examples library only.
- AMB: an imperative clarification request counts as asking; numbers with a unit that the statement does not contain count as invented. RT: phrases match after number-word and `.0` normalisation (second review, 2026-10-06).
- Candidates: direct qwen3.8-flash (P0–P3), OpenCode on qwen3.8-flash, Claude Code on qwen3.8-flash, direct qwen3.8-max (P0–P3); 3 repeats each.

## What will be compared (stated before the run)

- Within the direct candidates: P0→P1 isolates repair, P1→P2 the outline, P2→P3 retrieval; first-attempt pass inside each repaired cell is reported next to the final pass.
- Across candidates on the same model: the three ways of running flash, 27 tasks × 3 repeats each.
- No numeric target is pre-registered; the 2026-10-03 matrix (224/288 under its rules) is the archived point of comparison, not a baseline for the new rules.

## Amendments

**2026-10-06, after the scored batches (tag `freeze-2026-10-06-a1`).** By the user's decision, retrieval has no fallback. `agents/solve.py` (P3) and `bench/graph_query.py` no longer switch to a word ranking when the MiniLM + FAISS stack is missing; they raise. `bench/vector_index.py` loads the pinned MiniLM snapshot `1110a243fdf4706b3f48f1d95db1a4f5529b4d41` from the local cache, never from the network, names the install command when a package is missing, and has `--check` and `--download`; the package versions are pinned in `requirements-retrieval.txt`. Hashes before the amendment: `agents/solve.py` `12629456f89c8394`, `bench/vector_index.py` `d360376d10adbac1`, `bench/graph_query.py` `7a8e0754b66cc895`.

The scored batches stand without a rerun: all 162 P3 cells of the two direct batches recorded `hybrid` retrieval, so the removed branch never ran, and P3 retrieval with the amended code on the 27 task prompts reproduces the saved retrieval of all 162 cells exactly (same cards, same scores), with the network blocked.
