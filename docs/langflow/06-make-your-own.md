# 6 · Make your own: a flow, a card, a tool

**You get:** your own flow in Langflow, built from our cards or from scratch, examined on the 27 tasks and shown as a column on the results page.
**You need:** Langflow with the projects imported ([03](03-import-flows.md)), a key ([02](02-keys-and-models.md)). 20 minutes for a flow; an hour for a new card.

Nothing here is locked. Our flows are ordinary Langflow flows; our cards are ordinary Langflow custom components. The only rules are the three at the end, and they exist so that an exam stays an exam.

## A · Your own flow in 3 steps

1. **Start from a copy.** Open the flow closest to what you want (for an agent with tools: `Langflow Agent with memory chat · qwen3.8-max` in project 4; for a plain model: `Direct model chat · P1 …`). Projects page → the flow's **⋯** menu → **Duplicate**, then rename it (`My P1 with a checklist`). Or build from empty: **New Flow** → drag **Chat Input**, an **Agent**, **Chat Output**, and connect them.
2. **Change what you like.** The system prompt on the Agent card. The model and provider. Which tool cards are wired to the Agent's **Tools** port: ours (sidebar → **Rtrc**), Langflow's own (web search, calculator, …), or a **Run Flow** card pointing at one of the shared tool flows (`Validate SysML with the official Pilot`, `Memory search`). Test in the **Playground**.
3. **Examine it** (any system, as long as the flow does not run a sandboxed coding agent):

   ```bash
   .venv/bin/python bench/langflow_exam.py --flow "My P1 with a checklist" --column my-p1-checklist --login <your Langflow user>
   ```

   27 tasks × 3 repeats, scored by the frozen scorer. It runs the flow as you saved it (your provider, your model); add `--model "<name>"` to swap the model for this run only. The result folder `analysis/langflow-exam-my-p1-checklist-flow-<stamp>/` appears on results page 1.3 as a new column the next time the page refreshes. Commit that folder and it is on everyone's page. Details: [../benchmark/04-exam-your-flow.md](../benchmark/04-exam-your-flow.md).

To share the flow itself: `langflow/scripts/export_flows.py --new "My P1 with a checklist" --project 1-direct-model`, which writes the JSON (keys emptied) into `langflow/flows/1-direct-model/` and prints the line to add to [`langflow/flows/catalog.py`](../../langflow/flows/catalog.py). Then `python langflow/scripts/catalog_readme.py` and open a pull request ([CONTRIBUTING.md](../../CONTRIBUTING.md)).

## B · Your own card (a Langflow component)

A card is one Python class in [`langflow/components/rtrc/`](../../langflow/components/rtrc/). Langflow loads every file in that folder at start (`LANGFLOW_COMPONENTS_PATH`), so: add a file, restart Langflow, the card is in the sidebar under **Rtrc**.

The pattern, from the smallest card we have, [`rtrc_chat.py`](../../langflow/components/rtrc/rtrc_chat.py):

```python
from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, MessageInput, Output
from lfx.schema.message import Message

class MyCard(Component):
    display_name = "My card"            # what the sidebar shows
    description = "One sentence: what goes in, what comes out."
    icon = "wand"
    name = "MyCard"                     # unique; used in flow files

    inputs = [
        MessageInput(name="message", display_name="Message", info="Shown as a tooltip on the canvas."),
        DropdownInput(name="style", display_name="Style", options=["short", "long"], value="short", combobox=True),
    ]
    outputs = [Output(display_name="Reply", name="reply", method="run_it")]

    def run_it(self) -> Message:
        text = self.message.text if isinstance(self.message, Message) else str(self.message or "")
        self.status = f"{len(text)} characters in"   # the grey line under the card after a run
        return Message(text=text.upper() if self.style == "short" else text)
```

Rules of thumb, learned the hard way (they are in [`langflow/README.md`](../../langflow/README.md) too):

- Do the work in Python you can test outside Langflow, and keep the card thin. Our cards call the shell service (`bench/shell_service.py`, 127.0.0.1:8781) over HTTP with the token from `.langflow/secrets.env`; the same functions serve the results page, so a card and the page never disagree. Copy `_call()` from `rtrc_chat.py` for that.
- An input may not be named like a `Component` method (`run`) and may not contain `config` or `kwargs` in its name: Langflow parses such a parameter as JSON and silently drops it.
- Give a dropdown `combobox=True` when a person might need a value you did not list (model names).
- Restart Langflow after adding or changing a card. With `LANGFLOW_ALLOW_CUSTOM_COMPONENTS=False` (our setting) the server runs only the code in the components folder, never code pasted into a card on the canvas; that is what makes a shared instance safe.

## C · Your own tool

Three ways, from least to most work:

1. **A flow as a tool.** Any flow with a Chat Input and a Chat Output can be a tool: add a **Run Flow** card to your agent's flow, pick your flow, switch the card to **Tool Mode**, connect it to the Agent's Tools port. This is how the memory assistants run `Memory search` and the official Pilot. The Agent sees the flow's name and description as the tool's, so write them for the model.
2. **A Python function on the MCP server.** [`tools/assistant_mcp.py`](../../tools/assistant_mcp.py) is a standard MCP server (streamable HTTP, 127.0.0.1:8782). Add a function with `@server.tool(description="…")`; its signature is the tool's schema. Restart it (`python tools/assistant_mcp.py`). Every MCP client sees it: Langflow's **MCP Tools** card, OpenCode (project 3 uses exactly this), Cursor, Claude Desktop. This is the most portable form; the tool is not tied to Langflow.
3. **A card** (section B), when the tool must show its steps on the canvas (the write-to-memory flow's gate → write → record cards are this).

Write the tool description for the model that will call it: what it does, what each argument is, when to call it. The description is the only thing the model reads.

## The three rules

1. **Never put a key in a flow file or a card.** Keys live in Langflow's Global Variables and in `.env`. `export_flows.py` empties credential fields; check a hand-exported file before committing.
2. **An exam flow never sees an answer key.** The scorer opens the key; the flow gets the task statement and nothing else. If your tool reads files, keep `bench/tasks/*/gold/` out of its reach.
3. **Do not change a stated number to make a check pass.** A flow that moves a limit fails the task by design, and the person reading the result is told why.

Next: [07-troubleshooting.md](07-troubleshooting.md) when something does not work; [../benchmark/README.md](../benchmark/README.md) for the exam and the page.
