# 019 — Task verdict and design verdict are separate

Date: 2026-10-03.

## Problem

For tasks with an engineering check, `bench/score_task.py` used the check result as the task result, and `must_preserve` never affected the result. Four hand-written MOD-05 answers through the official Pilot and the scorer gave: honest answer (78 W against a 60 W limit) FAIL; limit raised to 80 W PASS; visible camera lowered to 23 W so the total is 60 W PASS; infrared camera left out FAIL. The scorer rewarded changing a requirement.

## Options

1. Keep the old rule and describe MOD-05 as "designed to fail".
2. Task verdict = official parse PASS, every required name and connection present, no invented number, every kept value unchanged, and every engineering check equal to the answer key's expected result. Report the design verdict (does the design meet its budget) separately.

## Decision

Option 2, chosen by the team on 2026-10-03.

- `status` is the task verdict; `engineering_status` is the design verdict.
- MOD-05 honest answers: task PASS, design FAIL.
- Tests: `bench/test_score_pwr01.py` (raised limit → task FAIL; lowered draw to fit → task FAIL; gold → task PASS with design FAIL). `bench/validate_gold.py` passes all 10 gold references.

## Applying it to saved results

No model was called again. `bench/rescore.py` re-scored all 143 saved GEN/MOD answers from their official parses into `analysis/rescore-20261003.jsonl`. 15 changed, all honest MOD-05 answers. The archived results files are unchanged; every reader (page, report, `STATUS.md`, failure classes, ablation) applies the overlay and shows the archived verdict beside the current one. Main matrix 212 → 224/288; OpenCode 20 → 21/24.

`bench/rescore_saved.py` compared saved statuses with a fresh score and exited non-zero on any difference. Under the new rule it would always fail, so it was removed; `bench/rescore.py` replaces it.

Model judges (qwen3.8-max, Jev 1.13) were asked whether a submission passes with over-budget counted as fail, so they are compared with the design verdict.

Run records that were written with the old rule or with a bug in the read-back number check were moved to `analysis/archive/2026-10-03-superseded/` (see its README); nothing was deleted.

## Open

The AMB scorer counts a question only when the text contains "?". Four of the 64 remaining failures are clarification requests written as imperatives. Changing that is an answer-key change and waits for the second reviewer.

## What would reverse it

The second reviewer deciding that the task verdict for budget tasks should be the design verdict. The old rule would still need `must_preserve` added, or it would again pass a raised limit.
