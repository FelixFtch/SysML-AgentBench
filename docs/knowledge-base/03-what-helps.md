# 3. What helps the model and what does not

Measured on the frozen 27-task maritime bank (decision 025), three repeats per cell. Differences of a few cells are within the repeat-to-repeat spread; no significance tests were run. Current numbers: `STATUS.md`.

| Lever | Effect measured here | Use it? |
|---|---|---|
| **A stronger model** | Direct qwen3.8-max passes 312 of 324 cells, qwen3.8-flash 267: by far the largest difference, at about 12× the cost. Max parses every SysML answer on the first attempt. | Yes, first. |
| **Rules in the prompt** | Stating the Pilot's `private import` convention removed the import and `Real` errors that were 22 of 64 failures in the 2026-10-03 matrix. | Yes. Put every convention the tool enforces into the prompt (page 2). |
| **Repair from the official errors** | Flash's final parse rises from 33→36, 37→39 and 31→38 of 39 SysML answers (P1, P2, P3), for 2–17 repairs per approach; no cell needed the cap of 20. The earlier loop (3 repairs, the first 8 error lines, a fresh conversation each time) made flash resubmit unchanged text in all 10 of its failing P1 generate cells. | Yes, with the complete error list in one conversation and a stop after three identical resubmissions. Not needed by max. |
| **An outline first** | P2 versus P1: −1 cell on flash, −2 on max. | No measured gain. |
| **Retrieval (MiniLM + FAISS)** | Finds 13 of 15 key elements on the query tasks (word ranking: 11); with only retrieved cards as context, max answers 5 of 5 query tasks. In the exam, P3 versus P2 is +2 cells on flash and +2 on max. On the paper's own EV model it answers 2 of 3 questions with a tenth of the authors' context, and 3 of 3 once each card carries the element's documentation text (decision 027). | Use it for large models and libraries, where the prompt cannot hold everything; do not expect it to raise a small exam's pass rate. Put documentation text into the cards: a purpose written only in a `doc` comment is otherwise invisible. |
| **An off-the-shelf agent with the validator** | OpenCode and Claude Code on flash pass 77 and 76 of 81 runs, against 69 of 81 for flash's best direct approach and 79 of 81 for direct max with repair; they cost 15–80× flash direct and more than max direct. | When the model is fixed and cheap. Give the agent the same validator the scorer uses (page 4). |
| **Code-written alignment** | The model's own alignment packages (the paper's and ours) fail the Pilot; alignment is the lowest task type for flash (20 of 36) and both agents, and the second lowest for max. | Yes: the model proposes pairs, code writes the package, a person reviews each pair. |

## Habits of the models worth designing around

- **Names.** Flash's most common miss (15 cells) is a right query answer written with a differently qualified name (`usv` instead of `MaritimeISR::usv`, a usage path instead of the definition). State the naming convention in the task, or normalise names before comparing.
- **Clarifications.** Both direct models sometimes ask about the wrong missing quantity (latency instead of bandwidth, voltage instead of the power limit). The agents always asked about the right one, but three of their questions showed an example value or arithmetic from the statement, which a strict "invented number" rule counts against them. Ask for the missing value without suggesting one.
- **Locking on.** A weak model can resubmit the same wrong text against the same error many times; feeding back the full error list with line and column, keeping earlier versions in the conversation, and stopping after three identical resubmissions keeps this cheap.
- **Agents and time.** In three of the four agent runs that hit the 900 s limit, the model in the workspace had already passed the validator, but the answer file was never written. Ask for the answer file early and update it.
- **Agents and the deliverable.** Two agent runs edited the baseline file in place and described the change instead of returning the model. Say exactly what the answer must contain.
