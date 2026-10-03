"""Write STATUS.md from the saved results with the current scorer.

GEN/MOD statuses come from analysis/rescore-20261003.jsonl; the archived results files are not rewritten.
"""
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


def _usd(value: float) -> str:
    return f"${value:.4f}" if value >= 0.01 else f"${value:.5f}"


def main() -> None:
    from bench.board_facts import facts
    f = facts()
    costs = {item["label"]: item for item in f["costs"]["items"]}
    lines = [
        "# STATUS",
        "",
        f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} by `python3 scripts/make_status.py` from saved results. "
        "All maritime numbers are synthetic, not RTX specifications. Official SysML v2 Pilot 0.62 is the syntax adjudicator.",
        "",
        "## Scoring rule (changed 2026-10-03)",
        "",
        "A task passes when the official parse passes, every required name and connection is present, no number was invented, "
        "every value the task said to keep is unchanged, and every engineering check comes out as the answer key expects. "
        "Whether the design meets its budget is reported separately as the design verdict.",
        "",
        f"The old rule scored MOD-05 honest answers FAIL and would have scored a raised limit PASS (checked with four hand-written probes). "
        f"All {sum(1 for _ in open(ANALYSIS / 'rescore-20261003.jsonl', encoding='utf-8'))} saved GEN/MOD answers were re-scored from their official parses; "
        f"{len(f['rescore']['changed'])} changed, all honest MOD-05 answers. Archived results files are unchanged; see `analysis/rescore-20261003.jsonl` "
        "and `docs/decisions/019-task-verdict-vs-design-verdict.md`.",
        "",
        "## Main matrix: qwen3.8-flash, 24 held-out tasks × P0–P3 × 3 repeats",
        "",
        f"Total {f['flash']['pass']}/{f['flash']['n']} PASS (archived rule: {f['rescore']['archived_flash_pass']}).",
        "",
        "| Configuration | PASS | FAIL | Tokens | Cost (USD, cn-beijing list price) |",
        "|---|---|---|---|---|",
    ]
    labels = {"P0": "P0 直接写", "P1": "P1 按报错返工", "P2": "P2 先列提纲", "P3": "P3 提纲 + 检索笔记"}
    for row in f["configs"]:
        cost = costs.get(labels[row["id"]], {})
        lines.append(f"| {row['id']} | {row['pass']} | {row['n'] - row['pass']} | {row['tokens']:,} | {_usd(cost.get('usd', 0))} |")
    lines += ["", "| Task type | PASS | Cells |", "|---|---|---|"]
    for kind in ("GEN", "MOD", "QRY", "AMB", "RT"):
        item = f["by_type"][kind]
        lines.append(f"| {kind} | {item['pass']} | {item['n']} |")
    reliability = f["reliability"]
    lines += ["", f"Repeat stability: {reliability['flips']} of {reliability['groups']} task × configuration groups gave different results across the three repeats "
              f"({', '.join(reliability['flip_tasks'])}).", ""]
    failures = [json.loads(line) for line in (ANALYSIS / "failure-classes.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    lines += [f"## Failures ({len(failures)})", "", "| Class | Cells |", "|---|---|"]
    for name, count in Counter(item["class"] for item in failures).most_common():
        lines.append(f"| {name} | {count} |")
    lines += ["", "Details: `docs/failure_taxonomy.md`, `analysis/failure-classes.jsonl`.", ""]
    oc = costs.get(next((label for label in costs if label.startswith("OpenCode")), ""), {})
    lines += [
        "## Off-the-shelf agents (separate cohorts, not added to the 288)",
        "",
        f"- OpenCode v1.18.27 on qwen3.8-flash: {f['opencode']['pass']}/{f['opencode']['n']}. MOD-02, MOD-03 and MOD-04 produced no SysML package. "
        f"Cost {_usd(oc.get('usd', 0))} for 24 tasks, mostly cached re-reads of the workspace.",
        f"- Claude Code through CCR on qwen3.8-max: {f['claude']['pass']}/{f['claude']['n']} after re-running the first run's GEN-04 failure and two timeouts (MOD-01, QRY-02). Token use was not recorded.",
        "",
        "## Model judges (not scored)",
        "",
        f"- Jev 1.13: agrees with the tool on {f['jev']['agree']}/{f['jev']['cells']}; {f['jev']['false_pass']} false passes, all GEN; {f['jev']['false_fail']} false fails (mostly AMB).",
        f"- qwen3.8-max: agrees on {f['judge']['agree']}/{f['judge']['n']}; {f['judge']['false_pass']} false passes.",
        "- Both judges were told that an over-budget design does not pass, so they are compared with the design verdict. Only MOD-05 differs between the two verdicts.",
        "",
    ]
    runs = []
    for path in sorted(ANALYSIS.glob("discover-2026*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(record.get("designs"), list):
            continue
        failing = sorted({check["id"] for design in record["designs"] for check in design.get("checks") or [] if check.get("status") == "FAIL"})
        runs.append(f"- `{record['id']}`: designs {', '.join(d['key'] + ' ' + d['sysml_status'] for d in record['designs'])}; "
                    f"alignment package {(record.get('alignment') or {}).get('package', {}).get('sysml_status', 'none')}; "
                    f"checks {'failing ' + ', '.join(failing) if failing else 'all pass'}; "
                    f"approved {', '.join(a['design'] for a in record.get('approvals') or []) or 'none'}.")
    memory = f["knowledge"]["memory"]
    lines += ["## Part 2 prototype: blank brief → requirements → two designs → Pilot → alignment → checks → human approval → memory", ""] + runs
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
    missing = f["costs"]["missing"]
    gaps = [f"{missing['matrix_cells']} matrix cells without call logs"] if missing["matrix_cells"] else []
    gaps += ["the qwen3.8-max judge over 288 answers", "Claude Code's 28 answers through CCR", "the two PURE tasks"]
    if missing["part2_partial"]:
        gaps.append(f"alignment and read-back calls in {missing['part2_partial']} Part 2 runs")
    if missing["mod_unlogged"]:
        gaps.append(f"{missing['mod_unlogged']} MOD change runs made before usage logging")
    lines += ["", "## Cost", "",
              f"Recorded spend at list price (China Beijing region, checked {f['costs']['prices']['checked']}): about {_usd(f['costs']['recorded_usd'])}. "
              f"Not recorded: {'; '.join(gaps)}. Part 2 and MOD runs made after 2026-10-03 19:00 UTC record every call.", ""]
    lines += [
        "## Not done",
        "",
        "- Second reviewer for the 24 answer keys; `bench/FREEZE.md` and a freeze tag.",
        "- Human blind review with Cohen's κ; confidence intervals for the configuration differences.",
        "- A frontier model and a qwen3.8-max run of the full matrix; graph retrieval as a P3 sub-configuration.",
        "- Alignment tasks with an answer key (paper 1) and tasks that must trigger the approval gate.",
        "- Second checker (Syside CLI) and vendor AI (Cameo AI Assistant); SysMBench 151 has no license file.",
        "- A scored evaluation set for the Part 2 prototype; dynamic simulation beyond static budget checks.",
        "",
    ]
    text = "\n".join(lines)
    (ROOT / "STATUS.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
