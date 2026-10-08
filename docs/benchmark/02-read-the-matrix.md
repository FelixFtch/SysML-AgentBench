# 2 · Read the matrix (section 1.3)

**You get:** every mark on the matrix explained.
**You need:** the page open at http://127.0.0.1:8770/#s13. 10 minutes.

## Rows

One row per task, grouped by type: GEN generate a model (5), MOD modify a model (5), ALN align two models (3), QRY query a model (5), AMB ambiguous, ask instead of guessing (4), RT round trip, model back to text (5). The group header carries the direct model's pass count for that type. The row end (`11/12`) is the direct model's passes out of 12 cells (4 approaches × 3 repeats).

## Columns, left to right

| Columns | What | Where the rows come from |
|---|---|---|
| P0, P1, P2, P3 × 3 | the direct model, one approach each, three repeats: P0 one answer; P1 the repair loop (the Pilot's complete error list back to the model, up to 20 times, stop after three identical answers); P2 an outline first; P3 retrieval of official examples, then the outline | `analysis/heldout-<model>-*/results.jsonl` |
| OpenCode × 3, Claude Code × 3 | the two coding agents in the sandbox with the task, a rules file and `./validate`; three runs per task | `analysis/opencode-jail-*`, `analysis/claude-jail-*` |
| Langflow columns × 3 each | flows that sat the exam through `bench/langflow_exam.py`: the three of projects 2, 3 and 4 first (Pilot only; OpenCode with memory; Langflow Agent with memory), then any flow a person examined with `--column` | `analysis/langflow-exam-<column>-<model>-*` |

The column foot is that column's pass rate over the 27 tasks. A header reads **not run yet** when no folder exists for that column on the selected model; its tooltip shows the command that would fill it.

## The switch at the top right

One button per **model set**: `qwen3.8-flash` (the frozen archive; the direct columns can also show `Direct · max`), `local 27B` (the same matrix rerun on the local 3-bit Qwen3.8-27B), and one more button for every other model that has at least one Langflow column on disk (a flow examined with `--model "<name>"` or run as saved). Sets are read from the folders; nothing is configured.

## Cells

| Mark | Meaning |
|---|---|
| green | PASS: official parse passes (where the answer is SysML), every required name, connection or mapping present, no invented number, every kept value unchanged, every engineering check as the key expects |
| red | FAIL, for any one of those reasons; the tooltip and section 1.4 say which |
| grey `·` | not run yet |
| `↻n` | the official parse needed n repairs (direct P1–P3 only; the agents repair inside their own session and the grader parses once) |

Hover a cell for its verdict, repairs, time and tokens where recorded. Click it: section 1.4 shows the task statement, every attempt with the Pilot's error list, the key, the scorer's reason, and for a parsed model a diagram drawn from the parse; section 1.1 lights the steps that cell went through.

## What the matrix does not do

It does not average, rank or judge. Three repeats are shown as three cells because the spread between repeats is part of the result (rerunning P3 with byte-identical prompts changed a handful of verdicts; decision 028). A model's cost is in 1.2, priced at list price from `bench/board_facts.py`; a model without a price there shows `—`.

Next: [3 · Run one task](03-run-one-task.md).
