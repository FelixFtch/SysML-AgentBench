"""Build the exam report from the saved results of the frozen 2026-10-06 batches. No model is called.

Four candidates, kept apart: direct qwen3.8-flash and direct qwen3.8-max (27 tasks × P0-P3 × 3), OpenCode and
Claude Code on qwen3.8-flash in the sandbox (27 × 3). Numbers come from bench.board_facts; failure classes from
analysis/failure-classes-20261006.jsonl. Output: analysis/report/exam-20261006/ (index.html, figures, CSV).
"""
from __future__ import annotations

import csv
import html
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bench.batches import COHORTS, TYPES, rows  # noqa: E402
from bench.board_facts import facts  # noqa: E402

OUT = ROOT / "analysis" / "report" / "exam-20261006"
ORDER = ["flash", "max", "opencode", "claude"]
COLORS = {"flash": "#0F4D92", "max": "#5B8DB8", "opencode": "#2F9C7D", "claude": "#C9792B"}
NAMES = {"P0": "P0 one-shot", "P1": "P1 repair loop (≤20)", "P2": "P2 outline first + repair", "P3": "P3 retrieval + outline + repair"}


def e(value) -> str:
    return html.escape(str(value))


def pct(a: int, b: int) -> str:
    return f"{100 * a / b:.1f}%" if b else "—"


def figures(C: dict) -> None:
    fig_dir = OUT / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8.2, 4.2))
    width = 0.2
    for index, key in enumerate(ORDER):
        values = [100 * C[key]["by_type"][kind]["pass"] / C[key]["by_type"][kind]["n"] if C[key]["by_type"][kind]["n"] else 0 for kind in TYPES]
        ax.bar([i + (index - 1.5) * width for i in range(len(TYPES))], values, width, label=C[key]["label"], color=COLORS[key])
    ax.set_xticks(range(len(TYPES)), TYPES)
    ax.set_ylim(0, 100)
    ax.set_ylabel("Pass rate (%)")
    ax.legend(fontsize=8, ncol=4, loc="lower center", bbox_to_anchor=(0.5, 1.01), frameon=False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(fig_dir / "by_type.png", dpi=160)
    fig.savefig(fig_dir / "by_type.pdf")
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(8.2, 3.6), sharey=True)
    for ax, key in zip(axes, ("flash", "max")):
        configs = C[key]["configs"]
        x = range(len(configs))
        ax.bar([i - 0.18 for i in x], [c["syntax_first"] for c in configs], 0.36, label="parses on the first attempt", color="#9BB4C4")
        ax.bar([i + 0.18 for i in x], [c["syntax_final"] for c in configs], 0.36, label="parses after the repair loop", color=COLORS[key])
        ax.set_xticks(list(x), [c["id"] for c in configs])
        ax.set_title(C[key]["label"], fontsize=10)
        ax.set_ylim(0, 40)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    axes[0].set_ylabel("SysML answers out of 39")
    axes[0].legend(fontsize=8, loc="lower left")
    fig.tight_layout()
    fig.savefig(fig_dir / "repair.png", dpi=160)
    fig.savefig(fig_dir / "repair.pdf")
    plt.close(fig)


def write_csv(path: Path, table: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(table[0]))
        writer.writeheader()
        writer.writerows(table)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    f = facts()
    C = f["cohorts"]
    figures(C)
    per_task = defaultdict(lambda: {key: [0, 0] for key in ORDER})
    for key in ORDER:
        for row in rows(key):
            slot = per_task[row["task_id"]][key]
            slot[0] += row["status"] == "PASS"
            slot[1] += 1
    tasks = sorted(per_task, key=lambda task: (TYPES.index(task.split("-")[0]), task))
    write_csv(OUT / "per_task.csv", [{"task_id": task, **{f"{key}_pass": per_task[task][key][0] for key in ORDER},
                                      **{f"{key}_n": per_task[task][key][1] for key in ORDER}} for task in tasks])
    failures = [json.loads(line) for line in (ROOT / "analysis" / "failure-classes-20261006.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    fail_counts = {key: Counter(item["class"] for item in failures if item["cohort"] == key) for key in ORDER}
    all_classes = [name for name, _count in Counter(item["class"] for item in failures).most_common()]
    flash, mx, oc, cl = (C[key] for key in ORDER)
    fcfg = {c["id"]: c for c in flash["configs"]}
    mcfg = {c["id"]: c for c in mx["configs"]}
    weakest = min((kind for kind in TYPES if flash["by_type"][kind]["n"]), key=lambda kind: flash["by_type"][kind]["pass"] / flash["by_type"][kind]["n"])
    seb, pure = f["side"]["sysengbench"], f["side"]["pure"]
    any_seb = next(iter(seb.values()), {})
    costs = f["costs"]
    item_of = {item["id"]: item for item in costs["items"]}

    def agent(c: dict) -> str:
        return f"{c['pass']}/{c['n']}" + ("" if c["n"] == c["expected"] else f" (of {c['expected']} runs; still running when this page was built)")

    type_rows = "\n".join(f"<tr><td>{kind}</td>" + "".join(
        f"<td>{C[key]['by_type'][kind]['pass']}/{C[key]['by_type'][kind]['n']}</td>" if C[key]["by_type"][kind]["n"] else "<td>—</td>" for key in ORDER) + "</tr>"
        for kind in TYPES)
    cfg_rows = "\n".join(
        f"<tr><td>{e(NAMES[c['id']])}</td><td>{c['pass']}/{c['n']}</td><td>{c['syntax_first']} → {c['syntax_final']}</td><td>{c['repairs']}</td>"
        f"<td>{c['tokens']:,}</td><td>${c['usd']:.4f}</td><td>{mcfg[c['id']]['pass']}/{mcfg[c['id']]['n']}</td><td>${mcfg[c['id']]['usd']:.4f}</td></tr>"
        for c in flash["configs"])
    fail_rows = "\n".join(f"<tr><td>{e(name)}</td>" + "".join(f"<td>{fail_counts[key].get(name, 0)}</td>" for key in ORDER) + "</tr>" for name in all_classes)
    task_rows = "\n".join(f"<tr><td>{task}</td>" + "".join(f"<td>{per_task[task][key][0]}/{per_task[task][key][1]}</td>" if per_task[task][key][1] else "<td>—</td>" for key in ORDER) + "</tr>"
                          for task in tasks)
    side_rows = "\n".join(
        f"<tr><td>{e(C[key]['label'])}</td><td>{(str(seb[key]['correct']) + '/' + str(seb[key]['n'])) if key in seb else '—'}</td>"
        f"<td>{(str(pure[key]['pass']) + '/' + str(pure[key]['n'])) if key in pure else '—'}</td></tr>" for key in ORDER)
    cost_rows = "\n".join(
        f"<tr><td>{e(item['group'])}</td><td>{e(item['label'])}</td><td>{e(item['model'])}</td><td>{item['input']:,}</td><td>{(item.get('cached') or 0):,}</td>"
        f"<td>{item['output']:,}</td><td>${item['usd']:.4f}</td></tr>" for item in costs["items"])
    discarded = "\n".join(f"<tr><td>{e(item['label'])}</td><td>{item['pass']}/{item['n']}</td><td>{e(item['reason'])}</td><td>{e(item['dir'])}</td></tr>" for item in f["discarded"])
    discarded += "".join(f"\n<tr><td>{e(item['label'])}</td><td>{item['pass']}/{item['n']}</td><td>{e(item['reason'])}</td><td>{e(item['dir'])} (replaced by {e(item['rerun_dir'])})</td></tr>"
                         for item in f["superseded"])
    agent_rows = "\n".join(
        f"<tr><td>{e(C[key]['label'])}</td><td>{C[key]['pass']}/{C[key]['n']}</td><td>{C[key]['agent']['timeouts']}</td><td>{C[key]['agent']['no_answer']}</td>"
        f"<td>{C[key]['agent']['runs_validated']}</td><td>{C[key]['agent']['validate_calls']}</td></tr>" for key in ("opencode", "claude"))
    order_file = ROOT / "analysis" / "validator-order-20261006.json"
    order = json.loads(order_file.read_text(encoding="utf-8"))["summary"] if order_file.is_file() else {}
    order_names = {"flash": "direct flash", "max": "direct max", "opencode": "OpenCode", "claude": "Claude Code",
                   "opencode-superseded": "OpenCode first batch (superseded)", "claude-superseded": "Claude Code first batch (superseded)",
                   "gold": "gold packages"}
    order_line = "; ".join(f"{e(order_names.get(name, name))} {slot['differ']} of {slot['answers']}" for name, slot in order.items()) or "not run yet"
    prices = costs["prices"]["models"]
    price_line = "; ".join(f"{name} input ${p['input']}, cached ${p['cache']}, output ${p['output']} per million tokens" for name, p in prices.items())
    p0, p3, m0 = item_of.get("flash-P0"), item_of.get("flash-P3"), item_of.get("max-P0")
    page = f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<title>Maritime SysML exam, frozen bank, four candidates</title>
<style>
body {{ margin: 0; background: #fff; color: #111; font: 17px/1.65 Georgia, serif; }}
main {{ max-width: 1040px; margin: 0 auto; padding: 45px 58px; }}
h1 {{ font-size: 29px; line-height: 1.25; margin: 0 0 12px; }}
h2 {{ font-size: 20px; margin-top: 28px; }}
.subtitle {{ font-size: 20px; }}
.byline {{ color: #444; }}
table {{ border-collapse: collapse; width: 100%; margin: 18px 0; font-size: 15px; }}
th, td {{ border: 1px solid #d9d9d9; padding: 8px 10px; text-align: left; vertical-align: top; }}
th {{ background: #f4f7f8; }}
figure {{ margin: 24px 0; }}
img {{ width: 100%; height: auto; }}
figcaption {{ font-size: 14px; color: #444; }}
code {{ font-size: 14px; }}
</style>
<main>
<h1>Maritime SysML exam</h1>
<p class="subtitle">27 sealed tasks, four candidates, scored only by the official SysML v2 Pilot and answer keys written in advance</p>
<p class="byline">RTRC 2706 · UConn Senior Design · synthetic maritime ISR scenario; no number is an RTX specification. Built from saved files by <code>python3 analysis/report/build_exam_report.py</code>.</p>

<h2>What can be said</h2>
<table>
<tr><th>Question</th><th>Saved result</th></tr>
<tr><td>How much do the candidates get right without the answer key?</td><td>Direct qwen3.8-flash {flash['pass']}/{flash['n']} ({pct(flash['pass'], flash['n'])}); direct qwen3.8-max {mx['pass']}/{mx['n']} ({pct(mx['pass'], mx['n'])}); OpenCode on flash {agent(oc)}; Claude Code on flash {agent(cl)}. The weakest task type for flash is {weakest}: {flash['by_type'][weakest]['pass']}/{flash['by_type'][weakest]['n']} (max {mx['by_type'][weakest]['pass']}/{mx['by_type'][weakest]['n']}).</td></tr>
<tr><td>With the same model, do repair, an outline or retrieval help?</td><td>Flash, 81 cells each: P0 {fcfg['P0']['pass']}, P1 {fcfg['P1']['pass']}, P2 {fcfg['P2']['pass']}, P3 {fcfg['P3']['pass']}. The repair loop lifts the official parse from the first attempt to the final one (39 SysML answers each): P1 {fcfg['P1']['syntax_first']} → {fcfg['P1']['syntax_final']}, P2 {fcfg['P2']['syntax_first']} → {fcfg['P2']['syntax_final']}, P3 {fcfg['P3']['syntax_first']} → {fcfg['P3']['syntax_final']}. Max parses 39/39 on the first attempt in every approach.</td></tr>
<tr><td>Can a model replace the tool as judge?</td><td>Not used. Two model judges were tried on the 2026-10-03 answers and agreed with the tool on 226/288 and 157/288; scores come only from the Pilot and the keys (decision 025).</td></tr>
<tr><td>Are the agent scores clean?</td><td>The scored agent runs ran in a sandbox that shows only the task input, the rules file and <code>./validate</code>. Two earlier agent batches of the same morning are discarded: OpenCode could read the answer keys, Claude Code had its tools denied. The agents' ALN rows come from a rerun: the first sandboxed batch checked alignment packages with <code>./validate</code> in a file order the official Pilot passes and the scorer's order fails (section 7).</td></tr>
<tr><td>What did this cost?</td><td>At the China (Beijing) list price the scored batches and the side benchmarks cost ${costs['batch_usd']:.4f}{f'; flash P0 ${p0["usd"]:.4f}, flash P3 ${p3["usd"]:.4f}, max P0 ${m0["usd"]:.4f}' if p0 and p3 and m0 else ''}. Everything recorded, including the discarded runs, about ${costs['recorded_usd']:.4f}.</td></tr>
</table>

<h2>1. What was measured</h2>
<p>27 tasks: generate a model (GEN 5), modify a model (MOD 5), align two models (ALN 3, paper 1), query a model (QRY 5), ask when a number is missing (AMB 4), restate a model as requirements (RT 5). A second reviewer checked every key (<code>bench/tasks/t4_maritime_isr/heldout/REVIEW.md</code>, 27/27 mechanical checks) and the bank, scorers, prompts, retrieval library and toolchain are frozen in <code>bench/FREEZE.md</code> (tag <code>freeze-2026-10-06</code>).</p>
<p>{e(f['rule'])}</p>
<p>Direct candidates answer through one conversation per cell. P0 writes once. P1 adds the repair loop: the complete official error list goes back after every earlier version, up to 20 repairs, stopping after three identical resubmissions. P2 writes an outline first; P3 also retrieves official example models and notes with MiniLM + FAISS (paper 2); P2 and P3 repair as P1. The agents get the task input, AGENTS.md and <code>./validate</code> in a bubblewrap sandbox and repair inside their own session; the grader parses only their final answer. The direct prompts carry the SysML rules (and the alignment rules for ALN); the agents do not get them and learn the Pilot's rules only from its diagnostics.</p>

<h2>2. Four candidates by task type</h2>
<table><tr><th>Type</th>{''.join(f'<th>{e(C[key]["label"])}</th>' for key in ORDER)}</tr>
{type_rows}
<tr><td><b>All</b></td>{''.join(f'<td><b>{C[key]["pass"]}/{C[key]["n"]}</b></td>' for key in ORDER)}</tr></table>
<figure><img src="figures/by_type.png" alt="Pass rate by task type for the four candidates"><figcaption>Figure 1. Pass rate by task type. Direct candidates: 60 cells per type (36 for ALN, 48 for AMB); agents: 15 runs per type (9 for ALN, 12 for AMB).</figcaption></figure>
<p>Repeat groups whose three repeats disagree: {', '.join(f"{C[key]['short']} {C[key]['reliability']['flips']}/{C[key]['reliability']['groups']}" for key in ORDER)}.</p>
<table><tr><th>Agent</th><th>Pass</th><th>Hit the 900 s limit</th><th>No answer.md</th><th>Runs that called ./validate</th><th>./validate calls</th></tr>
{agent_rows}</table>

<h2>3. Approaches with the same model</h2>
<table><tr><th>Approach</th><th>flash pass</th><th>flash parse 1st → final (of 39)</th><th>flash repairs</th><th>flash tokens</th><th>flash USD</th><th>max pass</th><th>max USD</th></tr>
{cfg_rows}</table>
<figure><img src="figures/repair.png" alt="Official parse on the first attempt and after repair"><figcaption>Figure 2. SysML answers (GEN, MOD, ALN; 39 per approach) that pass the official parse on the first attempt and after the repair loop. P0 has no loop.</figcaption></figure>

<h2>4. How the failures split</h2>
<table><tr><th>Class</th>{''.join(f'<th>{e(C[key]["short"])}</th>' for key in ORDER)}</tr>
{fail_rows}</table>
<p>Each failing cell gets one class from its saved evidence (<code>bench/classify_failures.py</code>, <code>analysis/failure-classes-20261006.jsonl</code>); <code>docs/failure_taxonomy.md</code> explains the classes with examples.</p>

<h2>5. Per task</h2>
<table><tr><th>Task</th>{''.join(f'<th>{e(C[key]["short"])}</th>' for key in ORDER)}</tr>
{task_rows}</table>

<h2>6. Side benchmarks named in the brief</h2>
<table><tr><th>Candidate</th><th>SysEngBench</th><th>PURE</th></tr>
{side_rows}</table>
<p>SysEngBench (rabell/SysEngBench, MIT): {any_seb.get('questions', 100)} questions fixed with seed 20261006, 10 per prompt, {any_seb.get('repeats', 3)} repeats; always answering B scores {any_seb.get('always_b', '—')}/{any_seb.get('questions', 100)} on this subset. PURE (Zenodo 7118517, CC BY 4.0): two excerpts, three repeats, extracted sentences must equal the key. Neither is added to the exam score.</p>

<h2>7. Runs that do not count</h2>
<table><tr><th>Batch</th><th>Score</th><th>Why it does not count</th><th>Folder</th></tr>
{discarded}
<tr><td>{e(f['archive']['label'])}</td><td>{f['archive']['pass']}/{f['archive']['n']}</td><td>{e(f['archive']['note'])}</td><td>analysis/heldout-20261003T*</td></tr></table>
<p>Validator order. The official Pilot 0.62 can give a different verdict for the same files in a different order: an alignment package that writes a nested usage as <code>Pkg::part::sub</code> fails with <code>Must be an accessible feature (use dot notation for nesting)</code> when the source models come first, as in the scorer, and passes when the package comes first. Re-validating every graded ALN answer with the package first changed (<code>bench/check_validator_order.py</code>): {order_line}. <code>./validate</code> now passes the files in the scorer's order (decision 026).</p>

<h2>8. What it cost</h2>
<p>Prices checked {e(costs['prices']['checked'])}, {e(costs['prices']['region'])}: {e(price_line)}. {e(' '.join(costs['unrecorded']))}</p>
<table><tr><th>Group</th><th>Item</th><th>Model</th><th>Input tokens</th><th>Of which cached</th><th>Output tokens</th><th>USD</th></tr>
{cost_rows}</table>

<h2>9. What these results cannot support</h2>
<table><tr><th>Claim</th><th>Why not</th></tr>
<tr><td>The models are ready to design maritime systems</td><td>27 synthetic tasks with one author and one reviewer; a Pilot PASS is syntax, and the budgets are static sums.</td></tr>
<tr><td>One approach is reliably better than another</td><td>Three repeats per cell and repeat groups that disagree; no confidence intervals were computed.</td></tr>
<tr><td>The agents beat the direct calls in general, or the reverse</td><td>One model (flash), one pinned version of each agent, one sandbox setup, and different help: the direct prompts carry the SysML rules, the agents have the validator in a loop they run themselves. Agents spend many more tokens per answer.</td></tr>
<tr><td>Alignment pairs are semantically right whenever the Pilot passes</td><td>The Pilot checks that names resolve; the ALN keys and the person in 2.3 decide meaning.</td></tr>
<tr><td>Results transfer to other model families</td><td>Only Qwen models were run.</td></tr>
</table>

<h2>10. Files</h2>
<p>Scored batches: {', '.join(f"<code>analysis/{e(C[key]['batch'])}/results.jsonl</code>" for key in ORDER if C[key]['batch'])}; agents' ALN rows: {', '.join(f"<code>analysis/{e(C[key]['rerun_batch'])}/results.jsonl</code>" for key in ORDER if C[key].get('rerun_batch'))}. Per-task table: <code>per_task.csv</code>. Status page: <code>STATUS.md</code>. Decisions 019 (task vs design verdict), 022 (repair loop), 023 (retrieval), 024 (alignment), 025 (no judges, second review, freeze), 026 (agent sandbox).</p>
<p>This page only summarises results already on disk; it calls no model.</p>
</main>
</html>
"""
    (OUT / "index.html").write_text(page, encoding="utf-8")
    print(OUT / "index.html")


if __name__ == "__main__":
    main()
