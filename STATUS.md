# STATUS

Generated 2026-10-06 18:02 UTC by `python3 scripts/make_status.py` from saved results. All maritime numbers are synthetic, not RTX specifications. The official SysML v2 Pilot 0.62 is the only syntax judge; the answer keys are the ground truth; no model judges (decision 025).

Task bank: 27 sealed tasks, second review recorded in `bench/tasks/t4_maritime_isr/heldout/REVIEW.md`, frozen in `bench/FREEZE.md` (tag `freeze-2026-10-06-r2`).

## Scoring rule

A task passes when the official parse passes (GEN, MOD, ALN), every required name, connection or mapping is present, no number was invented, every value the task said to keep is unchanged, and every engineering check comes out as the key expects. Whether the design meets its budget is a separate design verdict (decision 019).

Freeze revision 2 (decision 028), after the batches and by the user's decisions: retrieval cards carry documentation text (every direct P3 cell rerun); MOD-01's key also checks the radio part and link it says to keep; AMB-02's key accepts "maximum power", "power budget" and "limit"; an AMB number counts as invented only when the answer also writes SysML. Saved answers were re-scored with the batches' own scoring code (`bench/rescore.py`); six cells changed from FAIL to PASS (`analysis/rescore-r2.json`).

## Four candidates on the 27 tasks

| Candidate | Cells | PASS | Rate | Repeat groups that disagree | Cost (USD, cn-beijing) |
|---|---|---|---|---|---|
| Direct · qwen3.8-flash | 324 | 270 | 83.3% | 23/108 | $0.0707 |
| Direct · qwen3.8-max | 324 | 313 | 96.6% | 8/108 | $0.9375 |
| OpenCode · qwen3.8-flash | 81 | 78 | 96.3% | 3/27 | $0.6817 |
| Claude Code · qwen3.8-flash | 81 | 78 | 96.3% | 2/27 | $0.5143 |

Direct candidates: 27 tasks × P0–P3 × 3 repeats; the system prompt carries the SysML rules (and the alignment rules for ALN), and P1–P3 repair with the full official diagnostics. Agents: 27 tasks × 3 repeats, each run in a bubblewrap sandbox with the task statement, AGENTS.md and `./validate` (the official Pilot) and nothing else: no SysML rules in the prompt, and the repository, answer keys, past runs and transcripts are not visible (decision 026). The agents' ALN rows come from a rerun with `./validate` in the scorer's file order (see the validator note below).

| Task type | flash | max | OpenCode | Claude Code |
|---|---|---|---|---|
| GEN | 53/60 | 60/60 | 14/15 | 15/15 |
| MOD | 60/60 | 60/60 | 14/15 | 14/15 |
| ALN | 19/36 | 33/36 | 8/9 | 7/9 |
| QRY | 46/60 | 58/60 | 15/15 | 15/15 |
| AMB | 39/48 | 42/48 | 12/12 | 12/12 |
| RT | 53/60 | 60/60 | 15/15 | 15/15 |

| Agent | Runs | PASS | Hit the 900 s limit | No answer.md | Runs that called ./validate | ./validate calls | Tokens (input, cached, output) |
|---|---|---|---|---|---|---|---|
| OpenCode · qwen3.8-flash | 81 | 78 | 2 | 2 | 68 | 151 | 23,274,893, 21,470,720, 463,909 |
| Claude Code · qwen3.8-flash | 81 | 78 | 2 | 3 | 69 | 134 | 17,398,757, 16,263,680, 414,434 |

**Validator note.** The official Pilot 0.62 can give a different verdict for the same files in a different order. An alignment package that writes a nested usage as `Pkg::part::sub` instead of `Pkg::part.sub` fails with `Must be an accessible feature (use dot notation for nesting)` when the source models are listed first, and passes when the package itself is listed first. The scorer always lists the sources first; the direct candidates' repair loop uses the scorer. Re-validating every graded ALN answer in the other order changed none of the 72 direct answers or the three gold packages, and 8 of the 15 ALN answers the agents submitted in their first sandboxed batch (three runs submitted none); in all 8 the agent had validated its package with its own file listed first. `./validate` now passes the files in the scorer's order, and every agent ALN run was rerun.

### Approaches, Direct · qwen3.8-flash (81 cells each)

| Approach | PASS | Official parse 1st attempt → final (39 SysML answers) | Repairs | Tokens | USD |
|---|---|---|---|---|---|
| P0 | 65 | 34 → 34 | 0 | 46,864 | $0.00873 |
| P1 | 68 | 33 → 36 | 17 | 79,551 | $0.0123 |
| P2 | 67 | 37 → 39 | 2 | 128,529 | $0.0242 |
| P3 | 70 | 35 → 39 | 4 | 139,996 | $0.0254 |

### Approaches, Direct · qwen3.8-max (81 cells each)

| Approach | PASS | Official parse 1st attempt → final (39 SysML answers) | Repairs | Tokens | USD |
|---|---|---|---|---|---|
| P0 | 77 | 39 → 39 | 0 | 46,939 | $0.1199 |
| P1 | 79 | 39 → 39 | 0 | 46,727 | $0.1188 |
| P2 | 78 | 39 → 39 | 0 | 127,836 | $0.3372 |
| P3 | 79 | 39 → 39 | 0 | 140,010 | $0.3616 |

## Failures by class

| Class | flash | max | OpenCode | Claude Code |
|---|---|---|---|---|
| aln-missing-pair | 14 | 3 | 0 | 0 |
| query-renamed | 14 | 2 | 0 | 0 |
| missed-topic | 9 | 6 | 0 | 0 |
| missing-phrase | 7 | 0 | 0 | 0 |
| syntax-connection | 6 | 0 | 0 | 0 |
| agent-timeout | 0 | 0 | 2 | 2 |
| checklist-missing | 2 | 0 | 0 | 0 |
| syntax-reference | 2 | 0 | 0 | 0 |
| no-sysml | 0 | 0 | 1 | 1 |

Details: `docs/failure_taxonomy.md`, `analysis/failure-classes-20261006.jsonl` (rebuilt by `python3 bench/classify_failures.py`).

## Side benchmarks named in the brief (not in the exam score)

| Candidate | SysEngBench | PURE |
|---|---|---|
| flash | 283/300 | 6/6 |
| max | 291/300 | 6/6 |
| OpenCode | 272/300 | 6/6 |
| Claude Code | 291/300 | 6/6 |

SysEngBench (rabell/SysEngBench, MIT): 100 questions fixed with seed 20261006 (`analysis/sysengbench/ids-100.txt`), 10 per prompt, 3 repeats. Always answering B scores 51/100 on this subset; the key is mostly B and C. PURE: the two sealed excerpts (EIRENE, CDN peering), 3 repeats, extracted sentences must equal the key.

## Runs that do not count

- OpenCode, workspace inside the repository (77/81, `analysis/opencode-qwen3.8-flash-20261006T070152`): The agent could read the whole repository and read answer keys in several runs, including the key of the task it was solving (GEN-01, GEN-02, GEN-05). Not a clean score.
- Claude Code, tools denied (60/81, `analysis/claude-qwen3.8-flash-20261006T070153`): Every Bash and Write call was denied (43 and 10), so the agent never ran the validator; not the same setup as OpenCode.
- OpenCode, ALN runs of the first sandboxed batch (6/9, `analysis/opencode-jail-qwen3.8-flash-20261006T133737`, replaced by `analysis/opencode-jail-aln-qwen3.8-flash-20261006T152723`): ./validate passed the files in the order the agent gave them, and the Pilot's verdict depends on that order: with the agent's own file first, 8 alignment packages (OpenCode 3, Claude Code 5) that fail in the scorer's order (sources first) passed the agent's check and were submitted. Every ALN run of both agents was rerun with ./validate in the scorer's order (decision 026); the rerun replaces these rows.
- Claude Code, ALN runs of the first sandboxed batch (1/9, `analysis/claude-jail-qwen3.8-flash-20261006T133739`, replaced by `analysis/claude-jail-aln-qwen3.8-flash-20261006T152725`): ./validate passed the files in the order the agent gave them, and the Pilot's verdict depends on that order: with the agent's own file first, 8 alignment packages (OpenCode 3, Claude Code 5) that fail in the scorer's order (sources first) passed the agent's check and were submitted. Every ALN run of both agents was rerun with ./validate in the scorer's order (decision 026); the rerun replaces these rows.
- flash, P3 cells retrieved with cards that lacked documentation text (69/81, `analysis/heldout-qwen3.8-flash-20261006T070150`, replaced by `analysis/heldout-p3doc-qwen3.8-flash-20261006T171547`): The paper 2 replication (decision 027) showed that the authors' node text carries each element's documentation and our retrieval cards did not. The cards now do, and every P3 cell of both direct batches was rerun under freeze revision 2 (decision 028); the rerun replaces these rows.
- max, P3 cells retrieved with cards that lacked documentation text (79/81, `analysis/heldout-qwen3.8-max-20261006T070151`, replaced by `analysis/heldout-p3doc-qwen3.8-max-20261006T171549`): The paper 2 replication (decision 027) showed that the authors' node text carries each element's documentation and our retrieval cards did not. The cards now do, and every P3 cell of both direct batches was rerun under freeze revision 2 (decision 028); the rerun replaces these rows.
- 2026-10-03 matrix (24 tasks, old repair loop, old AMB/RT rules): 224/288. qwen3.8-flash, P1 repair with 3 rounds and only the latest error lines, re-scored once on 2026-10-03; kept as the record of the old rules, not comparable cell for cell.

## Part 2 prototype: blank brief → requirements → two designs → Pilot → alignment → checks → human approval → memory

- `20261003T144105`: designs A PASS, B PASS; alignment package PASS; checks failing LINK, POWER; approved none.
- `20261003T144529`: designs A PASS, B PASS; alignment package PASS; checks all pass; approved A.
- `20261003T144850`: designs A PASS, B PASS; alignment package PASS; checks all pass; approved none.
- `20261003T150116`: designs A PASS, B PASS; alignment package PASS; checks all pass; approved A.
- `20261003T192328`: designs A PASS, B PASS; alignment package PASS; checks all pass; approved none.
- `20261004T042212`: designs A PASS, B PASS; alignment package PASS; checks all pass; approved none.
- `20261006T063010`: designs A PASS, B PASS; alignment package PASS (1 pairs declared); checks all pass; approved none.
- `20261006T063305`: designs A PASS, B PASS; alignment package PASS (5 pairs declared); checks all pass; approved none.

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

At the China (Beijing) list price checked 2026-10-03: the four scored batches and the side benchmarks $2.4481; everything recorded, including the discarded runs, graph retrieval, Part 2 and the MOD chain, about $3.9294. 4 Part 2 runs recorded only requirements, designs and trade-offs, not alignment and read-back; later runs record everything. 5 MOD change runs predate usage logging; later runs record everything. 5 Claude Code runs hit the 900 s limit before Claude Code reported its usage (it reports only when a run ends); their tokens are not in these sums, so Claude Code's cost is a lower bound. The paper 1 replication (4 calls, qwen3.8-max) and the trial runs of 2026-10-06 are recorded in their own folders and not summed here.

## Not done

- Human blind review with Cohen's κ; confidence intervals for the differences between approaches and candidates.
- A frontier model outside the Qwen family; the vendor AI (Cameo AI Assistant) and a second checker (Syside CLI).
- Tasks that must trigger the approval gate; interface tasks in the UMAA style (interoperability); a scored evaluation set for the Part 2 prototype; dynamic simulation beyond static budgets.
- A reproduction on a clean machine (fresh clone, `requirements-retrieval.txt`, tests, one batch re-scored).
