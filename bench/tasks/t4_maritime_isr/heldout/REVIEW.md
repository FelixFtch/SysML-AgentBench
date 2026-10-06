# Second review of the 27 held-out answer keys

Date: 2026-10-06. Reviewer: the assistant, at the user's request, as the second reader after the single author. Method: `python3 bench/review_gold.py` (mechanical checks, record `analysis/gold-review-20261006T064816.json`) plus a reading of every statement against its key. No file under `gold/` was edited.

## Mechanical checks: 27/27

- GEN, MOD, ALN: every reference passes the official Pilot and its own key; every name the key requires is written in the statement or the baseline; every value to keep is given to the candidate; MOD-05's reference fails the power check as the key expects.
- QRY: all five gold answers recomputed from the official parse of MaritimeISR match (4 platforms; powerLimitW 60; 3 connections on commandShip; 4 parts in FixedWingUav; 60 / 8 / 128).
- AMB: every should-ask group names something the statement leaves unquantified.
- RT: every must-mention phrase is in the requirement text of the given model.

## Reading, task by task

| Task | Finding | Action |
|---|---|---|
| GEN-01, GEN-02, GEN-05 | Statement and key list the same names; no numbers. | none |
| GEN-03 | Statement fixes type Real and value 2.0; the key keeps 2.0. A repair that retypes the attribute to a quantity loses the value, which the key correctly fails. | none |
| GEN-04 | Two values stated, both kept. | none |
| MOD-01 | Statement says "keep the existing camera, AIS, and radio connections"; the key checks the camera and AIS connections but not the radio connection. A candidate that drops the radio connection still passes. | recommend adding `usv.processor.uplink → usv.radio.fromProcessor` to `must_connect` at the next key revision; not changed now |
| MOD-02, MOD-03, MOD-04 | Consistent. | none |
| MOD-05 | Design must go over budget; the key expects FAIL at 78/60 W and keeps all four numbers. | none |
| QRY-01..05 | Gold recomputed from the parse. | none |
| AMB-01 | Two quantities missing (latency, bandwidth); six archived answers asked only about latency and were failed. Correct. | none |
| AMB-02 | Word list `watt / power limit / how many watts` is narrow: the archived answer "What is the target power consumption value and unit?" asks the right question and fails the word list (1 of 12 cells). | recommend adding `power consumption`, `power budget`, `maximum power` to the group; not changed now |
| AMB-03 | Consistent. | none |
| AMB-04 | The unit conflict is the point; "MHz" appears in the statement on purpose. | none |
| RT-01..05 | Phrases are the requirement text. The three archived RT-05 failures restated the parts and never the requirement; correct failures. | none |
| ALN-01..03 | References pass; look-alike pairs and unmatched elements are deliberate. | none |

## Two scoring rules decided here (scorer, not keys)

1. **AMB asking.** The statements say "ask". An imperative request ("Please clarify whether the uplink value is 8 or 8 MHz.") is asking; the old scorer required a literal `?`. Now a question mark or an imperative clarification request counts, the missing-quantity words are still required, and a number with a unit that the statement does not contain counts as invented (the old scorer looked for numbers only inside a SysML block). Effect on the archived 288: 3 cells would pass (AMB-01 P2 r1, AMB-04 P1 r1, AMB-04 P3 r3); the fourth "no-question" cell describes what is missing without asking and still fails. The archive is not re-scored; the rule applies to new batches.
2. **RT phrase matching.** "2.0 seconds", "two seconds" and "2 seconds" are the same restatement; matching now normalises number words and trailing `.0` and ignores sentence punctuation. No archived RT verdict changes.

## Verdict

The bank is consistent enough to freeze. The two recommendations above are lenience in the keys, not errors, and are left for the next key revision so that the frozen keys are the ones that were reviewed.
