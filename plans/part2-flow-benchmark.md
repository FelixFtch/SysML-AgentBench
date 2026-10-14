# Scoring the whole design flow: a task bank generated from the parts catalogue

Date: 2026-10-10. Status: proposal and hand-off; nothing built yet. Scope: a benchmark of the Part 2 design flow
end to end (brief in, approvable design out), with expected outcomes computed by code from the same catalogue the
flow is built on. This is not asked for by the sponsor brief; D4 §8 and §11 name it as the missing measurement.
Every value is synthetic and not an RTX specification.

## 1. Where the "questions" come from today

There is no bank yet. What exists:

- `bench/discover.py` `CATALOG`: the parts and parameters the flow and the results page (2.2) offer. Slots: visible
  camera (41 W standard, 28 W low power), infrared camera (12 W, 7 W, none), edge computer (25 W, 14 W), uplink
  (8 Mbps, 20 Mbps), storage (128 GB, 256 GB). Parameters: recording rate 6/12/18 Mbps, keep originals 4/8 h,
  upload rate 2/6/12/18 Mbps, power limit fixed at 60 W.
- `bench/discover.py` `brief_from(choice)`: the brief text for one choice (the only text the flow sees).
- `bench/discover.py` `budgets(choice)`: the arithmetic outcome of one choice (power, link, storage PASS/FAIL,
  whether the upload is a preview). This is the expected outcome generator: code, no model, no hand-written number.
- `bench/discover.py` `run(brief, progress)`: the flow itself, the same code the page, the Langflow "Design
  pipeline" tool (through `bench/shell_service.py` `/run/*`) and the MCP `run_design` call. It writes
  `analysis/discover-<stamp>.json`.
- 20 saved runs, `analysis/discover-*.json`, and the simulation check over them, `bench/simulate_design.py`
  (`analysis/simulation/`), which is the same arithmetic over the mission timeline.

Full grid: 2 × 3 × 2 × 2 × 2 × 3 × 2 × 4 = 1,152 choices, each with a known outcome. Of those, a choice fails power
whenever the three draws exceed 60 W (41+25 already fails with any infrared camera; 41+25+0 = 66 fails too; 28+14+x
always passes), fails the link whenever upload > uplink, fails storage whenever rate × hours × 3600 / 8000 > GB
(only 18 Mbps × 8 h = 64.8 GB never exceeds 128 GB, so storage never fails in this catalogue: say so in the report
or add a 64 GB option as a catalogue change, which is a design decision for the team).

## 2. Kinds of tasks the bank can hold

| Kind | How the brief is made | What the flow must do | Scored how (all code) |
|---|---|---|---|
| FEASIBLE | a choice whose `budgets` are all PASS | write requirements with every brief number, two designs that parse, checks all PASS, gate `awaiting-person` with at least one eligible design | see §3 |
| INFEASIBLE-POWER / -LINK | a choice with a FAIL in `budgets` | same, but the matching check must FAIL, no design may be eligible, trade-offs must be proposed and recomputed, and no requirement may raise the 60 W limit or lower a stated draw | see §3; any change of a stated limit is a task FAIL (the MOD-05 rule) |
| MISSING-VALUE | a FEASIBLE brief with one number removed by the generator (for example the uplink rate) | requirements must carry a question for the missing quantity and no invented number; gate `needs-person` | `requirements.questions` non-empty and mentions the quantity; `requirements.unsourced` empty; no design eligible |
| PREVIEW | upload rate below the recording rate | the upload requirement must be the preview rate, not the recording rate | `uploadMbps` requirement value equals the brief's preview rate |
| ADAPT (optional) | a brief close to an approved design in memory | the flow retrieves the approved design and adapts it (shell route `/run/adapt`) rather than writing from nothing | retrieval returns the approved design; the adapted design keeps the unchanged values |

The first four kinds need no new flow code. ADAPT depends on what is in memory, so its expected outcome has to be
written per task; keep it small or leave it out.

## 3. Scoring one run (deterministic, from the saved record)

Read `analysis/discover-<stamp>.json`:

1. Requirements. `numbers_in(brief)` ⊆ numbers in `requirements[].quantity.value` or text; `requirements.unsourced`
   is empty; each number sits under the right attribute name (60 → `powerLimitW`, the draws → `drawW`, the recording
   rate → `dataRateMbps`, the upload rate → `uploadMbps`, the link rate → `uplinkMbps`, the storage → `storageGB`,
   the hours → `retentionHours`).
2. Designs. `designs[].sysml_status == "PASS"` for both; the `TRACE` check PASS (every requirement value is in the
   official parse).
3. Checks. `POWER`, `LINK`, `STORE` statuses equal `budgets(choice)`; the `REQS` row agrees with them; the `MISSION`
   row agrees with the static rows (it must, under constant rates).
4. Gate. `gate.eligible` non-empty exactly when every budget is PASS; empty when any budget FAILs; `gate.answer ==
   "needs-person"` for MISSING-VALUE.
5. Limits kept. No requirement states a power limit other than 60 W and no draw other than the brief's; no design
   attribute changes a brief value (compare the parse against the brief).
6. Read-back. `designs[].read_back_numbers` all true.

Task verdict PASS = 1 ∧ 2 ∧ 3 ∧ 4 ∧ 5; 6 is reported. Keep the task verdict and the design verdict apart, as the exam
does: an INFEASIBLE brief handled correctly is a task PASS with design FAIL.

## 4. Running it

- The candidates are the design writers of step ③, every one the tool offers, on flash and on max
  (`bench.discover.run(brief, progress, agent=..., model=..., flow=...)`, added 2026-10-10):

  | agent | flow | what writes the design |
  |---|---|---|
  | `direct` | — | the model in one call with the retrieved cards (paper 2) and the Pilot's error list pasted back up to 20 times (paper 3). Closest to the exam's P1 with P3's retrieval; no outline. |
  | `opencode` | — | OpenCode in the sandbox with `./validate` |
  | `claude-code` | — | Claude Code in the sandbox with `./validate` |
  | `langflow` | `Langflow Agent, Pilot only chat` | the Langflow Agent with the official Pilot as its only tool |
  | `langflow` | `OpenCode with memory chat` | the OpenCode harness with memory search and the Pilot |
  | `langflow` | `Langflow Agent with memory chat · qwen3.8-max` | the Langflow Agent with memory search and the Pilot (the model is set at run time, the flow file is not edited) |

  Five writers × two models is the matrix; the local 27B is a third model if the GPU is free. The exam's P0 and P2
  are not writers of this step: the flow always repairs from the Pilot's errors and never outlines first.
- After any writer, the flow's repair loop (`_validate_design`) still runs on the returned text with the direct model
  of `MVP_LLM_MODEL`; a writer that validated with its own tool normally passes on the first parse (the smoke run with
  the Pilot-only flow on flash: both designs PASS, 0 repairs, 5 model calls).
- Cost and time. Direct on max: 6–11 calls, one to two minutes. Direct on flash: when a design fails, the 20 repairs
  push a run to about 28 calls and several minutes. Langflow writers: about five minutes per design on flash while
  the instance is busy. 1,152 briefs × 5 writers × 2 models is not a day; take a seeded subset (for example 100 briefs,
  stratified over the outcome kinds) × 3 repeats for every writer, and the full 1,152 only for the cheapest writer.
- Call `bench.discover.run(brief, progress, agent=, model=, flow=, record_dir=<your results folder>/records,
  latest=False)` in-process (the record carries `writer`), or the shell routes `/run/start … /run/decision` with
  `agent`, `model` and `flow` in the start body. Pass `record_dir` and `latest=False`: without them every scored run
  lands in `analysis/discover-<stamp>.json` and overwrites `discover-latest.json`, which are the results page's list
  of real runs and the input of `bench/simulate_design.py`. The 22 records of the 2026-10-10 pilot and smoke runs were
  moved to `analysis/part2-bench-writers/pilot-records/` for that reason. Do not route through the results page. The
  shell service picks up the `langflow` writer after its next restart (`python scripts/up.py`); the in-process call
  has it now.
- A sandboxed writer (`opencode`, `claude-code`) refuses while the results page (8770) is up. Langflow (7860) must be
  up for the `langflow` writers.
- Output: `analysis/part2-bench-<writer>-<model>-<stamp>/results.jsonl` (one row per brief and repeat, the choice, the
  expected outcome, the verdicts, the run stamp) and `summary.json`; a generator `bench/build_part2_bank.py`
  (choices → briefs and expected outcomes, seeded) and a runner `bench/run_part2_bench.py` that takes `--agent`,
  `--model` and `--flow`. Register nothing in `bench/FREEZE.md`; this is a side benchmark, not the frozen exam.
- Branch. `run()` writes design A from nothing (the "new" branch). The "adapt a similar project" branch exists only
  in the shell routes (`/run/adapt`) and fires when retrieval finds an approved design; the ADAPT kind needs that
  route and a seeded memory, so leave it out of the first matrix and say so.
- Gate rule change on 2026-10-10 evening (decision 038), found by stage 1: the requirements step now returns
  `missing_values`, an open value makes the gate `needs-person`, and a fifth gated check SOURCE fails any design number
  that is not in the brief. Runs started before the change used the old prompt and gate; for a comparable matrix, run
  stage 1 again and start stage 2 and 3 after the change. `bench.discover.gate_for(record)` re-gates a saved record
  once its checks are recomputed with `simulate(..., brief)`.
- The first pilot (2026-10-10, direct writer on flash, 20 briefs) scored 1/20: 22 of 40 designs failed the parse after
  20 repairs. The failing designs wrote `part definition` / `port definition` instead of `part def` / `port def`,
  and 19 of 21 attempts were byte-identical resubmissions. Two fixes are proposed and not applied: a stop after three
  identical resubmissions in `_validate_design` (the exam's loop has it), and the keyword rule in `DESIGN_RULES`.
  Keep the flash result as it is before either change; it is a finding about the cheap model as design writer.
- The results page (8770) can stay down; nothing here needs a sandboxed coding agent unless the OpenCode writer is
  used, in which case the page must be down.

## 5. Rules that still apply

Expected outcomes come from `budgets(choice)` and the brief's own numbers, never from a model and never typed by
hand. No model is a judge. Frozen files are not touched. Repository text in English. Report every failing check
as it is; do not change a limit to make a run pass.
