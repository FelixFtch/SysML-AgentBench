# 5 · The cards (custom components)

**You get:** every card in the Langflow sidebar: what it does, its inputs and outputs, what it calls.
**You need:** nothing; find the card you dragged onto the canvas.

Each card is one Python class in [`langflow/components/cards/`](../../langflow/components/cards/). Langflow loads the folder at
start (`LANGFLOW_COMPONENTS_PATH`). The cards do little themselves: most call the shell service
(`bench/shell_service.py`, 127.0.0.1:8781) over HTTP, which runs the same functions the results page runs. Change a
card, restart Langflow. How to write one: [06-make-your-own.md](06-make-your-own.md), section B.

This page is generated from the card files by `langflow/scripts/card_docs.py`; do not edit it by hand.

## Cameo export (when licensed)

`CardCameoExport` · file [`cards/card_cameo.py`](../../langflow/components/cards/card_cameo.py)

Exports a run's designs for Cameo's SysML v2 edition. The official Pilot stays the judge; Cameo's result is recorded as agreement.

| Input | Type | What it is |
|---|---|---|
| **Run id** | MessageText | A run id such as 20261006T211951, or a message that contains it. |

| Output | Method |
|---|---|
| **Instructions** | `export` |

Calls the shell service at: `/cameo/export`.

**From the file:** Cameo export: writes a run's officially parsed designs as .sysml files for Cameo's SysML v2 edition and says
how to check them. Cameo has no headless command, so a person opens the file; the result is recorded with Cameo record.

## Cameo record

`CardCameoRecord` · file [`cards/card_cameo_record.py`](../../langflow/components/cards/card_cameo_record.py)

Put one after each Human Input branch. Stores the person's Cameo check of a design next to the official Pilot's verdict.

| Input | Type | What it is |
|---|---|---|
| **From the person's choice** | Message |  |
| **This branch** | Dropdown |  Options: Opens cleanly, Errors in Cameo, Not checked yet. |
| **Design** | Dropdown |  Options: A, B. |
| **Note (for example the Cameo error)** | Str |  |

| Output | Method |
|---|---|
| **Message** | `record` |

Calls the shell service at: `/cameo/result`.

**From the file:** Cameo record: one node per Human Input branch; stores the person's Cameo check of a design next to the official
Pilot's verdict (interoperability evidence). The Pilot stays the judge.

## Chat

`CardChat` · file [`cards/card_chat.py`](../../langflow/components/cards/card_chat.py)

A person's message to an exam candidate, as written, in a conversation that continues: the direct model with one approach, or a coding agent in its sandbox. The official Pilot parses a reply only when it holds a model. Nothing is scored.

| Input | Type | What it is |
|---|---|---|
| **Message** | Message | Whatever the person writes. A question gets an answer; a request for a model gets a model. |
| **Candidate** | Dropdown |  Options: Direct model · P0 one answer, Direct model · P1 repair from errors, Direct model · P2 outline first, Direct model · P3 retrieval then outline, OpenCode in the sandbox, Claude Code in the sandbox. |
| **Model** | Dropdown | Pick one of the names our runs used, or type any name: a cloud name goes to the endpoint of .env (or to the agent's own provider when OPENCODE_MODEL / CLAUDE_CODE_MODEL is set), '<tag> (Ollama)' to a model you pulled into Ollama (docs/langflow/02-keys-and-models.md). Options: qwen3.8-flash, qwen3.8-max, qwen3.8-27b (Ollama). Any value may be typed. |
| **Repair rounds (P1 to P3)** (advanced) | Int | How many times the official Pilot's error list goes back to the model in this conversation. P0 never repairs. |
| **Messages kept** (advanced) | Int | How many earlier messages of this session the direct model sees. The sandboxed agents keep their own session. |

| Output | Method |
|---|---|
| **Reply** | `as_message` |
| **Details** | `as_data` |

Calls the shell service at: `/chat/turn`.

**From the file:** Chat: the chat version of an exam candidate (decision 036). The person's message goes to the candidate as
written, in the conversation of this Langflow session, and the reply comes back. Nothing is scored.

Candidates: the direct model with one approach (P0 one answer; P1 the official Pilot's complete error list back for
repair; P2 an outline first; P3 retrieval from the official examples with the person's words, then the outline), or a
coding agent in a persistent sandbox (OpenCode, Claude Code) with ./validate and its own session continued across
messages. The shell service runs it (bench/shell_service.py /chat/turn, bench/chat_turns.py).

## Exam cell

`CardExamCell` · file [`cards/card_exam_cell.py`](../../langflow/components/cards/card_exam_cell.py)

One exam cell: replay any graded cell, or run a sealed task live on Qwen (direct or a sandboxed coding agent). Not added to any score.

| Input | Type | What it is |
|---|---|---|
| **Mode** | Dropdown |  Options: Replay a graded cell, Live: direct Qwen (P0–P3), Live: sandboxed agent on Qwen. |
| **Cell to replay** | Str | candidate:repeat:task:approach, e.g. flash:1:GEN-03:P1, max:2:ALN-02:P3, opencode:1:MOD-05:P-CODE, retry-claude:1:ALN-02 |
| **Task for a live run** | Str |  |
| **Approach (direct)** | Dropdown |  Options: P0, P1, P2, P3. |
| **Agent (sandboxed)** | Dropdown |  Options: opencode, claude-code. |
| **Model** | Dropdown | Pick one of the names our runs used, or type any name: a cloud name goes to the endpoint of .env, '<tag> (Ollama)' to a model you pulled into Ollama. The frozen columns were run on qwen3.8-flash (docs/langflow/02-keys-and-models.md). Options: qwen3.8-flash, qwen3.8-max, qwen3.8-27b (Ollama). Any value may be typed. |

| Output | Method |
|---|---|
| **Cell** | `as_data` |
| **Summary** | `as_message` |

Calls the shell service at: `/exam/agent-run`, `/exam/cell`, `/exam/run`.

**From the file:** Exam cell: F1 / F2, one exam cell, replayed from the archive or run live on Qwen; the answer key is used
only by the scorer and never returned.

## Exam step

`CardExamStep` · file [`cards/card_exam_step.py`](../../langflow/components/cards/card_exam_step.py)

One step of the exam cell, from the cell record: its state, the official errors, the verdict or the agent's tool calls.

| Input | Type | What it is |
|---|---|---|
| **Cell record** | JSON |  |
| **Step** | Dropdown |  Options: Issue task, Retrieve notes, Outline, Write answer, Official syntax, Repair from errors, Read values, Check against key…. |

| Output | Method |
|---|---|
| **Cell record** | `pass_on` |
| **This step** | `show` |

**From the file:** Exam step: shows one step of an exam cell (page 1.1 / 1.4) from the cell record, and passes the record on.
No service call: the cell record comes from Exam cell.

## Gate record

`CardGateRecord` · file [`cards/card_gate.py`](../../langflow/components/cards/card_gate.py)

Put one after each Human Input branch of a stop-and-ask gate; records the person's choice.

| Input | Type | What it is |
|---|---|---|
| **From the person's choice** | Message |  |
| **Gate** | Str |  |
| **This branch** | Str |  |

| Output | Method |
|---|---|
| **Message** | `record` |

Calls the shell service at: `/gate/decision`.

**From the file:** Gate record: one node per Human Input branch of a stop-and-ask gate (AGENTS.md: a stated limit may only change
with a person's approval). Stores the choice in analysis/langflow-gates.jsonl.

## Memory (paper 2)

`CardMemory` · file [`cards/project_memory.py`](../../langflow/components/cards/project_memory.py)

F0: MaritimeISR and every approved design as element cards from the official parse, with their links.

| Input | Type | What it is |
|---|---|---|
| **After (optional)** (advanced) | Message | Connect the card that changes the memory (the write card of the write-to-memory tool) so the library is read after the write; F0 leaves it empty. |

| Output | Method |
|---|---|
| **Summary** | `as_message` |
| **Cards** | `as_dataframe` |
| **Data** | `as_data` |

Calls the shell service at: `/memory`.

**From the file:** Memory: F0, the library the agent searches (paper 2): MaritimeISR plus every approved design, as cards
built from the official Pilot parse. The DataFrame output can be ingested into a Langflow knowledge base for browsing.

## MOD change

`CardModChange` · file [`cards/card_mod.py`](../../langflow/components/cards/card_mod.py)

F5: one change to an existing model (MOD-01 to MOD-05): the latest saved run, or a new run on Qwen (two model calls).

| Input | Type | What it is |
|---|---|---|
| **Task** | Dropdown |  Options: MOD-01, MOD-02, MOD-03, MOD-04, MOD-05. |
| **Mode** | Dropdown |  Options: Replay the latest run, Run it again (live). |

| Output | Method |
|---|---|
| **Case** | `as_data` |
| **Summary** | `as_message` |

Calls the shell service at: `/mod/case`, `/mod/run`.

**From the file:** MOD change: F5, the MOD change chain (page 2.4): the model edits an existing model, the official tool
judges it, a limit change stops for a person, and the model reads the edited model back. Replayed or run live.

## MOD step

`CardModStep` · file [`cards/card_mod_step.py`](../../langflow/components/cards/card_mod_step.py)

One step of the MOD change chain, from the case record.

| Input | Type | What it is |
|---|---|---|
| **Case record** | JSON |  |
| **Step** | Dropdown |  Options: Task and baseline, Model change, Official syntax, Task and design verdicts, Limit check, Read-back. |

| Output | Method |
|---|---|
| **Case record** | `pass_on` |
| **This step** | `show` |

**From the file:** MOD step: shows one step of a MOD change run (page 2.4) from the case record and passes the record on.
The "Limit check" message starts with "moved" or "unchanged", so an If-Else can stop for a person when a stated limit moved.

## OpenCode assistant

`CardOpenCodeAssistant` · file [`cards/card_opencode.py`](../../langflow/components/cards/card_opencode.py)

One turn of the design assistant: OpenCode with the tools (memory, the verified design pipeline, the official Pilot, the memory gate, decisions, Cameo export); or, in exam mode, one exam answer.

| Input | Type | What it is |
|---|---|---|
| **Engineer's message** | Message | Ask what exists, describe a need, confirm the brief it proposes, or decide on a run. In exam mode: one task statement. |
| **Mode** (advanced) | Dropdown |  Options: Chat: one OpenCode session per Langflow session, all nine tools, Exam: a fresh session per message, answer only, memory search and the official Pilot as the only tools. |
| **Model** (advanced) | Dropdown | Pick one of the names our runs used, or type any name: a cloud name goes to the endpoint of .env (or to OpenCode's own provider when OPENCODE_MODEL is set), '<tag> (Ollama)' to a model you pulled into Ollama. The exam flows used qwen3.8-flash. Options: qwen3.8-27b (Ollama), qwen3.8-max, qwen3.8-flash. Any value may be typed. |

| Output | Method |
|---|---|
| **Answer** | `turn` |

**From the file:** OpenCode assistant: one turn of the conversational design assistant per chat message, or one exam answer.

The assistant is OpenCode (the exam's pinned binary) with the MCP tools (tools/assistant_mcp.py on
127.0.0.1:8782) as its only tools; its file and shell tools are off. The workspace is prepared by
tools/assistant/workspace.py outside the repository. Decision 032.

Chat mode: the local Qwen3.8-27B served by Ollama (or a cloud Qwen), all nine tools, and each Langflow chat session
maps to one OpenCode session, so the conversation continues across messages.
Exam mode (decision 035): the exam workspace, qwen3.8-flash, the exam prompt, memory search and the official Pilot as
the only tools, and a fresh OpenCode session for every message, so one task cannot see another.

## Record the decision

`CardRecord` · file [`cards/card_record.py`](../../langflow/components/cards/card_record.py)

⑨ Put one after each Human Input branch. Approve writes the design into memory (paper 2; refused unless all four checks passed). Every branch saves the decision with each stage's verdict, attempts, seconds, model calls and cost.

| Input | Type | What it is |
|---|---|---|
| **From the person's choice** | Message |  |
| **This branch** | Dropdown |  Options: Approve design A, Approve design B, Reject, Send back. |
| **Note** | Str |  |

| Output | Method |
|---|---|
| **Message** | `as_message` |
| **Data** | `as_data` |

Calls the shell service at: `/run/approve`, `/run/decision`.

**From the file:** Record: ⑨ one node per Human Input branch. Approve writes the design into memory (paper 2); every branch saves
the person's decision with the grades and the times, the record page 2.3 shows.

## Results

`CardResults` · file [`cards/card_results.py`](../../langflow/components/cards/card_results.py)

F3: the frozen exam results (revision 2) as tables.


| Output | Method |
|---|---|
| **Tables** | `as_message` |
| **By task type** | `as_dataframe` |
| **Data** | `as_data` |

Calls the shell service at: `/facts`.

**From the file:** Results: F3, the frozen results (page 1.2) as tables: by task type, by approach, the agents, the side
benchmarks, the retry run and the cost. The matrix, cost chart and diagrams stay on the results page.

## Start

`CardStart` · file [`cards/card_start.py`](../../langflow/components/cards/card_start.py)

Starts one run of the agent flow: the brief, the agent and the Qwen model, or a replay of a saved run without model calls.

| Input | Type | What it is |
|---|---|---|
| **Requirement / brief** | Multiline | Everything the agent receives. Empty: the default brief of the 2.2 design space on the results page. |
| **Agent** | Dropdown | The model directly, or Claude Code / OpenCode running on it inside the bubblewrap sandbox. Options: Qwen direct, Claude Code on Qwen (sandbox), OpenCode on Qwen (sandbox). |
| **Model** | Dropdown | Pick one of the names our runs used, or type any name: a cloud name goes to the endpoint of .env, '<tag> (Ollama)' to a model you pulled into Ollama (docs/langflow/02-keys-and-models.md). Options: qwen3.8-flash, qwen3.8-max, qwen3.8-27b (Ollama). Any value may be typed. |
| **Replay a saved run** | Str | Empty for a live run. 'latest' or a run id such as 20261006T211951 replays that run without model calls. |
| **Refuse an empty brief** (advanced) | Bool | On in the pipeline used as a tool: an empty brief is an error, never the default brief of page 2.2. A tool call with a wrong argument name then fails loudly instead of running the demo numbers. |

| Output | Method |
|---|---|
| **Run** | `start` |

Calls the shell service at: `/run/start`.

**From the file:** Start: begins one run of the agent flow (Part 2) through the shell service (bench/shell_service.py).

## Step

`CardStep` · file [`cards/card_step.py`](../../langflow/components/cards/card_step.py)

One step of the agent flow, run by the code behind the results page through the shell service.

| Input | Type | What it is |
|---|---|---|
| **From the previous step** | Message |  |
| **Or from the other branch** | Message | Where two branches join (new or reuse; checks passed or trade-offs), connect the second branch here. |
| **Step** | Dropdown |  Options: ① Search memory (paper 2), ② Requirements, ③ New design (paper 3 create), ③ Adapt the similar project (paper 3 modify), ④ Official SysML v2 Pilot ⇄ repair (paper 3 loop), ⑤ Align with memory (paper 1), ⑥ Checks + read-back (paper 3 query), Trade-offs (catalog only, code recomputes)…. |

| Output | Method |
|---|---|
| **Message** | `as_message` |
| **Data** | `as_data` |

Calls the shell service at: `/run/adapt`, `/run/align`, `/run/checks`, `/run/design`, `/run/requirements`, `/run/retrieve`, `/run/review`, `/run/tradeoffs`, `/run/validate`.

**From the file:** Step: one step of the agent flow, run by the existing pipeline through the shell service.
The step and the paper it applies are chosen in the Step field; the node passes the run id on in its message.

## Tool step

`CardTool` · file [`cards/card_tool.py`](../../langflow/components/cards/card_tool.py)

One card of an assistant tool unfolded on the canvas; runs the code behind the results page through the shell service.

| Input | Type | What it is |
|---|---|---|
| **Engineer's text** | Message | From the sub-flow's Chat Input: the search words, '<run id> A' or '<run id> B', or the pasted SysML. |
| **From the previous card** | Message | Keeps the cards in order; the Pilot card reads the saved file from here, the prompt-part cards read the run id. |
| **Or from the other branch** | Message |  |
| **Card** | Dropdown |  Options: Memory library (paper 2): MaritimeISR + approved designs as cards, MiniLM + FAISS seeds (paper 2): cosine ≥ 0.30 + exact-name bonus, One hop of neighbours (paper 2) → cards for the assistant, Gate: Pilot PASS and all four checks PASS? (read only), Write the design into memory (through the page's gate), Record the approval on the run (page 2.3), Save the pasted SysML as a file, Official SysML v2 Pilot on that file…. |

| Output | Method |
|---|---|
| **Message** | `as_message` |
| **Data** | `as_data` |

Calls the shell service at: `/tool/gate`, `/tool/memory/hop`, `/tool/memory/library`, `/tool/memory/seeds`, `/tool/prompt-part`, `/tool/record-approval`, `/tool/validate/pilot`, `/tool/validate/save`, `/tool/write`.

**From the file:** Tool step: one card of an assistant tool unfolded into a sub-flow (decision 034): memory search (library,
MiniLM + FAISS seeds, one hop), write to memory (gate, write, record), validate pasted SysML (save, official Pilot),
and the read-only prompt-part cards of the design pipeline. Every card is stateless and calls the shell service,
which runs the same code as the results page; the chain order on the canvas is kept by the "From the previous card"
input. The engineer's text (query, "<run id> A", or SysML) comes from the sub-flow's Chat Input.
