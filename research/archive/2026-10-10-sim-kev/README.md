# Archived 2026-10-10: the SIM question bank, the Jev arena and the Kev tool flows

Side work produced by a second agent session on 2026-10-10 and set aside the same day. None of it is part of the
project's evidence or of the Langflow projects. It is kept here so nothing is lost and nothing of it is mistaken for
a result.

## What is here

| Folder | What it was | Why it is archived |
|---|---|---|
| `bench/` | Generators, curation, audit and scorer of a 1,000-item "SIM" bank (battery, backlog, thermal, harvest, latency, storage, scheduling arithmetic), its runner `run_sim_side.py`, and `run_pure_file_protocol.py` | The brief's activity (9) asks for simulation that evaluates the requirements and designs the agents produce; this bank instead examines agents on arithmetic. Not asked for by the brief. The bank's physics may be reused in `bench/simulate_design.py` once the Part 2 briefs carry those quantities. |
| `tasks_staging/` | The 1,000 selected and 1,000 archived SIM items (gitignored, 311 MB) | same |
| `analysis/` | The SIM runs (`side-sim-*`), the Jev arena pilot and cascade results, the Kev full-PURE run, the one-row file-protocol attempt | Not evidence: see the note on base rates below |
| `kev/` | The Kev requirement classifier as a Langflow card and MCP server, the four project-7 flows, start/stop scripts, the smoke log, and `tracked-edits.patch` with the edits made to `catalog.py`, `build_flows.py`, the flows README and two docs pages (reverted) | The classifier showed no discriminative power on the task (below) |
| `jev-arena-reports/` | `PILOT-REPORT.md` and the arena's scripts | The arena itself (40 GB of virtual environments and model weights) was moved outside the repository to `/data/robotics/RTRC-archive/2026-10-10-jev-arena/` |
| `time-sim-param-drafts/` | Three SysML drafts of time-domain parameters | drafts |

## Why the Kev/Jev results are not evidence

The arena judged 4,217 sentences of six PURE documents, 51.4% of them inside a `<req>` element. Answering "yes" to
every sentence scores F1 0.679; the best model, Kev-0.8B, scored 0.710 and its balanced accuracy per document was
0.55–0.69 (0.5 is a coin flip). On the EIRENE document it scored below the always-yes baseline. The cascade and
"max is weaker" conclusions rest on the same base rate. The requirement-demarcation question these runs asked is
also not what the brief asks of PURE; the current PURE protocol (`bench/build_pure_tasks.py`, `sysml-v2`) runs the
project's own requirements-to-SysML lines on PURE passages instead.

The Langflow instance no longer holds the project "7 · Kev tools" or the "Classify requirements" flow; the flow
files are in `kev/flows/` if anyone wants to look at them.
