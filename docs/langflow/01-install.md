# 1 · Install

**You get:** Langflow running on your computer with the RTRC cards loaded and the six projects imported.
**You need:** a terminal, about 25 minutes, 6 GB of disk (Langflow 2 GB, the local model 14 GB more if you want it).
**Works on:** Windows, macOS, Linux for the chats and for the results page. Scoring an exam, and any flow that writes a design through OpenCode or Claude Code, needs the official SysML v2 Pilot on Java 21, which runs on Linux and macOS; on Windows use WSL2 for that part ([../benchmark/06-task-bank.md](../benchmark/06-task-bank.md#the-toolchain)). Those two sandboxed agents also need Linux or WSL2, `bubblewrap` (`bwrap`), `slirp4netns`, and the OpenCode binary pinned in `tools/opencode/VERSION` ([../benchmark/05-sandbox-agents.md](../benchmark/05-sandbox-agents.md)). Ordinary chat and `python3 bench/exam_board.py` need none of that: the page reads scores already stored in the repository and does not call a model.

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

Open `.env` and fill in the model endpoint and key you have. A cloud model needs your own URL and key. If you only use a model you pulled into Ollama, leave the cloud key empty. Every variable is explained in [02-keys-and-models.md](02-keys-and-models.md). `.env` is git-ignored; it never leaves your machine and it is not on GitHub.

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

All three systems:

```bash
python scripts/up.py --import       # macOS / Linux: python3 scripts/up.py --import
```

It starts what is not running (the shell service on 8781, the MCP server on 8782, Ollama if installed), exports the Langflow settings, starts Langflow on 7860, and with `--import` imports the flow files into the six projects and runs the two set-up scripts once Langflow answers. Every command is printed before it runs; `python scripts/up.py --status` says what is up. On macOS / Linux `scripts/langflow.sh --import` does the same in bash.

First start takes a minute or two (Langflow builds its component index). Ctrl-C stops Langflow; the services keep running.

To leave the machine for other work, and to bring this stack back:

```bash
python scripts/up.py --down     # stop Langflow, the shell, MCP, the results page, and Ollama (frees the GPU)
python scripts/up.py --bg       # start them again in the background, then return
python scripts/up.py --status   # 7860 Langflow, 8781 shell, 8782 MCP, 11434 Ollama, 8770 results page
```

`--bg` does not re-import the flows. Use `--import` only after a fresh clone or after the flow files changed.

## Step 8 · Log in

Open http://127.0.0.1:7860. User `rtrc`; the password is in `.langflow/secrets.env` (created in step 7, never printed, never committed). On your own computer this account is all you need. If you make a second account for yourself, run `langflow/scripts/move_to_user.py <username>` once so the projects, keys and knowledge base belong to it.

## Check

- The left sidebar shows **Rtrc** under components: the cards loaded.
- The Projects page shows six projects named `1 · Direct model …` to `6 · Other`: the flows imported.
- Open `Direct model chat · P1 repair from errors`, press **Playground**, type `hello`: the model answers. If it does not, [07-troubleshooting.md](07-troubleshooting.md).

Next: [02-keys-and-models.md](02-keys-and-models.md).
