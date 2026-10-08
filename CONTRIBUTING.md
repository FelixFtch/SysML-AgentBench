# Contributing

Everything that is not frozen is open to change. This page is the whole set of rules.

## What is frozen, and what that means

`bench/FREEZE.md` lists the task bank, the answer keys, the scorers, the P0–P3 solver and the model client with their hashes; `python3 bench/freeze.py --check` must print `unchanged`. A change to one of those is a new freeze and a new batch of results, not an edit: open an issue first. Everything else — flows, cards, tools, runners, the page, the documentation — is yours to improve.

## Adding a flow

1. Build it in Langflow, test it in the Playground.
2. Export it into the repository: `python langflow/scripts/export_flows.py --new "<flow name>" --project <folder>` (folders: `1-direct-model`, `2-coding-agents`, `3-opencode-with-memory`, `4-langflow-agent-with-memory`, `5-shared-tools`, `6-other`). The script empties credential fields and prints the line to add to `langflow/flows/catalog.py`.
3. Add that line to `catalog.PROJECTS`, run `python langflow/scripts/catalog_readme.py`, and add a paragraph to `docs/langflow/04-flows.md` under the project (what it does, what to click).
4. If you examined it, commit its `analysis/langflow-exam-<column>-<model>-<stamp>/` folder too (results, summary, answers; a few hundred KB).

## Adding a card or a tool

A card is a file in `langflow/components/rtrc/`; a tool is a function in `tools/assistant_mcp.py` or a flow used through Run Flow. The how-to with the pitfalls is `docs/langflow/06-make-your-own.md`. Add a section to `docs/langflow/05-cards.md` for a card.

## Adding a column to the results page

Nothing to register: `bench/langflow_exam.py --flow "<name>" --column <id>` writes a folder the page picks up. To add a *direct* or *sandboxed* candidate on a new model, run the runners (`bench/experiment.py`, `bench/run_opencode.py`, `bench/run_claude_qwen.py`) and add a cohort to `bench/batches.py` (`LOCAL_MATRIX` shows the shape).

## Prices

The results page converts tokens to dollars with `PRICES` in `bench/board_facts.py`. Add a model with its official list price and the source URL; a model without an entry shows `—`. Never estimate a price.

## Pull requests

- One topic per pull request; say what you ran to check it.
- `python3 bench/freeze.py --check` → `unchanged`. `python3 -m py_compile` on what you touched; `node --check bench/board.js` if you touched the page.
- `rg -n "sk-|api_key\"?\s*[:=]\s*\"[^\"]" langflow/flows` prints nothing (no key in a flow file).
- English in files; British or American spelling, either, consistently within a file.
- Numbers in documentation come from a saved file you can name; do not write a number you cannot point to.

## Decisions

Design changes that others must know about get a short record in `docs/decisions/` (date, what was decided, why, what it affects, how it was checked). Read the last few before proposing something that looks like it was tried.
