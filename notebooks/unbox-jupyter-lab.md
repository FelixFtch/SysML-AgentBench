# Unbox JupyterLab

A local Jupyter notebook that runs **Langflow Agent with memory chat · local Qwen3.8-27B** one cell at a time, and prints what was sent and what came back.

The Langflow canvas stays as it is. This notebook calls the same system prompt, the same tools, and the same shell steps the cards call. It does not light the canvas, and it does not run in Google Colab: the model, the shell (port 8781), the MCP server (port 8782), and the official SysML v2 Pilot are on this machine.

## Files

| File | What it is |
|---|---|
| `notebooks/langflow_agent_with_memory.ipynb` | The notebook to open. Thinking is off for the design writer (`WRITER_THINK = False`). The saved outputs are run `20261021T073756`: both designs passed the writer's Pilot and the pipeline's second Pilot. |
| `notebooks/langflow_agent_with_memory-thinking-on.ipynb` | The same notebook from a run with thinking left on (`20261021T072601`). Design B hit the card's limit of 20 model calls; the pipeline's own Pilot repaired the handed-in draft. |
| `notebooks/agent_walk.py` | The code the notebook cells call. |
| `bench/shell_service.py` | Two added endpoints, `/run/prompt` and `/run/written`, so a writer outside the shell can take one design's task and hand the text back. Every other writer is unchanged. |

## Before you open it

In a terminal, from the repository root:

```bash
python3 scripts/up.py --bg
python3 scripts/qwen38.sh --serve
python3 -m jupyter lab notebooks/langflow_agent_with_memory.ipynb
```

`up.py --bg` starts the shell, the MCP server, Ollama, and Langflow. The results page on port 8770 may stay open. Jupyter prints a local URL; open that URL in the browser.

## How to run it

Run the cells from the top, in order. Each code cell is one step.

1. **The machine.** Confirms the shell, MCP server, the local model, the Pilot jar, OpenCode, bubblewrap, and slirp4netns.
2. **The Agent card.** Loads the system prompt and the nine tools from the flow file and prints them.
3. **Your first message.** The `agent.say("""...""")` cell is the sentence the engineer sends. Change the text between the quotes, then continue.
4. **`agent.decide()`** is one model call. It prints the model's thinking (if thinking is on) and the tool it chose. Nothing runs yet.
5. **`agent.act()`** runs that one tool and prints the receipt. Repeat decide / act, or run `agent.run_until_reply()`, until the agent answers.
6. **Design pipeline.** After you confirm a brief that has every number, the agent calls `Design-pipeline_tool`. The cells under section 3 run that flow one card at a time: start, memory search, requirements, the similar-project router, then the writer.
7. **The writer** is the Langflow Agent, Pilot only card, on the local 27B. `decide()` is one model call. `act()` is one official Pilot call; PASS or FAIL goes back to the model. Repeat until it hands the design in. Design A, then design B.
8. **The pipeline checks again.** `pipe.validate()` parses the handed-in text with the official Pilot a second time. Then alignment, budget checks, the checks router, trade-offs if a check failed, and the review.
9. **Back to the agent.** `agent.give_back(pipe)` returns the review. The agent answers.
10. **Approval.** `APPROVE = False` refuses Write to memory. Set it to `True` only when you want that design stored in `analysis/memory/approved.jsonl`.

A finished run appears on the results page, section 2.3: http://127.0.0.1:8770/#s23

## A new question

Edit the text inside `agent.say("""...""")`.

Then restart the kernel (Kernel → Restart) and run from the first cell again. The conversation lives in the kernel. Re-running only `agent.say` appends your new text onto the old conversation.

The later cell `agent.say("Confirmed. Run the design pipeline...")` is the second message. The agent calls the design pipeline only after you confirm a brief that already contains every number. If a number is missing, it asks for it and does not start the pipeline. In that case `pipe = agent.until_pipeline()` does not open a pipeline, and you skip section 3.

`WRITER_THINK` in the first cell controls the design writer only:

- `False` (the default here): thinking off. This is the setting OpenCode uses. Turns take a few seconds.
- `None`: no switch is sent, so Ollama's default applies and this 27B thinks before each turn. Turns take about a minute, and the model may spend its 20 calls testing small packages instead of finishing the design.

The outer agent keeps Langflow's own default (thinking on). `agent = Agent(think=False)` turns that off too.

## What you see, cell by cell

- The tool the agent chose, and the receipt that tool returned.
- Inside the design step: each model turn, then each Pilot call (save the text, official Pilot, PASS or FAIL with the error lines), then the model reading that result.
- After both designs are handed in: the pipeline's own Pilot parse, and whether that text is the same text the writer's last Pilot call checked.
- `pipe.recheck()` runs the Pilot once more on the files the run stored.

OpenCode, the writer the canvas uses, is described in the appendix. `pipe.design()` runs that sandbox instead. Do not run both writers on one run.

## Two runs already in the files

| Notebook | Writer thinking | What happened |
|---|---|---|
| `langflow_agent_with_memory.ipynb` | off | Run `20261021T073756`. A: 3 Pilot calls, all PASS, 41 s. B: FAIL, FAIL, FAIL, PASS, 44 s. The pipeline's second Pilot passed both with no repair. |
| `langflow_agent_with_memory-thinking-on.ipynb` | on | Run `20261021T072601`. A passed in 2 Pilot calls. B used 20 model calls, 17 of them on tiny test packages, and stopped at the card's limit. Its last Design B draft was handed in; the pipeline repaired it once and then passed it. |

On the Part 2 benchmark (qwen3.8-flash, 100 briefs) OpenCode and the Langflow agents land in the same band: OpenCode 249/300, Langflow Agent with memory 251/300, Pilot only 246/298. The gap shows up on this local 27B when thinking is left on.
