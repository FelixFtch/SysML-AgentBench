# 1 · Install

**You get:** Langflow running on your computer with the RTRC cards loaded and the six projects imported.
**You need:** a terminal, about 25 minutes, 6 GB of disk (Langflow 2 GB, the local model 14 GB more if you want it).
**Works on:** Windows, macOS, Linux for everything on this page. Only the *sandboxed coding-agent exams* need Linux; see [../benchmark/05-sandbox-agents.md](../benchmark/05-sandbox-agents.md).

Three programs, each installed the way its maker says. Nothing here is packaged by us.

## Step 1 · Get the repository

```bash
git clone https://github.com/FelixFtch/SysML-AgentBench.git
cd SysML-AgentBench
```

## Step 2 · Python 3.12 and Langflow 1.12.5

Install Python 3.12 from [python.org](https://www.python.org/downloads/) (Windows: tick "Add python.exe to PATH"). Then, in the repository folder:

| | macOS / Linux | Windows (PowerShell) |
|---|---|---|
| make the Langflow environment | `python3.12 -m venv .venv-langflow` | `py -3.12 -m venv .venv-langflow` |
| install Langflow | `.venv-langflow/bin/pip install -r requirements-langflow.txt` | `.venv-langflow\Scripts\pip install -r requirements-langflow.txt` |
| make the benchmark environment | `python3 -m venv .venv` | `py -3 -m venv .venv` |
| install the benchmark side | `.venv/bin/pip install -r requirements-bench.txt` | `.venv\Scripts\pip install -r requirements-bench.txt` |

Two environments on purpose: Langflow pins many packages; the benchmark side (the shell service the cards call, the scorers, the results page) is small and must not fight with them.

## Step 3 · Keys

```bash
cp .env.example .env        # Windows: copy .env.example .env
```

Open `.env` and fill in the model endpoint and key you have. Every variable is explained in [02-keys-and-models.md](02-keys-and-models.md). `.env` is git-ignored; it never leaves your machine.

## Step 4 · Ollama (optional, for a local model)

Install Ollama from [ollama.com/download](https://ollama.com/download) (all three systems). Then pull a model, for example the one we use:

```bash
ollama pull smtek/Qwen3.8-27B:Q3_K_XL     # 14 GB, needs a 24 GB GPU to run fully on the GPU
```

Any Ollama model works in the flows; the name you pulled is the name you type in the model field. On Linux with our GPU, `scripts/qwen38.sh --serve` also builds the 64k-context tag `qwen3.8-27b-q3:64k` that our runs used.

## Step 5 · Node and Claude Code (optional, only if you want the Claude Code flows)

Install Node 22 from [nodejs.org](https://nodejs.org/), then:

```bash
npm install -g @anthropic-ai/claude-code
```

With a real Anthropic key, that is all: run `claude` once and log in. To drive Claude Code with another provider's key (OpenAI, Gemini, Ollama…), also install the router: `npm install -g @musistudio/claude-code-router`, then see [02-keys-and-models.md](02-keys-and-models.md#claude-code-in-the-sandbox).

## Step 6 · OpenCode (optional, only if you want the OpenCode flows)

Download the release pinned in [`tools/opencode/VERSION`](../../tools/opencode/VERSION) for your system from the [OpenCode releases page](https://github.com/anomalyco/opencode/releases) and put the binary at `tools/opencode/opencode` (Windows: `opencode.exe`). The exam ran v1.18.27; a different version is fine for chat and is recorded in every exam row.

## Step 7 · Start

macOS / Linux:

```bash
scripts/langflow.sh --import
```

Windows (PowerShell), the same steps by hand (a `scripts/up.py` launcher is on the way; until then):

```powershell
python scripts\langflow_secrets.py                              # once: creates .langflow\secrets.env (login + tokens)
Start-Process .venv\Scripts\python -ArgumentList "-u bench\shell_service.py"      # the service the RTRC cards call, 127.0.0.1:8781
Start-Process .venv\Scripts\python -ArgumentList "-u tools\assistant_mcp.py"      # the RTRC tools as an MCP server, 127.0.0.1:8782
$env:LANGFLOW_COMPONENTS_PATH = "$PWD\langflow\components"; $env:LANGFLOW_ALLOW_CUSTOM_COMPONENTS = "False"
$env:LANGFLOW_AUTO_LOGIN = "False"; $env:LANGFLOW_CONFIG_DIR = "$PWD\.langflow\config"; $env:RTRC_ROOT = "$PWD"; $env:RTRC_SHELL_URL = "http://127.0.0.1:8781"
Get-Content .langflow\secrets.env | ForEach-Object { $k, $v = $_ -split "=", 2; Set-Item -Path "env:$k" -Value $v }
.venv-langflow\Scripts\langflow run --host 127.0.0.1 --port 7860
```

then, in a second terminal once http://127.0.0.1:7860 answers: `.venv-langflow\Scripts\python langflow\scripts\import_flows.py`.

What `scripts/langflow.sh` does, line by line, is in the script itself: start the shell service, the MCP server and Ollama if they are not running, export the Langflow settings, start Langflow, and with `--import` run `import_flows.py`, `setup_knowledge.py`, `setup_assistant.py` once Langflow answers.

## Step 8 · Log in

Open http://127.0.0.1:7860. User `rtrc`; the password is in `.langflow/secrets.env` (created in step 7, never printed, never committed). On your own computer this account is all you need. If you make a second account for yourself, run `langflow/scripts/move_to_user.py <username>` once so the projects, keys and knowledge base belong to it.

## Check

- The left sidebar shows **Rtrc** under components: the cards loaded.
- The Projects page shows six projects named `1 · Direct model …` to `6 · Other`: the flows imported.
- Open `Direct model chat · P1 repair from errors`, press **Playground**, type `hello`: the model answers. If it does not, [07-troubleshooting.md](07-troubleshooting.md).

Next: [02-keys-and-models.md](02-keys-and-models.md).
