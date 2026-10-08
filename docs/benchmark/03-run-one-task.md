# 3 · Run one task (section 1.5)

**You get:** one sealed task re-run live, or a task of your own written and scored, with every step shown in 1.1 and 1.4.
**You need:** the page open, a key in `.env` ([../langflow/02-keys-and-models.md](../langflow/02-keys-and-models.md)), Java for the official Pilot (the toolchain bootstrap in [06-task-bank.md](06-task-bank.md#the-toolchain)). 5 minutes; a P1–P3 run takes 1–3 minutes.

## Re-run a sealed task

Left side of 1.5: pick the task, the approach (P0–P3) and the model, press **Start the re-run**. The run uses exactly the exam's code path (`agents/solve.py`, frozen) with your model: the statement goes to the model, the Pilot parses the answer, P1–P3 repair from the error list, the key is opened only at the end. Section 1.1 lights up as it goes; when it ends, 1.4 shows the run, its tokens and its cost at list price. The result is saved under `analysis/langflow-console/` and **not added to any score**; it is a check, not a cell.

The model list of the console holds the exam's two cloud models; the default model of `.env` (`MVP_LLM_MODEL`) is what the flows use when nothing is chosen. To run a sealed task on any other model, use the Langflow exam-cell flow (`Direct model exam · P1 …`, type the model name on the card) or the runner: `MVP_LLM_MODEL="<name>" python3 bench/experiment.py --configs P1 --tasks GEN-03 --repeats 1`.

## Write a new task

Right side of 1.5: choose the type, fill the statement (the only text the model sees) and the key (YAML for GEN/MOD/AMB/RT, JSON for QRY; the three example buttons fill a complete pair), pick an approach and a model, press **Create task and run**. The task folder is written under `mvp/exam-inbox/` in the same format as the sealed ones ([06-task-bank.md](06-task-bank.md)), scored by the same scorers. It is a way to try a task before adding it to a bank; nothing is added to the matrix.

## From a terminal instead

```bash
MVP_LLM_MODEL=qwen3.8-flash .venv/bin/python bench/experiment.py --configs P0 P1 P2 P3 --tasks GEN-03 --repeats 1
```

writes `analysis/heldout-<model>-<stamp>/results.jsonl`, one row per cell, the same rows the matrix reads. A full direct matrix is `--repeats 3` without `--tasks`: 324 cells; the local 27B took 42 minutes for its 324 (`analysis/heldout-local27b-20261008T055755/summary.json`, started 05:57, finished 06:39 UTC). To show such a batch on the page as a new model set, see [CONTRIBUTING.md](../../CONTRIBUTING.md) ("Adding a column").

Next: [4 · Examine your flow](04-exam-your-flow.md).
