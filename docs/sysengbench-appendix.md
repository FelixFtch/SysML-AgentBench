# Appendix: SysEngBench

SysEngBench (Bell, Longshore, Madachy, the team behind paper 3) is a set of multiple-choice questions on systems engineering knowledge, organised by INCOSE Handbook category. It contains no SysML model that the official Pilot could check. Source: `rabell/SysEngBench` on Hugging Face, MIT licence, `test.csv` with 1,144 four-option questions, registered with its SHA-256 in `datasets/SOURCES.md`.

## How it is used

It is a side benchmark named in the sponsor's brief and is not added to the exam score. `bench/run_side.py` puts the same 100 questions, fixed with seed 20261006 (`analysis/sysengbench/ids-100.txt`), to the four exam candidates: direct qwen3.8-flash, direct qwen3.8-max, and OpenCode and Claude Code on qwen3.8-flash in the agent sandbox. Each prompt holds 10 questions and asks for a JSON map from question id to letter; every question is asked three times, 300 answers per candidate. The answer column is read only when scoring.

## Results

| Candidate | Correct of 300 |
|---|---|
| Direct qwen3.8-flash | 283 |
| Direct qwen3.8-max | 291 |
| OpenCode (flash) | 272 |
| Claude Code (flash) | 291 |

Answering B every time scores 51 of these 100 questions: in the full set the key is B for 557 questions and C for 394 of 1,144. All four candidates score 91–97%, so the benchmark says that the models know the vocabulary of systems engineering; it does not separate them the way the maritime exam does, and it says nothing about writing SysML v2. Current numbers are in `STATUS.md`; the run folders are `analysis/side-sysengbench-*`.

The 2026-10-03 run (20 questions answered by a judging model) is archived in `analysis/archive/2026-10-06-judges/` and not used.
