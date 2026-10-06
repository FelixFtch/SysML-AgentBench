# RTRC flows in Langflow

The RTRC SysML v2 agent flows as Langflow 1.12.5 flows: the Part 2 agent flow (requirement → approvable design, new or reusing a similar project), the memory, exam cells, the results, the MOD change chain and the Cameo check. Each RTRC node calls the RTRC shell service (`bench/shell_service.py`), which runs the code the results page runs, so a run started here gives the page's retrieval, prompts, official Pilot results and checks, and its record shows on page 2.3 (`bench/langflow_parity.py` checks this). Qwen only for now. The numbers are synthetic, not an RTX specification.

## Start

```bash
python3.12 -m venv .venv-langflow && .venv-langflow/bin/pip install -r requirements-langflow.txt   # once
scripts/langflow.sh --import    # the shell service (127.0.0.1:8781) and Langflow (127.0.0.1:7860); imports the flows
```

Open http://127.0.0.1:7860 and log in as `rtrc` with the password in `.langflow/secrets.env`, which `scripts/langflow_secrets.py` creates (gitignored, never printed). The flows are in the project **RTRC SysML-AgentBench**; the RTRC nodes are in the component list under **Rtrc**. A sandboxed agent (Claude Code or OpenCode) only runs while the results page is stopped, because the page serves answer keys.

## The flows

| Flow | What it shows | How it runs | Person |
|---|---|---|---|
| RTRC agent flow: requirement to approved SysML v2 design | ① search memory → ② requirements → new design, or adapt the similar project found in memory → ④ official Pilot ⇄ repair → ⑤ align with memory → ⑥ checks and read-back → trade-offs if a check fails → ⑦ diagram, Cameo export, review → ⑧ decision → write to memory, record grades and times | live on Qwen (direct, or Claude Code / OpenCode on Qwen in the sandbox), or replay of a saved run | ⑧ Approve A, Approve B, Reject or Send back |
| RTRC F0: memory | MaritimeISR plus every approved design, as cards from the official parse | no model call | |
| RTRC F1: exam cell, direct model | one exam cell step by step: task, retrieved notes, outline, answer, every Pilot attempt, repair, read values, verdict against the sealed key (missing items only), archive | replay any graded cell, or a live run (not added to any score) | |
| RTRC F2: exam cell, sandboxed coding agent | the same for OpenCode / Claude Code, with their tool calls | replay, or live | |
| RTRC F3: results | the frozen exam results as tables | no model call | |
| RTRC F5: MOD change chain | baseline → change → official syntax → task and design verdicts → read-back; if a stated limit moved, a person decides | replay, or run again on Qwen | keep the limit, or approve the new one |
| RTRC Cameo check (when licensed) | exports a run's passing designs for Cameo's SysML v2 edition | no model call | opens cleanly, errors in Cameo, not checked yet |

Run a flow from the editor's **Playground**. The agent flow's brief goes in the chat box (empty: the default brief of page 2.2). At ⑧ the run pauses and the editor shows a **Waiting for Human Input** card with the review text, the diagram link and the four choices; picking one finishes the run, and the chat shows the grades and times. To replay a saved run without model calls, set **Replay a saved run** in the agent node to `latest` or a run id; a replay writes nothing to memory and does not appear on page 2.3.

Click a node after a run (Inspect output) to read what it did: the retrieved cards, every Pilot attempt with its errors, the alignment pairs, the checks.

### Where the three papers are used

| Paper | Nodes |
|---|---|
| 2 · Bader et al., GRAG | ① Search memory (cards from the official parse, MiniLM + FAISS, seeds plus one hop); the approve branches write the design into memory |
| 3 · Longshore, Bell, Madachy | ③ create (rules + template + examples) and modify (adapt the similar project); ④ the correction loop, with the Pilot's errors in place of a person; ⑥ read-back is its query use |
| 1 · Li, Husung, Wang | ⑤ the alias / allocate alignment package; ⑧ the person's review |

### Cameo

⑦ writes each design that passes the Pilot to `analysis/cameo-exports/<run>/`. When RTRC provides the license, open it in Cameo's SysML v2 edition and record the result with **RTRC Cameo check** (type the run id); the result is stored on the run's record as agreement. The official Pilot stays the judge, and Cameo has no headless command, so this is a person's step.

## Without the editor

```bash
set -a; . .langflow/secrets.env; set +a
export RTRC_SHELL_URL=http://127.0.0.1:8781 LANGFLOW_CONFIG_DIR=$PWD/.langflow/config
.venv-langflow/bin/lfx run --human-input langflow/flows/rtrc-agent-flow.json "your brief"   # asks for the decision on the terminal
.venv-langflow/bin/lfx run langflow/flows/rtrc-f3-results.json ""
```

Through the server: `POST /api/v2/workflows` with `{"flow_id", "input_value", "tweaks", "mode": "background"}`; the job becomes `suspended` at ⑧; `GET /api/v2/workflows/pending?flow_id=…` gives the request id and choices; `POST /api/v2/workflows/{job_id}/resume` with `{"request_id", "decision": {"action_id": "send_back"}}` finishes it.

## What this setup enforces

- Local only (127.0.0.1), login on, sign-ups inactive, CORS limited to the local origin.
- `LANGFLOW_ALLOW_CUSTOM_COMPONENTS=False`: only built-in components and the code in `langflow/components` run; edited or pasted component code is refused, and the built-in code-execution components are disabled. Only the admin may edit component code.
- No model key in Langflow: the RTRC nodes call the shell service, which reads `.env` itself. The service needs the token from `.langflow/secrets.env`, serves no answer key, and refuses sandboxed agents while the results page runs.
- The flow files hold no key. Check before committing: `rg -l "sk-|api_key\":\s*\"[^\"]" langflow/flows` should print nothing.

## Changing the flows

The flows are code. Edit `langflow/flows/build_flows.py` or the components, then:

```bash
LANGFLOW_CONFIG_DIR=$PWD/.langflow/config .venv-langflow/bin/python langflow/flows/build_flows.py
.venv-langflow/bin/python langflow/flows/import_flows.py      # updates the project in place
```

The import overwrites edits made in the editor; export a flow first to keep them. Restart the shell service after changing `bench/shell_service.py`.

Learned with Langflow 1.12.5:

- **Human Input:** give each choice its own chain of nodes. Langflow skips the unchosen branches, but a node fed by two branches receives the review text on both (it cannot tell which was picked), and a node after two branch nodes fails with "has not been built yet". If-Else branches can join again.
- **Python graph API:** components added with `graph.add_component` after `Graph(start, end)` appear in `dump()` only after `graph.initialize()`.
- An input cannot be named after a `Component` method (`run`). The flow list is returned gzip-compressed.
- `lfx run` needs `LANGFLOW_CONFIG_DIR`; it pauses at Human Input only with `--human-input`, reading a 1-based choice from stdin.

## Files

| Path | What |
|---|---|
| `langflow/components/rtrc/` | the RTRC nodes: Start, Step (①–⑦), Record (⑨, writes memory on approve), Memory, Exam cell / step, MOD change / step, Results, Cameo export / record, Gate record |
| `langflow/flows/build_flows.py`, `*.json` | the flows as code, and the generated flow files |
| `langflow/flows/import_flows.py` | creates or updates the project |
| `bench/shell_service.py` | the local JSON API the nodes call |
| `bench/langflow_parity.py` | the parity checks |
| `scripts/langflow.sh`, `scripts/langflow_secrets.py`, `requirements-langflow.txt` | start, secrets, pinned versions |

The plan and its reasoning: [`plans/langflow-shell-plan.md`](../plans/langflow-shell-plan.md); the decision: [`docs/decisions/030-langflow-shell.md`](../docs/decisions/030-langflow-shell.md).
