# Benchmark: the exam and the results page

This half is for people who want to see how agents score, understand why a cell passed or failed, run a task, examine a flow of their own, or bring in a real task bank. The page you will look at most is the results page, `python3 bench/exam_board.py` → http://127.0.0.1:8770.

## Read in this order

| Page | You get | Minutes |
|---|---|---|
| [1 · Open the page](01-open-the-page.md) | the results page on your computer, what each section is | 5 |
| [2 · Read the matrix](02-read-the-matrix.md) | every column, colour and mark of section 1.3; switching between models | 10 |
| [3 · Run one task](03-run-one-task.md) | re-run a sealed task or write your own, live, from the page's console | 5 |
| [4 · Examine your flow](04-exam-your-flow.md) | your Langflow flow sits the 27 tasks and becomes a column on the page | 15 + the run |
| [5 · The sandboxed coding agents](05-sandbox-agents.md) | what OpenCode and Claude Code see, why the sandbox is Linux-only, how to run those two columns | 10 |
| [6 · The task bank](06-task-bank.md) | the task folder format, the answer keys, the freeze; how to replace the tasks with real ones | 15 |
| [7 · Scoring rules](07-scoring-rules.md) | what PASS means for each task type, in one page | 5 |

## The one idea

Every candidate — a plain model, an agent in a sandbox, a Langflow flow — gets the same 27 task statements and nothing else. Its answer is parsed once by the official SysML v2 Pilot and compared with a key written before any run. The page reads the resulting score files from `analysis/`. Nothing on the page is a model's opinion of a model.

## What is frozen

`bench/FREEZE.md`: the 27 tasks and keys, the scorers, the P0–P3 solver, the model client, the retrieval library, the toolchain lock. `python3 bench/freeze.py --check` says `unchanged`. New columns, new flows, new models and a new task bank are all additions; only the frozen files need a new freeze.
