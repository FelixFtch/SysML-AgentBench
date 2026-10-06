# Failure classes

Subject: the frozen 27-task bank (`bench/FREEZE.md`), four candidates (`bench/batches.py`): direct qwen3.8-flash and direct qwen3.8-max (27 tasks × P0–P3 × 3 repeats, 324 cells each), OpenCode and Claude Code on qwen3.8-flash in the sandbox (27 × 3, 81 runs each). Every failing cell gets one class from its saved evidence by `python3 bench/classify_failures.py`; no model is called. Records: `analysis/failure-classes-20261006.jsonl`. Counts per candidate are in `STATUS.md`.

## Direct candidates

Direct flash fails 57 of 324 cells, direct max 12.

| Class | flash | max | What it means, with an example from the saved runs |
|---|---|---|---|
| query-renamed | 15 | 2 | The answer has the right members or value but writes a qualified name differently. QRY-01 answers `["usv", "uav", "commandShip", "shore"]`; the key says `MaritimeISR::usv` and so on. QRY-02 writes `MaritimeISR::usv::powerLimitW` (value 60 right); the key names the definition, `MaritimeISR::UnmannedSurfaceVessel::powerLimitW`. QRY-04 writes dots instead of `::`. |
| aln-missing-pair | 12 | 3 | The alignment package parses but leaves out a required pair. Most are feature-level aliases: `alias imagery for OptronicsKit::EoCameraUnit::videoOut` (ALN-01), `alias toShore for VendorRadioPack::RadioUnit::dataOut` (ALN-02). Max misses the allocation `ShipLinkIcd::usv.radio → VendorRadioPack::vessel.radioUnit` in three ALN-02 cells. |
| missed-topic | 10 | 7 | Asks, but not about the missing quantity. AMB-01 asks only about latency, not bandwidth (flash 7 cells). AMB-02 asks about voltage, the power unit or "power output" instead of the limit; one max answer asks for "a numerical value, limit, or baseline (and its unit)" and still fails because the key accepts only "watt", "power limit" or "how many watts" (noted as a strict key in the second review). |
| missing-phrase | 8 | 0 | The round trip leaves out a required phrase: RT-05 omits "2 seconds" and "two uplinks" (6 cells), RT-04 omits "30 days" (2). |
| syntax-connection | 6 | 0 | The official parse fails on a connection: `no viable alternative at input '.'` (GEN-01, GEN-05, ALN-02). In P1 two of them stop after three identical resubmissions. |
| syntax-reference | 3 | 0 | The alignment package names something that does not resolve: `Couldn't resolve reference to Element 'OptronicsKit::powerDrawW'` (the feature is `OptronicsKit::EoCameraUnit::powerDrawW`). |
| checklist-missing | 3 | 0 | Parses, but a required part is missing: GEN-02 P3 drops `uav::searchRadar` and `uav::eoCamera`; GEN-03 P1 drops `commandShip::fusion`. |

Two classes of the 2026-10-03 matrix are gone: `syntax-real-or-import` (22 of its 64 failures) disappeared once the rules stated the toolchain's `private import` convention (decision 024), and `no-question` (4) disappeared once an imperative clarification request counts as asking (second review). The old classification is kept in `analysis/archive/2026-10-03-superseded/failure-classes-20261003.jsonl`.

## Agents

OpenCode fails 4 of 81 runs, Claude Code 5 of 81. The agents repair inside their own session with `./validate`, so a syntax failure in an agent row would mean its final answer did not parse; every SysML answer either agent wrote into `answer.md` parses.

| Class | OpenCode | Claude Code | What it means, with an example from the saved runs |
|---|---|---|---|
| agent-timeout | 2 | 2 | The run hit the 900 s limit before writing `answer.md`. In OpenCode GEN-05 r1 and ALN-02 r3 and Claude Code ALN-02 r2 the model in the workspace had already passed `./validate` (its last of 4, 15 and 3 runs); in Claude Code ALN-02 r1 the last run failed. |
| invented-number | 1 | 2 | Correct clarifications that the frozen rule fails because they contain a number with a unit that the statement does not: OpenCode AMB-02 r2 asks for the limit "as a number + unit (e.g. `<= 450 W`)"; Claude Code AMB-03 r1 and r3 derive 128 GB / 30 days ≈ 4.27 GB/day and say it must not be used. A change to the rule is proposed in `STATUS.md` (Not done), not applied. |
| no-sysml | 1 | 1 | A modify task answered with a description of the edit: OpenCode MOD-02 r3 edited `input/baseline/VesselAlign.sysml` in place and listed the change; Claude Code MOD-03 r3 returned only the added `connect` line. |

None of the direct calls' leading classes appears: no differently qualified query answer, no question about the wrong quantity, no missing alignment pair, no illegal connection.

Before the agents' ALN runs were rerun, 8 of their 15 submitted alignment packages failed the official parse with `Must be an accessible feature (use dot notation for nesting)` after passing `./validate` with the package listed first (decision 026); those rows are superseded and not counted. The class is `syntax-nesting` in `bench/classify_failures.py`.

## How the repair loop ended

Among the 39 SysML answers per approach, the official parse passes on the first attempt and after the loop as follows (flash): P1 33 → 36, P2 37 → 39, P3 31 → 38; P0 has no loop (34). Max parses 39/39 on the first attempt in every approach. Of the 9 flash cells whose final answer still fails to parse, 5 are P0 cells, which never repair; the other 4 (three P1, one P3) stopped after three identical resubmissions in a row, with the complete error list and every earlier version in the conversation. No cell reached the 20-repair cap.
