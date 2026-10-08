# 7 · Scoring rules, on one page

Only two things score: the official SysML v2 Pilot 0.62 and the key written before any run. No model judges another model (decision 025: two were tried and passed models that do not parse).

## The rule

A task **passes** when all of these hold:

1. where the answer is SysML (GEN, MOD, ALN), the official parse passes, in one fixed file order (sources first, the answer last; the Pilot's verdict on an alignment package can depend on the order, `bench/check_validator_order.py`);
2. every required name, connection or mapping of the key is present;
3. no number was invented: a value with a unit that the statement does not contain counts as invented, except in an AMB answer that writes no SysML (an example or a sum is allowed there);
4. every value the statement said to keep is unchanged;
5. every engineering check comes out as the key expects (power, link, storage, trace).

Whether a design meets its budget is a separate **design verdict** (decision 019): a MOD-05 answer that keeps the 60 W limit and reports the 78 W overrun passes the task and fails the design, which is the right outcome; one that raises the limit fails the task.

## By task type

| Type | The answer | PASS when | Scorer |
|---|---|---|---|
| GEN generate | one SysML package | parse PASS; `must_exist`, `must_connect` present; no invented number; checks as expected | `bench/score_task.py` |
| MOD modify | the edited package | as GEN, plus `must_preserve` values unchanged | `bench/score_task.py` |
| ALN align | one alignment package (aliases, allocations) + a JSON report | parse PASS of sources + package; every `must_map` pair declared; no `must_not_map` pair; unmatched elements reported | `bench/score_alignment.py` |
| QRY query | JSON | equals `gold/answer.json` after canonical ordering (keys sorted, lists sorted, numbers as floats); names must be the qualified names the key uses (`MaritimeISR::usv`, not `usv`) | `bench/score_answer.py` |
| AMB ambiguous | text that asks | an imperative request naming each missing quantity (`should_ask` word groups); no invented number with a unit | `bench/score_answer.py` |
| RT round trip | sentences | every `must_mention` phrase present, after number-word and `.0` normalisation | `bench/score_answer.py` |

## What the direct approaches get, and the agents do not

The direct prompts carry the SysML rules (one fenced block, one package, `private import ScalarValues::*;` when Real is used, never change a kept number) and, for ALN, the alignment rules; the harness runs the repair loop (the Pilot's complete error list back into the same conversation, up to 20 times, stop after three identical answers). The sandboxed agents get no rules in the prompt: the task, a rules file and `./validate`, and they repair inside their own session. The Langflow Agent exam flows get the exam prompt (`tools/assistant/rtrc-assistant-exam.md` with the frozen rules appended) and the Pilot as a tool. The columns compare harnesses on the same model; the help differs by design and is written down.

## Where the rules live

`bench/FREEZE.md` (the frozen files and the rules in force), `agents/solve.py` (the rules text and the repair loop), `bench/score_*.py` (the scorers), `docs/decisions/019`, `022`, `025`, `026`, `028` (why each rule is what it is).
