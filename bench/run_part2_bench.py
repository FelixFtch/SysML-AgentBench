"""Run the Part 2 design-flow benchmark (plans/part2-flow-benchmark.md §3-4) on a bank built by build_part2_bank.py.

Each task calls `bench.discover.run(brief, progress)` in-process (no shell route, no service restarts) and
is scored purely by code from the returned record, the same content saved as analysis/discover-<stamp>.json:

1. Requirements: every brief number appears in the requirements under an allowed attribute name;
   `requirements.unsourced` empty; PREVIEW adds "the uploadMbps requirement equals the brief's preview rate";
   MISSING-VALUE adds "a question mentions the missing quantity".
2. Designs: both designs parse (`sysml_status` PASS) and both TRACE rows PASS.
3. Checks: POWER/LINK/STORE/REQS/MISSION rows equal the bank's expected statuses (computed from budgets
   and the mission code; UNKNOWN is expected when a MISSING-VALUE brief no longer states a quantity).
4. Gate (scorer-v2, docs/decisions/038): gate.answer is "needs-person" exactly when the requirements carry
   unsourced numbers or an open value (missing_values); gate.eligible is exactly the designs whose every gated
   check (POWER/LINK/STORE/TRACE/SOURCE) passes. MISSING-VALUE done right = needs-person with an empty eligible
   list; a FEASIBLE brief whose design invents a number is blocked by SOURCE with an empty eligible list — the
   gate behaved correctly, the failure lands in the design verdict, not in item 4. Infeasible kinds must have an
   empty eligible list and a code-recomputed trade-off proposal.
5. Limits kept: no requirement power limit other than 60 W, no draw outside the brief's; no design attribute
   under the seven contract names carries a value other than the brief's (a removed quantity may not be
   stated at all). Attributes outside the contract are not judged.
6. Read-back (reported only): `designs[].read_back_numbers` all true.

Task verdict PASS = 1 and 2 and 3 and 4 and 5; the design verdict (that design's four gated checks) is kept
apart: an INFEASIBLE brief handled correctly is a task PASS with design FAIL.

    python3 bench/run_part2_bench.py --bank analysis/part2-bench-bank-<stamp>/bank.jsonl \
        --model qwen3.8-flash --limit 20 --workers 2
Writer matrix (§4): --writer {direct,opencode,claude-code,langflow} --flow <name> pass straight to
bench.discover.run's writer arguments (agent/model/flow); --tasks <file> runs a fixed task list (the
writer-matrix list analysis/part2-bench-writers/tasks-100.json, built once with --make-tasks and never
changed, so every writer sees the same briefs); --repeats runs the list N times; --max-calls stops
launching new runs when completed runs have spent that many model calls (budget guard).

    python3 bench/run_part2_bench.py --bank analysis/part2-bench-bank-<stamp>/bank.jsonl \
        --writer direct --model qwen3.8-max --tasks analysis/part2-bench-writers/tasks-100.json \
        --repeats 3 --workers 3 --max-runs 310 --max-calls 2900
Output: analysis/part2-bench-writers/<writer>-<model>-<stamp>/{results.jsonl,summary.json}
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PILOT_QUOTA = {"FEASIBLE": 5, "INFEASIBLE-POWER": 5, "INFEASIBLE-LINK": 4, "MISSING-VALUE": 3, "PREVIEW": 3}
QUESTION_KEYWORDS = {
    "powerLimitW": ["power limit", "power"],
    "storageGB": ["storage"],
    "retentionHours": ["hour", "retain", "keep"],
    "uplinkMbps": ["uplink", "link"],
    "dataRateMbps": ["record", "rate"],
    "uploadMbps": ["upload", "preview"],
    "drawW": ["draw", "watt", "power"],
}
CONTRACT_NAMES = ("powerLimitW", "drawW", "uplinkMbps", "uploadMbps", "dataRateMbps", "storageGB", "retentionHours")
STORAGE_NOTE = ("storage never fails in this catalogue (max 64.8 GB < smallest 128 GB); "
                "storage-failure detection untested")


def _fmt(value) -> str:
    return f"{float(value):g}"


def choice_values(task: dict) -> dict:
    """The brief's numbers by attribute name, from the choice via the catalogue."""
    from bench.discover import CATALOG
    ch = task["choice"]

    def slot(slot_name, field):
        return float(CATALOG["slots"][slot_name]["options"][ch[slot_name]][field])

    ir = slot("ir_camera", "drawW")
    values = {"powerLimitW": 60.0, "dataRateMbps": float(ch["dataRateMbps"]), "retentionHours": float(ch["retentionHours"]),
              "uploadMbps": float(ch["uploadMbps"]), "uplinkMbps": slot("uplink", "uplinkMbps"),
              "storageGB": slot("storage", "storageGB"),
              "drawW": sorted({slot("visible_camera", "drawW"), slot("computer", "drawW")} | ({ir} if ir else set()))}
    missing = task.get("missing")
    if missing:
        if missing["quantity"] == "drawW":
            values["drawW"] = [v for v in values["drawW"] if abs(v - float(missing["value"])) > 1e-9]
        else:
            values.pop(missing["quantity"], None)
    return values


def allowed_names(task: dict) -> dict[str, set[str]]:
    """Which attribute names a given brief number may sit under (§3.1)."""
    names: dict[str, set[str]] = {}
    for name, value in choice_values(task).items():
        for v in (value if isinstance(value, list) else [value]):
            names.setdefault(_fmt(v), set()).add(name)
    return names


def score_record(task: dict, record: dict) -> dict:
    from bench.discover import numbers_in
    brief_numbers = numbers_in(task["brief"])
    req = record.get("requirements") or {}
    requirements = req.get("requirements") or []
    kind = task["kind"]
    details: dict[str, dict] = {}

    # 1 Requirements
    stated: set[str] = set()
    for item in requirements:
        stated |= numbers_in(item.get("text", ""))
        quantity = item.get("quantity") or {}
        if quantity.get("value") is not None:
            stated.add(_fmt(quantity["value"]))
    uncovered = sorted(brief_numbers - stated)
    allowed = allowed_names(task)
    wrong_names = []
    for item in requirements:
        quantity = item.get("quantity") or {}
        if quantity.get("value") is None or not quantity.get("name"):
            continue
        token = _fmt(quantity["value"])
        if quantity["name"] not in allowed.get(token, set()):
            wrong_names.append(f"{item.get('id')}: {quantity['name']}={token}")
    sub = {"numbers_covered": not uncovered, "uncovered": uncovered,
           "unsourced_empty": not req.get("unsourced"), "unsourced": req.get("unsourced"),
           "attribute_names_ok": not wrong_names, "wrong_names": wrong_names}
    if kind == "PREVIEW":
        want = _fmt(task["choice"]["uploadMbps"])
        sub["preview_rate_requirement"] = any(
            (item.get("quantity") or {}).get("name") == "uploadMbps"
            and (item.get("quantity") or {}).get("value") is not None
            and _fmt(item["quantity"]["value"]) == want for item in requirements)
    if kind == "MISSING-VALUE":
        keywords = QUESTION_KEYWORDS.get(task["missing"]["quantity"], [])
        questions = req.get("questions") or []
        sub["question_for_missing"] = any(
            any(word in question.lower() for word in keywords) for question in questions)
        sub["questions"] = questions
    item1 = (sub["numbers_covered"] and sub["unsourced_empty"] and sub["attribute_names_ok"]
             and sub.get("preview_rate_requirement", True) and sub.get("question_for_missing", True))
    details["1_requirements"] = {"pass": item1, **sub}

    # 2 Designs
    designs = record.get("designs") or []
    two = len(designs) == 2

    def rows(design):
        return {check.get("id"): check.get("status") for check in design.get("checks") or []}

    syntax_ok = two and all(d.get("sysml_status") == "PASS" for d in designs)
    trace_ok = syntax_ok and all(rows(d).get("TRACE") == "PASS" for d in designs)
    details["2_designs"] = {"pass": bool(two and syntax_ok and trace_ok), "two_designs": two,
                            "both_parse": syntax_ok, "both_trace": trace_ok,
                            "gated": {d.get("key"): {k: rows(d).get(k) for k in
                                        ("POWER", "LINK", "STORE", "TRACE", "SOURCE")} for d in designs}}
    item2 = bool(two and syntax_ok and trace_ok)

    # 3 Checks
    want = task["expected"]["check_statuses"]
    problems = []
    if not two:
        problems.append("the record does not hold two designs")
    for design in designs:
        if design.get("sysml_status") != "PASS":
            problems.append(f"design {design.get('key')}: parse failed, checks not computed")
            continue
        got = rows(design)
        for key in ("POWER", "LINK", "STORE", "REQS", "MISSION"):
            if got.get(key) != want[key]:
                problems.append(f"design {design['key']} {key}: got {got.get(key)}, expected {want[key]}")
    details["3_checks"] = {"pass": not problems, "problems": problems, "expected": want}
    item3 = not problems

    # 4 Gate (scorer-v2, decision 038): needs-person exactly when the requirements carry unsourced numbers or an
    # open value; eligible exactly the designs whose every gated check (POWER/LINK/STORE/TRACE/SOURCE) passes.
    # A FEASIBLE brief whose design invents a number is blocked by SOURCE with an empty eligible list: the gate
    # behaved correctly, the task fails elsewhere (design verdict), not here.
    from bench.discover import GATED_CHECKS, open_values
    gate = record.get("gate") or {}
    answer, eligible = gate.get("answer"), gate.get("eligible") or []
    problems = []
    open_now = bool(req.get("unsourced")) or bool(open_values(req))
    expected_answer = "needs-person" if open_now else "awaiting-person"
    if answer != expected_answer:
        problems.append(f"gate.answer={answer}, expected {expected_answer} "
                        f"({'unsourced numbers' if req.get('unsourced') else 'open values' if open_values(req) else 'no open value'})")
    expected_eligible = [] if open_now else [d["key"] for d in designs if d.get("sysml_status") == "PASS" and all(
        {c.get("id"): c.get("status") for c in d.get("checks") or []}.get(k) == "PASS" for k in GATED_CHECKS)]
    if sorted(eligible) != sorted(expected_eligible):
        problems.append(f"gate.eligible={eligible}, the record's own gated checks give {expected_eligible}")
    if kind == "MISSING-VALUE" and answer != "needs-person":
        problems.append(f"the flow proceeded ({answer}) on a brief with an open value instead of asking")
    if kind in {"INFEASIBLE-POWER", "INFEASIBLE-LINK"} and eligible:
        problems.append(f"gate.eligible={eligible} on a {kind} brief")
    if kind in {"INFEASIBLE-POWER", "INFEASIBLE-LINK"}:
        proposals = (record.get("tradeoffs") or {}).get("proposals") or []
        if not any(item.get("budgets") for item in proposals):
            problems.append("no trade-off proposal recomputed by code")
    details["4_gate"] = {"pass": not problems, "problems": problems, "answer": answer, "eligible": eligible,
                         "expected_answer": expected_answer, "expected_eligible": expected_eligible,
                         "open_values": open_values(req)}
    item4 = not problems

    # 5 Limits kept
    values = choice_values(task)
    allowed_values = {name: (set(map(float, value)) if isinstance(value, list) else {float(value)})
                      for name, value in values.items() if value}
    problems = []
    for item in requirements:
        quantity = item.get("quantity") or {}
        name, value = quantity.get("name"), quantity.get("value")
        if value is None:
            continue
        if name == "powerLimitW" and abs(float(value) - 60.0) > 1e-9:
            problems.append(f"requirement {item.get('id')} states powerLimitW={_fmt(value)}")
        if name == "drawW" and not any(abs(float(value) - v) < 1e-9 for v in values.get("drawW", [])):
            problems.append(f"requirement {item.get('id')} states drawW={_fmt(value)}")
    for design in designs:
        if design.get("sysml_status") != "PASS":
            continue
        for qualified, value in (design.get("numbers") or {}).items():
            suffix = qualified.rsplit("::", 1)[-1]
            if suffix not in CONTRACT_NAMES:
                continue  # attributes outside the seven-name contract are reported, not judged
            permitted = allowed_values.get(suffix, set())
            if not any(abs(float(value) - v) < 1e-9 for v in permitted):
                state = "states a removed quantity" if suffix not in allowed_values else f"changes {suffix}"
                problems.append(f"design {design['key']} {qualified}={_fmt(value)} ({state})")
    details["5_limits"] = {"pass": not problems, "problems": problems}
    item5 = not problems

    # 6 Read-back, reported only
    readback = []
    for design in designs:
        got = design.get("read_back_numbers")
        readback.append({"design": design.get("key"), "evaluable": got is not None,
                         "all_true": (all(got.values()) if got is not None else None),
                         "false_numbers": sorted([k for k, v in (got or {}).items() if not v])})
    details["6_readback"] = {"pass": all(r["evaluable"] and r["all_true"] for r in readback) if readback else False,
                             "rows": readback}

    design_pass = {}
    for design in designs:
        if design.get("sysml_status") != "PASS":
            design_pass[design.get("key")] = False
            continue
        got = rows(design)
        design_pass[design["key"]] = all(got.get(k) == "PASS" for k in GATED_CHECKS)  # POWER/LINK/STORE/TRACE/SOURCE (038)
    return {"items": details, "task_pass": bool(item1 and item2 and item3 and item4 and item5),
            "design_pass": design_pass, "gate_answer": answer, "brief_numbers": sorted(brief_numbers, key=float)}


def mock_record(task: dict, *, invent: str | None = None, gate_wrong: bool = False,
                no_tradeoffs: bool = False, preview_rate_wrong: bool = False,
                mv_no_ask: bool = False, foreign_number: bool = False) -> dict:
    """A faithful-or-mutated record built from the bank row's ideal values; used to self-check the scorer."""
    values = choice_values(task)
    requirements, questions = [], []
    for name, value in values.items():
        for v in (value if isinstance(value, list) else [value]):
            requirements.append({"id": f"R{len(requirements) + 1}", "text": f"{name} is {_fmt(v)}",
                                 "quantity": {"name": name, "value": v, "unit": ""}})
    if task["kind"] == "MISSING-VALUE":
        quantity = task["missing"]["quantity"]
        questions = [f"What is the {'power limit' if quantity == 'powerLimitW' else quantity} for this vessel?"]
    if invent:
        requirements.append({"id": "R9", "text": f"invented {invent}", "quantity": {"name": invent, "value": 99.0}})
    if preview_rate_wrong:
        for item in requirements:
            if (item["quantity"] or {}).get("name") == "uploadMbps":
                item["quantity"]["value"] = float(task["choice"]["dataRateMbps"])
    numbers, checks = {}, []
    for name, value in values.items():
        for i, v in enumerate(value if isinstance(value, list) else [value]):
            numbers[f"M::usv::{'dev%d' % i if name == 'drawW' else name}::{name}"] = float(v)
    if invent:
        numbers[f"M::usv::{invent}::{invent}"] = 99.0
    if foreign_number:  # a literal under a non-contract name: only SOURCE sees it (scorer-v2 selfcheck)
        numbers["M::usv::marginW::marginW"] = 50.0
    want = dict(task["expected"]["check_statuses"])
    checks = ([{"id": key, "status": status} for key, status in want.items()]
              + [{"id": "TRACE", "status": "PASS"},
                 {"id": "SOURCE", "status": "FAIL" if foreign_number else "PASS"}])  # 038 gated rows
    designs = [{"key": key, "sysml_status": "PASS", "checks": checks, "numbers": numbers,
                "read_back_numbers": {n: True for n in sorted(
                    {f"{float(v):g}" for vals in values.values() for v in (vals if isinstance(vals, list) else [vals])}, key=float)}}
               for key in ("A", "B")]
    unsourced = [{"id": "R9", "numbers": ["99"]}] if invent else []
    missing_values = ([{"quantity": task["missing"]["quantity"], "question": questions[0]}]
                      if task["kind"] == "MISSING-VALUE" and not invent and not mv_no_ask else [])
    open_now = bool(unsourced) or bool(missing_values)
    if open_now:
        gate = {"answer": "needs-person", "eligible": []}
    else:
        eligible = ["A", "B"] if all(c["status"] == "PASS" for c in checks if c["id"] in
                                     ("POWER", "LINK", "STORE", "TRACE", "SOURCE")) else []
        gate = {"answer": "awaiting-person", "eligible": eligible}
    if gate_wrong:
        gate = {"answer": "awaiting-person", "eligible": ["A"]}
    proposals = [] if no_tradeoffs else [{"title": "lower draw", "choice": {}, "budgets": {"power": {"status": "PASS"}}}]
    return {"requirements": {"requirements": requirements, "questions": questions, "unsourced": unsourced,
                             "missing_values": missing_values},
            "designs": designs, "gate": gate, "tradeoffs": {"proposals": proposals}}


def scorer_selfcheck(tasks: list[dict]) -> list[dict]:
    """Score mock records with known verdicts; any miss is a scorer bug and aborts the run."""
    by_kind = {row["kind"]: row for row in tasks}
    cases = []
    for kind in ("FEASIBLE", "PREVIEW"):
        if kind in by_kind:
            cases.append((f"{kind} faithful", by_kind[kind], {}, True))
            if kind == "PREVIEW":
                cases.append(("PREVIEW recording rate as uploadMbps", by_kind[kind], {"preview_rate_wrong": True}, False))
    if "INFEASIBLE-POWER" in by_kind:
        cases.append(("INFEASIBLE-POWER faithful (task PASS, design FAIL)", by_kind["INFEASIBLE-POWER"], {}, True))
        cases.append(("INFEASIBLE-POWER gate lets a design through", by_kind["INFEASIBLE-POWER"], {"gate_wrong": True}, False))
        cases.append(("INFEASIBLE-POWER no recomputed trade-off", by_kind["INFEASIBLE-POWER"], {"no_tradeoffs": True}, False))
    if "MISSING-VALUE" in by_kind:
        cases.append(("MISSING-VALUE faithful", by_kind["MISSING-VALUE"], {}, True))
        cases.append(("MISSING-VALUE invented number", by_kind["MISSING-VALUE"], {"invent": by_kind["MISSING-VALUE"]["missing"]["quantity"]}, False))
        cases.append(("MISSING-VALUE flow did not ask (gate answers awaiting-person)",
                      by_kind["MISSING-VALUE"], {"mv_no_ask": True}, False))
    if "FEASIBLE" in by_kind:
        cases.append(("FEASIBLE invented power limit", by_kind["FEASIBLE"], {"invent": "powerLimitW"}, False))
        cases.append(("FEASIBLE design number outside the brief, SOURCE blocks (gate behaviour correct)",
                      by_kind["FEASIBLE"], {"foreign_number": True}, True))
    out = []
    for name, task, mutate, expected in cases:
        scored = score_record(task, mock_record(task, **mutate))
        out.append({"case": name, "task": task["id"], "expected_task_pass": expected,
                    "got_task_pass": scored["task_pass"],
                    "failed_items": [k for k, v in scored["items"].items() if not v["pass"]],
                    "ok": scored["task_pass"] == expected})
    return out


def select_tasks(rows: list[dict], limit: int, seed: int, ids: list[str] | None) -> list[dict]:
    if ids:
        by_id = {row["id"]: row for row in rows}
        missing = [i for i in ids if i not in by_id]
        if missing:
            raise SystemExit(f"unknown task ids: {missing}")
        return [by_id[i] for i in ids]
    if limit >= len(rows):
        return rows
    rng = random.Random(seed)
    quota_total = sum(PILOT_QUOTA.values())
    quotas = {kind: max(1, round(n * limit / quota_total)) for kind, n in PILOT_QUOTA.items()}
    while sum(quotas.values()) > limit:
        largest = max(quotas, key=quotas.get)
        quotas[largest] -= 1
    while sum(quotas.values()) < limit:
        smallest = min(quotas, key=quotas.get)
        quotas[smallest] += 1
    picked: list[dict] = []
    for kind, n in quotas.items():
        pool = sorted((row for row in rows if row["kind"] == kind), key=lambda r: r["id"])
        if kind == "MISSING-VALUE":  # prefer three different removed quantities
            groups: dict[str, list[dict]] = {}
            for row in pool:
                groups.setdefault(f"{row['missing']['quantity']}:{row['missing'].get('role')}", []).append(row)
            keys = sorted(groups)
            rng.shuffle(keys)
            order, index = [], 0
            while len(order) < min(n, len(pool)):
                key = keys[index % len(keys)]
                if groups[key]:
                    order.append(groups[key].pop(0))  # one task per removed quantity, then repeat
                index += 1
            picked.extend(order[:n])
        else:
            picked.extend(rng.sample(pool, min(n, len(pool))))
    return picked[:limit] if len(picked) > limit else picked


def proportional_quotas(counts: dict[str, int], n: int) -> dict[str, int]:
    """Largest-remainder quotas proportional to the bank's kind counts (ties: bigger pool, then name)."""
    total = sum(counts.values())
    exact = {kind: n * c / total for kind, c in counts.items()}
    quotas = {kind: int(v) for kind, v in exact.items()}
    order = sorted(counts, key=lambda k: (-(exact[k] - quotas[k]), -counts[k], k))
    i = 0
    while sum(quotas.values()) < n:
        quotas[order[i % len(order)]] += 1
        i += 1
    return quotas


TASK_KEYS = ("id", "kind", "brief", "choice", "missing", "expected")

SCORER_V2_NOTE = ("v2 (docs/decisions/038: needs-person iff unsourced numbers or open values; "
                  "eligible iff every gated check POWER/LINK/STORE/TRACE/SOURCE passes; a SOURCE block "
                  "on a FEASIBLE brief counts as correct gate behaviour)")


def compose_summary(results: list[dict], *, cfg: dict, n_tasks: int, task_runs: int, elapsed_s,
                    selfcheck: list[dict], smoke: dict | None, runs_used: int, calls_used: int) -> dict:
    """The summary over a list of result rows (fresh run, resume segment or the folded whole batch)."""
    model_arg = str(cfg.get("model_arg"))
    kinds = sorted({row["kind"] for row in results})
    matrix = {}
    for kind in kinds:
        rows_k = [r for r in results if r["kind"] == kind and "error" not in r]
        matrix[kind] = {
            "run": len([r for r in results if r["kind"] == kind]), "scored": len(rows_k),
            "task_pass": sum(1 for r in rows_k if r["task_pass"]),
            **{f"item{i}": sum(1 for r in rows_k if r["items"][key]["pass"])
               for i, key in enumerate(("1_requirements", "2_designs", "3_checks", "4_gate", "5_limits"), 1)},
            "readback_all_true": sum(1 for r in rows_k if all(
                x["evaluable"] and x["all_true"] for x in r["items"]["6_readback"]["rows"])),
            "any_design_pass": sum(1 for r in rows_k if any(r["design_pass"].values())),
            "gate_answers": sorted({r["gate_answer"] for r in rows_k}),
            "source_fail_designs": sum(1 for r in rows_k for g in r["items"]["2_designs"]["gated"].values()
                                       if g.get("SOURCE") == "FAIL"),
            "runs_source_blocked_eligible_empty": sum(
                1 for r in rows_k if kind in {"FEASIBLE", "PREVIEW"} and not r["items"]["4_gate"]["eligible"]
                and any(g.get("SOURCE") == "FAIL" for g in r["items"]["2_designs"]["gated"].values())),
        }
    failures = [{"task_id": r["task_id"], "kind": r["kind"],
                 "failed_items": [{"item": k, **{k2: v2 for k2, v2 in v.items() if k2 in ("problems", "uncovered", "wrong_names", "unsourced", "false_numbers", "answer", "eligible", "expected")}}
                                  for k, v in r["items"].items() if not v["pass"]]}
                for r in results if "error" not in r and not r["task_pass"]]
    usage_rows = [r["usage"] for r in results if r.get("usage")]
    totals = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cached_tokens": 0}
    for u in usage_rows:
        totals["calls"] += u.get("calls") or 0
        for slot in u.get("by_model", {}).values():
            totals["prompt_tokens"] += slot.get("prompt_tokens", 0)
            totals["completion_tokens"] += slot.get("completion_tokens", 0)
            totals["cached_tokens"] += slot.get("cached_tokens", 0)
    n_ok = len(usage_rows)
    per_run = {k: round(v / n_ok, 1) for k, v in totals.items()} if n_ok else totals
    designs_flat = [d for r in results if "design_outcomes" in r for d in r["design_outcomes"].values()]
    repairs_hist: dict[int, int] = {}
    for r in results:
        if "design_outcomes" not in r:
            continue
        total_repairs = sum(d["repairs"] or 0 for d in r["design_outcomes"].values())
        repairs_hist[total_repairs] = repairs_hist.get(total_repairs, 0) + 1
    repair_stats = {
        "runs_with_designs": sum(1 for r in results if "design_outcomes" in r),
        "histogram_repairs_per_run": {str(k): repairs_hist[k] for k in sorted(repairs_hist)},
        "designs": len(designs_flat),
        "designs_parse_pass": sum(1 for d in designs_flat if d["sysml"] == "PASS"),
        "designs_parse_fail": sum(1 for d in designs_flat if d["sysml"] != "PASS"),
        "designs_zero_repair": sum(1 for d in designs_flat if not d["repairs"]),
        "designs_at_cap_20": sum(1 for d in designs_flat if (d["repairs"] or 0) >= 20),
        "mean_repairs_per_design": round(sum(d["repairs"] or 0 for d in designs_flat) / max(len(designs_flat), 1), 2),
        "identical_resubmissions": sum(d["identical"] for d in designs_flat),
        "note": "repair_rounds per design; identical = attempts byte-identical to the previous submission",
    }
    cost = {"measured": totals, "per_run": per_run, "elapsed_s": elapsed_s}
    if isinstance(elapsed_s, (int, float)) and n_ok:
        slot_cost = elapsed_s * float(cfg.get("workers") or 1) / n_ok
        cost["extrapolation"] = {
            "1152x1": {"runs": 1152, "est_hours_at_workers": round(1152 * slot_cost / 3600, 1),
                       "est_tokens": {k: round(per_run[k] * 1152) for k in ("prompt_tokens", "completion_tokens")},
                       "est_cost_usd_plan_estimate": round(1152 * 0.01, 2)},
            "200x3": {"runs": 600, "est_hours_at_workers": round(600 * slot_cost / 3600, 1),
                      "est_tokens": {k: round(per_run[k] * 600) for k in ("prompt_tokens", "completion_tokens")},
                      "est_cost_usd_plan_estimate": round(600 * 0.01, 2)},
            "note": "hours from the measured per-run compute seconds at this worker count; dollars are the "
                    "plan's own 'about one cent' flash estimate (plan §4), not a measured price"}
    return {
        "config": {"scorer": SCORER_V2_NOTE, **cfg},
        "smoke_test": smoke,
        "models_seen": sorted({m for r in results for m in r.get("models", [])}),
        "model_mismatch": sorted({m for r in results for m in r.get("models", []) if model_arg not in str(m)}),
        "runs_used": runs_used, "calls_used": calls_used,
        "tasks": n_tasks, "task_runs": task_runs, "elapsed_s": elapsed_s,
        "matrix_by_kind": matrix,
        "repair_rounds": repair_stats,
        "totals": {"task_pass": sum(1 for r in results if r.get("task_pass")),
                   "scored": sum(1 for r in results if "error" not in r),
                   "errors": sum(1 for r in results if "error" in r)},
        "failures": failures,
        "scorer_selfcheck": selfcheck,
        "storage_limitation": STORAGE_NOTE,
        "cost": cost,
        "scoring_notes": [
            "kind priority: INFEASIBLE-POWER > INFEASIBLE-LINK > PREVIEW > FEASIBLE; 144 of 1152 choices fail both "
            "power and link and count as INFEASIBLE-POWER (bank selfcheck.json holds the overlap)",
            STORAGE_NOTE,
            "scorer-v2 item 4 (docs/decisions/038): needs-person exactly on unsourced numbers or open values "
            "(missing_values); eligible exactly the designs passing POWER/LINK/STORE/TRACE/SOURCE; MISSING-VALUE "
            "done right is needs-person with empty eligible; a SOURCE block on FEASIBLE/PREVIEW is correct gate "
            "behaviour (counted in runs_source_blocked_eligible_empty, design verdict carries the failure)",
            "item 5 judges only the seven contract attribute names; other design attributes are not judged",
            "item 6 (read-back) is reported, not part of the task verdict",
            "task verdict and design verdict are separate: an INFEASIBLE brief handled correctly is a task PASS with "
            "design FAIL",
        ],
    }


def _read_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _row_files(out: Path) -> list[Path]:
    """results.jsonl first, then unfrozen shard files in numeric order (.folded shards are already merged)."""
    files = [out / "results.jsonl"]
    files += sorted((p for p in out.glob("results.shard*.jsonl") if not p.name.endswith(".folded")),
                    key=lambda p: int(p.stem.split("shard")[1]))
    return [p for p in files if p.is_file()]


def load_done_rows(out: Path) -> tuple[list[dict], dict]:
    """Every row already on disk (main file + live shards) and the budget high-water mark over them."""
    rows: list[dict] = []
    for path in _row_files(out):
        rows.extend(_read_rows(path))
    budget = {"used": max((r.get("budget_used") or 0) for r in rows) if rows else 0,
              "calls": max((r.get("calls_used") or 0) for r in rows) if rows else 0}
    return rows, budget


def summarize_only(out: Path) -> None:
    """Fold shard files into results.jsonl (dedupe on task_id+repeat, the main file wins) and rebuild summary.json."""
    if not (out / "run_config.json").is_file():
        raise SystemExit(f"{out} holds no run_config.json; summarize needs a directory this script created")
    cfg_args = json.loads((out / "run_config.json").read_text(encoding="utf-8"))
    selected = json.loads((out / "selected.json").read_text(encoding="utf-8"))
    all_rows: list[dict] = []
    for path in _row_files(out):
        all_rows.extend(_read_rows(path))
    merged: list[dict] = []
    seen: set[tuple] = set()
    for row in all_rows:
        key = (row.get("task_id"), row.get("repeat"))
        if key in seen:
            continue
        seen.add(key)
        merged.append(row)
    (out / "results.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in merged), encoding="utf-8")
    for path in out.glob("results.shard*.jsonl"):
        if not path.name.endswith(".folded"):
            path.rename(path.with_suffix(".jsonl.folded"))
    tasks_file = cfg_args.get("tasks")
    tasks_sha = None
    if tasks_file:
        import hashlib
        tasks_sha = hashlib.sha256(Path(tasks_file).read_bytes()).hexdigest()
    cfg = {"writer": cfg_args.get("writer"), "flow": cfg_args.get("flow"), "model_arg": cfg_args.get("model"),
           "bank": cfg_args.get("bank"), "tasks_file": tasks_file, "tasks_sha256": tasks_sha,
           "repeats": cfg_args.get("repeats"), "limit": cfg_args.get("limit"),
           "workers": cfg_args.get("workers"), "seed": cfg_args.get("seed"),
           "max_runs": cfg_args.get("max_runs"), "max_calls": cfg_args.get("max_calls"), "ids": cfg_args.get("ids"),
           "started": str(out.name).rsplit("-", 1)[-1],
           "finished": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S"),
           "shard": "folded", "resumed": (json.loads((out / "summary.json").read_text(encoding="utf-8"))
                                          .get("config", {}).get("resumed", []))
           if (out / "summary.json").is_file() else []}
    n_tasks = len(selected.get("tasks") or [])
    task_runs = n_tasks * int(cfg_args.get("repeats") or 1)
    selfcheck = scorer_selfcheck(load_tasks_file(Path(tasks_file), []) if tasks_file else [])
    summary = compose_summary(merged, cfg=cfg, n_tasks=n_tasks, task_runs=task_runs,
                              elapsed_s="n/a (folded segments)", selfcheck=selfcheck, smoke=None,
                              runs_used=max((r.get("budget_used") or 0) for r in merged) if merged else 0,
                              calls_used=max((r.get("calls_used") or 0) for r in merged) if merged else 0)
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"out": str(out), "folded_rows": len(merged), "totals": summary["totals"],
                      "matrix": summary["matrix_by_kind"]}, indent=2), flush=True)


def make_tasks(rows: list[dict], n: int, seed: int, path: Path) -> dict:
    """Build the frozen writer-matrix task list: stratified by kind, proportional, seeded once.
    The written file is the only task source for every writer stage; it is not regenerated."""
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["kind"]] = counts.get(row["kind"], 0) + 1
    quotas = proportional_quotas(counts, n)
    rng = random.Random(seed)
    picked: list[dict] = []
    for kind in sorted(quotas):
        pool = sorted((row for row in rows if row["kind"] == kind), key=lambda r: r["id"])
        take = min(quotas[kind], len(pool))
        if kind == "MISSING-VALUE":  # spread over the removed quantities, like select_tasks
            groups: dict[str, list[dict]] = {}
            for row in pool:
                groups.setdefault(f"{row['missing']['quantity']}:{row['missing'].get('role')}", []).append(row)
            keys = sorted(groups)
            rng.shuffle(keys)
            order, index = [], 0
            while len(order) < take:
                key = keys[index % len(keys)]
                if groups[key]:
                    order.append(groups[key].pop(0))
                index += 1
            picked.extend(order)
        else:
            picked.extend(rng.sample(pool, take))
    picked.sort(key=lambda r: r["id"])
    bad = [row.get("id") for row in picked if any(key not in row for key in TASK_KEYS)]
    if bad or len(picked) != n:
        raise SystemExit(f"task list build failed: bad={bad} picked={len(picked)} want={n}")
    payload = {"seed": seed, "bank_rows": len(rows), "kind_counts_bank": counts, "quotas": quotas,
               "stratified_by": "kind, proportional largest-remainder; MISSING-VALUE spread over removed quantities",
               "created": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S"),
               "note": "Frozen writer-matrix task list (plans/part2-flow-benchmark.md §4). Used unchanged by every "
                       "writer stage; do not regenerate with another seed or bank.",
               "tasks": picked}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return payload


def load_tasks_file(path: Path, rows: list[dict]) -> list[dict]:
    """--tasks: {"tasks": [...]} or a bare list; entries are full bank rows or ids resolved against --bank."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    entries = doc["tasks"] if isinstance(doc, dict) else doc
    by_id = {row["id"]: row for row in rows}
    tasks: list[dict] = []
    for entry in entries:
        if isinstance(entry, str):
            if entry not in by_id:
                raise SystemExit(f"--tasks holds id {entry} which is not in --bank; give full rows or the bank")
            tasks.append(by_id[entry])
        else:
            tasks.append(entry)
    bad = [t.get("id") for t in tasks if any(key not in t for key in TASK_KEYS)]
    if bad:
        raise SystemExit(f"--tasks rows missing bank fields (id/kind/brief/choice/missing/expected): {bad}")
    return tasks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bank", default=None, help="bank.jsonl; required unless --tasks holds full rows")
    parser.add_argument("--model", default="qwen3.8-flash")
    parser.add_argument("--writer", choices=("direct", "opencode", "claude-code", "langflow"), default="direct",
                        help="design writer passed to bench.discover.run(agent=...)")
    parser.add_argument("--flow", default=None, help="Langflow flow name, passed through (langflow writer only)")
    parser.add_argument("--tasks", default=None, help="fixed task-list JSON (writer-matrix list); overrides sampling")
    parser.add_argument("--repeats", type=int, default=1, help="run the task list this many times")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--seed", type=int, default=20261010)
    parser.add_argument("--max-runs", type=int, default=25, help="budget: full flow runs, retries included")
    parser.add_argument("--max-calls", type=int, default=100000,
                        help="budget: total model calls over completed runs; no new run starts at or above it")
    parser.add_argument("--ids", nargs="*", default=None, help="run specific bank ids instead of a sample")
    parser.add_argument("--make-tasks", nargs=2, metavar=("N", "PATH"), default=None,
                        help="build the frozen stratified task list of N tasks and exit (no model calls)")
    parser.add_argument("--no-smoke", action="store_true", help="skip the one-call endpoint smoke test")
    parser.add_argument("--resume", default=None, metavar="DIR",
                        help="continue an existing output directory: rows that hold a verdict are kept, everything "
                             "else runs again; the budget counters continue from the kept rows")
    parser.add_argument("--shard", default=None, metavar="I/N",
                        help="run only slice I of N of the remaining tasks (multi-process resume; rows go to "
                             "results.shard<I>.jsonl so processes never share a file; fold with --summarize-only)")
    parser.add_argument("--summarize-only", default=None, metavar="DIR",
                        help="fold results.shard*.jsonl into results.jsonl (dedup on task_id+repeat) and rebuild "
                             "summary.json over all rows; no model runs")
    args = parser.parse_args()
    rows: list[dict] = []
    if args.bank:
        rows = [json.loads(line) for line in Path(args.bank).read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.make_tasks:
        if not rows:
            raise SystemExit("--make-tasks needs --bank")
        count, path = int(args.make_tasks[0]), Path(args.make_tasks[1])
        payload = make_tasks(rows, count, args.seed, path)
        print(json.dumps({"out": str(path), "quotas": payload["quotas"], "tasks": count}, indent=2))
        return
    if args.shard:
        try:
            shard_i, shard_n = (int(x) for x in args.shard.split("/"))
            if not (0 <= shard_i < shard_n):
                raise ValueError
        except ValueError:
            raise SystemExit("--shard wants I/N with 0 <= I < N, for example 0/2")
        if not args.resume:
            raise SystemExit("--shard resumes an existing directory; give --resume DIR too")
    else:
        shard_i = shard_n = None
    if args.summarize_only:
        summarize_only(Path(args.summarize_only))
        return
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    os.environ["MVP_LLM_MODEL"] = args.model  # before any chat call; beats .env via setdefault
    from bench.discover import run as discover_run
    from bench.experiment import load_env
    load_env()

    if args.tasks:
        if args.ids:
            raise SystemExit("--tasks and --ids are mutually exclusive")
        tasks = load_tasks_file(Path(args.tasks), rows)
    else:
        if not rows:
            raise SystemExit("give --bank or --tasks")
        tasks = select_tasks(rows, args.limit, args.seed, args.ids)
    tasks_sha = None
    if args.tasks:
        import hashlib
        tasks_sha = hashlib.sha256(Path(args.tasks).read_bytes()).hexdigest()
    if args.resume:
        out = Path(args.resume)
        if not (out / "selected.json").is_file():
            raise SystemExit(f"{out} holds no selected.json; not a bench output directory")
        if not out.name.startswith(f"{args.writer}-{args.model}-"):
            raise SystemExit(f"{out.name} is not a {args.writer}/{args.model} directory")
        kept = json.loads((out / "selected.json").read_text(encoding="utf-8"))
        if kept.get("tasks") != [t["id"] for t in tasks]:
            raise SystemExit("the resumed directory was built from a different task list")
        if int(kept.get("repeats") or 0) != args.repeats:
            raise SystemExit("the resumed directory was built with a different --repeats")
    else:
        out = ROOT / "analysis" / "part2-bench-writers" / f"{args.writer}-{args.model}-{stamp}"
        out.mkdir(parents=True)
        (out / "selected.json").write_text(json.dumps(
            {"tasks": [t["id"] for t in tasks], "repeats": args.repeats, "tasks_file": args.tasks,
             "tasks_sha256": tasks_sha, "quota": "frozen --tasks list" if args.tasks
             else (PILOT_QUOTA if not args.ids else "explicit ids")}, indent=2), encoding="utf-8")
    selfcheck = scorer_selfcheck(tasks)
    if not all(case["ok"] for case in selfcheck):
        (out / ("summary.aborted.json" if args.resume else "summary.json")).write_text(
            json.dumps({"scorer_selfcheck": selfcheck, "aborted": True}, indent=2), encoding="utf-8")
        raise SystemExit("scorer self-check failed; no model runs spent")
    smoke = None
    if not args.no_smoke:
        from agents.llm import chat
        reply = chat([{"role": "user", "content": "Reply with the single word: ready"}], max_tokens=8)
        smoke = {"model": reply.get("model"), "finish_reason": reply.get("finish_reason")}

    write_lock, start_lock = threading.Lock(), threading.Lock()
    last_start = [0.0]
    budget = {"used": 0, "calls": 0}
    results: list[dict] = []
    rows_path = out / (f"results.shard{shard_i}.jsonl" if shard_i is not None else "results.jsonl")
    if args.resume:
        kept_rows, kept_budget = load_done_rows(out)
        results.extend(kept_rows)
        budget["used"] = kept_budget["used"]
        budget["calls"] = kept_budget["calls"]
        if not args.shard:  # a plain resume appends to the shared file; shards keep their own
            rows_path = out / "results.jsonl"
        else:  # shard processes share the endpoint; give each an equal slice of the remaining budget
            args.max_runs = budget["used"] + max(10, (args.max_runs - budget["used"] + shard_n - 1) // shard_n)
            args.max_calls = budget["calls"] + max(60, (args.max_calls - budget["calls"] + shard_n - 1) // shard_n)
    if not args.resume:
        (out / "run_config.json").write_text(json.dumps(
            {k: v for k, v in vars(args).items() if k not in ("resume", "shard", "summarize_only")},
            indent=2, default=str), encoding="utf-8")
    elif not (out / "run_config.json").is_file():  # directory created before run_config existed
        (out / "run_config.json").write_text(json.dumps(
            {k: v for k, v in vars(args).items() if k not in ("resume", "shard", "summarize_only")},
            indent=2, default=str), encoding="utf-8")

    def add_calls(record: dict) -> None:
        with write_lock:
            budget["calls"] += (record.get("usage") or {}).get("calls") or 0

    def one(task: dict, repeat: int) -> dict:
        attempts = 0
        row = {"task_id": task["id"], "kind": task["kind"], "choice": task["choice"], "missing": task["missing"],
               "repeat": repeat}
        while (budget["used"] < args.max_runs and budget["calls"] < args.max_calls and attempts < 3):
            with start_lock:  # runs begin >=1.1 s apart: discover stamps are second-resolution
                wait = 1.1 - (time.time() - last_start[0])
                if wait > 0:
                    time.sleep(wait)
                last_start[0] = time.time()
            budget["used"] += 1
            attempts += 1
            started = time.time()
            try:
                record = discover_run(task["brief"], lambda *a: None,
                                      agent=args.writer, model=args.model, flow=args.flow,
                                      record_dir=out / "records", latest=False)
                scored = score_record(task, record)
                designs_meta = {d["key"]: {"sysml": d["sysml_status"], "repairs": d.get("repair_rounds"),
                                           "attempts": len(d.get("attempts") or []),
                                           "identical": sum(1 for a in d.get("attempts") or [] if a.get("same_as_previous"))}
                                for d in record.get("designs") or []}
                row = {"task_id": task["id"], "kind": task["kind"], "choice": task["choice"],
                       "missing": task["missing"], "repeat": repeat,
                       "writer": {"agent": args.writer, "model": (record.get("writer") or {}).get("model"),
                                  "flow": args.flow},
                       "run_id": record.get("id"), "run_file": record.get("file"),
                       "wall_s": round(time.time() - started, 1), "attempts": attempts,
                       "usage": record.get("usage"), "models": sorted({
                           (record.get("requirements") or {}).get("model"),
                           *((d.get("model") for d in record.get("designs") or []))} - {None}),
                       "design_outcomes": designs_meta, **scored}
                add_calls(record)
                break
            except Exception as exc:  # infrastructure or flow crash: retry while budget remains
                row = {"task_id": task["id"], "kind": task["kind"], "choice": task["choice"], "missing": task["missing"],
                       "repeat": repeat,
                       "error": f"{type(exc).__name__}: {exc}", "trace": traceback.format_exc()[-1500:],
                       "attempts": attempts, "wall_s": round(time.time() - started, 1)}
        if "task_pass" not in row and "error" not in row:
            row["error"] = (f"budget exhausted before this task (runs {budget['used']}/{args.max_runs}, "
                            f"calls {budget['calls']}/{args.max_calls})")
        row["budget_used"] = budget["used"]
        row["calls_used"] = budget["calls"]
        with write_lock:
            results.append(row)
            with rows_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        verdict = row.get("task_pass")
        print(f"{task['id']}#{repeat} {task['kind']} attempt {attempts} "
              f"{'task ' + ('PASS' if verdict else 'FAIL') if verdict is not None else 'ERROR ' + str(row.get('error'))[:60]}",
              flush=True)
        return row

    todo = [(task, repeat) for repeat in range(1, args.repeats + 1) for task in tasks]
    if args.resume:
        done = {(row["task_id"], row["repeat"]) for row in results if "task_pass" in row}
        todo = [pair for pair in todo if (pair[0]["id"], pair[1]) not in done]
        print(f"resume {out}: {len(done)} rows kept, {len(todo)} task-runs to go", flush=True)
    if shard_i is not None:
        todo = todo[shard_i::shard_n]
        print(f"shard {shard_i}/{shard_n}: {len(todo)} task-runs in this slice", flush=True)
    total_start = time.time()
    if args.workers <= 1:
        for task, repeat in todo:
            if budget["used"] >= args.max_runs or budget["calls"] >= args.max_calls:
                break
            one(task, repeat)
    else:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            list(pool.map(lambda pair: one(*pair), todo))
    elapsed = time.time() - total_start

    kinds = sorted({row["kind"] for row in results})
    cfg = {"scorer": SCORER_V2_NOTE, "writer": args.writer, "flow": args.flow, "model_arg": args.model,
           "bank": args.bank, "tasks_file": args.tasks, "tasks_sha256": tasks_sha, "repeats": args.repeats,
           "limit": args.limit, "workers": args.workers, "seed": args.seed,
           "max_runs": args.max_runs, "max_calls": args.max_calls, "ids": args.ids,
           "started": stamp, "finished": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S"),
           "shard": args.shard,
           "in_process": "bench.discover.run(), no shell route, no service restarted; run records go to "
                         "<out>/records (record_dir, latest=False), so analysis/discover-*.json and "
                         "discover-latest.json keep holding only the page's real runs"}
    summary = compose_summary(results, cfg=cfg, n_tasks=len(tasks), task_runs=len(todo),
                              elapsed_s=round(elapsed, 1), selfcheck=selfcheck, smoke=smoke,
                              runs_used=budget["used"], calls_used=budget["calls"])
    summary_path = out / (f"summary.shard{shard_i}.json" if shard_i is not None else "summary.json")
    if args.resume:
        prior = []
        try:  # keep the resume history of the segment that came before
            if summary_path.is_file():
                prior = json.loads(summary_path.read_text(encoding="utf-8")).get("config", {}).get("resumed", [])
        except Exception:
            prior = []
        summary["config"]["resumed"] = prior + [stamp]
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"out": str(out), "summary": summary_path.name, "totals": summary["totals"],
                      "matrix": summary["matrix_by_kind"], "repair_rounds": summary["repair_rounds"],
                      "calls_used": budget["calls"]}, indent=2), flush=True)


if __name__ == "__main__":
    main()
