# 029 · Failed tasks retried with the agents on qwen3.8-max and relaxed limits

Date: 2026-10-06. Status: done (user decisions of 2026-10-06). Not part of any score or of the frozen bank. Affects `bench/run_agents_retry.py` (new), `bench/summarize_retry.py` (new), `bench/board_facts.py`, `bench/board.js`, `bench/board.css`; data in `analysis/retry-opencode-qwen3.8-max-20261006T185737/`, `analysis/retry-claude-qwen3.8-max-20261006T185736/`, `analysis/retry-summary.json`.

## Question

Can the strongest combination we have, an off-the-shelf agent on qwen3.8-max, solve the tasks that failed somewhere, if it is given more room?

## What was run (the user's choices)

- **Tasks:** every task with at least one failing cell in the four scored candidates: 14 of 27 (ALN-01, ALN-02, AMB-01, AMB-02, GEN-01, GEN-03, GEN-05, MOD-02, MOD-03, QRY-01, QRY-02, QRY-04, RT-04, RT-05).
- **Candidates:** OpenCode 1.18.27 and Claude Code 2.1.278 on qwen3.8-max, three runs per task each (84 runs), in the sandbox of decision 026 with the same workspace, AGENTS.md, prompt and `./validate`.
- **Limits:** `./validate` at most 50 calls per run (it prints "call n of at most 50" and refuses later calls); 60 minutes per run (scored batches: 15); Claude Code 200 turns (scored batches: 60).
- **Stop on the first pass:** the answer is scored from outside the sandbox each time it changes; the agent never sees the key. The answer is answer.md or, before the agent has written one, the newest model file it wrote that declares the task's package. A run that passes ends at once and the next run starts.

## Method notes

- The workspace-model rule was added after the first runs, when a Claude Code GEN-01 run had a correct model for 8 minutes without writing answer.md. Both batches were stopped and resumed; finished rows were kept, and the four runs that were cut off are listed in each batch's `summary.json` (`interrupted`).
- Claude Code reports tokens only when a run ends, so runs stopped on a pass have no usage of their own. The Claude Code total therefore comes from CCR's request log between the batch start and its last result. Check: for the discarded 2026-10-06 Claude Code batch, where all 81 runs reported their usage and nothing else used CCR, the log matches Claude Code's own totals exactly (input 4,612,309, output 208,957 tokens). No other qwen3.8-max traffic passed through CCR that day.

## Results

| | OpenCode · max | Claude Code · max |
|---|---|---|
| Pass | 41 / 42 | 40 / 42 |
| Passed from answer.md / from the model file before answer.md existed | 32 / 9 | 27 / 13 |
| Stopped as soon as they passed | 17 | 31 |
| Hit 60 minutes | 0 | 0 |
| Most `./validate` calls in one run (limit 50) | 5 | 6 |
| Median time per run | 50 s | 105 s |
| Cost at the cn-beijing list price | $3.36 | $7.12 |

- The hardest tasks of the scored batches pass in every retry run: ALN-02 (direct flash 2/12, max 9/12, OpenCode 2/3, Claude Code 1/3 before), QRY-01 (flash 4/12, max 10/12), AMB-02 (max 6/12).
- Three runs still fail: OpenCode GEN-05 run 1 wrote no SysML that the official parse accepted; Claude Code QRY-02 runs 1 and 2 wrote no JSON answer. Both are delivery failures, not modeling errors.
- No run came near the 50-call limit (most used 1–2 calls) or the time limit: the limits that mattered in the scored batches were the 15-minute time limit and agents that kept working after their model already passed.

## How to read it

This is what the agents can reach, not a score. Stopping on a pass and accepting the model file before answer.md exists are both more lenient than the scored rule. The direct comparison with the scored agent batches on these 14 tasks (39 of 42 each) changes two things at once, the model (flash → max) and the limits, so it does not separate their effects.

## What would reverse it

A rerun under the scored rule (answer.md only, final answer only, 15 minutes) that finds the same tasks failing with max, which would mean the lenient rules, not the model, made the difference.
