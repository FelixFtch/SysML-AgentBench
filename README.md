# RTRC · Agentic AI for Systems Engineering Discovery and Design

**SysML-AgentBench** — a reproducible benchmark of AI agents that translate requirements into SysML v2 models, evaluated on a synthetic maritime ISR scenario with the official SysML v2 toolchain as adjudicator.

Sponsor: RTX Technology Research Center (RTRC). Faculty advisor: Prof. George Bollas (UConn). Team: Thomas Johanns, Tianchonghui Fang, Tedi Naqo.

## Start here

| Document | Purpose |
|---|---|
| [`plans/SysML_AgentBench_完整执行计划.md`](plans/SysML_AgentBench_完整执行计划.md) | **Authoritative execution plan v2.0** (Chinese): what we deliver, ground-truth method, architecture, task suite, agents, scoring, 12-week schedule, decisions |
| [`plans/project-statement.md`](plans/project-statement.md) | Project statement v1.1 for sponsor signature (English) |
| [`research/source-extracts/rtx-brief.txt`](research/source-extracts/rtx-brief.txt) | Sponsor brief (verbatim) |
| [`research/notes/vendor-ai-mcp-landscape-2026-10.md`](research/notes/vendor-ai-mcp-landscape-2026-10.md) | What SysML v2 tool vendors actually ship for AI/MCP (verified 2026-10-02) |
| [`mvp/README.md`](mvp/README.md) | The retained toolchain + engine + evidence layer (now the scorer and single-run viewer) |
| [`research/archive/plans-2026-09/`](research/archive/plans-2026-09/) | Superseded plans from the workbench-as-product phase (history only) |

## Repository layout (target state; see plan §11)

```
mvp/          retained: official SysML v2 toolchain (pinned), engine checks, evidence packs, Workbench viewer
tools/        validate / check / diff / query as pure functions + MCP server          (to build)
agents/       LangGraph workflow P0–P3, prompts, approval gate, external-agent adapters (to build)
bench/        task suite (t0 calibration, t4 maritime ISR, t5 requirements), scorers, Inspect tasks
scenario/     synthetic maritime ISR reference model package (D6)
datasets/     external data registry: source, date, SHA-256, license (SOURCES.md)
runs/         Inspect logs, checkpoints, evidence (git-ignored)
analysis/     plots, failure annotations
docs/         workflow diagram, failure taxonomy, decisions/, report/
research/     literature review, paper artifacts, audits (read-only history)
plans/        plans and project statement
vendor/       symlink to full upstream clones (not in git; recreate with `python3 -m mvp.bootstrap --all-references`)
```

## Quick checks

```bash
python3 -m unittest discover -s mvp/tests -v      # 9 boundary tests
python3 -m mvp.engine baseline                    # real official toolchain run → mvp/runs/<id>/
python3 -m mvp.app                                # Workbench viewer at http://127.0.0.1:8765
```

## Rules (do not violate)

1. Checks read the **parsed** official model, never input forms or LLM claims.
2. SysML PASS ≠ engineering acceptance; engineering status is UNKNOWN without evidence.
3. Requirement decisions are human-owned; no agent self-approval.
4. All maritime values are **synthetic**; never present them as RTX specifications.
5. Public/synthetic data only; no EAR/ITAR; register every external source in `datasets/SOURCES.md`.
6. Do not modify `vendor/`; the toolchain is pinned and hashed.
7. Gold answers are visible only to the scorer process, never to agents, retrieval indexes, or few-shot prompts.
