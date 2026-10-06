# Model judges and the Jev side benchmark (archived 2026-10-06)

These files are real records and are kept, but nothing on the results page, in STATUS.md or in the report reads them any more (decision 025).

| File | What it was |
|---|---|
| `jev-heldout-20261003.json`, `jev-mod05-20261003.json` | Jev 1.13 reading the 288 answers of the 2026-10-03 matrix: agreed with the official tool on 226/288, 32 false passes (all generate tasks), 30 false fails. |
| `validator-all-max.jsonl`, `validator-agreement.json` | qwen3.8-max reading the same answers: agreed on 157/288, 70 false passes. |
| `sysengbench-jev.json`, `sysengbench-ids.txt` | Jev answering SysEngBench questions 1–20 (20/20). Replaced by the same benchmark put to the four exam candidates: `analysis/side-sysengbench-*` (`bench/run_side.py`). |
| `scripts/` | The scripts that produced the files above (`run_jev_heldout.py`, `judge_all.py`, `validator_agreement.py`, `run_sysengbench.py`). They read paths that have moved and are kept for reference only. |

Conclusion carried into the report: a model judge is worse than the official tool plus the answer keys, so the benchmark has none. Jev cannot be an exam candidate either: its interface returns choices and scores, not text.
