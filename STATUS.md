# STATUS

Held-out set: 24 synthetic maritime tasks, single-author answer keys. Official Pilot accepted every GEN and MOD reference model before scoring. MOD-05's reference is an intentional power FAIL (78 W against a 60 W limit).

Model: qwen3.8-flash. Three replicates of P0–P3, one pass of pinned OpenCode v1.18.27.

## P0–P3, 288 cells

| Configuration | PASS | FAIL |
|---|---|---|
| P0 | 54 | 18 |
| P1 | 48 | 24 |
| P2 | 55 | 17 |
| P3 | 55 | 17 |

| Task type | PASS | FAIL |
|---|---|---|
| GEN | 26 | 34 |
| MOD | 48 | 12 |
| QRY | 43 | 17 |
| AMB | 38 | 10 |
| RT | 57 | 3 |

MOD-05 is FAIL on all 12 cells. In every cell the official parse passed, the required numbers were present, and the power check was FAIL. That FAIL matches the checklist.

The other 64 FAIL cells are classified in `docs/failure_taxonomy.md`: 34 official syntax failures, 16 renamed query answers, 1 wrong query number, 10 ambiguity misses, 3 missing round-trip phrases. Counting a checklist match on MOD-05, P0 matches 57/72, P1 matches 51/72, P2 matches 58/72, and P3 matches 58/72.

## OpenCode (P-CODE), 24 cells

PASS 20, FAIL 4. MOD-02, MOD-03, and MOD-04 produced no SysML package. MOD-05 parsed, kept every required number, and the power check is FAIL.

## Week 10–11 additions

Rescoring 120 saved GEN/MOD parses matched the archived status with 0 mismatches. Token yield is in `analysis/ablation.json` and `analysis/figures/ablation.png`. The second model agreed with the tool on 25/40 replicate-1 GEN/MOD cells and false-passed 12 failures, including all 4 MOD-05 budget FAILs. MOD-01 replay: checklist PASS, approval gate not triggered, round-trip kept the infrared camera and the 60 W limit (`analysis/demo-mod01.json`). Draft report: `docs/report/D4-初稿.md`.

## Not in this run

A second person has not signed the 24 answer keys. No frontier model, Cameo run, Claude Code full set, or human blind review.
