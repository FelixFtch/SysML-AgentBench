# 021 — Cost is reported in USD at list price

Date: 2026-10-03.

## Decision

Token counts are converted to USD with the official list prices, checked on 2026-10-03, stored in `bench/board_facts.py` (`PRICES`) with their source URLs:

| Model | Input | Cached input | Output | Source |
|---|---|---|---|---|
| qwen3.8-flash | $0.113 | $0.014 | $0.382 | Alibaba Cloud Model Studio, China (Beijing) |
| qwen3.8-max | $1.65 | $0.206 | $4.951 | same |
| jev-1.13 | $0.042 | — | free | OpenRouter |

Prices are per million tokens. Our endpoint is in cn-beijing, so that region's price is the main figure; the international price is shown for comparison. Free quota and promotions are not applied.

## Recording

`agents/llm.py` logs the usage of every call when a run sets `USAGE_LOG`. Discovery runs, MOD change runs and live console runs now record whole-run usage (checked with MOD-01 run 20261003T192237 and discovery run 20261003T192328). Nine first-batch matrix cells had no calls in `results.jsonl`; their `solve.json` (same official run id) has them and is used.

Not recorded: the qwen3.8-max judge over 288 answers, Claude Code through CCR, the two PURE tasks, older Part 2 runs (alignment and read-back) and older MOD runs. The page and `STATUS.md` list these instead of estimating them.

## What would reverse it

A billing export from the provider; it would replace list-price estimates.
