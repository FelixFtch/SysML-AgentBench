# 6 · The task bank: format, keys, freeze; replacing it with real tasks

**You get:** how a task is written, how its key is written, what "frozen" means, and the steps to bring in a real RTRC task bank when one arrives.
**You need:** nothing to read this; Java and the toolchain to validate keys. 15 minutes.

## One task is one folder

`bench/tasks/t4_maritime_isr/heldout/<ID>/`, listed in `heldout/index.jsonl` (`{"id", "type", "path"}` per line):

| Path | Holds |
|---|---|
| `case.yaml` | `id`, `type` (GEN, MOD, ALN, QRY, AMB, RT), `package` (the package name the answer must declare), `synthetic: true`, review status and reviewer |
| `input/requirements.md` | the statement the candidate sees, and nothing else; marked synthetic |
| `input/baseline/*.sysml` | models the candidate starts from or must not change (MOD, ALN) |
| `input/model.sysml` | the model to read (QRY, RT) |
| `gold/assertions.yaml` | the key. GEN/MOD: `must_exist` (qualified names), `must_connect` (port pairs), `must_preserve` (values to keep), engineering checks. ALN: `must_map`, `must_not_map`, `must_report_unmatched`. AMB: `should_ask` (word groups, one per missing quantity), `must_not_invent_number`. RT: `must_mention` |
| `gold/answer.json` | the expected query result (QRY) |
| `gold/reference/` | a reference answer that passes the Pilot and its own key (GEN, MOD, ALN) |

Candidates never see `gold/`; the sandbox does not even contain it. The scorers (`bench/score_task.py`, `score_answer.py`, `score_alignment.py`) read the parsed official model and the key, never the candidate's prose. The rules in one page: [07-scoring-rules.md](07-scoring-rules.md).

## Writing a task

1. Write the statement and the key together. Every number in the key must appear in the statement or the baseline model; a key that needs a number the statement does not give is a broken task, not a hard one.
2. Write the reference answer; `python3 bench/validate_gold.py` checks that every reference passes the Pilot and scores PASS against its own key.
3. Second review: `python3 bench/review_gold.py` runs the mechanical checks; a second person records a verdict per task in `REVIEW.md` and sets `status: reviewed` and `second_reviewer` in `case.yaml`.
4. Try it on a model from the page's console ([03-run-one-task.md](03-run-one-task.md), "Write a new task") before adding it to a bank.

ALN tasks are generated from pairs of models by `bench/build_aln_tasks.py`.

## The freeze

`python3 bench/freeze.py` hashes every task folder and the scoring code into `bench/FREEZE.md`; `--check` verifies them. A frozen bank is not edited while a batch runs, and a change after a batch is a *revision*: re-score the saved answers with `bench/rescore.py` (which writes `results-r2.jsonl` next to the original), list every verdict that changed, rerun the cells whose inputs changed, and add a line to the History section of `FREEZE.md`. Revision 2 of this bank (decision 028) fixed three keys and reran every P3 cell that way.

## Replacing the bank with real RTRC tasks

When a real task bank arrives, the shape stays and the content changes. The steps, in order:

1. **A new bank folder**, `bench/tasks/t6_rtrc/heldout/` (or whatever the family is), with the same per-task layout and its own `index.jsonl`. Keep the synthetic bank where it is; it remains the practice bank and the one the frozen results refer to.
2. **Keys before runs.** Write every key and reference before any model sees a statement; run `validate_gold.py` and `review_gold.py`; record the second review. If the real tasks carry restricted data, the bank does not go in this repository (rule 5 of the README); a private repository with the same layout works unchanged.
3. **Point the code at it.** The bank path is the constant `HELD` in the runners and the page (`bench/experiment.py`, `run_opencode.py`, `run_claude_qwen.py`, `langflow_exam.py`, `exam_board.py`, `shell_service.py`, `freeze.py`). `bench/experiment.py` is a frozen file, so this is by definition a new freeze: change the constants in one commit, run `bench/freeze.py`, tag it.
4. **Generalize the page's scenario text.** A few parts of the results page are written for the maritime scenario and would read wrong on other tasks: the task-type guide (`TYPE_GUIDE` in `bench/board.js`), the MOD-05 power note (78 W against 60 W) in `bench/exam_board.py`, and the drawn scene of section 1.4 (`bench/board.js`, the platforms and flows it knows). These should become per-bank configuration (a `bank.yaml` next to `index.jsonl` with the type guide, the scene, the budget tasks) in the same commit.
5. **New cohorts.** The frozen four columns refer to the synthetic bank; a real bank starts with empty columns. Run the candidates again; add their folders as cohorts in `bench/batches.py`. Langflow columns need nothing: `langflow_exam.py --column` already writes folders the page picks up, but it should carry the bank name in the folder (`langflow-exam-<bank>-<column>-…`) once two banks exist; that is a one-line change in `langflow_exam.py` and `batches.py`.
6. **Prices and models.** Other keys (Gemini, GPT, Claude) are a `.env` and Global-Variables matter ([../langflow/02-keys-and-models.md](../langflow/02-keys-and-models.md)); their list prices go into `PRICES` in `bench/board_facts.py` with a source URL, or the page shows `—`.

## The toolchain

The official SysML v2 Pilot (release 2026-08, kernel 0.62.0) runs on Java 21. `mvp/toolchain/bootstrap_java.py` fetches a pinned JDK and `bootstrap_kernel.py` the kernel; `python3 -m mvp.bootstrap --all-references` clones the pinned `SysML-v2-Release` library (`vendor/`). Today the JDK bootstrap is written for Linux x64 (`mvp/toolchain/java.lock.json`); on macOS or Windows, install Temurin 21 yourself and point `mvp/toolchain/java21` at it (a symlink or junction) until the bootstrap learns the other platforms. The library path is `vendor/SysML-v2-Release/sysml.library`, checked against the pinned commit on every run.

Next: [07-scoring-rules.md](07-scoring-rules.md).
