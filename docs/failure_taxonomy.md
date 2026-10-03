# Failure classes

Subject: qwen3.8-flash, 24 tasks × P0/P1/P2/P3 × 3 repeats, 288 cells. Under the current scoring rule (`docs/decisions/019-task-verdict-vs-design-verdict.md`) 64 cells FAIL. Classes were read from the saved official diagnostics and answers; no model was called again. Detail is in `analysis/failure-classes.jsonl`, rebuilt by `python3 bench/classify_failures.py`.

| Class | Cells | Where | Meaning and an example |
|---|---|---|---|
| syntax-real-or-import | 22 | GEN-03 12, GEN-04 10 | Official syntax fails, involving the import of `Real` or an attribute's type. The two most common official diagnostics: `mismatched input 'import' expecting '}'` (the import is written where it is not allowed) and `Couldn't resolve reference to Type 'Real'` (`Real` is used without importing `ScalarValues`). All 12 GEN-03 cells are in this class. |
| syntax-connection | 8 | GEN-05 6, GEN-01 2 | A connection is not written with two legal ends. Official diagnostics: `Must have at least two related elements`, `no viable alternative at input '.'`. |
| syntax-other | 4 | GEN-02 2, GEN-01 1, GEN-04 1 | Other official syntax errors: `A port must be typed by port definitions.`, `no viable alternative at input 'uav'`, `Couldn't resolve reference to Type 'PartUsage'`, `no viable alternative at input 'def'`. |
| query-renamed | 16 | QRY-01 7, QRY-02 6, QRY-04 3 | A query answer has the right value or members but the qualified name is written wrong. QRY-01 writes the platforms as `usv` or `MaritimeISR.usv`; the key says `MaritimeISR::usv`. QRY-02 writes `MaritimeISR::usv.powerLimitW` (the value 60 is right); the key says `MaritimeISR::UnmannedSurfaceVessel::powerLimitW`. |
| query-wrong-number | 1 | QRY-03 1 | Asked how many connections have an end on `commandShip`, answered 2; the key says 3. |
| missed-topic | 6 | AMB-01 4, AMB-02 2 | A question was asked, but not about the missing quantity: AMB-01 does not ask about bandwidth, AMB-02 does not ask about the power limit. No number was invented. |
| no-question | 4 | AMB-01 2, AMB-04 2 | See the note below. |
| missing-phrase | 3 | RT-05 3 | All three P1 repeats fail to write back "2 seconds" and "two uplinks". |

Of the 64, 34 die on official syntax, 16 are name spelling, 1 reads a number wrong, 10 are question problems when information is missing, and 3 drop a required phrase on the read-back.

Passes by approach: P0 57/72, P1 51/72, P2 58/72, P3 58/72. Repairing from errors (P1) does not beat one-shot (P0). All 10 P1 generate-a-model failures used the full 3 repair rounds, and every one resubmitted the previous text unchanged at least once; 4 of them submitted the same text all four times (GEN-03's three repeats and GEN-04's third).

## The 4 no-question cells, separately

All four answers do ask for clarification, but as imperatives with no question mark. One AMB-04 answer: "Please clarify whether the uplink value is 8 (unitless) or 8 MHz." Both AMB-01 answers list the latency, bandwidth and update rate they need. The scorer (`bench/score_answer.py`) decides that a question was asked only when the text contains "?", so these are FAIL. None invents a number, and each asks about the missing topic.

This is a limit of the scoring rule, not the model inventing numbers. Whether a clarification request counts as asking is an answer-key change and waits for the second reviewer. It has not been changed, so the 64 still include these 4.

## Difference from the old rule

The old rule had 76 failures, 12 of them MOD-05 "designed power failures" (official syntax PASS, all four required numbers present, 78 W against a 60 W limit). The current rule separates the design verdict from the task verdict: those 12 still have design verdict FAIL, but the limit and every value to keep are unchanged and the check result is what the key expects, so the task verdict is PASS and they are no longer failures.
