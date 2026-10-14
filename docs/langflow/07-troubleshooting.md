# 7 · Troubleshooting

One symptom, one cause, one fix. Logs: `.langflow/langflow.log`, `.langflow/shell_service.log`, `.langflow/assistant_mcp.log`.

| You see | Why | Do |
|---|---|---|
| The sidebar has no **Rtrc** group; imported flows show empty cards | Langflow started without our components folder | Start with `scripts/langflow.sh` (it sets `LANGFLOW_COMPONENTS_PATH=langflow/components`), or set that variable yourself and restart |
| A card says `The RTRC shell service is not reachable at http://127.0.0.1:8781` | The shell service is not running | `.venv/bin/python -u bench/shell_service.py` (the start script does it); check `.langflow/shell_service.log` |
| `missing or wrong X-RTRC-Token` | Langflow and the shell service read different `.langflow/secrets.env` values | Restart both after `python scripts/langflow_secrets.py`; the token must be in Langflow's environment (the start script exports it) |
| An Agent flow fails in seconds with `Incorrect API key provided: EMPTY` or `API key is required` | The Agent's provider variable is missing for *your* Langflow user (variables are per user) | Settings → Global Variables → add `OPENAI_COMPATIBLE_API_KEY` and `OPENAI_COMPATIBLE_BASE_URL` (or your provider's), or run `langflow/scripts/setup_assistant.py` then `move_to_user.py <you>` |
| `HTTP 401 Token has expired` during a long exam | Langflow's access token lasts one hour | `bench/langflow_exam.py` logs in again by itself; if you drive the API yourself, log in again |
| A model name is refused, or the model dropdown does not have yours | Old build of the cards | Type the name in the model field (the dropdowns accept any value); for an Ollama model use `<tag> (Ollama)` |
| `The local Qwen is not running. Start it with qwen38` | Ollama is down or the tag is not pulled | `python scripts/up.py --bg` (or `scripts/qwen38.sh --serve`); `ollama list` must show the tag your name points at |
| The GPU is busy and another project needs it | Ollama still holds the local Qwen | `python scripts/up.py --down` stops Ollama as well as Langflow. Bring the stack back with `python scripts/up.py --bg` |
| Ollama answers slowly, GPU partly idle | The model does not fit in GPU memory with its context size | Use a smaller quantization, or a tag with a smaller `num_ctx` (our `qwen3.8-27b-q3:64k`: 64k context so the whole model stays on a 24 GB GPU) |
| `The results page (8770) is running and serves answer keys; stop it before …` | This machine's sandbox shares the network with the page that serves answer keys (slirp4netns is not installed), or the exam runner `bench/langflow_exam.py` was started while the page runs | Install slirp4netns, and the sandbox gets its own network that cannot reach the page (`agents/external/netns.py`); or stop `bench/exam_board.py` for the run. Chats are not blocked |
| OpenCode or Claude Code exam/chat does nothing on macOS or Windows | The sandbox is bubblewrap, Linux only | Use Linux or WSL2 for those two columns; everything else runs on all systems ([../benchmark/05-sandbox-agents.md](../benchmark/05-sandbox-agents.md)) |
| `ccr: command not found` / Claude Code reports `unrecognized_model` | claude-code-router is not installed, or the router has no provider by that name | `npm i -g @musistudio/claude-code-router`, `ccr start`, add the provider on its page; the `unrecognized_model` line is a warning Claude Code prints for any non-Anthropic name and is harmless |
| Claude Code's `costUSD` looks wrong | Claude Code guesses a price for models it does not know (`costBasis: unknown`) | Ignore it; the results page prices tokens from its own list-price table, and shows `—` for a model without one |
| `Failed to initialize MCP servers: greenlet_spawn …` in the Langflow log | A known Langflow start-up message when the MCP server is registered | Harmless; the flows still import and run |
| Human Input pauses but the chosen branch fails with `has not been built yet` | Two branches feed one node | Give each choice its own chain of nodes (see "Learned with Langflow 1.12.5" in [`langflow/README.md`](../../langflow/README.md)) |
| A field you added to a card is ignored | Its name contains `config` or `kwargs`, or matches a `Component` method | Rename it |
| Knowledge base ingest fails, then `an instance already exists with different settings` | Chroma kept the failed state | Restart Langflow before retrying; Qwen's embedding endpoint takes at most 20 texts per request |
| `python3 bench/exam_board.py` shows the frozen numbers but empty cell details | The run folders under `mvp/runs/` and `mvp/agent-runs/` are not in git (19 GB) | Expected on a fresh clone: the matrix and scores are in git; per-attempt text exists only where the run was made. Your own runs fill your own folders |

Still stuck: open an issue with the log lines and the flow name. Do not paste keys.
