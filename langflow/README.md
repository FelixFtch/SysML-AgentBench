# RTRC flows in Langflow

The RTRC SysML v2 flows as Langflow 1.12.5 flows, in six projects (decision 035): each exam candidate has an **exam** version (one sealed task in, scored by the frozen scorer outside Langflow) and a **chat** version (a task text or a conversation in, the answer out, nothing scored) side by side; the shared tool flows the memory assistants run; and the design agent flow with a person's decision, the knowledge-base fill, the results tables, the MOD change chain and the Cameo check. Each RTRC node calls the RTRC shell service (`bench/shell_service.py`), which runs the code the results page runs, so a run started here gives the page's retrieval, prompts, official Pilot results and checks (`bench/langflow_parity.py` checks this). Qwen only for now. The numbers are synthetic, not an RTX specification.

## Start

```bash
python3.12 -m venv .venv-langflow && .venv-langflow/bin/pip install -r requirements-langflow.txt   # once
scripts/langflow.sh --import    # the shell service (127.0.0.1:8781), the MCP server (8782), Ollama, Langflow (7860); imports the flows
```

Open http://127.0.0.1:7860 and log in as `rtrc` with the password in `.langflow/secrets.env`, which `scripts/langflow_secrets.py` creates (gitignored, never printed); if people log in with another account, run `langflow/flows/move_to_user.py <username>` once after an import. The RTRC nodes are in the component list under **Rtrc**. Run **Memory knowledge base fill** once (Playground) to fill the knowledge base; the write-to-memory flow refreshes it after an approval. A sandboxed agent (Claude Code, OpenCode) and the OpenCode exam only run while the results page (8770) is stopped, because the page serves answer keys.

## The six projects

| Project | Exam version (a sealed task in, scored) | Chat version (a text in, the answer out) |
|---|---|---|
| **1 · Direct model, approaches P0 to P3** | `Direct model exam · P0 one-shot`, `· P1 repair from errors`, `· P2 outline first`, `· P3 retrieval then outline`: the exam cell with the approach preset; type a task id | `Direct model chat · P0 … P3`: the same fixed path on a task text you type; the official Pilot parses a model answer; no key |
| **2 · Coding agents without memory** | `OpenCode in the sandbox exam`, `Claude Code in the sandbox exam` (the sandbox of decision 026: files and `./validate`); `Langflow Agent, Pilot only exam` (Langflow's Agent with the official Pilot as its only tool) | `OpenCode in the sandbox chat`, `Claude Code in the sandbox chat`, `Langflow Agent, Pilot only chat` |
| **3 · OpenCode with memory** | `OpenCode with memory exam`: the assistant's harness on qwen3.8-flash, the exam prompt, memory search and the Pilot as its only tools, a fresh session per task | `OpenCode with memory chat`: the design assistant (below) |
| **4 · Langflow Agent with memory** | `Langflow Agent with memory exam`: the same exam prompt and the same two tools as project 3, on Langflow's Agent | `Langflow Agent with memory chat · qwen3.8-max`, `· local Qwen3.8-27B` (the assistant unfolded, one card per tool), `· one MCP card (decision 031)` |
| **5 · Shared tool flows** | `Memory search`, `Validate SysML with the official Pilot`, `Write to memory`, `Design pipeline`: run as tools by projects 3 and 4; open one to see its cards | |
| **6 · Other** | `Design agent flow with a person's decision`, `· local Qwen3.8-27B via OpenCode`, `Memory knowledge base fill`, `Exam results tables`, `MOD change chain`, `Cameo check` | |

The names and projects are in `langflow/flows/catalog.py`. Every exam version uses qwen3.8-flash, the model of the frozen exam, so the columns compare harnesses, not models.

### Sitting the exam through Langflow

```bash
python3 bench/langflow_exam.py --flow "OpenCode with memory exam"          # 27 tasks × 3, a new column on results page 1.3
python3 bench/langflow_exam.py --flow "Langflow Agent with memory exam"
python3 bench/langflow_exam.py --flow "Langflow Agent, Pilot only exam"
python3 bench/langflow_exam.py --flow "Direct model exam · P1 repair from errors" --repeats 1   # a rerun of a frozen column, kept as a record
```

The runner sends each task's statement (as the direct candidates get it) through the flow's Chat Input, a fresh session per cell, scores the reply with the frozen scorer (`bench.experiment.validate_and_grade`: the official Pilot once, then the key), and records wall time, tool calls and tokens (the Agent's usage field; the OpenCode node's usage file). The three columns of projects 2, 3 and 4 appear on results page 1.3 next to the four frozen candidates, grey until run, with time and tokens in each cell's tooltip; they are not part of the frozen score. A rerun of a project-1 or project-2 cell flow is saved under `analysis/langflow-rerun-*` and shown nowhere. The exam versions never see an answer key: the prompt is the task statement, the key is opened only by the scorer. Stop the results page (8770) before the OpenCode or sandboxed exams. Langflow shows a user only its own flows, so the runner (which logs in as the superuser) imports a private copy of the flow it needs into the project `RTRC exam runner (admin)` when the people's copy is not visible to it.

What the exam versions have and lack: the OpenCode and Langflow-Agent exams get the exam prompt (`tools/assistant/rtrc-assistant-exam.md` with the frozen rules of `agents/solve.py`), and two tools at most (memory search over MaritimeISR and the approved designs; the official Pilot); no design pipeline, no write to memory, no conversation. The direct approaches have no tools; the sandboxed agents have files and `./validate` and no rules in the prompt, as in the frozen batches.

## The design assistant (for use)

**OpenCode with memory chat** (project 3) is the flow to talk to: Chat Input → **RTRC OpenCode assistant** → Chat Output. The middle node runs OpenCode (the exam's pinned binary) on the local Qwen3.8-27B, with the RTRC MCP server `tools/assistant_mcp.py` (127.0.0.1:8782) as its only tools: list_projects, search_memory (the page's retrieval), read_project, run_design, design_status, validate_sysml_text, write_to_memory, record_decision, export_cameo. Its own file and shell tools are off, and session titles use the same local model, so nothing leaves this computer. Open it, press **Playground**, and write as you would to a colleague:

1. Ask what exists ("what projects are in the memory?"); it calls the memory tools and answers with the numbers.
2. Describe a need in your own words. It reads the related elements, asks for any number it is missing, and shows the exact brief it would send. It never invents a number and never moves a stated limit.
3. Confirm. It calls `run_design`: the same verified pipeline as the design agent flow and the results page (requirements, designs A and B, the official Pilot, alignment, the four checks, trade-offs, diagram, Cameo export; 2 to 10 minutes). Inside, a second, sandboxed OpenCode writes each design with `./validate` in hand, so **stop the results page (8770) first**; if it is running, the assistant says so and offers the direct writer instead. Its record appears on page 2.3.
4. Decide. "Approve A" writes the design into memory through the same gate as the page (all four checks must have passed); "Reject" or "Send back" records the decision with your reason.

Each chat session continues one OpenCode session (the mapping is in `~/.rtrc-assistant/sessions.json`). The same assistant in the terminal: `scripts/assistant.sh` (OpenCode's own interface; `scripts/assistant.sh "a message"` for one turn, `--cloud` for qwen3.8-max). The workspace `~/.rtrc-assistant` is written by `tools/assistant/workspace.py` from `tools/assistant/rtrc-assistant.md` (the rules) and the provider configuration of `agents/external/opencode_run.py`; `--mode exam` writes the exam workspace `~/.rtrc-assistant-exam`. Decision 032 says why the designs are written by OpenCode and not by the model directly: written directly, the 27B got stuck on `part usage vessel` for 20 identical repairs; OpenCode gets the Pilot's errors as a tool result and edits the file.

**Langflow Agent with memory chat** (project 4) is the same assistant with its parts on the canvas: Langflow's Agent in the middle, one card per tool, the knowledge base, and the four shared tool flows run through Run Flow; **write to memory pauses for your approval** on its card (decisions 033, 034). Edit a shared tool flow and the assistant runs the edited version.

## The local model

The 3-bit Qwen3.8-27B runs on this machine's RTX 4090 through Ollama (127.0.0.1:11434). `scripts/qwen38.sh --serve` starts Ollama and builds the tag `qwen3.8-27b-q3:64k` (the published weights with a 64k context, so the whole model stays on the GPU: `scripts/qwen38.sh --status` shows the placement); `scripts/langflow.sh` and `scripts/assistant.sh` call it. In the fixed flows it is the model `qwen3.8-27b (Ollama)`, usable with **Qwen direct** and with **OpenCode (sandbox)**; Claude Code still uses the cloud Qwen. **Design agent flow · local Qwen3.8-27B via OpenCode** is the design agent flow with those presets, so a measuring run makes no call outside this computer. The exam versions use qwen3.8-flash (cloud), the model of the frozen exam.

Langflow keeps credentials and knowledge bases per user, so if people log in with an account other than the superuser, run `langflow/flows/move_to_user.py <username>` once after an import and restart Langflow.

After a design is approved, the memory tools see it at once (they re-read `analysis/memory/approved.jsonl`), and the write-to-memory flow also refreshes the knowledge base `rtrc_memory`; only an approval made in the OpenCode chat or on the design agent flow's ⑧ card still needs **Memory knowledge base fill** run once to refresh that knowledge base.

## The design flows and the rest (project 6)

| Flow | What it shows | How it runs | Person |
|---|---|---|---|
| Design agent flow with a person's decision | ① search memory → ② requirements → new design, or adapt the similar project found in memory → ④ official Pilot ⇄ repair → ⑤ align with memory → ⑥ checks and read-back → trade-offs if a check fails → ⑦ diagram, Cameo export, review → ⑧ decision → write to memory, record grades and times | live on Qwen (direct, or Claude Code / OpenCode on Qwen in the sandbox), or replay of a saved run | ⑧ Approve A, Approve B, Reject or Send back |
| Design agent flow · local Qwen3.8-27B via OpenCode | the same flow, preset to OpenCode in the sandbox on the local 27B; every model call stays on this machine | live, local only (Ollama); results page stopped | the same decision |
| Design pipeline (project 5) | the design pipeline as a tool of the memory assistants: ① memory → ② requirements → ③ designs by OpenCode in the sandbox, with the rules, template and examples it was given shown as read-only cards → ④ official Pilot → ⑤ alignment → ⑥ checks → trade-offs → ⑦ review; no person's step (the chat decides) | live, local only; results page stopped | |
| Memory search (project 5) | library → MiniLM + FAISS seeds → one hop → cards (paper 2) | no model call | |
| Write to memory (project 5) | gate (Pilot PASS, four checks PASS) → write → record → library re-read → knowledge base `rtrc_memory` refreshed; run after the approval card | Qwen embeddings for the new cards | approves on the card |
| Validate SysML with the official Pilot (project 5) | pasted text saved as a file → official Pilot → verdict (paper 3) | no model call | |
| Memory knowledge base fill | MaritimeISR plus every approved design, as cards from the official parse; fills the Langflow knowledge base **rtrc_memory** (Knowledge page: search the cards, filter by metadata) | Qwen embeddings for new cards only; runs in the server (editor or API), not with `lfx run` | |
| Exam results tables | the frozen exam results as tables | no model call | |
| MOD change chain | baseline → change → official syntax → task and design verdicts → read-back; if a stated limit moved, a person decides | replay, or run again on Qwen | keep the limit, or approve the new one |
| Cameo check (when licensed) | exports a run's passing designs for Cameo's SysML v2 edition | no model call | opens cleanly, errors in Cameo, not checked yet |

Run a flow from the editor's **Playground**. The design agent flow's brief goes in the chat box (empty: the default brief of page 2.2). At ⑧ the run pauses and the editor shows a **Waiting for Human Input** card with the review text, the diagram link and the four choices; picking one finishes the run, and the chat shows the grades and times. To replay a saved run without model calls, set **Replay a saved run** in the agent node to `latest` or a run id; a replay writes nothing to memory and does not appear on page 2.3. An exam cell flow (projects 1 and 2) replays a graded cell when its mode is set to *Replay a graded cell* with a cell id such as `flash:1:GEN-03:P1`.

Click a node after a run (Inspect output) to read what it did: the retrieved cards, every Pilot attempt with its errors, the alignment pairs, the checks.

### Where the three papers are used

| Paper | Nodes |
|---|---|
| 2 · Bader et al., GRAG | ① Search memory (cards from the official parse, MiniLM + FAISS, seeds plus one hop); the approve branches write the design into memory; the P3 approach's retrieval over the official examples |
| 3 · Longshore, Bell, Madachy | ③ create (rules + template + examples) and modify (adapt the similar project); ④ the correction loop, with the Pilot's errors in place of a person; ⑥ read-back is its query use; the P1 to P3 repair loop of the exam |
| 1 · Li, Husung, Wang | ⑤ the alias / allocate alignment package; ⑧ the person's review; the ALN tasks of the exam |

### Cameo

⑦ writes each design that passes the Pilot to `analysis/cameo-exports/<run>/`. When RTRC provides the license, open it in Cameo's SysML v2 edition and record the result with **Cameo check** (type the run id); the result is stored on the run's record as agreement. The official Pilot stays the judge, and Cameo has no headless command, so this is a person's step.

## Without the editor

```bash
set -a; . .langflow/secrets.env; set +a
export RTRC_SHELL_URL=http://127.0.0.1:8781 LANGFLOW_CONFIG_DIR=$PWD/.langflow/config
.venv-langflow/bin/lfx run --human-input langflow/flows/other-design-agent-flow.json "your brief"   # asks for the decision on the terminal
.venv-langflow/bin/lfx run langflow/flows/other-exam-results.json ""
```

Through the server: `POST /api/v2/workflows` with `{"flow_id", "input_value", "tweaks", "mode": "background", "session_id"}`; the job becomes `suspended` at ⑧; `GET /api/v2/workflows/pending?flow_id=…` gives the request id and choices; `POST /api/v2/workflows/{job_id}/resume` with `{"request_id", "decision": {"action_id": "send_back"}}` finishes it. The status route answers 500 while a run is in flight; `bench/langflow_exam.py` polls the job table instead and reads the route once the job has ended.

## What this setup enforces

- Local only (127.0.0.1), login on, sign-ups inactive, CORS limited to the local origin.
- `LANGFLOW_ALLOW_CUSTOM_COMPONENTS=False`: only built-in components and the code in `langflow/components` run; edited or pasted component code is refused, and the built-in code-execution components are disabled. Only the admin may edit component code.
- The RTRC nodes call the shell service, which reads `.env` itself; the service needs the token from `.langflow/secrets.env`, serves no answer key, and refuses sandboxed agents while the results page runs. The only key Langflow holds is the Qwen key for the knowledge base's embeddings (user decision of 2026-10-06): `langflow/flows/setup_knowledge.py` copies it from `.env` into an encrypted Langflow credential (provider "OpenAI Compatible", model `qwen3.7-text-embedding`) without printing it. The knowledge base itself is stored in `~/.langflow/knowledge_bases/`.
- The flow files hold no key. Check before committing: `rg -l "sk-|api_key\":\s*\"[^\"]" langflow/flows` should print nothing.

## Changing the flows

The flows are code. Edit `langflow/flows/build_flows.py` or the components, then:

```bash
LANGFLOW_CONFIG_DIR=$PWD/.langflow/config .venv-langflow/bin/python langflow/flows/build_flows.py
.venv-langflow/bin/python langflow/flows/import_flows.py      # updates the six projects in place
```

The import overwrites edits made in the editor; export a flow first to keep them. Restart the shell service after changing `bench/shell_service.py`, and Langflow after changing or adding a component under `langflow/components` (it registers component code at start and refuses code it does not know).

Learned with Langflow 1.12.5:

- **Human Input:** give each choice its own chain of nodes. Langflow skips the unchosen branches, but a node fed by two branches receives the review text on both (it cannot tell which was picked), and a node after two branch nodes fails with "has not been built yet". If-Else branches can join again.
- **Python graph API:** components added with `graph.add_component` after `Graph(start, end)` appear in `dump()` only after `graph.initialize()`.
- An input cannot be named after a `Component` method (`run`), and not with `config` or `kwargs` in its name: Langflow parses such a parameter as JSON and drops it when that fails (`lfx.interface.initialize.loading.convert_kwargs`), so the exam cell's approach field was ignored until it was renamed (decision 035). The flow list is returned gzip-compressed.
- A Run Flow tool stores its sub-flow's Chat Output message under the caller's session, so the caller's own message is found by flow id, not by session alone.
- `lfx run` needs `LANGFLOW_CONFIG_DIR`; it pauses at Human Input only with `--human-input`, reading a 1-based choice from stdin. It cannot run F0, whose Knowledge node needs the server's model provider settings.
- Qwen's embedding endpoint takes at most 20 texts per request; F0's Knowledge node sends 10. After a failed ingest, restart Langflow before retrying (Chroma otherwise reports "an instance already exists with different settings").

## Files

| Path | What |
|---|---|
| `langflow/flows/catalog.py` | the six projects, the flow names and slugs, the retired names |
| `langflow/components/rtrc/` | the RTRC nodes: the OpenCode assistant (chat and exam modes), Exam chat (the chat versions of projects 1 and 2), and the fixed flows' Start, Step (①–⑦), Record (⑨, writes memory on approve), Memory, Exam cell / step, MOD change / step, Results, Cameo export / record, Gate record |
| `bench/langflow_exam.py` | sits the 27-task exam through a flow: the three Langflow columns of page 1.3, or a rerun of a frozen column |
| `tools/assistant_mcp.py` | the assistant's tools (MCP, streamable HTTP, 127.0.0.1:8782) |
| `tools/assistant/`, `scripts/assistant.sh` | the assistant's rules (`rtrc-assistant.md`), the exam prompt (`rtrc-assistant-exam.md`), the OpenCode workspaces (chat and exam); the terminal entry |
| `langflow/flows/build_assistant.py`, `rtrc-assistant-langchain.json`, `setup_assistant.py` | the one-MCP-card comparison flow of decision 031; the per-user set-up of every Langflow-Agent flow (credentials, Ollama address, the models including qwen3.8-flash for the exams, MCP registration) |
| `langflow/flows/langflow-agent-*.json`, `tool-*.json` | the Langflow-Agent flows (chat and exam) and the shared tool flows (built by `build_flows.py`; needs the MCP server running for the tool descriptions) |
| `langflow/components/rtrc/rtrc_tool.py` | the cards of the tool flows (memory library, seeds, hop; gate, write, record; save, Pilot; the pipeline's prompt parts), calling `/tool/...` of the shell service |
| `langflow/flows/build_flows.py`, `*.json` | the flows as code, and the generated flow files |
| `langflow/flows/import_flows.py` | creates the six projects and creates or updates the flows; removes retired names |
| `langflow/flows/setup_knowledge.py` | the Qwen embedding provider and the knowledge base `rtrc_memory` (safe to repeat) |
| `langflow/flows/move_to_user.py` | gives the six projects, credentials and knowledge base to the account people log in with |
| `bench/shell_service.py` | the local JSON API the nodes call |
| `bench/langflow_parity.py` | the parity checks |
| `agents/llm_local.py`, `agents/external/opencode_run.py` | the local model: direct calls, and OpenCode's provider pointed at Ollama |
| `scripts/qwen38.sh`, `tools/ollama/qwen3.8-27b-q3-64k.Modelfile` | Ollama and the local tag |
| `scripts/langflow.sh`, `scripts/langflow_secrets.py`, `requirements-langflow.txt` | start, secrets, pinned versions |

The plan and its reasoning: [`plans/langflow-shell-plan.md`](../plans/langflow-shell-plan.md); the decisions: [`docs/decisions/030-langflow-shell.md`](../docs/decisions/030-langflow-shell.md), [`031`](../docs/decisions/031-design-assistant.md) (the assistant's tools and rules), [`032`](../docs/decisions/032-opencode-harness-local-model.md) (OpenCode as its harness, the local model), [`033`](../docs/decisions/033-unfolded-assistant.md) (the assistant unfolded on the canvas), [`034`](../docs/decisions/034-unfolded-tools.md) (the tools as flows) and [`035`](../docs/decisions/035-six-projects-exam-and-chat.md) (the six projects, the exam versions, the Langflow columns of page 1.3).
