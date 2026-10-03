"""Numbers for the exam page. Read archived files only. Do not invent a price."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis"


def _rows(pattern: str) -> list[dict]:
    rows = []
    for path in sorted(ANALYSIS.glob(pattern)):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def fill_calls(rows: list[dict]) -> list[dict]:
    """Nine first-batch GEN rows have no calls in results.jsonl; their solve.json (same engine run) has them."""
    missing = {row.get("engine_run") for row in rows if not row.get("calls") and row.get("engine_run")}
    if not missing:
        return rows
    found = {}
    for path in (ROOT / "mvp" / "agent-runs").glob("*/solve.json"):
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("engine_run") in missing and record.get("calls"):
            found[record["engine_run"]] = record["calls"]
    return [row if row.get("calls") or row.get("engine_run") not in found else {**row, "calls": found[row["engine_run"]]}
            for row in rows]


def _tokens(rows: list[dict]) -> int:
    total = 0
    for row in rows:
        for call in row.get("calls") or []:
            total += (call.get("usage") or {}).get("total_tokens") or 0
    return total


def _opencode_trace() -> list[dict]:
    folders = sorted((ROOT / "mvp" / "agent-runs").glob("*-P-CODE-MOD-05"))
    if not folders:
        return []
    path = folders[-1] / "stdout.jsonl"
    if not path.is_file():
        return []
    steps = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        part = json.loads(line).get("part") or {}
        if part.get("type") != "tool":
            continue
        state = part.get("state") if isinstance(part.get("state"), dict) else {}
        target = state.get("title") or ""
        steps.append({
            "tool": part.get("tool") or "",
            "status": state.get("status") or "",
            "target": str(target)[:160],
        })
    return steps


def _sysengbench() -> dict:
    path = ANALYSIS / "sysengbench-jev.json"
    if not path.is_file():
        return {
            "status": "未打分",
            "reason": "题号已写在 analysis/sysengbench-ids.txt。打分结果文件还没有。",
            "n": 0,
            "correct": 0,
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        "status": "已打分",
        "reason": "选择题，单独计分，不并进 288 格。",
        "n": payload["n"],
        "correct": payload["correct"],
        "ids": payload["ids"],
    }


PRICES = {
    "checked": "2026-10-03",
    "region": "中国（北京）",
    "region_note": "我们的端点在 cn-beijing，按这一区的标价算；国际区价格只作对照。不含免费额度和促销。",
    "models": {
        "qwen3.8-flash": {"input": 0.113, "cache": 0.014, "output": 0.382, "intl": {"input": 0.15, "cache": 0.016, "output": 0.47},
                          "source": "https://www.alibabacloud.com/help/en/model-studio/qwen3-8-flash"},
        "qwen3.8-max": {"input": 1.65, "cache": 0.206, "output": 4.951, "intl": {"input": 2.0, "cache": 0.25, "output": 6.0},
                        "source": "https://www.alibabacloud.com/help/en/model-studio/qwen3-8-max"},
        "jev-1.13.0": {"input": 0.042, "cache": 0.042, "output": 0.0, "intl": None,
                       "source": "https://openrouter.ai/typesafe/jev-1.13"},
    },
}


def _usd(model: str, tokens: dict, intl: bool = False) -> float:
    price = PRICES["models"][model]
    if intl and price.get("intl"):
        price = price["intl"]
    fresh = max((tokens.get("input") or 0) - (tokens.get("cached") or 0), 0)
    return (fresh * price["input"] + (tokens.get("cached") or 0) * price["cache"] + (tokens.get("output") or 0) * price["output"]) / 1e6


def _call_tokens(calls: list[dict]) -> dict:
    total = {"input": 0, "cached": 0, "output": 0, "calls": 0}
    for call in calls:
        usage = call.get("usage") or {}
        total["input"] += usage.get("prompt_tokens") or usage.get("input_tokens") or 0
        total["cached"] += (usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0
        total["output"] += usage.get("completion_tokens") or usage.get("output_tokens") or 0
        total["calls"] += 1
    return total


def _opencode_tokens() -> dict:
    total = {"input": 0, "cached": 0, "output": 0, "calls": 0, "runs": 0}
    for folder in sorted((ROOT / "mvp" / "agent-runs").glob("*-P-CODE-*")):
        if not ("20261003T001321" <= folder.name[:15] < "20261003T014507"):
            continue
        log = folder / "stdout.jsonl"
        if not log.is_file():
            continue
        total["runs"] += 1
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
            if '"tokens"' not in line:
                continue
            tokens = (json.loads(line).get("part") or {}).get("tokens") or {}
            cache = tokens.get("cache") or {}
            total["input"] += (tokens.get("input") or 0) + (cache.get("read") or 0) + (cache.get("write") or 0)
            total["cached"] += cache.get("read") or 0
            total["output"] += (tokens.get("output") or 0) + (tokens.get("reasoning") or 0)
            total["calls"] += 1
    return total


def _run_tokens(record: dict) -> tuple[dict, bool]:
    """Tokens of one discovery or MOD record, and whether every model call in it was recorded."""
    if record.get("usage"):
        merged = {"input": 0, "cached": 0, "output": 0, "calls": 0}
        for slot in record["usage"]["by_model"].values():
            merged["input"] += slot["prompt_tokens"]
            merged["cached"] += slot["cached_tokens"]
            merged["output"] += slot["completion_tokens"]
            merged["calls"] += slot["calls"]
        return merged, True
    calls = [record.get("requirements") or {}] + list(record.get("designs") or []) + [record.get("tradeoffs") or {}]
    return _call_tokens([item for item in calls if item.get("usage")]), False


def _costs(flash: list[dict]) -> dict:
    items = []
    for name, label in (("P0", "P0 直接写"), ("P1", "P1 按报错返工"), ("P2", "P2 先列提纲"), ("P3", "P3 提纲 + 检索笔记")):
        rows = [row for row in flash if row["configuration"] == name]
        tokens = _call_tokens([call for row in rows for call in row.get("calls") or []])
        items.append({"group": "主力矩阵（72 格）", "label": label, "model": "qwen3.8-flash", **tokens,
                      "passes": sum(row["status"] == "PASS" for row in rows), "cells": len(rows),
                      "unrecorded": sum(1 for row in rows if not row.get("calls"))})
    opencode = _opencode_tokens()
    opencode_rows = _rows("opencode-20261003T001321/results.jsonl")
    items.append({"group": "现成 agent", "label": f"OpenCode（{opencode['runs']} 题）", "model": "qwen3.8-flash", **opencode,
                  "cells": len(opencode_rows)})
    jev = json.loads((ANALYSIS / "jev-heldout-20261003.json").read_text(encoding="utf-8"))["summary"]["usage"]
    items.append({"group": "裁判", "label": "Jev 判 288 格", "model": "jev-1.13.0",
                  "input": jev["input_tokens"], "cached": 0, "output": jev["output_tokens"], "calls": 36})
    graph = json.loads((ANALYSIS / "graph-query-max.json").read_text(encoding="utf-8"))
    items.append({"group": "其他实验", "label": f"图检索读模型（{len(graph)} 题）", "model": "qwen3.8-max",
                  **_call_tokens([item for item in graph if item.get("usage")])})
    sysengbench = json.loads((ANALYSIS / "sysengbench-jev.json").read_text(encoding="utf-8"))
    items.append({"group": "其他实验", "label": f"SysEngBench（{sysengbench['n']} 题）", "model": "jev-1.13.0",
                  "input": sysengbench["usage"]["input_tokens"], "cached": 0, "output": sysengbench["usage"]["output_tokens"], "calls": 1})
    runs = []
    for path in sorted(ANALYSIS.glob("discover-2026*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(record.get("designs"), list):
            continue
        tokens, complete = _run_tokens(record)
        if tokens["calls"]:
            runs.append({"id": record["id"], **tokens, "complete": complete})
    complete_runs = [run for run in runs if run["complete"]]
    basis = complete_runs or runs
    if basis:
        average = {key: round(sum(run[key] for run in basis) / len(basis)) for key in ("input", "cached", "output", "calls")}
        if complete_runs:
            label = "一次运行（整次记录）" if len(basis) == 1 else f"一次运行（整次记录的 {len(basis)} 次平均）"
        else:
            label = f"一次运行（{len(basis)} 次平均，缺对齐和读回）"
        items.append({"group": "第二部分", "label": label, "model": "qwen3.8-max", **average, "complete": bool(complete_runs)})
    mod_runs, mod_unlogged = [], 0
    for path in sorted(ANALYSIS.glob("mvp-case-*-MOD-*/case.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("usage"):
            mod_runs.append(_run_tokens(record)[0])
        else:
            mod_unlogged += 1
    part2_partial = sum(1 for run in runs if not run["complete"])
    if mod_runs:
        average = {key: round(sum(run[key] for run in mod_runs) / len(mod_runs)) for key in ("input", "cached", "output", "calls")}
        items.append({"group": "MOD 变更链", "label": "一次运行" if len(mod_runs) == 1 else f"一次运行（{len(mod_runs)} 次平均）",
                      "model": "qwen3.8-max", **average})
    for item in items:
        item["usd"] = round(_usd(item["model"], item), 6)
        item["usd_intl"] = round(_usd(item["model"], item, intl=True), 6)
    unrecorded = [
        "qwen3.8-max 当裁判看 288 份答卷：当时没有记录 token。",
        "Claude Code 两批共 28 次作答：经 CCR 路由，没有拿到用量。",
        "PURE 两题：没有记录 token。",
    ]
    if part2_partial:
        unrecorded.append(f"第二部分有 {part2_partial} 次运行只记了需求、设计和权衡，对齐和读回两步没有记；之后的运行整次都记。")
    if mod_unlogged:
        unrecorded.append(f"MOD 变更链有 {mod_unlogged} 次运行早于用量记录，没有记；之后的运行整次都记。")
    missing_cells = sum(item.get("unrecorded") or 0 for item in items)
    if missing_cells:
        unrecorded.insert(0, f"主力矩阵里有 {missing_cells} 格没有调用记录（第一批里没交卷或出错的格）。")
    return {"prices": PRICES, "items": items, "runs": runs, "mod_runs": mod_runs, "unrecorded": unrecorded,
            "missing": {"matrix_cells": missing_cells, "part2_partial": part2_partial, "mod_unlogged": mod_unlogged},
            "recorded_usd": round(sum(item["usd"] for item in items if item["group"] not in {"第二部分", "MOD 变更链"})
                                  + sum(_usd("qwen3.8-max", run) for run in runs)
                                  + sum(_usd("qwen3.8-max", run) for run in mod_runs), 4)}


def _knowledge() -> dict:
    """Where every prompt's context comes from, with sizes read from disk."""
    from bench.discover import CATALOG, MARITIME_PARSE, load_memory
    from bench.graph_query import build_graph
    from mvp.engine import exported_elements
    held = ROOT / "bench" / "tasks" / "t4_maritime_isr" / "heldout"
    index = [json.loads(line) for line in (held / "index.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    corpus = []
    for path in sorted((ROOT / "bench" / "corpus").glob("*.md")):
        chunks = [block for block in path.read_text(encoding="utf-8").split("\n\n") if block.strip()]
        corpus.append({"file": path.name, "chunks": len(chunks)})
    cards, _neighbors, kinds = build_graph(MARITIME_PARSE, "MaritimeISR::")
    elements = exported_elements(json.loads((MARITIME_PARSE / "sysml" / "model.json").read_text(encoding="utf-8")))
    validation = json.loads((MARITIME_PARSE / "sysml" / "validation.json").read_text(encoding="utf-8"))
    memory = load_memory()
    return {
        "tasks": {"n": len(index), "types": dict(Counter(item["type"] for item in index)),
                  "gold": sum(1 for item in index if (ROOT / item["path"] / "gold").is_dir())},
        "corpus": corpus,
        "maritime": {"file": "scenario/maritime-isr/MaritimeISR.sysml", "parse_run": MARITIME_PARSE.name,
                     "elements": len(elements), "cards": len(cards), "links": len(kinds) // 2,
                     "library_files": validation.get("library_resource_count")},
        "memory": {"n": len(memory), "file": "analysis/memory/approved.jsonl",
                   "entries": [{"run_id": item["run_id"], "design": item["design"], "approved_at": item["approved_at"]} for item in memory]},
        "catalog": {"slots": len(CATALOG["slots"]), "options": sum(len(spec["options"]) for spec in CATALOG["slots"].values()),
                    "params": len(CATALOG["params"])},
    }


def facts() -> dict:
    from bench.rescore import OUT as RESCORED, RULE, apply, load
    table = load()
    archived_flash = fill_calls(_rows("heldout-*/results.jsonl"))
    flash = [apply("flash", row, table) for row in archived_flash]
    type_pass: dict[str, dict] = {}
    for row in flash:
        slot = type_pass.setdefault(row.get("type") or row["task_id"].split("-")[0], {"n": 0, "pass": 0})
        slot["n"] += 1
        slot["pass"] += 1 if row["status"] == "PASS" else 0
    by_config = []
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in flash:
        grouped[row["configuration"]].append(row)
    for name in ("P0", "P1", "P2", "P3"):
        rows = grouped.get(name, [])
        counts = Counter(row["status"] for row in rows)
        by_config.append({
            "id": name,
            "pass": counts.get("PASS", 0),
            "fail": counts.get("FAIL", 0),
            "n": len(rows),
            "tokens": _tokens(rows),
        })
    opencode = [apply("opencode", row, table) for row in _rows("opencode-20261003T001321/results.jsonl")]
    first = [apply("claude1", row, table) for row in _rows("claude-qwen-20261003T014507/results.jsonl")]
    retry = {row["task_id"]: apply("claude2", row, table) for row in _rows("claude-qwen-20261003T034819/results.jsonl")}
    claude = []
    for row in first:
        if row["status"] != "PASS" and row["task_id"] in retry:
            claude.append(retry[row["task_id"]])
        else:
            claude.append(row)
    judge = _rows("validator-all-max.jsonl")
    judge_by_type: dict[str, dict] = {}
    for item in judge:
        kind = item["task_id"].split("-")[0]
        slot = judge_by_type.setdefault(kind, {"n": 0, "agree": 0, "false_pass": 0})
        slot["n"] += 1
        slot["agree"] += 1 if item.get("agree") else 0
        slot["false_pass"] += 1 if item.get("false_pass") else 0
    jev_path = ANALYSIS / "jev-heldout-20261003.json"
    if not jev_path.is_file():
        jev_path = ANALYSIS / "jev-mod05-20261003.json"
    jev = None
    if jev_path.is_file():
        payload = json.loads(jev_path.read_text(encoding="utf-8"))
        jev = payload["summary"]
        cells = payload.get("cells") or []
        jev["false_fail"] = sum(1 for item in cells if item.get("agree") is False and not item.get("false_pass"))
        jev["file"] = jev_path.name
        by_type: dict[str, dict] = {}
        for item in cells:
            kind = item["task_id"].split("-")[0]
            slot = by_type.setdefault(kind, {"n": 0, "agree": 0, "false_pass": 0, "false_fail": 0})
            slot["n"] += 1
            slot["agree"] += 1 if item.get("agree") else 0
            slot["false_pass"] += 1 if item.get("false_pass") else 0
            slot["false_fail"] += 1 if (item.get("agree") is False and not item.get("false_pass")) else 0
        jev["by_type"] = by_type
    graph = {item["task_id"]: item for item in json.loads((ANALYSIS / "graph-query-max.json").read_text(encoding="utf-8"))}
    flips = 0
    groups: dict[tuple, set] = defaultdict(set)
    for row in flash:
        groups[(row["task_id"], row["configuration"])].add(row["status"])
    flip_keys = sorted(key for key, statuses in groups.items() if len(statuses) > 1)
    flips = len(flip_keys)
    hazards = (ROOT / "scenario" / "maritime-isr" / "hazards.sysml").read_text(encoding="utf-8")
    pure = []
    for name in ("PURE-EIRENE", "PURE-PEERING"):
        path = ANALYSIS / "pure-20261003T052120" / f"{name}.json"
        if path.is_file():
            pure.append({"id": name, "status": json.loads(path.read_text(encoding="utf-8")).get("status")})
    flash_counts = Counter(row["status"] for row in flash)
    gen05 = [row for row in flash if row["task_id"] == "GEN-05"]
    qry01 = [row for row in flash if row["task_id"] == "QRY-01"]
    mod05 = [row for row in flash if row["task_id"] == "MOD-05"]
    return {
        "flash": {"n": len(flash), "pass": flash_counts.get("PASS", 0), "fail": flash_counts.get("FAIL", 0)},
        "by_type": type_pass,
        "knowledge": _knowledge(),
        "configs": by_config,
        "opencode": {
            "n": len(opencode),
            "pass": sum(row["status"] == "PASS" for row in opencode),
            "fail": sum(row["status"] != "PASS" for row in opencode),
            "mod05": next((row["status"] for row in opencode if row["task_id"] == "MOD-05"), ""),
            "trace": _opencode_trace(),
        },
        "claude": {
            "n": len(claude),
            "pass": sum(row["status"] == "PASS" for row in claude),
            "fail_tasks": [row["task_id"] for row in claude if row["status"] != "PASS"],
        },
        "judge": {
            "n": len(judge),
            "agree": sum(bool(row.get("agree")) for row in judge),
            "false_pass": sum(bool(row.get("false_pass")) for row in judge),
            "by_type": judge_by_type,
        },
        "jev": jev,
        "costs": _costs(flash),
        "pure": pure,
        "sysengbench": _sysengbench(),
        "reliability": {
            "groups": len(groups),
            "flips": flips,
            "flip_tasks": sorted({task for task, _config in flip_keys}),
            "mod05_fail": sum(row["status"] == "FAIL" for row in mod05),
            "mod05_pass": sum(row["status"] == "PASS" for row in mod05),
        },
        "interop": {
            "gen05_pass": sum(row["status"] == "PASS" for row in gen05),
            "gen05_n": len(gen05),
            "qry01_pass": sum(row["status"] == "PASS" for row in qry01),
            "qry01_n": len(qry01),
            "links": [
                "水面船无线电 → 指挥船",
                "无人机无线电 → 指挥船",
                "指挥船 → 岸",
            ],
        },
        "safety": {
            "kept": "LossOfSeparation" in hazards and "HazardTrackNotShared" in hazards,
            "file": "scenario/maritime-isr/hazards.sysml",
        },
        "graph": {task: {"status": item["status"], "answer": item["answer"]} for task, item in sorted(graph.items())},
        "rescore": {
            "file": f"analysis/{RESCORED.name}",
            "rule": RULE,
            "archived_flash_pass": sum(row["status"] == "PASS" for row in archived_flash),
            "changed": [{"cohort_id": item["cohort_id"], "task_id": item["task_id"], "configuration": item["configuration"],
                         "repeat": item["repeat"], "archived": item["archived_status"], "status": item["status"]}
                        for item in table.values() if item.get("changed")],
            "judge_basis": "两个裁判被问的是「答卷达不达标」，问法里写明超预算算不达标，所以和它们比的是工具的设计判定。只有 MOD-05 的设计判定（超预算 FAIL）和题目判定（老实作答 PASS）不同。",
        },
    }
