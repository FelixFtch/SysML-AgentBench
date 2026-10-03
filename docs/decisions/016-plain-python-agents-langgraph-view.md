# 016 — P0–P3 run as plain Python; LangGraph is a read-only view

Date: 2026-10-03. Supersedes the open choice in decision 004.

## Options

1. Build P0–P3 as LangGraph graphs and run the matrix through them.
2. Keep P0–P3 as plain Python functions and use LangGraph only to show the steps of a saved run.

## Decision

Option 2. The four configurations are `agents/solve.py::solve(task_dir, config)`; `bench/experiment.py` runs the matrix. `agents/exam_graph.py` builds a LangGraph `StateGraph` whose nodes read the latest saved MOD-05 case (`analysis/mvp-case-latest-MOD-05.json`). Opening it in LangGraph Studio does not call a model.

## Reason

Each configuration is a short loop: one or two model calls, the official Pilot, at most three repairs. Plain functions keep every prompt and call in one file and record exactly what was sent. The live flow the advisors asked for is on the exam page (`bench/exam_board.py`, port 8770), which highlights each step as a run proceeds. LangGraph added a dependency without changing any score.

## What would reverse it

A configuration that needs checkpoint-and-resume, a human interrupt inside the loop, or branching that plain code makes hard to read.
