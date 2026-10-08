# 4 · Examine your flow

**You get:** your Langflow flow sits the 27 tasks three times, scored by the frozen scorer, and shows up as a column on results page 1.3; committed, it shows up on everyone's page.
**You need:** the flow saved in your Langflow ([../langflow/06-make-your-own.md](../langflow/06-make-your-own.md)), the shell service running, Java for the official Pilot ([06-task-bank.md](06-task-bank.md#the-toolchain)). The run itself: the three repository columns took 37 to 47 minutes each on the cloud flash (`analysis/langflow-exam-*/summary.json`, `seconds_total`); a slower model takes longer. Any system, unless the flow runs a sandboxed coding agent (then Linux).

## The command

```bash
.venv/bin/python bench/langflow_exam.py --flow "My P1 with a checklist" --column my-p1-checklist --login <your Langflow user>
```

| Option | What it does |
|---|---|
| `--flow` | the flow's name exactly as Langflow shows it. Any flow shaped Chat Input → … → Chat Output can sit the exam |
| `--column` | the id your column gets on the page and in the folder name (letters, digits, dashes). The three repository flows have fixed ids and do not take it |
| `--login` | the Langflow account that owns the flow. Langflow shows an account only its own flows; the password is asked for on the terminal and never stored |
| `--model "<name>"` | optional: put this model on the flow's model card for the run only (the flow file is unchanged). `"<tag> (Ollama)"` for a local model. Without it your flow runs exactly as saved |
| `--repeats 3` `--tasks all` | the defaults of the matrix; `--tasks GEN-01,MOD-05 --repeats 1` for a quick look |
| `--sandboxed` | say so if your flow runs OpenCode or Claude Code in the sandbox: the results page must be stopped first, because it serves answer keys on the network the sandbox shares |

## What happens

For each task and repeat, the runner sends the task statement (the same text the direct candidates get, `agents.solve._task`: the requirements plus the given models) to your flow's Chat Input with a fresh session id, waits for the Chat Output, and scores the reply with `bench.experiment.validate_and_grade`: the official Pilot once, then the key. It records wall time, tool calls and the Agent's token usage. One line per cell goes to

```
analysis/langflow-exam-<column>-<model tag>-<stamp>/
    results.jsonl     one row per cell: status, sysml_status, reason, elapsed_s, tool_calls, usage, answer_file
    summary.json      the flow, the model (or "as saved in the flow"), the login, the tasks, how it was scored
    answers/          every reply, <task>-r<repeat>.md
    graded/           the Pilot's parse of every SysML answer
```

The page lists every such folder as a column (`bench/batches.py`, `exam_columns()`); a set button for your model appears if it is not flash or the local 27B. Refresh the page and the column is there, cells filling in as the run writes them.

## Share the result

```bash
git add "analysis/langflow-exam-my-p1-checklist-flow-<stamp>"
git commit -m "Column my-p1-checklist: <flow name> on <model>, 27 x 3"
```

A few hundred kilobytes. On every clone, the page shows your column next to the others. Add the flow file itself the same way ([../langflow/06-make-your-own.md](../langflow/06-make-your-own.md), section A).

## Interrupted?

Run the same command with `--out <that folder>`: finished cells are kept, missing ones are run. The Langflow login token lasts an hour; the runner logs in again by itself.

## What your flow is allowed to see

The statement, and whatever your tools reach. The keys live under `bench/tasks/*/gold/`; a flow whose tools read the repository's files could read them, and that would not be an exam. The sandboxed agents cannot see the repository at all; a Langflow Agent with our tool cards reaches only the memory, the Pilot and the design pipeline. If you write a file-reading tool, keep `gold/` out of its reach and say so in the flow's note card.

Next: [5 · The sandboxed coding agents](05-sandbox-agents.md) or [6 · The task bank](06-task-bank.md).
