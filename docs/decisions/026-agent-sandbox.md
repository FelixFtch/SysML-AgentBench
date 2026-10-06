# 026 · Off-the-shelf agents run in a sandbox without answer keys; the first agent batches of 2026-10-06 are discarded

Date: 2026-10-06. Status: accepted (user decision). Affects `agents/external/jail.py` (new), `agents/external/opencode_run.py`, `bench/run_opencode.py`, `bench/run_claude_qwen.py`, `bench/run_side.py` (new), `bench/batches.py` (new).

## What was found

Both agent batches launched with the frozen bank on 2026-10-06 (81 runs each, qwen3.8-flash) were unusable as scores:

- **OpenCode** worked in a workspace inside the repository with `--auto`. In 23 of 81 runs it opened files in the held-out task folders; in several it read the answer key of the task it was solving (`heldout/GEN-01/gold/assertions.yaml`, `heldout/GEN-02/gold/assertions.yaml` and the GEN-02 reference model, `heldout/GEN-05/gold/assertions.yaml`, which it then scored with the project's scorer). Its 77/81 is not a clean score. The 2026-10-03 OpenCode batch had the same access; 8 of its 24 runs mention gold paths.
- **Claude Code** ran with `-p` and no pre-approved tools. Every Bash call (43) and Write call (10) was denied, so it never ran the validator and wrote no files; 60/81 is a one-shot answer through Claude Code's system prompt, not the setup OpenCode had.

Both batches stay on disk (`analysis/opencode-qwen3.8-flash-20261006T070152/`, `analysis/claude-qwen3.8-flash-20261006T070153/`), are listed as discarded with the reason in `bench/batches.py`, and their cost is shown separately.

## Rule now

Both agents get the same thing and nothing else:

- a fresh workspace with the task input, `AGENTS.md` (also as `CLAUDE.md`) and `./validate`, a wrapper around the official Pilot 0.62 that prints the status and every diagnostic;
- the same prompt: the task statement plus "Write the answer into answer.md in this workspace. Follow AGENTS.md. The official SysML v2 validator is available as ./validate …";
- the same tools: OpenCode with `--auto`; Claude Code with Bash, Read, Write, Edit, Glob and Grep pre-approved; no MCP server for either; a 900 s limit per run;
- a bubblewrap sandbox (`agents/external/jail.py`): the repository is an empty tmpfs except the validator (read-only, its compile directory a private copy), the pinned OpenCode binary and the SysML standard library; the home directory is fresh per run (node and the Claude Code binary read-only, OpenCode's provider packages read-only with the MCP entry removed, a copy of the CCR client config); `/tmp`, `/root` and `/run/user` are empty; a new PID namespace and `/proc`, so other processes' root directories are unreachable. The network is shared for the model API, so the results page server (which serves keys on localhost) is stopped while agents run.

A probe inside the sandbox showed only `mvp/`, `tools/` and `vendor/` under the repository path, no `bench/tasks`, `analysis`, `docs` or `mvp/runs`, an empty `/tmp`, four visible processes, and `./validate` returning PASS on a good file and the expected `mismatched input 'import'` on a bad one. The grader parses only the final answer, outside the sandbox, with the frozen scorer.

What the agents do not get: the direct prompts carry `SYSML_RULES` (and `ALIGN_RULES` for ALN) in the system message; the agents get the task statement, `AGENTS.md` and `./validate`, and learn the Pilot's rules only from its diagnostics.

## Validator order (found after the first sandboxed batch)

The official Pilot 0.62 can give a different verdict for the same files in a different order. The adapter loads every file, resolves all references, then validates the files one by one in the order given; some checks read state that validating an earlier file computes. An alignment package that names a nested usage as `Pkg::part::sub` (the tasks ask for `Pkg::part.sub`) fails with `validateSubsettingFeaturingTypes: Must be an accessible feature (use dot notation for nesting)` when the two source models come first, and passes when the package comes first.

The scorer always lists the sources first, and the direct candidates' repair loop uses the scorer. `./validate` passed the files in the order the agent typed them, and both agents typed their own file first. Re-validating every graded ALN answer with the package first (`bench/check_validator_order.py`, output `analysis/validator-order-20261006.json`) changed none of the 72 direct answers and none of the three gold packages, and 8 of the 15 ALN answers the agents submitted in the first sandboxed batch (OpenCode 3, Claude Code 5; three Claude Code runs hit the 900 s limit without an answer). In all 8 the agent's own check had passed the package it submitted; the scorer failed it. No other task type validates more than one file: every non-ALN `./validate` call of both agents had a single file.

By the user's decision of 2026-10-06, `./validate` now passes the files in the scorer's order (the file that declares the requested package last), and all 18 ALN runs (9 per agent) were rerun in the same sandbox (`analysis/opencode-jail-aln-qwen3.8-flash-*`, `analysis/claude-jail-aln-qwen3.8-flash-*`). `bench/batches.py` takes the agents' ALN rows from the rerun; the first batch's ALN rows stay on disk and are listed as superseded with the reason and their cost. The Pilot itself is frozen and unchanged.

Rerun result: OpenCode passes 8 of 9 ALN runs (first batch 6), Claude Code 7 of 9 (first batch 1; both failures hit the 900 s limit). Every rerun answer gets the same verdict in both file orders. With the rerun rows, OpenCode passes 77 of 81 runs and Claude Code 76 of 81; after freeze revision 2 re-scored three of their clarifications (decision 028), both pass 78 of 81.

The side benchmarks (`bench/run_side.py`) put SysEngBench (100 questions, seed 20261006, 10 per prompt) and PURE (2 excerpts) to all four candidates, the agents in the same sandbox.
