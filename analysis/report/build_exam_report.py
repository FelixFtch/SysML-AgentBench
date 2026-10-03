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
from bench.rescore import RULE, apply, load as load_rescore  # noqa: E402
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
        return f"{counter['PASS']} 通过，{counter['FAIL']} 失败"

    task_body = "\n".join(
        "<tr><td>{task_id}</td><td>{P0}</td><td>{P1}</td><td>{P2}</td><td>{P3}</td><td>{pass_of_12}/12</td></tr>".format(**row)
        for row in task_rows
    )
    fail_body = "\n".join(
        f"<tr><td>{name}</td><td>{count}</td></tr>" for name, count in fail_counts.most_common()
    )
    names = {"P0": "P0 直接写", "P1": "P1 按报错再改，最多 3 次", "P2": "P2 先列提纲再写", "P3": "P3 提纲加关键词笔记"}
    cfg_body = "\n".join(
        f"<tr><td>{names[row['configuration']]}</td><td>{row['pass']}</td><td>{row['archived_pass']}</td><td>{row['tokens']}</td><td>{row['pass_per_1k_tokens']}</td></tr>"
        for row in cfg_rows
    )
    labels = {"GEN": "GEN 写出", "MOD": "MOD 修改", "QRY": "QRY 读模型", "AMB": "AMB 缺信息", "RT": "RT 读回"}
    type_body = "\n".join(
        f"<tr><td>{labels[row['type']]}</td><td>{row['cells']}</td><td>{row['pass']}</td><td>{row['fail']}</td></tr>" for row in type_rows
    )
    oc_fail = [row for row in opencode if row["status"] != "PASS"]
    oc_lines = "；".join(
        f"{row['task_id']}（语法 {row.get('sysml_status') or '无包'}，工程 {row.get('engineering_status') or '未进入清单'}）"
        for row in oc_fail
    )
    board = facts()
    jev = board["jev"]
    costs = board["costs"]
    prices = costs["prices"]
    price_line = "；".join(
        f"{name} 输入 ${p['input']}、缓存读 ${p['cache']}、输出 ${p['output']}（国际区 ${p['intl']['input']} / ${p['intl']['output']}）"
        if p.get("intl") else f"{name} 输入 ${p['input']}、输出 ${p['output']}"
        for name, p in prices["models"].items()
    )
    cost_body = "\n".join(
        f"<tr><td>{item['group']}</td><td>{item['label']}</td><td>{item['model']}</td><td>{item['input']:,}</td>"
        f"<td>{item.get('cached') or 0:,}</td><td>{item['output']:,}</td><td>${item['usd']:.4f}</td></tr>"
        for item in costs["items"]
    )
    no_question = fail_counts.get("no-question", 0)
    html = f"""<!doctype html>
<html lang="zh-CN">
<meta charset="utf-8">
<title>海事 SysML 考试 · 已保存成绩</title>
<style>
body {{ margin: 0; background: #fff; color: #111; font: 17px/1.65 Georgia, "Noto Serif CJK SC", "Source Han Serif SC", serif; }}
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
<h1>海事 SysML 考试</h1>
<p class="subtitle">已保存答卷的成绩。各批分开计，不合成一个总分。</p>
<p class="byline">合成数字，不是 RTX 规格。官方 Pilot 判语法。清单判规定的数字和功率。第二个模型只作对照。</p>

<h2>能说什么</h2>
<table>
<tr><th>问题</th><th>已保存的结果</th></tr>
<tr><td>主力模型四种写法，哪一种更合算？</td><td>qwen3.8-flash，24 题 × 4 种 × 3 遍 = 288 格。{' · '.join(f"{row['configuration']} 通过 {row['pass']}/72" for row in cfg_rows)}。每千 token 的通过数 {best['configuration']} 最高。P1 返工没有超过 P0。P2、P3 只比 P0 多 1 格，token 大约是三倍。</td></tr>
<tr><td>失败是不是改个数字就能过？</td><td>按现行判分 {totals['FAIL']} 格失败，其中 {syntax_fail} 格死在官方语法。官方能解析的 {parsed} 份 GEN/MOD 答卷里，没有一份改过必须保留的数（包括上限）；另外 {unparsed} 份没有通过官方解析或没有官方运行记录，无从判断。MOD-05 的设计必然超预算（78 W 对 60 W）；12 格都没改上限、该保留的数都在，按现行判分算通过。</td></tr>
<tr><td>现成编程代理和主力矩阵是同一批吗？</td><td>不是。OpenCode（qwen3.8-flash）24 格、Claude Code 加 qwen3.8-max 24 格单独列表。不能和 288 格加总。</td></tr>
<tr><td>第二个模型能不能当裁判？</td><td>不能。qwen3.8-max 看完全部 288 份 flash 答卷，和工具一致 157/288。它把 70 份工具判失败的卷说成通过，其中 MOD-05 的 12 份超功率全部被说成通过。Jev {jev['model']} 一致 {jev['agree']}/{jev['cells']}，误判通过 {jev['false_pass']} 格，全是官方语法都过不了的写新模型题。分数不因此改写。</td></tr>
<tr><td>跑这些花了多少钱？</td><td>按阿里云中国（北京）区标价，主力矩阵四种写法合计约 ${sum(item['usd'] for item in costs['items'] if item['group'].startswith('主力矩阵')):.3f}；OpenCode 做 24 题 ${next(item['usd'] for item in costs['items'] if item['label'].startswith('OpenCode')):.3f}。见第 6 节。</td></tr>
</table>

<h2>1. 测的是什么</h2>
<p>24 道合成海事题，五种：写出模型、修改模型、读模型、缺信息时提问、把模型读回文字。标准答案在阅卷时使用，不放进考生提示。生成和修改题先过官方 SysML v2 Pilot。语法通过之后，清单核对规定的名字、连接、必须保留的数，以及检查结果是否和标准答案预期一致。MOD-05 的清单写明功率检查应为失败：设计判定是失败，但老实作答的题目判定是通过。</p>
<p>判分规则在 10 月 3 日改过一次。原规则下，有功率检查的题直接拿功率结果当题目结果，必须保留的数也不计入结果：MOD-05 老实作答被记为失败，把上限改成 80 W 的试卷反而记为通过（用四份手写试卷经官方 Pilot 验证过）。现行规则：{RULE} 已保存的 143 份 GEN/MOD 答卷都按现行规则重算，结果在 <code>analysis/rescore-20261003.jsonl</code>，原判和现判并列。只有 MOD-05 的答卷结果变了。</p>
<p>语法通过不是工程验收。没有功率检查的题，工程状态记为 UNKNOWN，只表示清单没有一项功率预算可算。</p>

<h2>2. 主力矩阵：qwen3.8-flash</h2>
<p>288 格：{totals['PASS']} 通过，{totals['FAIL']} 失败（原判 {archived_totals['PASS']} 通过，{archived_totals['FAIL']} 失败）。来源是 <code>analysis/heldout-20261003T000045/results.jsonl</code>（96 格）和 <code>analysis/heldout-20261003T001321/results.jsonl</code>（192 格），GEN/MOD 按 <code>analysis/rescore-20261003.jsonl</code> 重算。</p>
<figure>
<img src="figures/flash_config.png" alt="四种写法按现行判分和原判的通过率">
<figcaption>图 1. 每种写法 72 格。深色是现行判分，浅色是原判。差别只来自 MOD-05 的 3 格：设计超预算，上限没改，现行判分算通过。</figcaption>
</figure>
<table>
<tr><th>写法</th><th>通过 / 72</th><th>原判通过 / 72</th><th>token</th><th>每千 token 的通过数</th></tr>
{cfg_body}
</table>
<table>
<tr><th>题型</th><th>格数</th><th>通过</th><th>失败</th></tr>
{type_body}
</table>
<p>下表是每种写法三次里通过几次。MOD-05 的 3/3 是题目判定：设计超预算，但上限和该保留的数都没改。</p>
<table>
<tr><th>题</th><th>P0</th><th>P1</th><th>P2</th><th>P3</th><th>12 格中通过</th></tr>
{task_body}
</table>

<h2>3. {totals['FAIL']} 格失败怎么分</h2>
<p>分类读已保存的官方诊断和答卷，没有重新调用模型。明细在 <code>analysis/failure-classes.jsonl</code>。</p>
<table>
<tr><th>类别</th><th>格数</th></tr>
{fail_body}
</table>
<p>{totals['FAIL']} 格没有对上清单。其中 {syntax_fail} 格是官方语法，{fail_counts['query-renamed']} 格是合格名没写成 <code>::</code>，{fail_counts['query-wrong-number']} 格是 QRY-03 把连接数答成 2，标准答案是 3。原分类里的 12 格「设计好的功率失败」按现行判分已算通过，不在表里。</p>
<p>no-question 的 {no_question} 格要单独看：这几份答卷都用祈使句提出了澄清请求（例如 “Please clarify whether the uplink value is 8 (unitless) or 8 MHz.”），没有写数字，但没有问号；判分程序按文本里有没有 “?” 判断是否提问。要不要放宽属于答案清单的修改，等第二审核人决定，目前仍算失败。</p>

<h2>4. 另外两批考生，不并进 288</h2>
<table>
<tr><th>批次</th><th>模型与入口</th><th>结果</th><th>文件</th></tr>
<tr><td>OpenCode v1.18.27</td><td>qwen3.8-flash（和主力矩阵同一个模型），命令行，24 题各一次</td><td>{oc_pass} 通过，{len(opencode) - oc_pass} 失败。失败是 {oc_lines}。MOD-05 设计超预算、上限没改，现行判分算通过（原判失败）。</td><td>analysis/opencode-20261003T001321/results.jsonl</td></tr>
<tr><td>Claude Code，第一次</td><td>qwen3.8-max，经本机 Qwen 路由</td><td>{sum(row['status'] == 'PASS' for row in claude_first)} 通过，{len(first_fail)} 失败（{'、'.join(first_fail) or '无'}），{len(first_timeout)} 次没交卷（{'、'.join(first_timeout) or '无'}）。没交卷不计失败。MOD-05 现行判分算通过（原判失败）。</td><td>analysis/claude-qwen-20261003T014507/results.jsonl</td></tr>
<tr><td>Claude Code，四题重跑</td><td>同一路由，不设时限</td><td>{'、'.join(f"{row['task_id']} {row['status']}" for row in claude_retry)}。用重跑的行盖住第一次没通过的题之后，这一批是 {claude_pass} 通过、{len(claude) - claude_pass} 失败。</td><td>analysis/claude-qwen-20261003T034819/results.jsonl</td></tr>
</table>
<p>网页上的空会话「RTRC 海事题」没有消息，不在这张表里。OpenCode 的证据是上面这 24 次命令行答卷。</p>

<h2>5. 第二个模型看 288 份 flash 答卷</h2>
<p>裁判是 qwen3.8-max。288 格里一致 {sum(1 for row in judge if row.get('agree'))} 格，误把失败说成通过 {sum(1 for row in judge if row.get('false_pass'))} 格。文件是 <code>analysis/validator-all-max.jsonl</code>。它不改第 2 节的通过数。裁判的问法写明超预算算失败，所以和它比的是工具的设计判定；只有 MOD-05 的设计判定（失败）和题目判定（通过）不同。</p>
<p>第二个裁判是 Jev {jev['model']}（TypeSafe），同样看 288 份。一致 {jev['agree']} 格，误判通过 {jev['false_pass']} 格（全是写新模型题，官方语法都过不了），误判失败 {jev['false_fail']} 格。文件是 <code>analysis/jev-heldout-20261003.json</code>。也不计分。</p>

<h2>6. 花了多少钱</h2>
<p>单价按阿里云 Model Studio 中国（北京）区标价，{prices['checked']} 核对，每百万 token 美元：{price_line}。Jev 按 OpenRouter 页面的价格。本机调用的接口在北京区，所以主数字用北京区价。</p>
<table>
<tr><th>分组</th><th>项目</th><th>模型</th><th>输入 token</th><th>其中缓存读</th><th>输出 token</th><th>美元</th></tr>
{cost_body}
</table>
<p>没有记录用量、不在表里的：{' '.join(costs['unrecorded'])}</p>

<h2>7. 三条可以指着讲的旧记录</h2>
<table>
<tr><th>记录</th><th>题面里有的</th><th>考生交的</th><th>判定</th></tr>
<tr><td>MOD-05，flash 全部 12 格，以及 OpenCode、Claude</td><td>功率上限 60，三笔功耗 41、25、12</td><td>语法通过，数字还在，上限没改</td><td>设计判定失败：78 &gt; 60，和标准答案预期一致。题目判定通过。</td></tr>
<tr><td>MOD-01 回放</td><td>加上红外相机，上限保持 60</td><td>官方语法通过</td><td>清单通过。审批门没有人改 60。回读里有红外和 60。见 analysis/demo-mod01.json。</td></tr>
<tr><td>图检索五题，单独一批</td><td>不把整份模型交给模型，只给词匹配的节点和一跳邻居</td><td>qwen3.8-max</td><td>QRY-01、02、04、05 通过。QRY-03 答 0 条连接，标准答案是 3。见 analysis/graph-query-max.json。这不是论文里的 0.904。</td></tr>
</table>

<h2>8. 这份成绩还不能说的事</h2>
<table>
<tr><th>还没做</th><th>因此不能写的句子</th></tr>
<tr><td>第二个人还没有签 24 道标准答案，FREEZE.md 还没写</td><td>不能写题库已经冻结。</td></tr>
<tr><td>没有独立人工看图复核</td><td>不能把工具通过写成工程师已经接受该设计。</td></tr>
<tr><td>Cameo 企业助手没有许可；社区版安装包已下载，还没装好打开</td><td>不能写和厂商 AI 比过。</td></tr>
<tr><td>Syside 免费编辑器已安装；命令行批量检查仍要付费许可</td><td>不能写第二套检查器已经跑完 288 格。</td></tr>
<tr><td>151 道 SysMBench 还没有带许可证的文件</td><td>不能写和公开 151 题对照过。</td></tr>
<tr><td>PURE 只有两份摘录（qwen3.8-max 两题都对，见 analysis/pure-20261003T052120/）</td><td>不能写需求抽取已经测完。</td></tr>
<tr><td>AMB 的提问按问号判，祈使句的澄清请求算失败；第二审核人还没决定要不要放宽</td><td>不能把 AMB 的失败都写成“没有提问”。</td></tr>
</table>

<h2>9. 文件对照</h2>
<table>
<tr><th>内容</th><th>路径</th></tr>
<tr><td>本页数字</td><td>tables/flash_by_config.csv，flash_by_type.csv，flash_by_task.csv</td></tr>
<tr><td>图 1</td><td>figures/flash_config.png</td></tr>
<tr><td>失败分类说明</td><td>docs/failure_taxonomy.md</td></tr>
<tr><td>重算本页</td><td>python3 analysis/report/build_exam_report.py</td></tr>
</table>
<footer>本页只汇总已经落盘的成绩。超时不是失败。各批的分母不同，不能相加。</footer>
</main>
</html>
"""
    (OUT / "index.html").write_text(html, encoding="utf-8")
    print(OUT / "index.html")


if __name__ == "__main__":
    main()
