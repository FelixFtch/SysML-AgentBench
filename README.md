# RTRC · Agentic AI for Systems Engineering Discovery and Design

**SysML-AgentBench** — a reproducible benchmark of AI agents that translate requirements into SysML v2 models, evaluated on a synthetic maritime ISR scenario with the official SysML v2 toolchain as adjudicator.

Sponsor: RTX Technology Research Center (RTRC). Faculty advisor: Prof. George Bollas (UConn). Team: Thomas Johanns, Tianchonghui Fang, Tedi Naqo.

## Start here

| Document | Purpose |
|---|---|
| [`STATUS.md`](STATUS.md) | **Current numbers**, generated from saved results by `python3 scripts/make_status.py` |
| `python3 bench/exam_board.py` → http://127.0.0.1:8770/ | Results page and demo: the 27-task exam cell by cell for four candidates, live runs, the MOD change chain, the Part 2 prototype, cost |
| `scripts/langflow.sh --import` → http://127.0.0.1:7860/ · [`langflow/README.md`](langflow/README.md) | Langflow 1.12.5: the **RTRC design assistant** (talk to it; OpenCode on the local Qwen3.8-27B over our tools and memory; also `scripts/assistant.sh` in the terminal), the same assistant **unfolded** on the canvas (one card per tool, the pipeline as a flow run as a tool, approval as a card) and the fixed benchmark flows (agent flow with a person's decision, the same flow on the local model, memory, exam cells, results, MOD chain, Cameo check); Qwen only |
| [`analysis/report/exam-20261006/index.html`](analysis/report/exam-20261006/index.html) | Exam report, rebuilt by `python3 analysis/report/build_exam_report.py` |
| [`docs/report/D4-draft.md`](docs/report/D4-draft.md) | Report draft (D4) |
| [`docs/knowledge-base/`](docs/knowledge-base/README.md) | Process knowledge base (D7): the process, Pilot notes, what helps, evaluating agents fairly, extending the bank, glossary |
| [`docs/failure_taxonomy.md`](docs/failure_taxonomy.md) | The failures of the four candidates by class |
| [`bench/FREEZE.md`](bench/FREEZE.md) · [`REVIEW.md`](bench/tasks/t4_maritime_isr/heldout/REVIEW.md) | What is frozen (hashes, tag `freeze-2026-10-06-r2`, with the history of the freeze) and the second review of the 27 answer keys |
| [`docs/decisions/`](docs/decisions/) | Decision records; 016–027 (2026-10-03 to 2026-10-06) override the plan where they differ |
| [`plans/execution-plan-v2.md`](plans/execution-plan-v2.md) | Execution plan v2.0: deliverables, ground-truth method, task suite, schedule, decisions §18 |
| [`plans/project-statement.md`](plans/project-statement.md) | Project statement v1.1 for sponsor signature (English) |
| [`research/source-extracts/rtx-brief.txt`](research/source-extracts/rtx-brief.txt) | Sponsor brief (verbatim) |
| [`mvp/README.md`](mvp/README.md) | Official toolchain, engine checks and evidence layer, used as the syntax adjudicator |

Scoring (decisions 019, 025): a task passes when the official parse passes (GEN, MOD, ALN), every required name, connection or mapping is present, no number was invented, every value to keep is unchanged, and every engineering check comes out as the answer key expects. Whether the design meets its budget is a separate design verdict. Only the official Pilot and the keys score; no model judges.

Candidates (bench/batches.py): direct qwen3.8-flash and direct qwen3.8-max, 27 tasks × P0–P3 × 3 repeats; OpenCode and Claude Code on qwen3.8-flash, 27 tasks × 3 repeats, in a bubblewrap sandbox that shows only the task input, the rules and `./validate` (decision 026). The agents' ALN rows come from a rerun after `./validate` was made to pass files in the scorer's order: the official Pilot's verdict on an alignment package can depend on that order (`bench/check_validator_order.py`).

## Repository layout

```
mvp/          official SysML v2 toolchain (pinned), engine, evidence packs; mvp/runs/ and mvp/agent-runs/ hold every run (git-ignored)
agents/       P0–P3 and the repair loop (solve.py), LLM client with usage logging (llm.py), approval gate, LangGraph read-only view,
              external/ (OpenCode runner, the agent sandbox jail.py)
bench/        tasks (t4 maritime ISR, t5 requirements), scorers, runners, batches.py, freeze and review tools, the results page
tools/        tool functions and MCP server
scenario/     synthetic maritime ISR reference model
datasets/     external data registry: source, date, SHA-256, license (SOURCES.md)
analysis/     scored batches, side benchmarks, failure classes, retrieval library, memory of approved designs, report, archive/
docs/         decisions/, failure taxonomy, report draft
scripts/      make_status.py
research/     literature review, paper artifacts, audits (read-only history)
plans/        plan and project statement
vendor/       symlink to full upstream clones (not in git; recreate with `python3 -m mvp.bootstrap --all-references`)
```

## Quick checks

Retrieval (paper 2) is MiniLM + FAISS only, with pinned versions: `pip install --user -r requirements-retrieval.txt`, then `python3 bench/vector_index.py --check` (versions, the pinned MiniLM snapshot, a test search). Without them retrieval stops with an error; there is no other ranking, and the results page refuses to start. (`rdflib` is needed only to rerun the paper 2 authors' code under `research/`.) The exam's retrieval library is built once with `python3 bench/build_examples_library.py` (official SysML-v2-Release examples through the Pilot, about 7 minutes). The agent sandbox needs `bwrap` (bubblewrap). Model diagrams on the page (`bench/model_diagram.py`: any officially parsed model, drawn from its parse, plus the Pilot's own tree view) need Graphviz in `tools/graphviz`: `micromamba create -p tools/graphviz -c conda-forge graphviz`.

```bash
python3 -m unittest discover -s mvp/tests -v      # 11 toolchain boundary tests
python3 -m unittest bench.test_score_pwr01 bench.test_score_answer   # scoring rule tests
python3 bench/validate_gold.py                    # every gold reference passes its own answer list
python3 bench/review_gold.py                      # mechanical second-review checks over the 27 keys
python3 bench/freeze.py --check                   # the frozen files are unchanged
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
7. Gold answers are visible only to the scorer process, never to agents, retrieval indexes, or few-shot prompts; agents run in the sandbox, and the results page server is not running while they do.
