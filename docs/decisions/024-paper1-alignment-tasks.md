# 024 · Paper 1 replicated on its own example; alignment becomes a scored task type (ALN)

Date: 2026-10-06. Status: accepted. Affects `bench/replicate_paper1.py` (new), `bench/build_aln_tasks.py` (new), `bench/score_alignment.py` (new), `agents/solve.py`, `bench/experiment.py`, `bench/validate_gold.py`, `bench/exam_board.py`, `bench/board.js`, the held-out index (24 → 27 tasks).

## Replication of the authors' pipeline (`analysis/paper1-replication-20261006T055247/`)

The authors' seven-stage prompt (`research/paper-artifacts/CMBSE-main/prompts/sysmlv2_alignment_process.md`, commit 42a8a0d) was run verbatim as the system prompt on their own OEM / supplier load-cell example, with qwen3.8-max, the script typing every "confirmed, proceed to Stage N". Departures: stage 0 and stage 5 were done by the official Pilot 0.62 instead of the model; no specification PDF was uploaded. 4 calls, 43,646 input and 13,916 output tokens.

| Check | Result |
|---|---|
| Authors' OEM, supplier and extension-library files through the Pilot | all three PASS |
| Authors' published package `IntegratedModel_Alignment.txt` through the Pilot with its sources | FAIL: `#RequireModification allocation def_LoadCell to loadcell_v1;` is not accepted (`no viable alternative at input 'to'`), `OverallSystem_v1::EnergySystem` uses `::` inside an allocation, and it imports `OEM::*` / `Supplier::*` although the packages are `OEMRequirements` / `LoadCellSolution`. The authors' own `stage6_diagnostics.csv` already lists four "target not found" entries |
| Mappings | 7 of the authors' 11 distinct (OEM, supplier) pairs were proposed by our run; our run proposed 16, including 4 supplier-only elements reported as unmatched and 3 plausible pairs the authors did not list. The 4 pairs only the authors have are their "auto-converted from alias due to type mismatch" definition-to-usage pairs |
| Generated package through the Pilot | FAIL: the model wrote `alloc def` / `alloc … from … to` and `target sup :>> …`, which are not SysML v2 |

Reading: the mapping stage transfers; the package stage does not survive the real tool, for the authors' file or for ours. That is the reason the project's alignment step keeps the model for proposals only and lets code write and the Pilot check the package.

## The ALN task type

Three sealed tasks, `bench/tasks/t4_maritime_isr/heldout/ALN-01..03`, written by `bench/build_aln_tasks.py`. Each gives a specification package and a supplier package (read-only, in `input/baseline/`) and asks for one alignment package of `alias` (definition and feature names) and `allocation` (usages) declarations plus a JSON report with `mappings` and `unmatched`. Synthetic maritime content, not an RTX specification.

Answer key (`gold/assertions.yaml`): `must_map` pairs with their construct, `must_not_map` look-alike pairs (heater power vs draw, control-in vs health-out, data rate vs transmit power, a definition aliased to a usage), `must_report_unmatched` elements. Reference packages in `gold/reference/` pass the Pilot and score PASS; `bench/validate_gold.py` checks them with the other gold files.

Scorer `bench/score_alignment.py`: the Pilot parses sources + package together; aliases are read from the export as `Membership` (member name → referenced element), allocations as `AllocationUsage` with ends resolved to usage paths; the package may own nothing but imports, aliases and allocations. Task PASS = parse PASS, every required pair declared with the right construct, no forbidden pair, no stray declaration, every listed unmatched element reported. Precision and recall over declared pairs are recorded alongside. Negative probes (a forbidden alias, a stray `part def`, a definition aliased to a usage, a misspelled target) each fail for the stated reason.

Solver: ALN answers go through the same repair loop as GEN/MOD (decision 022), with the two source files parsed alongside the package. The alignment rules state the toolchain's import convention (`private import`), that alias targets use `::` throughout and allocation ends use `Pkg::usage.nested`. The JSON report from the latest reply that had one is kept when a repair reply omits it.

First flash trial, P1, one repeat each (`analysis/trial-aln-flash-20261006T061550/`, `…T061828/`): ALN-02 PASS (9/9 pairs, both unmatched reported, 2 repairs); ALN-03 PASS at the first attempt once the path wording was fixed, and before that locked onto `Pkg.usage` paths for four attempts despite thirteen "Couldn't resolve reference" errors; ALN-01 FAIL in both runs, missing `imagery → videoOut` and pairing `Processor` with the supplier's recorder, which the key neither requires nor forbids.

## Part 2 alignment, same day

`bench/discover.align` now runs the paper's method the way the replication says it must: the model only proposes pairs; code checks both names exist, classifies each pair from the two official parses (`element_kinds`), and writes the package itself (`alignment_lines`): `alias` for two definitions or two definition features, `allocation` for two usages reached through usages, `alias` with a recorded level note when the design states a feature on a usage and the existing model states it in a definition, nothing for a part usage against a part definition (typing it is a design decision) or for a category mismatch (a part against a port). The package imports both sources privately and goes through the Pilot with them. Live run `20261006T063305`: 5 proposed, 5 verified, 5 declared (3 definitions, 2 level-noted features), package PASS.

Review: 2.3 shows every pair with its construct or the reason it was not declared, and Accept / Reject buttons. A decision is appended to `analysis/memory/alignment-reviews.jsonl` (`POST /api/review-mapping`) and written into the saved run; it cannot be undone from the page. One review exists, made while testing: `DesignA::ImageryPort ↔ MaritimeISR::ImageryPort` accepted.

The exam rules (`SYSML_RULES`) now also state the import convention, by the user's decision of 2026-10-06: in the flash and max trials no attempt ever wrote `private import` on its own; the attempts either kept the bare form or dropped the import and wrote `ScalarValues::Real`. The old matrix has 14 of 64 failures with that diagnostic first.

## Still open

- ALN keys have one author; the second review and the freeze are pending with the rest of the bank.
- The paper's extension metadata (`#FullyMatched` and the like) and its LLM-written element summaries are not used; the Pilot parse plays the summary's role.
- The authors' repository has no licence file; their prompt and models are used only in `research/` for this replication.
