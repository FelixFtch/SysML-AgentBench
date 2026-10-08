# 5 · The sandboxed coding agents

**You get:** what the OpenCode and Claude Code columns are, why they need Linux, and how to run them.
**You need:** Linux (or WSL2 on Windows), `bwrap` (`apt install bubblewrap`), the agent installed ([../langflow/01-install.md](../langflow/01-install.md) steps 5–6), Java for the Pilot. 10 minutes to read; a column takes hours to run.

## What the agent sees

Each run gets a fresh workspace with three things: the task's `input/` (the statement and any given models), a rules file (`AGENTS.md` / `CLAUDE.md`: write the answer into `answer.md`, run `./validate`, never invent a number), and `./validate`, a script that runs the official SysML v2 Pilot on a file. The agent decides what to do; it may write, read and run the validator as often as it likes (OpenCode: no limit inside 900 s; Claude Code: 60 turns). The grader then parses `answer.md` once and scores it. The agent never gets the rules the direct approaches get, and never sees a key.

The workspace is wrapped in **bubblewrap** (`agents/external/jail.py`): the agent process sees the workspace, its own home, the system libraries and the network, and nothing else of this computer. In particular it cannot see the repository, so not `bench/tasks/*/gold/`, not earlier runs, not other tasks. We checked why this matters: a first batch without the jail let the agent read the whole repository, and it read answer keys in several runs, including the key of the task it was solving (GEN-01, GEN-02, GEN-05); that batch is kept but not scored (`DISCARDED` in `bench/batches.py`).

## Why Linux

bubblewrap is a Linux program (user namespaces). On Windows, WSL2 is Linux and runs everything here. On macOS there is no bubblewrap; the honest options are a Linux machine, or a Linux container that mounts only the workspace (not built yet; `agents/external/jail.py` is the one file a Docker variant would replace). An unjailed run (`run_opencode(..., jailed=False)`) exists for debugging and must never be scored.

The page also keeps itself out of the way: `bench/exam_board.py` serves answer keys over HTTP, and the sandbox shares the network, so the runners and the shell service refuse a sandboxed exam while the page is up. Stop the page, run, start it again. Chats are not refused: a conversation is not scored.

## Run a column

```bash
.venv/bin/python bench/run_opencode.py    --model qwen3.8-flash --repeats 3 --workers 3     # 81 runs → analysis/opencode-jail-<model>-<stamp>/
.venv/bin/python bench/run_claude_qwen.py --model qwen3.8-flash --repeats 3 --workers 3     # 81 runs → analysis/claude-jail-<model>-<stamp>/
```

`--model` takes a cloud name (routed as [../langflow/02-keys-and-models.md](../langflow/02-keys-and-models.md) describes: `OPENCODE_MODEL` / `CLAUDE_CODE_MODEL`, or the `.env` endpoint) or `"<tag> (Ollama)"` for a local model. `--resume <folder>` continues an interrupted batch. The folder is picked up by the page when it is listed as a cohort in `bench/batches.py` (`LOCAL_MATRIX` shows the shape; the frozen four are `COHORTS`).

What our runs took: on the cloud flash with three workers, both batches started 13:37 UTC and their ALN reruns started 15:27 UTC the same day, so under two hours each; on the local 27B with one worker (one GPU), OpenCode 81 runs in 1 h 33 min and Claude Code 81 runs in 4 h 13 min (`analysis/*-local27b-*/summary.json`, `started`, and the next batch's start).

## Reading a run

`mvp/agent-runs/<stamp>-<id>-P-CODE-<task>/`: `workspace/` (what the agent left, including `answer.md` and every `validation/` folder of `./validate`), `stdout.jsonl` or `stdout.json` (the agent's own event log, tokens included), `stderr.txt`. Section 1.6 of the page shows the tool calls of a run in order.

Next: [6 · The task bank](06-task-bank.md).
