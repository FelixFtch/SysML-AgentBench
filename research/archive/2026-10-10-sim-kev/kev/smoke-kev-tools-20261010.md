# Kev tools smoke log · 2026-10-10

First verification of project 7 (`langflow/flows/7-kev-tools/`) and the shared tool flow
`5-shared-tools/tool-classify-requirement.json` ("Classify requirements") after importing them into the running
Langflow (127.0.0.1:7860). Message sent through the Langflow v2 workflow API (background job, as
`bench/langflow_exam.py` sends exam tasks); replies read back from the message table. Services: Langflow restarted
once to load the two new cards, Kev decision service on 127.0.0.1:8009 (started with `scripts/kev_up.sh` after the
instance another agent had left was stopped mid-test), kev MCP server on 127.0.0.1:8793, rtrc MCP on 8782, Ollama on
11434.

Smoke message (both chat flows): `Classify whether this is a requirement: 'The system shall log all logins.'`

## 1 · Langflow Agent with memory + Kev chat · qwen3.8-max (endpoint langflow-agent-memory-kev-chat)

- Job completed in 16 s; tool calls: `Classify-requirements_tool`; the sub-flow received exactly
  `The system shall log all logins.` at its Chat Input and its card answered `yes (0.87) — The system shall log all logins.`
- Reply:
  > I'll send it to the Kev requirement classifier.
  >
  > **Kev verdict: yes — requirement (probability 0.87).**
  >
  > One note from my side, not the tool: the sentence is verifiable only if "all logins" is bounded — which logins
  > (successful, failed, both), on which subsystem, and with what retention. If you want, give me those limits and I
  > can search the memory for existing logging/audit parts before we turn it into numbered requirements.

Earlier run of the same flow while the Kev service was down (stopped by the other agent mid-test): the agent called
the tool, the card failed at once with `The Kev service is not reachable at http://127.0.0.1:8009 ([Errno 111]
Connection refused); start it with scripts/kev_up.sh`, and the agent reported that clearly instead of hanging — the
service-down behaviour the card promises.

## 2 · OpenCode with memory + Kev chat (endpoint opencode-memory-kev-chat)

- Job completed in 201 s (local Qwen3.8-27B); the usage sidecar
  (`~/.rtrc-assistant-kev/usage/kev-smoke-oc-1791649512.json`) records `tool_calls: ["kev_classify_requirement"]`,
  6926 in / 122 out tokens, 198.2 s — OpenCode really called the kev MCP tool.
- Reply:
  > Yes — Kev classifies it as a requirement with a probability of 0.87.
  >
  > "The system shall log all logins." is a clear, testable "shall" statement: it specifies a verifiable system
  > behavior (logging every login event), which is why it scores high. For comparison, "The system logs logins"
  > (indicative) or "should log" would score lower.

## 3 · Langflow Agent with memory + Kev exam (endpoint langflow-agent-memory-kev-exam)

- Imported (flow id 1526e0d9-397d-473d-9452-2ec0cefc8469); structure complete: Chat Input → Agent (qwen3.8-flash, the
  exam prompt plus the Kev tool line) → Chat Output, Run Flow cards validate + search + classify, all wired to the
  Agent's Tools port, the classify card pointing at flow id 60605efa-0d99-40be-a976-a501bdc69d45 ("Classify requirements").
- One live message through it: job completed in 8 s, tool calls `Classify-requirements_tool`, reply:
  > Yes — this is a software requirement statement ("The system shall log all logins.", probability 0.87).

## 4 · OpenCode with memory + Kev exam (endpoint opencode-memory-kev-exam)

- Imported (flow id a38f1c28-5f25-4f6b-ab91-b205c7d2cb81); structure complete: Chat Input → RTRC OpenCode assistant ·
  Kev (exam mode, qwen3.8-flash) → Chat Output. The tool is mounted the way this harness mounts tools: the kev MCP
  server (8793) in the workspace `~/.rtrc-assistant-kev-exam` (prepared by `tools/assistant/kev_workspace.py`), with
  `kev_classify_requirement` enabled next to the exam's two rtrc tools; verified in the workspace's opencode.json and
  prompt. Live run deferred (a fresh OpenCode session on the local 27B; the chat twin of the same component path is
  evidence above) — run `python3 bench/langflow_exam.py --flow "OpenCode with memory + Kev exam"` for the full exam.

## Unit checks of the tool itself (direct, outside Langflow)

- `tools/kev_mcp.py::_judge` on 44 sentences: two batches (40 + 4), every verdict present;
  `The system shall log all logins.` → yes 0.83, background sentence → no 0.07 (same wording as the jev-arena pilot).
- Sentence parsing: JSON array, one-per-line, and single-line running text all accepted.
- Service-down path: `ValueError` in 0.00 s with the `scripts/kev_up.sh` hint — no hang, no retries.
