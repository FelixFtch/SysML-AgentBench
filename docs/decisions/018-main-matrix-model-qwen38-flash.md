# 018 — The 288-cell matrix uses qwen3.8-flash

Date: 2026-10-03. Narrows decision 011 (flash for development, max for experiments).

## What was run

- Main matrix, 24 held-out tasks × P0–P3 × 3 repeats: qwen3.8-flash.
- OpenCode v1.18.27: qwen3.8-flash, so it compares with the matrix on the same model.
- Claude Code through CCR, graph retrieval, the MOD change chain and the Part 2 prototype: qwen3.8-max.

## Reason

The flash matrix ran in about 37 minutes (00:00–00:38 UTC) and cost about $0.05 at list price (China Beijing region). qwen3.8-max costs 13–15× more per token; running it first would have spent that before the scorer was settled, and decision 019 later showed the scorer still had a bug.

## Consequences

Results are reported as flash results. Nothing in them says how max or a frontier model would do. The live console on the exam page now has a model menu (qwen3.8-flash by default, qwen3.8-max optional); the chosen model is recorded with each run.

## What would reverse it

Running the full matrix on qwen3.8-max or a frontier model. That is still on the open list.
