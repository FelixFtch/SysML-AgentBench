# SysML-AgentBench · RTRC Agentic AI for Systems Engineering

A reproducible benchmark of AI agents that translate requirements into SysML v2 models, scored only by the official SysML v2 toolchain and answer keys written in advance, on a synthetic maritime ISR scenario; and a set of Langflow flows that run those agents, let you talk to them, and let you build and examine your own.

Sponsor: RTX Technology Research Center (RTRC). Faculty advisor: Prof. George Bollas (UConn). Team: Thomas Johanns, Tianchonghui Fang, Tedi Naqo. Every maritime number is synthetic and is not an RTX specification.

## Two doors

<table>
<tr>
<td width="50%" valign="top">

### Langflow — use and build flows

Talk to the agents, change a flow, build your own flow or tool, use your own API key or a local Ollama model.

→ [`langflow/README.md`](langflow/README.md)
→ [1 · Install](docs/langflow/01-install.md) · [2 · Keys and models](docs/langflow/02-keys-and-models.md) · [3 · Import](docs/langflow/03-import-flows.md) · [6 · Make your own](docs/langflow/06-make-your-own.md)

```bash
python scripts/up.py --import    # → http://127.0.0.1:7860 (all systems; macOS/Linux also: scripts/langflow.sh --import)
```

</td>
<td width="50%" valign="top">

### Benchmark — the exam and the results page

See every score, open a cell end to end, run one task, examine your own flow and put it on the page, replace the tasks with real ones.

→ [`docs/benchmark/README.md`](docs/benchmark/README.md)
→ [1 · Open the page](docs/benchmark/01-open-the-page.md) · [4 · Examine your flow](docs/benchmark/04-exam-your-flow.md) · [6 · The task bank](docs/benchmark/06-task-bank.md)

```bash
python3 bench/exam_board.py      # → http://127.0.0.1:8770
```

</td>
</tr>
</table>

New here: [`docs/START-HERE.md`](docs/START-HERE.md) (ten minutes, what you need, where things are). Want to contribute a flow, a card or a column: [`CONTRIBUTING.md`](CONTRIBUTING.md).

## What the numbers say

27 sealed tasks (generate, modify, align, query, ask-when-ambiguous, round-trip), scored only by the official SysML v2 Pilot 0.62 and the keys. Frozen results (`bench/FREEZE.md`, tag `freeze-2026-10-06-r2`): direct qwen3.8-max 313/324, direct qwen3.8-flash 270/324, OpenCode and Claude Code on flash in the sandbox 78/81 each; the three Langflow agent flows on flash 81, 81 and 79 of 81. The same matrix on the local 3-bit Qwen3.8-27B: direct 196/324, OpenCode 60/81, Claude Code 68/81, Langflow Agent Pilot only 71/81, Langflow Agent with memory 80/81 (`analysis/langflow-exam-*-local27b-*/summary.json`); OpenCode with memory on the local model is still running. All of it, cell by cell, is on the results page; the current numbers are generated into [`STATUS.md`](STATUS.md) by `python3 scripts/make_status.py`.

Scoring rule (decisions 019, 025): a task passes when the official parse passes (GEN, MOD, ALN), every required name, connection or mapping is present, no number was invented, every value to keep is unchanged, and every engineering check comes out as the key expects. Whether a design meets its budget is a separate design verdict. No model judges.

## Repository layout

```
langflow/     flows/ (the flow files, one folder per Langflow project) · components/rtrc/ (the cards) · scripts/ (build, import, export, set-up)
bench/        tasks (t4 maritime ISR, t5 requirements), scorers, runners, batches.py, freeze and review tools, the results page, the shell service
agents/       P0–P3 and the repair loop (solve.py), the model client (llm.py), the local-model dispatcher (llm_local.py),
              external/ (the sandbox jail.py, the OpenCode runner)
mvp/          the pinned official SysML v2 toolchain, the engine, evidence packs; mvp/runs/ and mvp/agent-runs/ hold every run (git-ignored)
tools/        the RTRC tools as an MCP server (assistant_mcp.py), the OpenCode assistant workspace, Ollama model files
scenario/     the synthetic maritime ISR reference model
analysis/     every score file the page reads: the frozen batches, the local-27B rerun, the Langflow exam columns, side benchmarks, the memory
docs/         langflow/ and benchmark/ (the two doors), decisions/ (why things are the way they are), knowledge-base/, report/
datasets/     external data registry: source, date, SHA-256, license
research/     literature review, paper artifacts, audits (read-only history)
plans/        plan and project statement
vendor/       upstream clones (not in git; `python3 -m mvp.bootstrap --all-references`)
```

Further reading: the exam report [`analysis/report/exam-20261006/index.html`](analysis/report/exam-20261006/index.html), the report draft [`docs/report/D4-draft.md`](docs/report/D4-draft.md), the process knowledge base [`docs/knowledge-base/`](docs/knowledge-base/README.md), the failure taxonomy [`docs/failure_taxonomy.md`](docs/failure_taxonomy.md), the second review of the keys [`REVIEW.md`](bench/tasks/t4_maritime_isr/heldout/REVIEW.md), the decision records [`docs/decisions/`](docs/decisions/), the plan [`plans/execution-plan-v2.md`](plans/execution-plan-v2.md), the sponsor brief [`research/source-extracts/rtx-brief.txt`](research/source-extracts/rtx-brief.txt), the toolchain [`mvp/README.md`](mvp/README.md).

## Quick checks

```bash
python3 -m unittest discover -s mvp/tests -v                         # toolchain boundary tests
python3 -m unittest bench.test_score_pwr01 bench.test_score_answer   # scoring rule tests
python3 bench/validate_gold.py                                       # every gold reference passes its own answer list
python3 bench/review_gold.py                                         # mechanical second-review checks over the 27 keys
python3 bench/freeze.py --check                                      # the frozen files are unchanged
python3 bench/vector_index.py --check                                # retrieval: versions, the pinned MiniLM snapshot, a test search
python3 -m mvp.engine baseline                                       # a real official toolchain run → mvp/runs/<id>/
```

Retrieval (paper 2) is MiniLM + FAISS only, pinned in `requirements-retrieval.txt` (included by `requirements-bench.txt`); the exam's retrieval library is built once with `python3 bench/build_examples_library.py`. The agent sandbox needs `bwrap` (bubblewrap, Linux). Model diagrams on the page need Graphviz in `tools/graphviz` (`micromamba create -p tools/graphviz -c conda-forge graphviz`).

## Rules (do not violate)

1. Checks read the **parsed** official model, never input forms or LLM claims.
2. SysML PASS ≠ engineering acceptance; engineering status is UNKNOWN without evidence.
3. Requirement decisions are human-owned; no agent self-approval.
4. All maritime values are **synthetic**; never present them as RTX specifications.
5. Public/synthetic data only; no EAR/ITAR; register every external source in `datasets/SOURCES.md`.
6. Do not modify `vendor/`; the toolchain is pinned and hashed.
7. Gold answers are visible only to the scorer process, never to agents, retrieval indexes, or few-shot prompts; sandboxed agents run while the results page server is stopped.
8. No key in any committed file: keys live in `.env` and in Langflow's Global Variables, both outside git.
