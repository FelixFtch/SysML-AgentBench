# RTRC flows in Langflow

The RTRC SysML v2 agent flows as Langflow 1.12.5 flows: the Part 2 agent flow (requirement → approvable design, new or reusing a similar project), the memory, exam cells, the results, the MOD change chain and the Cameo check. Each RTRC node calls the RTRC shell service (`bench/shell_service.py`), which runs the code the results page runs, so a run started here gives the page's retrieval, prompts, official Pilot results and checks, and its record shows on page 2.3 (`bench/langflow_parity.py` checks this). Qwen only for now. The numbers are synthetic, not an RTX specification.

## Start

```bash
python3.12 -m venv .venv-langflow && .venv-langflow/bin/pip install -r requirements-langflow.txt   # once
scripts/langflow.sh --import    # the shell service (127.0.0.1:8781) and Langflow (127.0.0.1:7860); imports the flows
```

Open http://127.0.0.1:7860 and log in as `rtrc` with the password in `.langflow/secrets.env`, which `scripts/langflow_secrets.py` creates (gitignored, never printed). The flows are in the project **RTRC SysML-AgentBench**; the RTRC nodes are in the component list under **Rtrc**. Run **RTRC F0: memory** once (Playground) to fill the knowledge base, and again after a design is approved. A sandboxed agent (Claude Code or OpenCode) only runs while the results page is stopped, because the page serves answer keys.

## The design assistant (for use)

**RTRC design assistant** is the flow to talk to: Chat Input → **RTRC OpenCode assistant** → Chat Output. The middle node runs OpenCode (the exam's pinned binary) on the local Qwen3.8-27B, with the RTRC MCP server `tools/assistant_mcp.py` (127.0.0.1:8782) as its only tools: list_projects, search_memory (the page's retrieval), read_project, run_design, design_status, validate_sysml_text, write_to_memory, record_decision, export_cameo. Its own file and shell tools are off, and session titles use the same local model, so nothing leaves this computer. Open it, press **Playground**, and write as you would to a colleague:

1. Ask what exists ("what projects are in the memory?"); it calls the memory tools and answers with the numbers.
2. Describe a need in your own words. It reads the related elements, asks for any number it is missing, and shows the exact brief it would send. It never invents a number and never moves a stated limit.
3. Confirm. It calls `run_design`: the same verified pipeline as the agent flow and the results page (requirements, designs A and B, the official Pilot, alignment, the four checks, trade-offs, diagram, Cameo export; 2 to 10 minutes). Inside, a second, sandboxed OpenCode writes each design with `./validate` in hand, so **stop the results page (8770) first**; if it is running, the assistant says so and offers the direct writer instead. Its record appears on page 2.3.
4. Decide. "Approve A" writes the design into memory through the same gate as the page (all four checks must have passed); "Reject" or "Send back" records the decision with your reason.

Each chat session continues one OpenCode session (the mapping is in `~/.rtrc-assistant/sessions.json`). The same assistant in the terminal: `scripts/assistant.sh` (OpenCode's own interface; `scripts/assistant.sh "a message"` for one turn, `--cloud` for qwen3.8-max). The workspace `~/.rtrc-assistant` is written by `tools/assistant/workspace.py` from `tools/assistant/rtrc-assistant.md` (the rules) and the provider configuration of `agents/external/opencode_run.py`. Decision 032 says why the designs are written by OpenCode and not by the model directly: written directly, the 27B got stuck on `part usage vessel` for 20 identical repairs; OpenCode gets the Pilot's errors as a tool result and edits the file.

## The local model

The 3-bit Qwen3.8-27B runs on this machine's RTX 4090 through Ollama (127.0.0.1:11434). `scripts/qwen38.sh --serve` starts Ollama and builds the tag `qwen3.8-27b-q3:64k` (the published weights with a 64k context, so the whole model stays on the GPU: `scripts/qwen38.sh --status` shows the placement); `scripts/langflow.sh` and `scripts/assistant.sh` call it. In the fixed flows it is the model `qwen3.8-27b (Ollama)`, usable with **Qwen direct** and with **OpenCode (sandbox)**; Claude Code still uses the cloud Qwen. **RTRC agent flow · local Qwen3.8-27B via OpenCode** is the agent flow with those presets, so a measuring run makes no call outside this computer.

Langflow keeps credentials and knowledge bases per user, so if people log in with an account other than the superuser, run `langflow/flows/move_to_user.py <username>` once after an import and restart Langflow.

## The flows

| Flow | What it shows | How it runs | Person |
|---|---|---|---|
| RTRC design assistant | the conversational assistant above: OpenCode on the local 27B, the RTRC tools, memory | live, local only | asks, confirms, decides in the chat |
| RTRC design assistant (Langflow Agent, qwen3.8-max) | the same tools and rules on Langflow's own Agent component, `run_design` with the model writing directly (decision 031); kept to compare the two harnesses | live, qwen3.8-max (cloud) | the same |
| RTRC design assistant · unfolded (qwen3.8-max) / (local 27B) | the assistant with its parts on the canvas: Langflow's Agent, one card per RTRC tool, the knowledge base, and the design pipeline as a flow the Agent runs as a tool; **write to memory pauses for approval** (decision 033) | live; the pipeline runs on the local 27B with OpenCode | asks, confirms, decides in the chat; approves on a card |
| RTRC design pipeline | the design pipeline as a tool of the unfolded assistants: ① memory → ② requirements → ③ designs by OpenCode in the sandbox → ④ official Pilot → ⑤ alignment → ⑥ checks → trade-offs → ⑦ review; no person's step (the chat decides). Edit it and the unfolded assistants run the edited version | live, local only; results page stopped | |
| RTRC agent flow: requirement to approved SysML v2 design | ① search memory → ② requirements → new design, or adapt the similar project found in memory → ④ official Pilot ⇄ repair → ⑤ align with memory → ⑥ checks and read-back → trade-offs if a check fails → ⑦ diagram, Cameo export, review → ⑧ decision → write to memory, record grades and times | live on Qwen (direct, or Claude Code / OpenCode on Qwen in the sandbox), or replay of a saved run | ⑧ Approve A, Approve B, Reject or Send back |
| RTRC agent flow · local Qwen3.8-27B via OpenCode | the same flow, preset to OpenCode in the sandbox on the local 27B; every model call stays on this machine | live, local only (Ollama); results page stopped | the same decision |
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
| `langflow/components/rtrc/` | the RTRC nodes: the OpenCode assistant, and the fixed flows' Start, Step (①–⑦), Record (⑨, writes memory on approve), Memory, Exam cell / step, MOD change / step, Results, Cameo export / record, Gate record |
| `tools/assistant_mcp.py` | the assistant's tools (MCP, streamable HTTP, 127.0.0.1:8782) |
| `tools/assistant/`, `scripts/assistant.sh` | the assistant's rules and OpenCode workspace; the terminal entry |
| `langflow/flows/build_assistant.py`, `rtrc-assistant-langchain.json`, `setup_assistant.py` | the Langflow-Agent comparison flow; the per-user set-up of every Langflow-Agent flow (credentials, Ollama address, models, MCP registration) |
| `langflow/flows/rtrc-assistant-unfolded*.json`, `rtrc-pipeline-tool.json` | the unfolded assistants and the pipeline flow they run as a tool (built by `build_flows.py`; needs the MCP server running for the tool descriptions) |
| `langflow/flows/build_flows.py`, `*.json` | the flows as code, and the generated flow files |
| `langflow/flows/import_flows.py` | creates or updates the project |
| `langflow/flows/setup_knowledge.py` | the Qwen embedding provider and the knowledge base `rtrc_memory` (safe to repeat) |
| `langflow/flows/move_to_user.py` | gives the project, credentials and knowledge base to the account people log in with |
| `bench/shell_service.py` | the local JSON API the nodes call |
| `bench/langflow_parity.py` | the parity checks |
| `agents/llm_local.py`, `agents/external/opencode_run.py` | the local model: direct calls, and OpenCode's provider pointed at Ollama |
| `scripts/qwen38.sh`, `tools/ollama/qwen3.8-27b-q3-64k.Modelfile` | Ollama and the local tag |
| `scripts/langflow.sh`, `scripts/langflow_secrets.py`, `requirements-langflow.txt` | start, secrets, pinned versions |

The plan and its reasoning: [`plans/langflow-shell-plan.md`](../plans/langflow-shell-plan.md); the decisions: [`docs/decisions/030-langflow-shell.md`](../docs/decisions/030-langflow-shell.md), [`031`](../docs/decisions/031-design-assistant.md) (the assistant's tools and rules), [`032`](../docs/decisions/032-opencode-harness-local-model.md) (OpenCode as its harness, the local model) and [`033`](../docs/decisions/033-unfolded-assistant.md) (the assistant unfolded on the canvas).
