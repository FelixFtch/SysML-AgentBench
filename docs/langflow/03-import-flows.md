# 3 · Import the flows, find your way around

**You get:** the six projects in your Langflow, and you know which flow to open for what.
**You need:** Langflow running ([01-install.md](01-install.md)). 5 minutes.

## Two ways to import

**All at once** (what `scripts/langflow.sh --import` does):

```bash
.venv-langflow/bin/python langflow/scripts/import_flows.py
```

It creates the six projects, imports every file under [`langflow/flows/`](../../langflow/flows/README.md) into the right one, and points the "Run Flow" cards of projects 3 and 4 at the shared tool flows. Safe to run again: it updates in place.

**One flow:** drag its JSON file from `langflow/flows/<project folder>/` into the Langflow window, or Projects page → **Upload a flow**. This is Langflow's own import; it works for any of our files. Flows of projects 3 and 4 that call the shared tool flows need those imported first (project folder `5-shared-tools/`).

Before either: the RTRC cards must be loaded (`LANGFLOW_COMPONENTS_PATH=langflow/components`, set by the start script). A flow imported without them shows empty cards.

## The six projects

| Project | Open this to… | Chat or exam |
|---|---|---|
| **1 · Direct model, approaches P0 to P3** | talk to a plain model that writes SysML, with the repair loop (P1), an outline first (P2), retrieval of official examples (P3) | `Direct model chat · P1 …` to talk; `Direct model exam · P1 …` to replay or run one sealed task |
| **2 · Coding agents without memory** | the same with a coding agent that has files and the official validator: OpenCode, Claude Code (sandbox, Linux), or Langflow's Agent with the Pilot as its only tool | `… chat` / `… exam` |
| **3 · OpenCode with memory** | the design assistant: ask what exists, describe a need, run the design pipeline, approve into memory | `OpenCode with memory chat`; its exam version |
| **4 · Langflow Agent with memory** | the same assistant with every tool as a card on the canvas (the one to copy from when you build your own) | `Langflow Agent with memory chat · …`; its exam version |
| **5 · Shared tool flows** | the tools as flows: memory search, the official Pilot, write to memory, the design pipeline. Open one to see its steps | run by 3 and 4 |
| **6 · Other** | the design agent flow with a person's decision, the knowledge-base fill, the results tables, the MOD change chain, the Cameo check | |

Every flow has a note card on its canvas saying what it does and what to click. Full list with file names: [`langflow/flows/README.md`](../../langflow/flows/README.md).

## First conversation

1. Open `1 · Direct model …` → `Direct model chat · P1 repair from errors` → **Playground**.
2. Type a question (`what is the difference between a part and an attribute in SysML v2?`). You get an answer, no model.
3. Ask for a model (`write a package Buoy with a part def Radio that has an attribute bandMHz : Real = 2400.0`). The reply holds a fenced `sysml` block, parsed by the official Pilot; the card's status line shows PASS or the repairs it took.
4. Ask for a change (`add uplinkMbps : Real = 8.0 to Radio`). The conversation continues; the whole file comes back.

Same steps in project 2 with `OpenCode in the sandbox chat` (Linux) or `Langflow Agent, Pilot only chat` (any system).

## Edit → export → share

Edit any flow on the canvas. To bring your version back into the repository (or share it as a file):

```bash
.venv-langflow/bin/python langflow/scripts/export_flows.py "Direct model chat · P1 repair from errors"     # one of ours, back into its file
.venv-langflow/bin/python langflow/scripts/export_flows.py --new "My P1 with a checklist" --project 1-direct-model   # a new flow of yours
```

The export is Langflow's own JSON with every credential field emptied and instance ids dropped, so the file is safe to commit. Langflow's **Share → Export** button produces the same JSON; use whichever you like. How to add it to the catalog and examine it: [06-make-your-own.md](06-make-your-own.md).

Next: [02-keys-and-models.md](02-keys-and-models.md) if you have not set a key yet; otherwise [06-make-your-own.md](06-make-your-own.md).
