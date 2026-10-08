# 2 · Keys and models: where each line reads them

**You get:** every flow running on *your* key and *your* model.
**You need:** `.env` from step 3 of the install, and Langflow open. 10 minutes.

There are four kinds of model line in the flows. Each reads its key from a different place, because each is a different program. The table is the whole story; the sections below are the details.

| Line | Flows | Key lives in | Model name set in | Works with |
|---|---|---|---|---|
| **Langflow Agent** | `Langflow Agent, Pilot only …`, `Langflow Agent with memory …` | Langflow → Settings → **Global Variables** | the Agent card on the canvas (provider + model dropdown) | OpenAI, Anthropic, Google, Ollama, any OpenAI-compatible endpoint: whatever Langflow's Agent lists |
| **Direct model** | `Direct model chat/exam · P0 … P3`; the direct steps of the design flows | `.env` → `MVP_LLM_API_KEY` | `.env` → `MVP_LLM_MODEL`, or the model field on the RTRC card | an OpenAI-compatible chat endpoint (see the caveat below) |
| **OpenCode** | `OpenCode in the sandbox …`, `OpenCode with memory …` | OpenCode's own login (`opencode auth login`), or `.env` for a custom endpoint | `.env` → `OPENCODE_MODEL` (`provider/model`) | everything OpenCode supports: Anthropic, OpenAI, Google, GitHub Copilot, Ollama, custom endpoints |
| **Claude Code** | `Claude Code in the sandbox …` | Claude Code's own login (Anthropic), or the router's provider page for other keys | `.env` → `CLAUDE_CODE_MODEL` (`provider,model`) | Anthropic directly; anything else through claude-code-router |

## Langflow Agent flows

These are plain Langflow. The Agent card has a **provider** and a **model** dropdown; pick yours. Keys are Langflow Global Variables (Settings → Global Variables → Add): `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, or for an OpenAI-compatible endpoint `OPENAI_COMPATIBLE_BASE_URL` + `OPENAI_COMPATIBLE_API_KEY`; for Ollama `OLLAMA_BASE_URL` (`http://127.0.0.1:11434`). Langflow stores credentials encrypted and per user.

Our flows are preset to the Qwen endpoint through "OpenAI Compatible". `langflow/scripts/setup_assistant.py` creates those two variables and the Ollama address from your `.env` and enables the model names; run it once after the import, or set the variables by hand in the UI.

Exported flow files never carry a key: Langflow writes the variable *name* into the file, the value stays in your account.

## Direct model (P0–P3)

`agents/llm.py` posts to one OpenAI-compatible `chat/completions` URL:

```
MVP_LLM_URL=https://.../v1/chat/completions    # the full URL, including /chat/completions
MVP_LLM_API_KEY=...                            # sent as "Authorization: Bearer <key>"
MVP_LLM_MODEL=qwen3.8-flash                    # the default model; a card's model field overrides it
```

Caveat, stated plainly: this client is part of the frozen benchmark code (`bench/FREEZE.md`) and sends Qwen's `enable_thinking: false` field. Endpoints that ignore unknown fields (Qwen, Ollama, most proxies) are fine. OpenAI's API rejects unknown fields, so for OpenAI or Anthropic on this line put a proxy in front, for example [LiteLLM](https://docs.litellm.ai/) (`litellm --model gpt-...` gives you a local OpenAI-compatible URL and strips what the provider does not take). The local Ollama model is wired without a proxy (`agents/llm_local.py`): type `qwen3.8-27b (Ollama)` as the model, or add your own Ollama model there.

## OpenCode

OpenCode manages its own keys: run `tools/opencode/opencode auth login` once and pick the provider (Anthropic, OpenAI, Google, GitHub Copilot, …). Then tell our runners which model to ask for:

```
OPENCODE_MODEL=anthropic/claude-sonnet-4-5     # provider/model as OpenCode names them (`opencode models` lists them)
```

For a custom OpenAI-compatible endpoint, leave `OPENCODE_MODEL` empty: the runner writes an `opencode.json` with your `MVP_LLM_URL` / `MVP_LLM_API_KEY` and the model `MVP_LLM_MODEL`, which is how the Qwen runs were made (`agents/external/opencode_run.py`). The local Ollama model works the same way with the model name `qwen3.8-27b (Ollama)`.

## Claude Code in the sandbox

With an Anthropic key: run `claude` once, log in, and set

```
CLAUDE_CODE_MODEL=anthropic,claude-sonnet-4-5
```

With any other key, Claude Code needs [claude-code-router](https://github.com/musistudio/claude-code-router) (`npm install -g @musistudio/claude-code-router`, then `ccr start`). Open its page (printed by `ccr start`, usually http://127.0.0.1:3458), add a **provider** (name, base URL, key, model names), and set

```
CLAUDE_CODE_MODEL=<provider name>,<model name>   # e.g. openai,gpt-5 · gemini,gemini-2.5-pro · ollama,qwen3.8-27b-q3:64k
```

Our runs used the provider `qwen` for the cloud model and a provider `ollama` pointing at `http://127.0.0.1:11434/v1/chat/completions` for the local one.

## GitHub Copilot

Only OpenCode can use a Copilot login (`opencode auth login` → GitHub Copilot). The Langflow Agent, the direct line and Claude Code cannot; Copilot is not an API.

## Prices on the results page

The results page converts tokens to dollars with the list prices in `bench/board_facts.py` (`PRICES`). A model without a price there shows `—`, never a guess. To add one, copy the provider's official price into that table with its source URL.

Next: [03-import-flows.md](03-import-flows.md).
