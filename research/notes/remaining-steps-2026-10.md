# The nine remaining items: checked on 2026-10-03

The model was switched to qwen3.8-max (`MVP_LLM_MODEL` in `.env`). The endpoint returns the model name `qwen3.8-max`. Each item below records what was found, what was done, and why it stopped.

## Graph retrieval

The second paper (Bader et al., ISSE 2025) measures this: an existing model is first turned into a graph; nodes are picked by similarity between the question and the nodes, together with their one-hop neighbours, and handed to GPT. They have one electric-vehicle model and three questions. At a threshold of 0.45 the retrieval F1 is 0.904; this measures how accurately the relevant elements are found, not whether the answers are right. The authors' code hard-codes a demo server address, computes a ranking parameter it never uses, and the evaluation numbers were filled in by hand, so their notebook was not re-run.

We did the same kind of step: the maritime model parsed by the official tool (428 elements, 56 named), nodes chosen by the words in the question, plus one hop of neighbours, without handing the whole `.sysml` file to the model. qwen3.8-max on five read-the-model tasks: QRY-01, 02, 04 and 05 pass; QRY-03 answers 0 connections where the key says 3. For counting connections, neighbour snippets alone are not enough. MiniLM vectors were not used, so this is not a reproduction of their 0.904.

## Claude Code

Locally, `claude -p` gave no answer within 20 seconds and returned `unrecognized_model`, with the model name `glm-5.3`. The router on port 3456 was not listening. The 24 tasks were therefore not run. To run them, Claude must first be pointed at a working qwen3.8-max and then the whole batch retried. Claude's global configuration was not changed.

## Cameo assistant

The vendor check of 2026-10-02 still holds: the AI Assistant is part of Magic Cyber Systems Engineer / SoS Architect 2026x, and the Community Edition page does not say it includes the assistant. The desktop edition has no headless command. Without Bollas's license and login this item cannot run, and no score is invented for it.

## PURE

The dataset page of Zenodo 7118517 is CC BY 4.0, but the curators state that they did not confirm the copyright of each original requirements document. The 79 PDFs were therefore not put into the repository. The XML subset was downloaded to `datasets/pure/` (not in git). Two short excerpts were turned into tasks: EIRENE railway radio, and content-delivery-network peering. The excerpts cite their source. These are "extract the requirements from the original text" tasks and have not yet been scored with max.

## STPA

DLR's SysML v2 STPA library is MIT or Apache-2.0 and uses metadata such as `#hazard`. Without that library loaded, this notation does not pass the official Pilot. Two ordinary requirements were written into the scenario instead: `LossOfSeparation` (the loss: a collision) and `HazardTrackNotShared` (the hazard: a track not delivered to the command ship). Official validation PASS, run `20261003T011336-a33d5bdc`. The numbers are still synthetic.

## SysEngBench

MIT-licensed multiple-choice questions, about 1,100 of them, with no SysML files. The appendix is in `docs/sysengbench-appendix.md`. Not part of the main 24-task score.

## The 151 SysMBench tasks

Jin et al., arXiv:2508.03215, wrote 151 scenarios and said they would release them. The paper HTML we read gives no repository address with a license. The similarly named SysMoBench (Apache-2.0) is about formal modeling of operating systems, not these 151 tasks. The cmuchancel repository belongs to another 2026 paper and has no stated license. The 151 tasks were not downloaded, not mixed into retrieval, and not used for scoring.

## The demonstration for Bollas

`python3 bench/demo_bollas.py` tells a five-minute story from saved results: the MOD-01 replay, MOD-05's power FAIL, the alignment and tokens of the four approaches, max's five graph-retrieval queries, and why Cameo was not run. It has not been shown to him in person yet.

## A second model reviewing all 288 answers

Done. The judge is qwen3.8-max, reviewing the 288 answers flash submitted, without changing the original scores. Agreement 157/288 (54.5%). Of the 76 answers the tool failed, max called 70 a pass, including all 12 over-power MOD-05 answers. Results are in `analysis/validator-all-max.jsonl`.
