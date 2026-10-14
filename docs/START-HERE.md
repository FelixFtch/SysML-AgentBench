# Start here

**What this is.** A benchmark of AI agents that turn requirements into SysML v2 models, and a set of Langflow flows that run those agents and let you build your own. 27 sealed tasks on a synthetic maritime scenario, scored only by the official SysML v2 Pilot and answer keys written in advance. Nothing here is an RTX specification.

**Two doors.** Pick the one you came for; each has its own numbered pages.

| | I want to… | Go to | First command |
|---|---|---|---|
| **Langflow** | talk to the agents, change a flow, build my own flow or tool, use my own API key or a local model | [`langflow/README.md`](../langflow/README.md) → [01 · Install](langflow/01-install.md) | `python scripts/up.py --import` |
| **Benchmark** | see the results, understand a cell, run one task, examine my own flow and put it on the page, replace the tasks with real ones | [`docs/benchmark/README.md`](benchmark/README.md) → [01 · Open the page](benchmark/01-open-the-page.md) | `python3 bench/exam_board.py` → http://127.0.0.1:8770 |

## Ten minutes

1. Clone, make the two Python environments, copy `.env.example` to `.env` and fill in one key ([install page](langflow/01-install.md), steps 1–3).
2. `python3 bench/exam_board.py` → http://127.0.0.1:8770. The results page: every score of the frozen exam, the local-27B rerun, and every Langflow column, read from files in the repository. No model call.
3. `python scripts/up.py --import` → http://127.0.0.1:7860. Langflow with the six projects (30 flows). Open `Direct model chat · P1 repair from errors`, press Playground, ask for a small SysML package.

The three papers are steps, not separate apps: paper 2 is memory search, paper 3 is the writing rules and the Pilot repair loop, paper 1 is alignment. They sit in that order on **Design agent flow with a person's decision**. Each approach you run has an exam flow (scored, shown on the results page) and a chat flow (talk, not scored): [the repository README](../README.md#the-flows).

## What you need

| | For the chats and the page | For examining a flow | For the two sandboxed coding agents |
|---|---|---|---|
| Python 3.12 (Langflow) + Python 3.10+ (benchmark) | yes | yes | yes |
| Your own `.env` key, or Ollama with the cloud key left empty | yes | yes | yes |
| Java 21 (the official Pilot) | no | yes, Linux or macOS (Windows: WSL2) | yes |
| Linux or WSL2, bubblewrap, slirp4netns, the pinned OpenCode binary | no | no | yes |

`python3 bench/exam_board.py` reads scores already in the repository. It does not call a model. `.env` is git-ignored and is not on GitHub.

## Where things are

```
langflow/   flows/ (the flow files, six folders) · components/rtrc/ (the cards) · scripts/ (import, export, build, set-up)
bench/      the tasks (bench/tasks/), the scorers, the exam runners, the results page (exam_board.py), the shell service
agents/     the direct approaches P0–P3 and the model clients; agents/external/: the sandbox and the coding-agent runners
mvp/        the pinned official SysML v2 toolchain and the engine that runs it
tools/      the RTRC tools as an MCP server (assistant_mcp.py) and the OpenCode assistant workspace
analysis/   every score file the page reads; your exam columns go here too
docs/       langflow/ and benchmark/ (the two doors), decisions/ (why things are the way they are), knowledge-base/, report/
```

Frozen: the task bank, the scorers, the P0–P3 solver and the model client are hashed in [`bench/FREEZE.md`](../bench/FREEZE.md). Changing them is a new freeze, not an edit; everything else is open.
