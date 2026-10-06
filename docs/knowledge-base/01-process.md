# 1. The process: from a brief to an approved design

This is the loop the Part 2 prototype implements (decision 020), with what the exam taught folded in. Every step has one owner; a model never owns a decision.

| Step | Owner | What happens | Rule learned in this project |
|---|---|---|---|
| 0 · Brief | Person | States the mission need and the numbers that bind: limits, rates, budgets. | Every later number must trace to the brief or to an officially parsed model. |
| 1 · Retrieve | Code | MiniLM + FAISS over element cards made from Pilot-parsed existing models and approved designs; 4 seeds plus their one-hop neighbours become the "examples" in the prompt. | Retrieval supplies context, never decisions. Pin the embedding stack and let a missing dependency stop the run; a silent fallback changes the method unnoticed (decision 023). |
| 2 · Requirements | Model | Numbered requirements, each with an attribute name and value, plus questions. | A number that is not in the brief is flagged as of unknown origin. When a value is missing, the model asks instead of inventing one (task type AMB). |
| 3 · Designs | Model | Two candidate designs written in SysML v2. | The prompt states the Pilot's conventions (page 2); without them a weak model repeats the same syntax error. |
| 4 · Official validation and repair | Official Pilot, then the model | The Pilot parses each design. On failure the complete diagnostic list (line, column, message) goes back in the same conversation, with every earlier version; at most 20 repairs, stopping after three identical resubmissions. | Only the Pilot decides syntax; no model judges (decisions 022, 025). |
| 5 · Align | Model proposes, code writes, Pilot checks, person reviews | The model proposes "design element ↔ existing element" pairs. Code checks both names exist, classifies each pair from the two official parses, and writes an alignment package of `alias` and `allocation` lines; the Pilot parses it with both sources; a person accepts or rejects each pair. | A model-written alignment package does not survive the Pilot (paper 1 replication, decision 024). Validate multi-file packages in one fixed order (decision 026). Neither source model is edited. |
| 6 · Checks and read-back | Code, then model | Power, uplink, storage and traceability are computed from the officially parsed numbers; the model restates the design as requirement sentences, which are compared with the brief. | The task verdict (did it do what was asked) and the design verdict (does the design meet its budget) are separate; an over-budget design is reported, never hidden by raising the limit (decision 019). |
| 7 · Decide and remember | Person, then code | A person approves a design only when all checks pass; an approved design joins the retrieval library. When a design fails a budget, the model may propose trade-offs from the catalog, and code recomputes each one before a person sees it. | The model may propose relaxing a requirement but never applies it; the approval gate refuses a raised limit. |

## What a person must own

- The numbers in the brief and the answer keys used to check the work.
- Any change to a requirement, limit, rate or budget.
- Which alignment pairs are accepted.
- Which design enters memory.

## What the evidence says about each step

- **Model choice dominates** (page 3): on the 27-task exam the stronger model gains far more than any added step.
- **Repair** (step 4) is cheap and is what lets a weaker model reach a parsing model; the cap of 20 was never reached.
- **Retrieval** (step 1) finds the right elements (13 of 15 on the query tasks) but did not change the exam pass rate measurably.
- **Alignment** (step 5) is the lowest task type for the cheaper model and both agents, and the second lowest for the stronger model; this is why code writes the package and a person reviews the pairs.
- **The checks** (step 6) give definite verdicts: on the over-budget task every candidate reported the overrun.

Evidence: Part 2 runs `analysis/discover-*.json`; memory `analysis/memory/approved.jsonl`; alignment reviews `analysis/memory/alignment-reviews.jsonl`; results page section 2.
