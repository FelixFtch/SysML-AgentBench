# 017 — Inspect AI not adopted

Date: 2026-10-03. Supersedes decision 007.

## Options

1. Wrap tasks, scorers and the OpenCode/Claude Code runs as Inspect AI tasks and use Inspect View for logs.
2. Keep the project's own runner and scorers and save results as JSON/JSONL beside the official Pilot runs.

## Decision

Option 2. Scoring is `bench/score_task.py` (GEN/MOD, from the official parse) and `bench/score_answer.py` (QRY/AMB/RT). Results are `analysis/heldout-*/results.jsonl`, the re-scored overlay `analysis/rescore-20261003.jsonl`, and one folder per official run under `mvp/runs/` (git-ignored). The exam page and `analysis/report/exam-20261003/index.html` are the viewers.

## Reason

The adjudicator is the official SysML v2 Pilot plus a written answer list; both were already wired before Inspect would have been. Inspect would have added a second log format without changing a verdict. The scoring fix in decision 019 was made and re-applied to all saved answers without re-running models, which is easier with plain files.

## Consequences

The plan still describes an Inspect Task in §9.1 and Inspect View in §12; decision 017 overrides them. The project statement (`plans/project-statement.md`, "Tooling") says benchmark runs use Inspect AI. It is a sponsor-facing text and was not edited; suggested replacement: "Benchmark runs use the project's own runner; every answer, official validation run and score is saved as files and shown on a local results page."

## What would reverse it

A reviewer or the sponsor needing Inspect logs, or adding many external benchmarks that already ship as Inspect tasks.
