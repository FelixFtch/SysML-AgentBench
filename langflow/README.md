# RTRC flows in Langflow

The RTRC SysML v2 agent flows as Langflow 1.12.5 flows: the Part 2 agent flow (requirement → approvable design, new or reusing a similar project), the memory, exam cells, the results, the MOD change chain and the Cameo check. Each RTRC node calls the RTRC shell service (`bench/shell_service.py`), which runs the code the results page runs, so a run started here gives the page's retrieval, prompts, official Pilot results and checks, and its record shows on page 2.3 (`bench/langflow_parity.py` checks this). Qwen only for now. The numbers are synthetic, not an RTX specification.

## Start

```bash
python3.12 -m venv .venv-langflow && .venv-langflow/bin/pip install -r requirements-langflow.txt   # once
scripts/langflow.sh --import    # the shell service (127.0.0.1:8781) and Langflow (127.0.0.1:7860); imports the flows
```

Open http://127.0.0.1:7860 and log in as `rtrc` with the password in `.langflow/secrets.env`, which `scripts/langflow_secrets.py` creates (gitignored, never printed). The flows are in the project **RTRC SysML-AgentBench**; the RTRC nodes are in the component list under **Rtrc**. Run **RTRC F0: memory** once (Playground) to fill the knowledge base, and again after a design is approved. A sandboxed agent (Claude Code or OpenCode) only runs while the results page is stopped, because the page serves answer keys.

## The design assistant (for use)

**RTRC design assistant** is the flow to talk to. It is Langflow's Agent harness (`qwen3.8-max`, a LangGraph tool-calling loop with chat history) over our tools: the MCP server `tools/assistant_mcp.py` on 127.0.0.1:8782 (list_projects, search_memory with the page's retrieval, read_project, run_design, design_status, validate_sysml_text, write_to_memory, record_decision, export_cameo) and the knowledge base `rtrc memory` in Retrieve mode. Open it, press **Playground**, and write as you would to a colleague:

1. Ask what exists ("what projects are in the memory?"); it calls `list_projects` / `search_memory` and answers with the numbers.
2. Describe a need in your own words. It reads the related elements, computes the power / upload / storage budgets by hand, asks for any number it is missing, and shows the exact brief it would send. It never invents a number and never moves a stated limit.
3. Confirm ("方案 1，跑"). It calls `run_design`: the same verified pipeline as the fixed flow and the results page (requirements, designs A and B, the official Pilot repair loop, alignment, the four checks, trade-offs, diagram, Cameo export; 1 to 8 minutes). Its record appears on page 2.3.
4. Decide. "Approve A" writes the design into memory through the same gate as the page (all four checks must have passed); "Reject" or "Send back" records the decision with your reason.

The fixed flows below stay as the benchmark; this one is the product. Tested 2026-10-06 on a four-turn conversation (ask, change request, run, send back); each turn 10 to 70 seconds.

Set-up: `langflow/flows/setup_assistant.py` registers the MCP server and enables the chat model (run by `scripts/langflow.sh --import`). Langflow keeps credentials, knowledge bases and MCP servers per user, so if people log in with an account other than the superuser, run `langflow/flows/move_to_user.py <username>` once and restart Langflow.

## The flows

| Flow | What it shows | How it runs | Person |
|---|---|---|---|
| RTRC design assistant | the conversational assistant above: Agent harness, tools, memory | live, qwen3.8-max (the pipeline it calls can use flash, max or the local 27B) | asks, confirms, decides in the chat |
| RTRC agent flow: requirement to approved SysML v2 design | ① search memory → ② requirements → new design, or adapt the similar project found in memory → ④ official Pilot ⇄ repair → ⑤ align with memory → ⑥ checks and read-back → trade-offs if a check fails → ⑦ diagram, Cameo export, review → ⑧ decision → write to memory, record grades and times | live on Qwen (direct, or Claude Code / OpenCode on Qwen in the sandbox), or replay of a saved run | ⑧ Approve A, Approve B, Reject or Send back |
| RTRC F0: memory | MaritimeISR plus every approved design, as cards from the official parse; fills the Langflow knowledge base **rtrc memory** (Knowledge page: search the cards, filter by metadata) | Qwen embeddings for new cards only; runs in the server (editor or API), not with `lfx run` | |
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
- The RTRC nodes call the shell service, which reads `.env` itself; the service needs the token from `.langflow/secrets.env`, serves no answer key, and refuses sandboxed agents while the results page runs. The only key Langflow holds is the Qwen key for the knowledge base's embeddings (user decision of 2026-10-06): `langflow/flows/setup_knowledge.py` copies it from `.env` into an encrypted Langflow credential (provider "OpenAI Compatible", model `qwen3.7-text-embedding`) without printing it. The knowledge base itself is stored in `~/.langflow/knowledge_bases/`.
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
- `lfx run` needs `LANGFLOW_CONFIG_DIR`; it pauses at Human Input only with `--human-input`, reading a 1-based choice from stdin. It cannot run F0, whose Knowledge node needs the server's model provider settings.
- Qwen's embedding endpoint takes at most 20 texts per request; F0's Knowledge node sends 10. After a failed ingest, restart Langflow before retrying (Chroma otherwise reports "an instance already exists with different settings").

## Files

| Path | What |
|---|---|
| `langflow/components/rtrc/` | the RTRC nodes of the fixed flows: Start, Step (①–⑦), Record (⑨, writes memory on approve), Memory, Exam cell / step, MOD change / step, Results, Cameo export / record, Gate record |
| `langflow/flows/build_flows.py`, `*.json` | the flows as code, and the generated flow files |
| `langflow/flows/import_flows.py` | creates or updates the project |
| `langflow/flows/setup_knowledge.py` | the Qwen embedding provider and the knowledge base `rtrc_memory` (safe to repeat) |
| `langflow/flows/build_assistant.py`, `rtrc-assistant.json` | the design assistant flow as code |
| `langflow/flows/setup_assistant.py` | registers the MCP server and enables the chat model |
| `langflow/flows/move_to_user.py` | gives the project, credentials, knowledge base and MCP server to the account people log in with |
| `tools/assistant_mcp.py` | the assistant's MCP tools (streamable HTTP, 127.0.0.1:8782) |
| `bench/shell_service.py` | the local JSON API the nodes call |
| `bench/langflow_parity.py` | the parity checks |
| `scripts/langflow.sh`, `scripts/langflow_secrets.py`, `requirements-langflow.txt` | start, secrets, pinned versions |

The plan and its reasoning: [`plans/langflow-shell-plan.md`](../plans/langflow-shell-plan.md); the decision: [`docs/decisions/030-langflow-shell.md`](../docs/decisions/030-langflow-shell.md).
