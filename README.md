# RTRC · Agentic AI for Systems Engineering Discovery and Design

**SysML-AgentBench** — a reproducible benchmark of AI agents that translate requirements into SysML v2 models, evaluated on a synthetic maritime ISR scenario with the official SysML v2 toolchain as adjudicator.

Sponsor: RTX Technology Research Center (RTRC). Faculty advisor: Prof. George Bollas (UConn). Team: Thomas Johanns, Tianchonghui Fang, Tedi Naqo.

## Start here

| Document | Purpose |
|---|---|
| [`STATUS.md`](STATUS.md) | **Current numbers**, generated from saved results by `python3 scripts/make_status.py` |
| `python3 bench/exam_board.py` → http://127.0.0.1:8770/ | Results page and demo: the 288-cell exam cell by cell, live runs, the MOD change chain, the Part 2 prototype, cost |
| [`analysis/report/exam-20261003/index.html`](analysis/report/exam-20261003/index.html) | Exam report, rebuilt by `python3 analysis/report/build_exam_report.py` |
| [`docs/report/D4-初稿.md`](docs/report/D4-初稿.md) | Report draft |
| [`docs/failure_taxonomy.md`](docs/failure_taxonomy.md) | The 64 failures by class |
| [`docs/decisions/`](docs/decisions/) | Decision records; 016–021 (2026-10-03) override the plan where they differ |
| [`plans/SysML_AgentBench_完整执行计划.md`](plans/SysML_AgentBench_完整执行计划.md) | Execution plan v2.0 (Chinese): deliverables, ground-truth method, task suite, schedule, decisions §18 |
| [`plans/project-statement.md`](plans/project-statement.md) | Project statement v1.1 for sponsor signature (English) |
| [`research/source-extracts/rtx-brief.txt`](research/source-extracts/rtx-brief.txt) | Sponsor brief (verbatim) |
| [`mvp/README.md`](mvp/README.md) | Official toolchain, engine checks and evidence layer, used as the syntax adjudicator |

Scoring rule since 2026-10-03 (decision 019): a task passes when the official parse passes, required names and connections are present, no number was invented, kept values are unchanged, and engineering checks match the answer key. Whether the design meets its budget is a separate design verdict. Archived results files are not rewritten; `analysis/rescore-20261003.jsonl` holds the re-scored statuses.

## Repository layout

```
mvp/          official SysML v2 toolchain (pinned), engine, evidence packs; mvp/runs/ and mvp/agent-runs/ hold every run (git-ignored)
agents/       P0–P3 (solve.py), LLM client with usage logging (llm.py), approval gate, LangGraph read-only view (exam_graph.py)
bench/        tasks (t0 calibration, t4 maritime ISR, t5 requirements), scorers, runners, re-scoring, exam page
tools/        tool functions and MCP server used by the external agents
scenario/     synthetic maritime ISR reference model
datasets/     external data registry: source, date, SHA-256, license (SOURCES.md)
analysis/     saved results, re-scoring overlay, failure classes, memory of approved designs, report, archive/
docs/         decisions/, failure taxonomy, report draft
scripts/      make_status.py
research/     literature review, paper artifacts, audits (read-only history)
plans/        plan and project statement
vendor/       symlink to full upstream clones (not in git; recreate with `python3 -m mvp.bootstrap --all-references`)
```

## Quick checks

```bash
python3 -m unittest discover -s mvp/tests -v      # 11 toolchain boundary tests
python3 -m unittest bench.test_score_pwr01 bench.test_score_answer   # scoring rule tests
python3 bench/validate_gold.py                    # every gold reference passes its own answer list
python3 -m mvp.engine baseline                    # real official toolchain run → mvp/runs/<id>/
python3 bench/exam_board.py                       # results page at http://127.0.0.1:8770/
```

## Rules (do not violate)

1. Checks read the **parsed** official model, never input forms or LLM claims.
2. SysML PASS ≠ engineering acceptance; engineering status is UNKNOWN without evidence.
3. Requirement decisions are human-owned; no agent self-approval.
4. All maritime values are **synthetic**; never present them as RTX specifications.
5. Public/synthetic data only; no EAR/ITAR; register every external source in `datasets/SOURCES.md`.
6. Do not modify `vendor/`; the toolchain is pinned and hashed.
7. Gold answers are visible only to the scorer process, never to agents, retrieval indexes, or few-shot prompts.
