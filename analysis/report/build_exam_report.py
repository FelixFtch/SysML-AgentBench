"""Build a continuous benchmark report from saved score files.

Cohorts stay separate. The second model does not change a tool score.
GEN/MOD statuses come from analysis/rescore-20261003.jsonl (current scorer); the archived verdict is shown beside them.
"""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import sys

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bench.board_facts import facts  # noqa: E402
from bench.rescore import RULE_EN, apply, load as load_rescore  # noqa: E402
OUT = ROOT / "analysis" / "report" / "exam-20261003"
TASKS = [
    "GEN-01", "GEN-02", "GEN-03", "GEN-04", "GEN-05",
    "MOD-01", "MOD-02", "MOD-03", "MOD-04", "MOD-05",
    "QRY-01", "QRY-02", "QRY-03", "QRY-04", "QRY-05",
    "AMB-01", "AMB-02", "AMB-03", "AMB-04",
    "RT-01", "RT-02", "RT-03", "RT-04", "RT-05",
]
CONFIGS = ["P0", "P1", "P2", "P3"]


def fail_counts_from(rows: list[dict]) -> Counter:
    return Counter(row["class"] for row in rows)


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def figure(current: dict, archived: dict) -> None:
    names = CONFIGS
    now = [100 * current[name] / 72 for name in names]
    before = [100 * archived[name] / 72 for name in names]
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    x = range(len(names))
    width = 0.36
    ax.bar([i - width / 2 for i in x], now, width, label="Pass, current scorer", color="#0F4D92")
    ax.bar([i + width / 2 for i in x], before, width, label="Pass, archived scorer", color="#9BB4C4")
    ax.set_xticks(list(x), names)
    ax.set_ylim(0, 100)
    ax.set_ylabel("Percent of 72 cells")
    ax.legend()
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig_dir = OUT / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(fig_dir / "flash_config.png", dpi=160)
    fig.savefig(fig_dir / "flash_config.pdf")
    plt.close(fig)


def main() -> None:
    table = load_rescore()
    archived = load(ROOT / "analysis/heldout-20261003T000045/results.jsonl")
    archived += load(ROOT / "analysis/heldout-20261003T001321/results.jsonl")
    flash = [apply("flash", row, table) for row in archived]
    opencode = [apply("opencode", row, table) for row in load(ROOT / "analysis/opencode-20261003T001321/results.jsonl")]
    claude_first = [apply("claude1", row, table) for row in load(ROOT / "analysis/claude-qwen-20261003T014507/results.jsonl")]
    claude_retry = [apply("claude2", row, table) for row in load(ROOT / "analysis/claude-qwen-20261003T034819/results.jsonl")]
    judge = load(ROOT / "analysis/validator-all-max.jsonl")
    ablation = json.loads((ROOT / "analysis/ablation.json").read_text(encoding="utf-8"))
    now_pass = {(row["task_id"], row["configuration"], row["repeat"]) for row in flash if row["status"] == "PASS"}
    failures = [row for row in load(ROOT / "analysis/failure-classes.jsonl")
                if (row["task_id"], row["configuration"], row["repeat"]) not in now_pass]

    by_cfg = {name: Counter(row["status"] for row in flash if row["configuration"] == name) for name in CONFIGS}
    archived_cfg = {name: Counter(row["status"] for row in archived if row["configuration"] == name) for name in CONFIGS}
    totals = Counter(row["status"] for row in flash)
    archived_totals = Counter(row["status"] for row in archived)
    by_type = defaultdict(Counter)
    by_task_cfg = defaultdict(Counter)
    for row in flash:
        by_type[row["type"]][row["status"]] += 1
        by_task_cfg[(row["task_id"], row["configuration"])][row["status"]] += 1

    cfg_rows = []
    for name in CONFIGS:
        item = ablation[name]
        cfg_rows.append({
            "configuration": name,
            "cells": item["cells"],
            "pass": by_cfg[name]["PASS"],
            "fail": item["cells"] - by_cfg[name]["PASS"],
            "archived_pass": archived_cfg[name]["PASS"],
            "tokens": item["tokens"],
            "pass_per_1k_tokens": round(1000 * by_cfg[name]["PASS"] / item["tokens"], 3),
        })
    type_rows = []
    for name in ["GEN", "MOD", "QRY", "AMB", "RT"]:
        counts = by_type[name]
        type_rows.append({
            "type": name,
            "cells": sum(counts.values()),
            "pass": counts["PASS"],
            "fail": counts["FAIL"],
        })
    task_rows = []
    for task in TASKS:
        record = {"task_id": task}
        for name in CONFIGS:
            counts = by_task_cfg[(task, name)]
            record[name] = f"{counts['PASS']}/3"
        record["pass_of_12"] = sum(by_task_cfg[(task, name)]["PASS"] for name in CONFIGS)
        task_rows.append(record)

    claude = {row["task_id"]: row for row in claude_first}
    claude.update({row["task_id"]: row for row in claude_retry if claude[row["task_id"]]["status"] != "PASS"})
    first_fail = [row["task_id"] for row in claude_first if row["status"] == "FAIL"]
    first_timeout = [row["task_id"] for row in claude_first if row["status"] == "TIMEOUT"]
    claude_pass = sum(row["status"] == "PASS" for row in claude.values())
    oc_pass = sum(row["status"] == "PASS" for row in opencode)
    best = max(cfg_rows, key=lambda row: row["pass_per_1k_tokens"])
    syntax_fail = sum(count for name, count in fail_counts_from(failures).items() if name.startswith("syntax"))
    parsed = sum(1 for item in table.values() if item.get("sysml_status") == "PASS")
    unparsed = len(table) - parsed
    assert not any((item.get("must_preserve") or {}).get("missing") for item in table.values())
    fail_counts = fail_counts_from(failures)

    OUT.mkdir(parents=True, exist_ok=True)
    write_csv(OUT / "tables/flash_by_config.csv", cfg_rows)
    write_csv(OUT / "tables/flash_by_type.csv", type_rows)
    write_csv(OUT / "tables/flash_by_task.csv", task_rows)
    figure({row["configuration"]: row["pass"] for row in cfg_rows}, {row["configuration"]: row["archived_pass"] for row in cfg_rows})

    def cells(counter: Counter) -> str:
        return f"{counter['PASS']} pass, {counter['FAIL']} fail"

    task_body = "\n".join(
        "<tr><td>{task_id}</td><td>{P0}</td><td>{P1}</td><td>{P2}</td><td>{P3}</td><td>{pass_of_12}/12</td></tr>".format(**row)
        for row in task_rows
    )
    fail_body = "\n".join(
        f"<tr><td>{name}</td><td>{count}</td></tr>" for name, count in fail_counts.most_common()
    )
    names = {"P0": "P0 one-shot", "P1": "P1 repair from errors, up to 3 times", "P2": "P2 outline first", "P3": "P3 outline plus keyword notes"}
    cfg_body = "\n".join(
        f"<tr><td>{names[row['configuration']]}</td><td>{row['pass']}</td><td>{row['archived_pass']}</td><td>{row['tokens']}</td><td>{row['pass_per_1k_tokens']}</td></tr>"
        for row in cfg_rows
    )
    labels = {"GEN": "GEN generate", "MOD": "MOD modify", "QRY": "QRY query", "AMB": "AMB ambiguous", "RT": "RT round trip"}
    type_body = "\n".join(
        f"<tr><td>{labels[row['type']]}</td><td>{row['cells']}</td><td>{row['pass']}</td><td>{row['fail']}</td></tr>" for row in type_rows
    )
    oc_fail = [row for row in opencode if row["status"] != "PASS"]
    oc_lines = "; ".join(
        f"{row['task_id']} (syntax {row.get('sysml_status') or 'no package'}, engineering {row.get('engineering_status') or 'checklist not reached'})"
        for row in oc_fail
    )
    board = facts()
    jev = board["jev"]
    costs = board["costs"]
    prices = costs["prices"]
    price_line = "; ".join(
        f"{name} input ${p['input']}, cached ${p['cache']}, output ${p['output']} (international ${p['intl']['input']} / ${p['intl']['output']})"
        if p.get("intl") else f"{name} input ${p['input']}, output ${p['output']}"
        for name, p in prices["models"].items()
    )
    cost_body = "\n".join(
        f"<tr><td>{item['group']}</td><td>{item['label']}</td><td>{item['model']}</td><td>{item['input']:,}</td>"
        f"<td>{item.get('cached') or 0:,}</td><td>{item['output']:,}</td><td>${item['usd']:.4f}</td></tr>"
        for item in costs["items"]
    )
    no_question = fail_counts.get("no-question", 0)
    html = f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<title>Maritime SysML exam · saved results</title>
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
figcaption {{ font-size: 14px; color: #333; }}
footer {{ border-top: 1px solid #bbb; margin-top: 28px; padding-top: 16px; font-size: 14px; color: #444; }}
</style>
<main>
<h1>Maritime SysML exam</h1>
<p class="subtitle">Results from saved answers. Each cohort is listed on its own; there is no combined total.</p>
<p class="byline">Synthetic numbers, not RTX specifications. The official Pilot judges syntax. The answer key judges the required numbers and the power budget. A second model is compared and never changes a score.</p>

<h2>What can be said</h2>
<table>
<tr><th>Question</th><th>Saved result</th></tr>
<tr><td>Which of the main model's four approaches is worth the tokens?</td><td>qwen3.8-flash, 24 tasks × 4 approaches × 3 repeats = 288 cells. {' · '.join(f"{row['configuration']} passes {row['pass']}/72" for row in cfg_rows)}. {best['configuration']} has the most passes per thousand tokens. Repair (P1) does not beat one-shot (P0). P2 and P3 pass only 1 more cell than P0 and use about three times the tokens.</td></tr>
<tr><td>Can a failure be turned into a pass by changing a number?</td><td>Under the current scorer {totals['FAIL']} cells fail, {syntax_fail} of them on official syntax. Of the {parsed} GEN/MOD answers the Pilot could parse, none changed a value the task said to keep (including the limit); {unparsed} more never parsed or have no official run, so there is nothing to judge. MOD-05's design is over budget by construction (78 W against 60 W); all 12 cells kept the limit and every required value, so the current scorer passes them.</td></tr>
<tr><td>Are the off-the-shelf agents part of the main matrix?</td><td>No. OpenCode (qwen3.8-flash) has 24 cells and Claude Code with qwen3.8-max has 24 cells, listed separately. They cannot be added to the 288.</td></tr>
<tr><td>Can a second model replace the tool as judge?</td><td>No. qwen3.8-max read all 288 flash answers and agrees with the tool on 157/288. It calls 70 tool-failures a pass, including all 12 over-budget MOD-05 answers. Jev {jev['model']} agrees on {jev['agree']}/{jev['cells']} and false-passes {jev['false_pass']}, all of them generate-a-model answers that fail official syntax. No score is rewritten.</td></tr>
<tr><td>What did this cost?</td><td>At Alibaba Cloud's China (Beijing) list price, the four main-matrix approaches cost about ${sum(item['usd'] for item in costs['items'] if item['group_id'] == 'matrix'):.3f}; OpenCode's 24 tasks cost ${next(item['usd'] for item in costs['items'] if item['id'] == 'opencode'):.3f}. See section 6.</td></tr>
</table>

<h2>1. What was measured</h2>
<p>24 synthetic maritime tasks of five kinds: generate a model, modify a model, query a model, ask when information is missing, and restate a model in words. The answer key is used only for scoring and is not in the agent's prompt. Generate and modify answers first go through the official SysML v2 Pilot. After the syntax passes, the checklist checks required names, connections and values that must stay, and whether each engineering check comes out as the answer key expects. MOD-05's key says the power check should fail: the design verdict is FAIL, and an honest answer's task verdict is PASS.</p>
<p>The scoring rule changed once, on October 3. Under the old rule a task with a power check took the power result as its task result, and values to keep never counted: an honest MOD-05 answer was recorded as FAIL, while an answer that raised the limit to 80 W was recorded as PASS (checked with four hand-written answers through the official Pilot). Current rule: {RULE_EN} All 143 saved GEN/MOD answers were re-scored under the current rule into <code>analysis/rescore-20261003.jsonl</code>, with the archived and current verdicts side by side. Only MOD-05 answers changed.</p>
<p>A syntax pass is not engineering acceptance. A task with no power check has engineering status UNKNOWN, which only means the checklist has no power budget to compute.</p>

<h2>2. Main matrix: qwen3.8-flash</h2>
<p>288 cells: {totals['PASS']} pass, {totals['FAIL']} fail (archived scorer: {archived_totals['PASS']} pass, {archived_totals['FAIL']} fail). Sources are <code>analysis/heldout-20261003T000045/results.jsonl</code> (96 cells) and <code>analysis/heldout-20261003T001321/results.jsonl</code> (192 cells); GEN/MOD were re-scored from <code>analysis/rescore-20261003.jsonl</code>.</p>
<figure>
<img src="figures/flash_config.png" alt="Pass rate of the four approaches under the current and the archived scorer">
<figcaption>Figure 1. 72 cells per approach. Dark bars are the current scorer, light bars the archived scorer. The difference is MOD-05's 3 cells: the design is over budget, the limit is unchanged, and the current scorer counts that as a pass.</figcaption>
</figure>
<table>
<tr><th>Approach</th><th>Pass / 72</th><th>Archived pass / 72</th><th>Tokens</th><th>Passes per 1,000 tokens</th></tr>
{cfg_body}
</table>
<table>
<tr><th>Task type</th><th>Cells</th><th>Pass</th><th>Fail</th></tr>
{type_body}
</table>
<p>The next table is how many of the three repeats passed, per approach. MOD-05's 3/3 is the task verdict: the design is over budget, but the limit and every value to keep are unchanged.</p>
<table>
<tr><th>Task</th><th>P0</th><th>P1</th><th>P2</th><th>P3</th><th>Pass of 12</th></tr>
{task_body}
</table>

<h2>3. How the {totals['FAIL']} failures split</h2>
<p>Classes were read from the saved official diagnostics and answers; no model was called again. Detail is in <code>analysis/failure-classes.jsonl</code>.</p>
<table>
<tr><th>Class</th><th>Cells</th></tr>
{fail_body}
</table>
<p>{totals['FAIL']} cells missed the checklist. {syntax_fail} fail official syntax, {fail_counts['query-renamed']} use a name that is not written with <code>::</code>, and {fail_counts['query-wrong-number']} is QRY-03 answering 2 connections where the key says 3. The old class of 12 "designed power failures" passes under the current scorer and is not in the table.</p>
<p>The {no_question} no-question cells need a separate look: each one does ask for clarification, but as an imperative with no question mark (for example "Please clarify whether the uplink value is 8 (unitless) or 8 MHz."). None invents a number. The scorer treats a question as present only when the text contains "?". Whether to relax that is an answer-key change and waits for the second reviewer; they still count as failures.</p>

<h2>4. Two more cohorts, not added to the 288</h2>
<table>
<tr><th>Cohort</th><th>Model and entry</th><th>Result</th><th>File</th></tr>
<tr><td>OpenCode v1.18.27</td><td>qwen3.8-flash (the same model as the main matrix), command line, 24 tasks once each</td><td>{oc_pass} pass, {len(opencode) - oc_pass} fail. Failures: {oc_lines}. MOD-05 is over budget with the limit unchanged, so the current scorer passes it (the archived scorer failed it).</td><td>analysis/opencode-20261003T001321/results.jsonl</td></tr>
<tr><td>Claude Code, first run</td><td>qwen3.8-max, through the local Qwen route</td><td>{sum(row['status'] == 'PASS' for row in claude_first)} pass, {len(first_fail)} fail ({', '.join(first_fail) or 'none'}), {len(first_timeout)} not submitted ({', '.join(first_timeout) or 'none'}). A missing submission is not a failure. MOD-05 passes under the current scorer (it failed under the archived one).</td><td>analysis/claude-qwen-20261003T014507/results.jsonl</td></tr>
<tr><td>Claude Code, four tasks re-run</td><td>Same route, no time limit</td><td>{', '.join(f"{row['task_id']} {row['status']}" for row in claude_retry)}. Replacing the first run's failures with the re-run leaves this cohort at {claude_pass} pass and {len(claude) - claude_pass} fail.</td><td>analysis/claude-qwen-20261003T034819/results.jsonl</td></tr>
</table>
<p>An empty session named "RTRC maritime tasks" on the web UI has no messages and is not in this table. OpenCode's evidence is the 24 command-line answers above.</p>

<h2>5. A second model reads the 288 flash answers</h2>
<p>The judge is qwen3.8-max. It agrees on {sum(1 for row in judge if row.get('agree'))} of 288 cells and calls a failure a pass on {sum(1 for row in judge if row.get('false_pass'))}. The file is <code>analysis/validator-all-max.jsonl</code>. It does not change the pass counts in section 2. The question it was asked says an over-budget design fails, so it is compared with the tool's design verdict; only MOD-05 has a design verdict (FAIL) different from its task verdict (PASS).</p>
<p>The second judge is Jev {jev['model']} (TypeSafe), over the same 288. It agrees on {jev['agree']}, false-passes {jev['false_pass']} (all generate-a-model answers that fail official syntax) and false-fails {jev['false_fail']}. The file is <code>analysis/jev-heldout-20261003.json</code>. It is not scored either.</p>

<h2>6. What it cost</h2>
<p>Prices are Alibaba Cloud Model Studio list prices for China (Beijing), checked {prices['checked']}, USD per million tokens: {price_line}. Jev uses the price on its OpenRouter page. The endpoint we call is in the Beijing region, so that price is the main figure.</p>
<table>
<tr><th>Group</th><th>Item</th><th>Model</th><th>Input tokens</th><th>Of which cached</th><th>Output tokens</th><th>USD</th></tr>
{cost_body}
</table>
<p>Usage was not recorded, so these are not in the table: {' '.join(costs['unrecorded'])}</p>

<h2>7. Three saved records you can point at</h2>
<table>
<tr><th>Record</th><th>The task states</th><th>The agent submitted</th><th>Verdict</th></tr>
<tr><td>MOD-05, all 12 flash cells, plus OpenCode and Claude</td><td>Power limit 60, three draws 41, 25 and 12</td><td>Syntax passes, the numbers are still there, the limit is unchanged</td><td>Design verdict FAIL: 78 &gt; 60, as the answer key expects. Task verdict PASS.</td></tr>
<tr><td>MOD-01 replay</td><td>Add an infrared camera, keep the limit at 60</td><td>Official syntax passes</td><td>Checklist passes. The approval gate did not change 60. The read-back mentions infrared and 60. See analysis/demo-mod01.json.</td></tr>
<tr><td>Five graph-retrieval questions, a separate batch</td><td>The model is not given the whole model, only word-matched nodes and one hop of neighbours</td><td>qwen3.8-max</td><td>QRY-01, 02, 04 and 05 pass. QRY-03 answers 0 connections; the key says 3. See analysis/graph-query-max.json. This is not the paper's 0.904.</td></tr>
</table>

<h2>8. What these results cannot support</h2>
<table>
<tr><th>Not done</th><th>Sentence that cannot be written</th></tr>
<tr><td>A second person has not signed the 24 answer keys, and FREEZE.md is not written</td><td>The task bank is frozen.</td></tr>
<tr><td>No independent person has reviewed the diagrams</td><td>A tool pass means an engineer has accepted the design.</td></tr>
<tr><td>The Cameo enterprise assistant has no license; the community-edition installer is downloaded and not yet installed</td><td>We compared against the vendor's AI.</td></tr>
<tr><td>The free Syside editor is installed; batch checking on the command line still needs a paid license</td><td>A second checker has run all 288 cells.</td></tr>
<tr><td>The 151 SysMBench tasks have no licensed files</td><td>We compared against the public 151.</td></tr>
<tr><td>PURE is two excerpts (qwen3.8-max got both right; see analysis/pure-20261003T052120/)</td><td>Requirements extraction has been fully tested.</td></tr>
<tr><td>AMB counts a question only when the text has a question mark, so an imperative clarification fails; the second reviewer has not decided whether to relax that</td><td>Every AMB failure means the agent asked nothing.</td></tr>
</table>

<h2>9. Files</h2>
<table>
<tr><th>Content</th><th>Path</th></tr>
<tr><td>Numbers on this page</td><td>tables/flash_by_config.csv, flash_by_type.csv, flash_by_task.csv</td></tr>
<tr><td>Figure 1</td><td>figures/flash_config.png</td></tr>
<tr><td>Failure classes</td><td>docs/failure_taxonomy.md</td></tr>
<tr><td>Rebuild this page</td><td>python3 analysis/report/build_exam_report.py</td></tr>
</table>
<footer>This page only summarises results already on disk. A timeout is not a failure. Cohorts have different denominators and cannot be added together.</footer>
</main>
</html>
"""
    (OUT / "index.html").write_text(html, encoding="utf-8")
    print(OUT / "index.html")


if __name__ == "__main__":
    main()
