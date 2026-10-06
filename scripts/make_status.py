"""Write STATUS.md from the saved results of the frozen 2026-10-06 batches (bench/batches.py). No model is called."""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TYPES = ["GEN", "MOD", "ALN", "QRY", "AMB", "RT"]
ORDER = ["flash", "max", "opencode", "claude"]


def _usd(value: float) -> str:
    return f"${value:.4f}" if value >= 0.01 else f"${value:.5f}"


def _cell(item: dict) -> str:
    return f"{item['pass']}/{item['n']}" if item["n"] else "—"


def main() -> None:
    from bench.board_facts import facts
    f = facts()
    C = f["cohorts"]
    lines = [
        "# STATUS",
        "",
        f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} by `python3 scripts/make_status.py` from saved results. "
        "All maritime numbers are synthetic, not RTX specifications. The official SysML v2 Pilot 0.62 is the only syntax judge; "
        "the answer keys are the ground truth; no model judges (decision 025).",
        "",
        f"Task bank: 27 sealed tasks, second review recorded in `bench/tasks/t4_maritime_isr/heldout/REVIEW.md`, frozen in `{f['freeze']['file']}` (tag `{f['freeze']['tag']}`).",
        "",
        "## Scoring rule",
        "",
        f["rule"],
        "",
        "Freeze revision 2 (decision 028), after the batches and by the user's decisions: retrieval cards carry documentation text "
        "(every direct P3 cell rerun); MOD-01's key also checks the radio part and link it says to keep; AMB-02's key accepts "
        "\"maximum power\", \"power budget\" and \"limit\"; an AMB number counts as invented only when the answer also writes SysML. "
        "Saved answers were re-scored with the batches' own scoring code (`bench/rescore.py`); six cells changed from FAIL to PASS "
        "(`analysis/rescore-r2.json`).",
        "",
        "## Four candidates on the 27 tasks",
        "",
        "| Candidate | Cells | PASS | Rate | Repeat groups that disagree | Cost (USD, cn-beijing) |",
        "|---|---|---|---|---|---|",
    ]
    for key in ORDER:
        item = C[key]
        note = "" if item["n"] == item["expected"] else f" (of {item['expected']})"
        rate = f"{100 * item['pass'] / item['n']:.1f}%" if item["n"] else "—"
        lines.append(f"| {item['label']} | {item['n']}{note} | {item['pass']} | {rate} | {item['reliability']['flips']}/{item['reliability']['groups']} | {_usd(item['usd'])} |")
    lines += ["", "Direct candidates: 27 tasks × P0–P3 × 3 repeats; the system prompt carries the SysML rules (and the alignment rules for ALN), "
              "and P1–P3 repair with the full official diagnostics. Agents: 27 tasks × 3 repeats, each run in a bubblewrap sandbox with the task "
              "statement, AGENTS.md and `./validate` (the official Pilot) and nothing else: no SysML rules in the prompt, and the repository, "
              "answer keys, past runs and transcripts are not visible (decision 026). The agents' ALN rows come from a rerun with `./validate` "
              "in the scorer's file order (see the validator note below).",
              "", "| Task type | " + " | ".join(C[key]["short"] for key in ORDER) + " |", "|---|" + "---|" * len(ORDER)]
    for kind in TYPES:
        lines.append(f"| {kind} | " + " | ".join(_cell(C[key]["by_type"][kind]) for key in ORDER) + " |")
    lines += ["", "| Agent | Runs | PASS | Hit the 900 s limit | No answer.md | Runs that called ./validate | ./validate calls | Tokens (input, cached, output) |",
              "|---|---|---|---|---|---|---|---|"]
    for key in ("opencode", "claude"):
        item = C[key]
        stats = item.get("agent") or {}
        usage = item["usage"]
        lines.append(f"| {item['label']} | {item['n']} | {item['pass']} | {stats.get('timeouts', 0)} | {stats.get('no_answer', 0)} | "
                     f"{stats.get('runs_validated', 0)} | {stats.get('validate_calls', 0)} | {usage['input']:,}, {usage['cached']:,}, {usage['output']:,} |")
    lines += ["", "**Validator note.** The official Pilot 0.62 can give a different verdict for the same files in a different order. "
              "An alignment package that writes a nested usage as `Pkg::part::sub` instead of `Pkg::part.sub` fails with "
              "`Must be an accessible feature (use dot notation for nesting)` when the source models are listed first, and passes when the "
              "package itself is listed first. The scorer always lists the sources first; the direct candidates' repair loop uses the scorer. "
              "Re-validating every graded ALN answer in the other order changed none of the 72 direct answers or the three gold packages, "
              "and 8 of the 15 ALN answers the agents submitted in their first sandboxed batch (three runs submitted none); in all 8 the agent "
              "had validated its package with its own file listed first. `./validate` now passes the files in the scorer's order, and every "
              "agent ALN run was rerun."]
    for key in ("flash", "max"):
        lines += ["", f"### Approaches, {C[key]['label']} (81 cells each)", "",
                  "| Approach | PASS | Official parse 1st attempt → final (39 SysML answers) | Repairs | Tokens | USD |", "|---|---|---|---|---|---|"]
        for row in C[key]["configs"]:
            lines.append(f"| {row['id']} | {row['pass']} | {row['syntax_first']} → {row['syntax_final']} | {row['repairs']} | {row['tokens']:,} | {_usd(row['usd'])} |")
    failures = [json.loads(line) for line in (ANALYSIS / "failure-classes-20261006.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    lines += ["", "## Failures by class", "", "| Class | " + " | ".join(C[key]["short"] for key in ORDER) + " |", "|---|" + "---|" * len(ORDER)]
    counts = {key: Counter(item["class"] for item in failures if item["cohort"] == key) for key in ORDER}
    for name, _total in Counter(item["class"] for item in failures).most_common():
        lines.append(f"| {name} | " + " | ".join(str(counts[key].get(name, 0)) for key in ORDER) + " |")
    lines += ["", "Details: `docs/failure_taxonomy.md`, `analysis/failure-classes-20261006.jsonl` (rebuilt by `python3 bench/classify_failures.py`).", ""]
    seb, pure = f["side"]["sysengbench"], f["side"]["pure"]
    any_seb = next(iter(seb.values()), None)
    lines += ["## Side benchmarks named in the brief (not in the exam score)", "",
              "| Candidate | SysEngBench | PURE |", "|---|---|---|"]
    for key in ORDER:
        seb_cell = f"{seb[key]['correct']}/{seb[key]['n']}" if key in seb else "—"
        pure_cell = f"{pure[key]['pass']}/{pure[key]['n']}" if key in pure else "—"
        lines.append(f"| {C[key]['short']} | {seb_cell} | {pure_cell} |")
    if any_seb:
        lines += ["", f"SysEngBench (rabell/SysEngBench, MIT): {any_seb['questions']} questions fixed with seed 20261006 (`{any_seb['subset']}`), 10 per prompt, "
                      f"{any_seb['repeats']} repeats. Always answering B scores {any_seb['always_b']}/{any_seb['questions']} on this subset; the key is mostly B and C. "
                      "PURE: the two sealed excerpts (EIRENE, CDN peering), 3 repeats, extracted sentences must equal the key."]
    lines += ["", "## Runs that do not count", ""]
    for item in f["discarded"]:
        lines.append(f"- {item['label']} ({item['pass']}/{item['n']}, `{item['dir']}`): {item['reason']}")
    for item in f["superseded"]:
        lines.append(f"- {item['label']} ({item['pass']}/{item['n']}, `{item['dir']}`, replaced by `{item['rerun_dir']}`): {item['reason']}")
    lines.append(f"- {f['archive']['label']}: {f['archive']['pass']}/{f['archive']['n']}. {f['archive']['note']}")
    runs = []
    for path in sorted(ANALYSIS.glob("discover-2026*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(record.get("designs"), list):
            continue
        failing = sorted({check["id"] for design in record["designs"] for check in design.get("checks") or [] if check.get("status") == "FAIL"})
        alignment = record.get("alignment") or {}
        declared = f" ({alignment['declared']} pairs declared)" if alignment.get("declared") is not None else ""
        runs.append(f"- `{record['id']}`: designs {', '.join(d['key'] + ' ' + d['sysml_status'] for d in record['designs'])}; "
                    f"alignment package {alignment.get('package', {}).get('sysml_status', 'none')}{declared}; "
                    f"checks {'failing ' + ', '.join(failing) if failing else 'all pass'}; "
                    f"approved {', '.join(a['design'] for a in record.get('approvals') or []) or 'none'}.")
    memory = f["knowledge"]["memory"]
    lines += ["", "## Part 2 prototype: blank brief → requirements → two designs → Pilot → alignment → checks → human approval → memory", ""] + runs
    lines += ["", f"Memory (`analysis/memory/approved.jsonl`): {memory['n']} approved designs "
              f"({', '.join(e['run_id'] + ' ' + e['design'] for e in memory['entries'])}). Approved designs are retrieved by the next run.", ""]
    lines += ["## MOD change chain (latest run per task, qwen3.8-max)", "", "| Task | Task verdict | Design verdict | Kept values | Read-back numbers |", "|---|---|---|---|---|"]
    for task in ("MOD-01", "MOD-02", "MOD-03", "MOD-04", "MOD-05"):
        path = ANALYSIS / f"mvp-case-latest-{task}.json"
        if not path.is_file():
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        kept = record.get("must_preserve") or {}
        said = record.get("round_trip_mentions") or {}
        lines.append(f"| {task} | {record['status']} | {record['engineering_status'] if record.get('checks') else 'n/a'} | "
                     f"{kept.get('hit', 0)}/{kept.get('expected', 0)} | {sum(said.values())}/{len(said)} |")
    costs = f["costs"]
    lines += ["", "## Cost", "",
              f"At the China (Beijing) list price checked {costs['prices']['checked']}: the four scored batches and the side benchmarks {_usd(costs['batch_usd'])}; "
              f"everything recorded, including the discarded runs, graph retrieval, Part 2 and the MOD chain, about {_usd(costs['recorded_usd'])}. "
              + " ".join(costs["unrecorded"]), ""]
    lines += [
        "## Not done",
        "",
        "- Human blind review with Cohen's κ; confidence intervals for the differences between approaches and candidates.",
        "- A frontier model outside the Qwen family; the vendor AI (Cameo AI Assistant) and a second checker (Syside CLI).",
        "- Tasks that must trigger the approval gate; interface tasks in the UMAA style (interoperability); a scored evaluation set for the Part 2 prototype; dynamic simulation beyond static budgets.",
        "- A reproduction on a clean machine (fresh clone, `requirements-retrieval.txt`, tests, one batch re-scored).",
        "",
    ]
    text = "\n".join(lines)
    (ROOT / "STATUS.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
