"""Numbers for the results page, STATUS.md and the report. Read saved files only. Do not invent a price.

The scored batches are defined in bench/batches.py: direct qwen3.8-flash and qwen3.8-max (27 tasks × P0-P3 × 3),
OpenCode and Claude Code on qwen3.8-flash in the sandbox (27 × 3). Model judges are not used (decision 025).
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from bench.batches import (ANALYSIS, ARCHIVE, COHORTS, CONFIGS, DISCARDED, RERUNS, ROOT, TYPES, batch_dir, discarded_rows,
                           rerun_dir, rerun_scope, rows, side_results, superseded_rows, usage_of_row)

EXPECTED = {"direct": 324, "agent": 81}


def graph_query_file() -> Path:
    """The newest graph-retrieval QRY batch. graph-query-max.json is the 2026-10-03 keyword run;
    bench/graph_query.py now writes graph-query-<stamp>.json with the retrieval settings recorded."""
    candidates = sorted(ANALYSIS.glob("graph-query-*.json"), key=lambda path: path.stat().st_mtime)
    return candidates[-1]


def _lines(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _opencode_trace() -> list[dict]:
    """Tool calls of the newest sandboxed OpenCode run on MOD-05."""
    folders = sorted(path for path in (ROOT / "mvp" / "agent-runs").glob("*-P-CODE-MOD-05") if (path / "stdout.jsonl").is_file())
    if not folders:
        return []
    steps = []
    for line in (folders[-1] / "stdout.jsonl").read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            part = json.loads(line).get("part") or {}
        except json.JSONDecodeError:
            continue
        if part.get("type") != "tool":
            continue
        state = part.get("state") if isinstance(part.get("state"), dict) else {}
        steps.append({"tool": part.get("tool") or "", "status": state.get("status") or "", "target": str(state.get("title") or "")[:160]})
    return steps


PRICES = {
    "checked": "2026-10-03",
    "region": "China (Beijing)",
    "region_note": "Our endpoint is in cn-beijing, so that region's list price is used; the international price is shown for comparison. Free quota and promotions are not applied.",
    "models": {
        "qwen3.8-flash": {"input": 0.113, "cache": 0.014, "output": 0.382, "intl": {"input": 0.15, "cache": 0.016, "output": 0.47},
                          "source": "https://www.alibabacloud.com/help/en/model-studio/qwen3-8-flash"},
        "qwen3.8-max": {"input": 1.65, "cache": 0.206, "output": 4.951, "intl": {"input": 2.0, "cache": 0.25, "output": 6.0},
                        "source": "https://www.alibabacloud.com/help/en/model-studio/qwen3-8-max"},
    },
}


def _usd(model: str, tokens: dict, intl: bool = False) -> float:
    price = PRICES["models"][model]
    if intl and price.get("intl"):
        price = price["intl"]
    fresh = max((tokens.get("input") or 0) - (tokens.get("cached") or 0), 0)
    return (fresh * price["input"] + (tokens.get("cached") or 0) * price["cache"] + (tokens.get("output") or 0) * price["output"]) / 1e6


def _sum_usage(items: list[dict]) -> dict:
    total = {"input": 0, "cached": 0, "output": 0, "calls": 0}
    for item in items:
        for key in total:
            total[key] += item.get(key) or 0
    return total


def _call_tokens(calls: list[dict]) -> dict:
    total = {"input": 0, "cached": 0, "output": 0, "calls": 0}
    for call in calls:
        usage = call.get("usage") or {}
        total["input"] += usage.get("prompt_tokens") or usage.get("input_tokens") or 0
        total["cached"] += (usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0
        total["output"] += usage.get("completion_tokens") or usage.get("output_tokens") or 0
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


def _summary(cohort: str, cells: list[dict]) -> dict:
    from bench.batches import ALL_COHORTS
    spec = ALL_COHORTS[cohort]
    by_type = {kind: {"n": 0, "pass": 0} for kind in TYPES}
    for row in cells:
        slot = by_type.setdefault(row["type"], {"n": 0, "pass": 0})
        slot["n"] += 1
        slot["pass"] += row["status"] == "PASS"
    groups: dict[tuple, set] = defaultdict(set)
    for row in cells:
        groups[(row["task_id"], row.get("configuration"))].add(row["status"])
    flip_keys = sorted(key for key, statuses in groups.items() if len(statuses) > 1)
    usage = _sum_usage([usage_of_row(row) for row in cells])
    folder, rerun = batch_dir(cohort), rerun_dir(cohort)
    return {
        "label": spec["label"], "short": spec["short"], "kind": spec["kind"], "model": spec["model"],
        "batch": folder.name if folder else None, "rerun_batch": rerun.name if rerun else None,
        "rerun_scope": rerun_scope(cohort), "n": len(cells), "expected": EXPECTED[spec["kind"]],
        "pass": sum(row["status"] == "PASS" for row in cells), "fail": sum(row["status"] != "PASS" for row in cells),
        "by_type": by_type, "usage": usage, "usd": round(_usd(spec["model"], usage), 4), "usd_intl": round(_usd(spec["model"], usage, intl=True), 4),
        "reliability": {"groups": len(groups), "flips": len(flip_keys), "flip_tasks": sorted({task for task, _config in flip_keys})},
        "fail_tasks": dict(Counter(row["task_id"] for row in cells if row["status"] != "PASS")),
        "errors": sum(1 for row in cells if row.get("error")),
    }


def _agent_stats(cells: list[dict]) -> dict:
    """Timeouts, runs that left no answer.md, and how often the agent ran ./validate (read from its workspace)."""
    stats = {"timeouts": 0, "no_answer": 0, "validate_calls": 0, "runs_validated": 0}
    for row in cells:
        stats["timeouts"] += str(row.get("returncode")) == "timeout"
        if not row.get("workspace"):
            stats["no_answer"] += 1
            continue
        workspace = Path(row["workspace"])
        stats["no_answer"] += not (workspace / "answer.md").is_file()
        calls = len(list((workspace / "validation").glob("*/result.json")))
        stats["validate_calls"] += calls
        stats["runs_validated"] += calls > 0
    return stats


def _rerun_spread(cohorts: dict) -> dict:
    """Cells of a rerun whose prompt was byte-identical to the replaced run, and how many changed verdict."""
    spread = {}
    for cohort, spec in RERUNS.items():
        if "inputs_changed" not in spec:
            continue
        old = {(row["task_id"], row.get("configuration"), int(row["repeat"])): row["status"] for row in superseded_rows(cohort)}
        new = {(row["task_id"], row.get("configuration"), int(row["repeat"])): row["status"] for row in cohorts[cohort]["_cells"]}
        same = [key for key in old if key in new and key[0] not in spec["inputs_changed"]]
        if same:
            spread[cohort] = {"cells": len(same), "changed": sum(old[key] != new[key] for key in same)}
    return spread


def _configs(cohort: str, cells: list[dict]) -> list[dict]:
    model = COHORTS[cohort]["model"]
    out = []
    for name in CONFIGS:
        part = [row for row in cells if row["configuration"] == name]
        sysml = [row for row in part if row["type"] in {"GEN", "MOD", "ALN"}]
        usage = _sum_usage([usage_of_row(row) for row in part])
        out.append({
            "id": name, "n": len(part), "pass": sum(row["status"] == "PASS" for row in part),
            "fail": sum(row["status"] != "PASS" for row in part),
            "tokens": usage["input"] + usage["output"], "usage": usage,
            "usd": round(_usd(model, usage), 5), "usd_intl": round(_usd(model, usage, intl=True), 5),
            "syntax_n": len(sysml),
            "syntax_first": sum(row.get("first_pass_attempt") == 1 for row in sysml),
            "syntax_final": sum(row.get("sysml_status") == "PASS" for row in sysml),
            "repairs": sum(int(row.get("repair_rounds") or 0) for row in sysml),
            "stops": dict(Counter(row.get("stop_reason") for row in sysml if row.get("sysml_status") != "PASS")),
            "unchanged_resubmits": sum(int(row.get("resubmitted_unchanged") or 0) for row in sysml),
        })
    return out


def _costs(cohorts: dict, side: dict) -> dict:
    items = []
    for cohort in ("flash", "max"):
        for config in cohorts[cohort]["configs"]:
            items.append({"id": f"{cohort}-{config['id']}", "group_id": "direct", "group": "Direct calls (81 cells per approach)",
                          "label": f"{config['id']} · {COHORTS[cohort]['model']}", "model": COHORTS[cohort]["model"], **config["usage"],
                          "passes": config["pass"], "cells": config["n"]})
    for cohort in ("opencode", "claude"):
        summary = cohorts[cohort]["summary"]
        if summary["n"]:
            items.append({"id": cohort, "group_id": "agent", "group": "Agents in the sandbox (81 runs each)",
                          "label": f"{summary['short']} ({summary['n']} runs)", "model": summary["model"], **summary["usage"],
                          "passes": summary["pass"], "cells": summary["n"]})
    for bench, label in (("sysengbench", "SysEngBench"), ("pure", "PURE")):
        for cohort, entry in side[bench].items():
            items.append({"id": f"{bench}-{cohort}", "group_id": "side", "group": "Side benchmarks",
                          "label": f"{label} · {COHORTS[cohort]['short']}", "model": entry["model"], **entry["usage"]})
    graph = json.loads(graph_query_file().read_text(encoding="utf-8"))
    items.append({"id": "graph", "group_id": "other", "group": "Other experiments", "label": f"Graph retrieval, query tasks ({len(graph)})",
                  "model": "qwen3.8-max", **_call_tokens([item for item in graph if item.get("usage")])})
    for agent, data in (_retry().get("agents") or {}).items():
        items.append({"id": f"retry-{agent}", "group_id": "other", "group": "Other experiments",
                      "label": f"Failed tasks retried · {data['label'].split(' · ')[0]} ({data['n']} runs)", "model": "qwen3.8-max",
                      **data["usage"], "passes": data["pass"], "cells": data["n"]})
    for key, spec in DISCARDED.items():
        found = discarded_rows(key)
        if found:
            items.append({"id": key, "group_id": "discarded", "group": "Discarded runs (spent, not counted)",
                          "label": f"{spec['label']} ({len(found)} runs)", "model": spec["model"],
                          **_sum_usage([usage_of_row(row) for row in found])})
    for cohort in RERUNS:
        found = superseded_rows(cohort)
        if found:
            items.append({"id": f"{cohort}-superseded", "group_id": "discarded", "group": "Discarded runs (spent, not counted)",
                          "label": f"{COHORTS[cohort]['short']}, {RERUNS[cohort]['label']} ({len(found)})",
                          "model": COHORTS[cohort]["model"], **_sum_usage([usage_of_row(row) for row in found])})
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
        label = ("One run (fully recorded)" if len(basis) == 1 else f"One run (average of {len(basis)} fully recorded)") if complete_runs \
            else f"One run (average of {len(basis)}, alignment and read-back missing)"
        items.append({"id": "part2", "group_id": "part2", "group": "Part 2 prototype", "label": label, "model": "qwen3.8-max", **average,
                      "complete": bool(complete_runs)})
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
        items.append({"id": "mod", "group_id": "mod", "group": "MOD change chain",
                      "label": "One run" if len(mod_runs) == 1 else f"One run (average of {len(mod_runs)})", "model": "qwen3.8-max", **average})
    for item in items:
        item["usd"] = round(_usd(item["model"], item), 6)
        item["usd_intl"] = round(_usd(item["model"], item, intl=True), 6)
    unrecorded = []
    if part2_partial:
        unrecorded.append(f"{part2_partial} Part 2 runs recorded only requirements, designs and trade-offs, not alignment and read-back; later runs record everything.")
    if mod_unlogged:
        unrecorded.append(f"{mod_unlogged} MOD change runs predate usage logging; later runs record everything.")
    silent = [row for row in rows("claude") + superseded_rows("claude")
              if str(row.get("returncode")) == "timeout" and not usage_of_row(row)["input"]]
    if silent:
        unrecorded.append(f"{len(silent)} Claude Code runs hit the 900 s limit before Claude Code reported its usage (it reports only when a run ends); "
                          "their tokens are not in these sums, so Claude Code's cost is a lower bound.")
    unrecorded.append("The paper 1 replication (4 calls, qwen3.8-max), the paper 2 replication (18 calls, qwen3.8-max) and the trial runs of "
                      "2026-10-06 are recorded in their own folders and not summed here.")
    counted = [item for item in items if item["group_id"] not in {"part2", "mod"}]
    return {"prices": PRICES, "items": items, "runs": runs, "mod_runs": mod_runs, "unrecorded": unrecorded,
            "missing": {"part2_partial": part2_partial, "mod_unlogged": mod_unlogged},
            "batch_usd": round(sum(item["usd"] for item in counted if item["group_id"] in {"direct", "agent", "side"}), 4),
            "recorded_usd": round(sum(item["usd"] for item in counted)
                                  + sum(_usd("qwen3.8-max", run) for run in runs)
                                  + sum(_usd("qwen3.8-max", run) for run in mod_runs), 4)}


def _knowledge() -> dict:
    """Where every prompt's context comes from, with sizes read from disk."""
    from bench.discover import CATALOG, load_memory
    from bench.graph_query import build_graph, maritime_parse
    from mvp.engine import exported_elements
    held = ROOT / "bench" / "tasks" / "t4_maritime_isr" / "heldout"
    index = [json.loads(line) for line in (held / "index.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    corpus = []
    for path in sorted((ROOT / "bench" / "corpus").glob("*.md")):
        chunks = [block for block in path.read_text(encoding="utf-8").split("\n\n") if block.strip()]
        corpus.append({"file": path.name, "chunks": len(chunks)})
    library = ANALYSIS / "vector-index" / "examples" / "manifest.json"
    examples = json.loads(library.read_text(encoding="utf-8")) if library.is_file() else {}
    parse = maritime_parse()
    cards, _neighbors, kinds = build_graph(parse, "MaritimeISR::")
    elements = exported_elements(json.loads((parse / "sysml" / "model.json").read_text(encoding="utf-8")))
    validation = json.loads((parse / "sysml" / "validation.json").read_text(encoding="utf-8"))
    memory = load_memory()
    return {
        "tasks": {"n": len(index), "types": dict(Counter(item["type"] for item in index)),
                  "gold": sum(1 for item in index if (ROOT / item["path"] / "gold").is_dir())},
        "corpus": corpus,
        "examples": {"cards": examples.get("cards"), "notes": examples.get("notes"),
                     "folders": sum(1 for item in examples.get("folders") or [] if item.get("status") == "PASS"),
                     "folders_total": len(examples.get("folders") or [])},
        "maritime": {"file": "scenario/maritime-isr/MaritimeISR.sysml", "parse_run": parse.name,
                     "elements": len(elements), "cards": len(cards), "links": len(kinds) // 2,
                     "library_files": validation.get("library_resource_count")},
        "memory": {"n": len(memory), "file": "analysis/memory/approved.jsonl",
                   "entries": [{"run_id": item["run_id"], "design": item["design"], "approved_at": item["approved_at"]} for item in memory]},
        "catalog": {"slots": len(CATALOG["slots"]), "options": sum(len(spec["options"]) for spec in CATALOG["slots"].values()),
                    "params": len(CATALOG["params"])},
    }


def _retry() -> dict:
    """The failed tasks retried with the agents on qwen3.8-max (decision 029), as summarized by bench/summarize_retry.py."""
    path = ANALYSIS / "retry-summary.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def facts() -> dict:
    cohorts = {}
    for cohort in COHORTS:
        cells = rows(cohort)
        entry = {"summary": _summary(cohort, cells)}
        if COHORTS[cohort]["kind"] == "direct":
            entry["configs"] = _configs(cohort, cells)
        else:
            entry["summary"]["agent"] = _agent_stats(cells)
        cohorts[cohort] = entry
        cohorts[cohort]["_cells"] = cells
    flash_cells = cohorts["flash"]["_cells"]
    side = side_results()
    hazards = (ROOT / "scenario" / "maritime-isr" / "hazards.sysml").read_text(encoding="utf-8")
    graph = {item["task_id"]: item for item in json.loads(graph_query_file().read_text(encoding="utf-8"))}
    mod05 = [row for row in flash_cells if row["task_id"] == "MOD-05"]
    opencode_mod05 = [row for row in cohorts["opencode"]["_cells"] if row["task_id"] == "MOD-05"]
    discarded = []
    for key, spec in DISCARDED.items():
        found = discarded_rows(key)
        discarded.append({"key": key, "label": spec["label"], "reason": spec["reason"], "dir": f"analysis/{spec['dir']}",
                          "n": len(found), "pass": sum(row["status"] == "PASS" for row in found)})
    superseded = []
    for cohort in RERUNS:
        found = superseded_rows(cohort)
        if found:
            superseded.append({"key": f"{cohort}-superseded", "cohort": cohort,
                               "who": COHORTS[cohort]["short"], "what": RERUNS[cohort]["label"],
                               "label": f"{COHORTS[cohort]['short']}, {RERUNS[cohort]['label']}",
                               "reason": RERUNS[cohort]["reason"], "dir": f"analysis/{batch_dir(cohort).name}",
                               "rerun_dir": f"analysis/{rerun_dir(cohort).name}",
                               "n": len(found), "pass": sum(row["status"] == "PASS" for row in found)})
    flash = cohorts["flash"]["summary"]
    out = {
        "freeze": {"tag": "freeze-2026-10-06-r2", "file": "bench/FREEZE.md", "tasks": sum(flash["by_type"][kind]["n"] for kind in TYPES) // 12 if flash["n"] else 27},
        "cohorts": {cohort: {**entry["summary"], **({"configs": entry["configs"]} if "configs" in entry else {})} for cohort, entry in cohorts.items()},
        "flash": {"n": flash["n"], "pass": flash["pass"], "fail": flash["fail"]},
        "by_type": flash["by_type"],
        "configs": cohorts["flash"]["configs"],
        "opencode": {**cohorts["opencode"]["summary"], "mod05": [row["status"] for row in opencode_mod05], "trace": _opencode_trace()},
        "claude": cohorts["claude"]["summary"],
        "side": side,
        "discarded": discarded,
        "superseded": superseded,
        "archive": ARCHIVE,
        "retry": _retry(),
        "knowledge": _knowledge(),
        "costs": _costs(cohorts | {cohort: {"summary": entry["summary"], **({"configs": entry["configs"]} if "configs" in entry else {})}
                                   for cohort, entry in cohorts.items()}, side),
        "reliability": {**flash["reliability"],
                        "mod05_pass": sum(row["status"] == "PASS" for row in mod05),
                        "mod05_fail": sum(row["status"] == "FAIL" for row in mod05),
                        "mod05_design_fail": sum(row.get("engineering_status") == "FAIL" for row in mod05),
                        "mod05_by_cohort": {cohort: {"n": len(cells), "honest": sum(row["status"] == "PASS" and row.get("engineering_status") == "FAIL" for row in cells)}
                                            for cohort, cells in ((c, [row for row in entry["_cells"] if row["task_id"] == "MOD-05"]) for c, entry in cohorts.items())},
                        "rerun_spread": _rerun_spread(cohorts)},
        "safety": {"kept": "LossOfSeparation" in hazards and "HazardTrackNotShared" in hazards, "file": "scenario/maritime-isr/hazards.sysml"},
        "graph": {task: {"status": item["status"], "answer": item["answer"]} for task, item in sorted(graph.items())},
        "rule": "A task passes when the official parse passes (GEN, MOD, ALN), every required name, connection or mapping is present, "
                "no number was invented, every value the task said to keep is unchanged, and every engineering check comes out as the key "
                "expects. Whether the design meets its budget is a separate design verdict (decision 019).",
        "langflow_cohorts": _langflow_cohorts(),
    }
    return out


def _langflow_cohorts() -> dict:
    """The Langflow exam columns (decision 035), kept apart from the frozen candidates: pass counts, tokens, USD and time per
    cohort; n is 0 for a cohort that has not been run yet."""
    from bench.batches import LANGFLOW_COHORTS
    out = {}
    for cohort, spec in LANGFLOW_COHORTS.items():
        cells = rows(cohort)
        summary = _summary(cohort, cells)
        seconds = [row.get("elapsed_s") for row in cells if isinstance(row.get("elapsed_s"), (int, float))]
        reported = sum(1 for row in cells if (row.get("usage") or {}).get("input"))
        out[cohort] = {**summary, "flow": spec["flow"], "project": spec["project"],
                       "seconds_total": round(sum(seconds), 1), "seconds_median": (sorted(seconds)[len(seconds) // 2] if seconds else None),
                       "usage_reported": reported, "tool_calls": sum(len(row.get("tool_calls") or []) for row in cells)}
    return out
