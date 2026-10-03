# STATUS

Generated 2026-10-03 19:39 UTC by `python3 scripts/make_status.py` from saved results. All maritime numbers are synthetic, not RTX specifications. Official SysML v2 Pilot 0.62 is the syntax adjudicator.

## Scoring rule (changed 2026-10-03)

A task passes when the official parse passes, every required name and connection is present, no number was invented, every value the task said to keep is unchanged, and every engineering check comes out as the answer key expects. Whether the design meets its budget is reported separately as the design verdict.

The old rule scored MOD-05 honest answers FAIL and would have scored a raised limit PASS (checked with four hand-written probes). All 143 saved GEN/MOD answers were re-scored from their official parses; 15 changed, all honest MOD-05 answers. Archived results files are unchanged; see `analysis/rescore-20261003.jsonl` and `docs/decisions/019-task-verdict-vs-design-verdict.md`.

## Main matrix: qwen3.8-flash, 24 held-out tasks × P0–P3 × 3 repeats

Total 224/288 PASS (archived rule: 212).

| Configuration | PASS | FAIL | Tokens | Cost (USD, cn-beijing list price) |
|---|---|---|---|---|
| P0 | 57 | 15 | 31,190 | $0.00510 |
| P1 | 51 | 21 | 50,377 | $0.00855 |
| P2 | 58 | 14 | 89,059 | $0.0160 |
| P3 | 58 | 14 | 105,304 | $0.0183 |

| Task type | PASS | Cells |
|---|---|---|
| GEN | 26 | 60 |
| MOD | 60 | 60 |
| QRY | 43 | 60 |
| AMB | 38 | 48 |
| RT | 57 | 60 |

Repeat stability: 23 of 96 task × configuration groups gave different results across the three repeats (AMB-01, AMB-02, AMB-04, GEN-01, GEN-02, GEN-04, QRY-01, QRY-02, QRY-03, QRY-04).

## Failures (64)

| Class | Cells |
|---|---|
| syntax-real-or-import | 22 |
| query-renamed | 16 |
| syntax-connection | 8 |
| missed-topic | 6 |
| syntax-other | 4 |
| no-question | 4 |
| missing-phrase | 3 |
| query-wrong-number | 1 |

Details: `docs/failure_taxonomy.md`, `analysis/failure-classes.jsonl`.

## Off-the-shelf agents (separate cohorts, not added to the 288)

- OpenCode v1.18.27 on qwen3.8-flash: 21/24. MOD-02, MOD-03 and MOD-04 produced no SysML package. Cost $0.1389 for 24 tasks, mostly cached re-reads of the workspace.
- Claude Code through CCR on qwen3.8-max: 24/24 after re-running the first run's GEN-04 failure and two timeouts (MOD-01, QRY-02). Token use was not recorded.

## Model judges (not scored)

- Jev 1.13: agrees with the tool on 226/288; 32 false passes, all GEN; 30 false fails (mostly AMB).
- qwen3.8-max: agrees on 157/288; 70 false passes.
- Both judges were told that an over-budget design does not pass, so they are compared with the design verdict. Only MOD-05 differs between the two verdicts.

## Part 2 prototype: blank brief → requirements → two designs → Pilot → alignment → checks → human approval → memory

- `20261003T144105`: designs A PASS, B PASS; alignment package PASS; checks failing LINK, POWER; approved none.
- `20261003T144529`: designs A PASS, B PASS; alignment package PASS; checks all pass; approved A.
- `20261003T144850`: designs A PASS, B PASS; alignment package PASS; checks all pass; approved none.
- `20261003T150116`: designs A PASS, B PASS; alignment package PASS; checks all pass; approved A.
- `20261003T192328`: designs A PASS, B PASS; alignment package PASS; checks all pass; approved none.

Memory (`analysis/memory/approved.jsonl`): 2 approved designs (20261003T144529 A, 20261003T150116 A). Approved designs are retrieved by the next run.

## MOD change chain (latest run per task, qwen3.8-max)

| Task | Task verdict | Design verdict | Kept values | Read-back numbers |
|---|---|---|---|---|
| MOD-01 | PASS | n/a | 1/1 | 1/1 |
| MOD-02 | PASS | n/a | 0/0 | 0/0 |
| MOD-03 | PASS | n/a | 0/0 | 0/0 |
| MOD-04 | PASS | n/a | 1/1 | 1/1 |
| MOD-05 | PASS | FAIL | 4/4 | 4/4 |

## Cost

Recorded spend at list price (China Beijing region, checked 2026-10-03): about $0.2639. Not recorded: the qwen3.8-max judge over 288 answers; Claude Code's 28 answers through CCR; the two PURE tasks; alignment and read-back calls in 4 Part 2 runs; 5 MOD change runs made before usage logging. Part 2 and MOD runs made after 2026-10-03 19:00 UTC record every call.

## Not done

- Second reviewer for the 24 answer keys; `bench/FREEZE.md` and a freeze tag.
- Human blind review with Cohen's κ; confidence intervals for the configuration differences.
- A frontier model and a qwen3.8-max run of the full matrix; graph retrieval as a P3 sub-configuration.
- Alignment tasks with an answer key (paper 1) and tasks that must trigger the approval gate.
- Second checker (Syside CLI) and vendor AI (Cameo AI Assistant); SysMBench 151 has no license file.
- A scored evaluation set for the Part 2 prototype; dynamic simulation beyond static budget checks.
