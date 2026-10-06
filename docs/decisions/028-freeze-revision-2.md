# 028 · Freeze revision 2: documentation in retrieval cards, three key fixes, saved answers re-scored, P3 rerun

Date: 2026-10-06. Status: accepted (user decisions of 2026-10-06). Tag `freeze-2026-10-06-r2`. Affects `bench/graph_query.py`, `bench/build_examples_library.py`, `analysis/vector-index/examples/`, `bench/score_answer.py`, `bench/test_score_answer.py`, `bench/tasks/t4_maritime_isr/heldout/*/case.yaml`, `heldout/MOD-01/gold/assertions.yaml`, `heldout/AMB-02/gold/assertions.yaml`, the review field of every key, `bench/batches.py`, `bench/rescore.py` (new), `bench/freeze.py`.

## Changes

1. **Retrieval cards carry documentation text** (decision 027). `build_graph` appends `doc: <text>` to the card of every element that has a `doc` comment, as the paper 2 authors' node text does. The exam's examples library was rebuilt from the same official parses (`bench/build_examples_library.py --from-runs`): 761 cards, of which 14 gained documentation text, the rest unchanged; neighbour lists are now written sorted, so a rebuild gives the same file. With the new library, P3 retrieval changes for GEN-04 and GEN-05 and is identical for the other 25 tasks; by the user's decision every P3 cell of both direct batches was rerun anyway.
2. **MOD-01 checks what it says to keep.** The statement says "Keep the existing camera, AIS, and radio connections"; the key checked the camera and AIS links only. It now also requires `UsvPlain::usv::radio` and the link `processor.uplink → radio.fromProcessor`. No saved answer changes verdict: none of the 30 MOD-01 answers dropped the radio.
3. **AMB-02 accepts more ways to ask for the limit.** Besides "watt", "power limit" and "how many watts", the key accepts "maximum power", "power budget" and "limit". Three saved answers change from FAIL to PASS, exactly the three that asked for the limit in other words: direct flash P0 repeats 2 and 3 ("What is the target maximum power consumption value and unit?") and direct max P2 repeat 3 ("What numerical value, limit, or baseline (and its unit) should be used…"). The seven that asked about voltage, units, output power or the meaning of "vessel" still fail.
4. **An AMB number counts as invented only when the answer also writes SysML.** The AMB statements say "ask, do not invent a value and do not write SysML". An answer that asks the right question and writes no model may now show an example format or arithmetic from the statement; the numbers are still listed (`numbers_not_counted`). Three saved answers change from FAIL to PASS, all agent clarifications: OpenCode AMB-02 repeat 2 ("e.g. `<= 450 W`") and Claude Code AMB-03 repeats 1 and 3 ("128 GB / 30 days ≈ 4.27 GB/day", which the answers say must not be used). No direct answer changes. A new test covers both sides of the rule.
5. **The review fields record the second review.** Every `case.yaml` now reads `status: reviewed` and `second_reviewer: the assistant, 2026-10-06 (REVIEW.md)`, every key `status: reviewed`. No verdict depends on these fields.

The files under `gold/` were edited at the user's explicit decision; the workspace rule that keeps `gold/` read-only applies to the candidates and to unrequested edits. Before the edits, a dry run with the scoring code reproduced every saved AMB verdict and showed exactly the six changes above.

## How the scores follow

- `bench/rescore.py` re-scores the saved answers of the four scored batches with the batch's own `grade()`: AMB rows from the saved answer text, MOD-01 rows from the saved official parse. It writes `results-r2.jsonl` next to each `results.jsonl`, which stays as run, and `analysis/rescore-r2.json` with the six changed rows. `bench/batches.py` reads `results-r2.jsonl` where it exists.
- The P3 cells of both direct batches were rerun under revision 2 (`analysis/heldout-p3doc-qwen3.8-flash-*`, `…-max-*`); `bench/batches.py` takes P3 rows from the rerun and lists the earlier P3 rows as superseded, with their cost.
- Graph-retrieval queries and the retrieval evaluation were rerun with the new cards.

## Results

- **P3 rerun** (`analysis/heldout-p3doc-qwen3.8-flash-20261006T171547`, `…-max-20261006T171549`): flash 70 of 81 (69 before), max 79 of 81 (79 before). The two tasks whose retrieval changed, GEN-04 and GEN-05, pass in all three repeats before and after for both models, so the documentation text changed no outcome here. On the other 25 tasks the P3 prompts were byte-identical in both runs, and 9 of 75 flash cells and 2 of 75 max cells changed verdict anyway: a direct measure of the spread between runs.
- **Retrieval evaluation** (`analysis/retrieval-eval-20261006T171839.json`): unchanged, hybrid 13 of 15 key elements. **Graph-retrieval queries** (`analysis/graph-query-20261006T171913.json`): 5 of 5, as before.
- **Totals under revision 2:** direct flash 270 of 324 (267 before: +2 from AMB-02, +1 from the P3 rerun), direct max 313 of 324 (312: +1 from AMB-02), OpenCode 78 of 81 (77: +1), Claude Code 78 of 81 (76: +2). The superseded P3 rows and their cost are listed with the discarded runs.

## What would reverse it

A key revision that a second human reviewer does not accept, or a P3 rerun that shows the documentation text hurting retrieval on a larger library.
