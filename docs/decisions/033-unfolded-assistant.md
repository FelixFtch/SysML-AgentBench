# 033 · The assistant unfolded on the canvas: one card per tool, the pipeline as a flow run as a tool, approval as a card

Date: 2026-10-07. Status: done (user decision of 2026-10-07: add, do not change; both an OpenAI-compatible qwen3.8-max and a local Qwen3.8-27B version). Adds three flows next to the ten of decisions 030 to 032; nothing existing was changed. Affects `langflow/flows/build_flows.py` (`unfolded_flow`, `main_flow(as_tool=True)`), `import_flows.py`, `setup_assistant.py` (the Ollama address and model), `move_to_user.py` (the Ollama variable), `langflow/README.md`.

## Why

The assistant of decision 032 works, but on the canvas it is one card: an engineer cannot see what it can do, and RTRC asked for the reasoning to be visible as steps. Langflow's own pattern for this is an Agent with its tools as cards around it (its coding-agent tutorial does exactly that with a filesystem MCP), and a flow used as a tool through the Run Flow component.

## What was built

- **`RTRC design pipeline`** (14 cards): the agent flow of decision 030 without the person's step, ending at the review text, preset to OpenCode in the sandbox on the local Qwen3.8-27B. It is a tool: Run Flow turns its Chat Input into the tool's argument (the brief) and names the tool `RTRC-design-pipeline_tool`. Edit this flow and the unfolded assistants run the edited version; the OpenCode assistant of 032 does not (its `run_design` is Python).
- **`RTRC design assistant · unfolded (qwen3.8-max)`** and **`· unfolded (local 27B)`** (13 cards each): Chat Input → Langflow's Agent → Chat Output, with eight MCP Tools cards (one tool each: list projects, search memory, read project, status of a run, official Pilot on pasted SysML, write to memory, record decision, export for Cameo), the knowledge base card and the pipeline Run Flow card wired to the Agent's Tools port. The write-to-memory card's Actions row asks for approval: the Agent pauses and the Playground shows a card with Approve / Reject before the tool runs. The rules are those of 031/032 (`tools/assistant/rtrc-assistant.md`), with the tool names of this canvas.

Three things Langflow 1.12.5 needed, found while building: a flow becomes a tool only if its input component lists its fields in `field_order` (the generated node had none, so the Run Flow card exposed no tool); the Run Flow card must carry the flow id as `null`, not `""`, or `run_flow` refuses the id as not matching the loaded flow; and one tool per MCP card is done through the card's Actions table (every tool of the server listed, one enabled), which is also where `approval_actions` lives.

## Evidence (2026-10-07, through the Workflow API, superuser copies before the move to the user account)

- Unfolded (qwen3.8-max): "what projects are in the memory" → `list_projects`, correct list with numbers, 15 s. "which tools do you have" → it listed the eight MCP tools, the knowledge-base search, `RTRC-design-pipeline_tool` and the calculator.
- Brief → `RTRC-design-pipeline_tool` → run 20261007T055712: designs A and B PASS at the first parse, all four checks PASS on both (POWER 49 ≤ 60 W, LINK 12 ≤ 20 Mbps, STORE 43.2 ≤ 128 GB, TRACE 9/9), alignment 4/4; 641 s end to end, the designs written by OpenCode on the local 27B. The Max agent paraphrased the brief it passed ("existing baseline devices from the MaritimeISR memory…"); the numbers were unchanged and the pipeline's unsourced-number check passed.
- "Approve A, write to memory" → the job reported `suspended` with a `tool_approval` request ("Tool: write_to_memory, Args: run_id 20261007T055712, design A", Approve / Reject). Resumed with Reject: the Agent reported the write was cancelled, read `design_status`, and the memory file still holds its two entries.
- Unfolded (local 27B): the memory question → `list_projects` then `read_project`; it reported the USV's 60 W and the UAV's 120 W limits of MaritimeISR; 15 s.

What the canvas does not do: nodes do not light up per tool call during a chat; the tool calls are under each answer in the Playground, and the pipeline flow shows the outputs of its last run when opened.

## What would reverse it

RTRC preferring the one-card assistant after seeing both, or the Run Flow path proving fragile (its tool-call timeouts, or the paraphrased brief slipping a number past the pipeline's check); the records on page 2.3 would show it.
