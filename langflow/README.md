# Langflow: use the flows, build your own

This half of the repository is for people who work in Langflow. Two folders are yours:

| Folder | What is in it |
|---|---|
| [`flows/`](flows/README.md) | the flow files, one folder per Langflow project (six), one JSON per flow; drag one into Langflow or import all with a script |
| [`components/rtrc/`](components/rtrc/) | the RTRC cards (Langflow custom components): chat, exam cell, the tool-flow steps, the design-flow steps |

`scripts/` holds the helpers (build the flow files from code, import, export, set up keys, move ownership); `flows/catalog.py` is the one list of flow names and projects.

## Read in this order

| Page | You get | Minutes |
|---|---|---|
| [1 · Install](../docs/langflow/01-install.md) | Langflow running with the cards loaded and the six projects imported (Windows, macOS, Linux) | 25 |
| [2 · Keys and models](../docs/langflow/02-keys-and-models.md) | every flow on *your* key and *your* model: Langflow Agent, direct model, OpenCode, Claude Code, Ollama | 10 |
| [3 · Import and find your way](../docs/langflow/03-import-flows.md) | the six projects, which flow to open for what, a first conversation, export back to a file | 5 |
| [4 · The flows](../docs/langflow/04-flows.md) | one section per project: what each flow does, what to click, what to change | read as needed |
| [5 · The cards](../docs/langflow/05-cards.md) | one section per RTRC card: inputs, outputs, the function behind it | read as needed |
| [6 · Make your own](../docs/langflow/06-make-your-own.md) | a flow, a card, a tool, in that order of effort; the three rules | 20 |
| [7 · Troubleshooting](../docs/langflow/07-troubleshooting.md) | symptom → cause → fix | when needed |
| [8 · Reference](../docs/langflow/08-reference.md) | the long form: the design assistant, the local model, what the setup enforces, lessons about Langflow 1.12.5 | when needed |

Examining a flow you built and seeing it on the results page is the other half: [`docs/benchmark/`](../docs/benchmark/README.md), in particular [04 · Examine your flow](../docs/benchmark/04-exam-your-flow.md).

## The shortest path

```bash
python3.12 -m venv .venv-langflow && .venv-langflow/bin/pip install -r requirements-langflow.txt
python3 -m venv .venv && .venv/bin/pip install -r requirements-bench.txt
cp .env.example .env            # fill in your endpoint and key
python scripts/up.py --import   # all systems; prints every command it runs (macOS / Linux also: scripts/langflow.sh --import)
```

Open http://127.0.0.1:7860, log in as `rtrc` with the password in `.langflow/secrets.env`, open `1 · Direct model …` → `Direct model chat · P1 repair from errors` → **Playground**.

## Two facts worth knowing before you start

- The flows are also code: `scripts/build_flows.py` generates every JSON under `flows/` from Python, the way Langflow builds its own starter projects. You may edit either; `scripts/export_flows.py` brings a canvas edit back into the files, `scripts/build_flows.py` regenerates them from code. If you edit the Python, regenerate and re-import.
- The cards do little themselves: they call the RTRC shell service (`bench/shell_service.py`, 127.0.0.1:8781), which runs the same functions the results page runs. So a flow, the page and the exam runner never disagree on a verdict, and `bench/langflow_parity.py` checks that they do not.
