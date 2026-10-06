# Process knowledge base (D7)

The reusable part of SysML-AgentBench: how to run AI-assisted early-stage systems engineering with SysML v2, and how to evaluate it, written for the next team (RTRC engineers or future students). Each page says what to do, why, with evidence from this project's saved runs, and where that evidence is. Numbers change as runs are added; the current ones are in [`STATUS.md`](../../STATUS.md), and the full argument is in the report draft [`docs/report/D4-draft.md`](../report/D4-draft.md). All maritime values are synthetic, not RTX specifications.

| Page | Read it when you are |
|---|---|
| [1. The process](01-process.md) | setting up an AI-assisted design loop: the steps, who owns each, what a person must keep |
| [2. Working with the official SysML v2 Pilot](02-sysml-v2-pilot.md) | writing or checking SysML v2 with Pilot 0.62: what it rejects, its exact messages, the accepted forms, its quirks |
| [3. What helps the model and what does not](03-what-helps.md) | choosing a model, prompt rules, repair, outline, retrieval, alignment, or an off-the-shelf agent |
| [4. Evaluating agents fairly](04-evaluating-agents.md) | building a benchmark or comparing agents: the traps this project fell into and the fixes |
| [5. Extending the task bank and rerunning](05-extending-the-bank.md) | adding tasks and answer keys, running batches, regenerating the results |
| [6. Glossary](06-glossary.md) | meeting a term used across the repository |

Where the evidence lives: decision records [`docs/decisions/`](../decisions/) (016–026 cover 2026-10-03 to 2026-10-06), failure classes [`docs/failure_taxonomy.md`](../failure_taxonomy.md), the freeze [`bench/FREEZE.md`](../../bench/FREEZE.md) and second review [`REVIEW.md`](../../bench/tasks/t4_maritime_isr/heldout/REVIEW.md), the exam report `analysis/report/exam-20261006/index.html`, and the results page (`python3 bench/exam_board.py`, http://127.0.0.1:8770/).
