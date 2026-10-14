"""Build the Part 2 design-flow task bank from the parts catalogue (plans/part2-flow-benchmark.md §1-2).

Every row is one catalogue choice: the brief text (`bench.discover.brief_from`), the expected outcome
(`bench.discover.budgets`, code arithmetic, never a model, never typed by hand), and a kind. Kinds are
classified with a fixed priority, POWER before LINK, because a choice can fail both:

- INFEASIBLE-POWER: budgets.power FAILS (link may fail too; the overlap count is reported)
- INFEASIBLE-LINK: budgets.power passes, budgets.link FAILS
- PREVIEW: every budget passes and the upload is a preview (upload < recording rate)
- FEASIBLE: every budget passes, upload at or above the recording rate

MISSING-VALUE rows are derived tasks: a FEASIBLE-kind choice with exactly one brief number removed by a
phrase replacement (the removed quantity and value are recorded in the row). ADAPT is not built.

Expected POWER/LINK/STORE/REQS/MISSION statuses are computed here so the runner only scores. The static
statuses mirror `bench.discover.simulate` (including UNKNOWN when the post-removal brief no longer states
a quantity a check needs); REQS and MISSION come from `bench.simulate_design.consistency` / `integrate`
over the ideal values, with the status formula copied from `mission_checks`. A seeded sample of rows is
cross-checked against the real `simulate()` (OpenModelica included) and any mismatch aborts the build.

    python3 bench/build_part2_bank.py                # analysis/part2-bench-bank-<stamp>/{bank.jsonl,selfcheck.json}
"""
from __future__ import annotations

import argparse
import itertools
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bench.discover import CATALOG, NUMBER, budgets, brief_from  # noqa: E402

SEED = 20261010
SLOTS = ("visible_camera", "ir_camera", "computer", "uplink", "storage")
PARAMS = ("dataRateMbps", "retentionHours", "uploadMbps")
# Plan §1 arithmetic, used only by the self-check against the plan's own numbers.
PLAN_COUNTS = {"feasible": 432, "power_fail": 576, "link_fail": 288, "preview": 576, "power_and_link": 144}


def slot_value(choice: dict, slot: str, field: str):
    return CATALOG["slots"][slot]["options"][choice[slot]][field]


def ideal_quantities(choice: dict, missing: dict | None = None) -> dict[str, float | list[float]]:
    """The quantities a perfect brief-derived model states, keyed by attribute name."""
    out: dict[str, float | list[float]] = {
        "powerLimitW": 60.0,
        "dataRateMbps": float(choice["dataRateMbps"]),
        "retentionHours": float(choice["retentionHours"]),
        "uploadMbps": float(choice["uploadMbps"]),
        "uplinkMbps": float(slot_value(choice, "uplink", "uplinkMbps")),
        "storageGB": float(slot_value(choice, "storage", "storageGB")),
        "drawW": [float(slot_value(choice, "visible_camera", "drawW")),
                  *([float(slot_value(choice, "ir_camera", "drawW"))] if slot_value(choice, "ir_camera", "drawW") else []),
                  float(slot_value(choice, "computer", "drawW"))],
    }
    if missing:
        if missing["quantity"] == "drawW":
            # Draws are pairwise distinct in this catalogue and the removal candidates require the
            # value to appear exactly once in the brief, so removing by value removes one device.
            out["drawW"] = [draw for draw in out["drawW"] if draw != float(missing["value"])] or []
        else:
            out.pop(missing["quantity"], None)
    return out


def expected_static(quantities: dict) -> dict[str, str]:
    """POWER/LINK/STORE exactly as bench.discover.simulate would compute them from the ideal numbers."""
    draws = quantities.get("drawW") or []
    power = ("PASS" if sum(draws) <= quantities["powerLimitW"] else "FAIL") \
        if "powerLimitW" in quantities and draws else "UNKNOWN"
    sent = quantities.get("uploadMbps", quantities.get("dataRateMbps"))
    link = ("PASS" if sent <= quantities["uplinkMbps"] else "FAIL") \
        if "uplinkMbps" in quantities and sent is not None else "UNKNOWN"
    store = ("PASS" if quantities["dataRateMbps"] * quantities["retentionHours"] * 3600 / 8000 <= quantities["storageGB"]
             else "FAIL") if all(k in quantities for k in ("storageGB", "retentionHours", "dataRateMbps")) else "UNKNOWN"
    return {"POWER": power, "LINK": link, "STORE": store}


def expected_reqs_mission(quantities: dict) -> dict[str, str]:
    """REQS and MISSION statuses from the mission code itself, no OpenModelica call."""
    from bench.simulate_design import consistency, integrate
    req_values = {"drawW": [(f"R{i + 1}", draw) for i, draw in enumerate(quantities.get("drawW") or [])]}
    for name, value in quantities.items():
        if name != "drawW":
            req_values[name] = ("R0", float(value))
    agreed = consistency(req_values)
    reqs = {"PASS": "PASS", "FAIL": "FAIL"}.get(agreed["status"], "UNKNOWN")
    design_values = {"drawW": [(f"D{i}", draw) for i, draw in enumerate(sorted(quantities.get("drawW") or []))]}
    for name, value in quantities.items():
        if name != "drawW":
            design_values[name] = ("D0", float(value))
    sim = integrate(design_values)
    statuses = [check["status"] for check in sim["checks"]]
    # Same formula as mission_checks in bench/discover.py.
    mission = "FAIL" if "FAIL" in statuses else ("UNKNOWN" if "UNKNOWN" in statuses or not sim.get("final") else "PASS")
    return {"REQS": reqs, "MISSION": mission}


def removal_candidates(choice: dict, brief: str) -> list[dict]:
    """Phrase removals that take exactly one number out of the brief (§2 MISSING-VALUE)."""
    vis = slot_value(choice, "visible_camera", "drawW")
    ir = slot_value(choice, "ir_camera", "drawW")
    comp = slot_value(choice, "computer", "drawW")
    uplink = slot_value(choice, "uplink", "uplinkMbps")
    storage = slot_value(choice, "storage", "storageGB")
    rate, hours, upload = choice["dataRateMbps"], choice["retentionHours"], choice["uploadMbps"]
    preview = float(upload) < float(rate)
    plans = [
        ("powerLimitW", None, 60, "The vessel power limit is 60 W.", "The vessel power limit is still to be confirmed."),
        ("storageGB", None, storage, f"on {storage} GB of storage", "on local storage whose size is still to be confirmed"),
        ("retentionHours", None, hours, f"for {hours:g} hours", "for a retention window still to be confirmed"),
        ("uplinkMbps", None, uplink, f"one {uplink} Mbps uplink", "one uplink whose capacity is still to be confirmed"),
        ("dataRateMbps", None, rate, f"at {rate:g} Mbps", "at a recording rate still to be confirmed"),
        ("drawW", "visible_camera", vis, f"visible camera drawing {vis} W", "visible camera whose draw is still to be confirmed"),
        ("drawW", "computer", comp, f"edge computer drawing {comp} W", "edge computer whose draw is still to be confirmed"),
    ]
    if ir:
        plans.append(("drawW", "ir_camera", ir, f"infrared camera drawing {ir} W",
                      "infrared camera whose draw is still to be confirmed"))
    if preview:
        plans.append(("uploadMbps", None, upload, f"A {upload:g} Mbps preview", "A preview"))
    else:
        plans.append(("uploadMbps", None, upload, f"at {upload:g} Mbps over", "at a rate still to be confirmed over"))
    tokens = [f"{float(raw):g}" for raw in NUMBER.findall(brief)]
    out = []
    for quantity, role, value, old, new in plans:
        token = f"{float(value):g}"
        if old in brief and tokens.count(token) == 1:
            out.append({"quantity": quantity, "role": role, "value": value, "old": old, "new": new})
    return out


def brief_with_number_removed(choice: dict, missing: dict) -> str:
    brief = brief_from(choice)
    removed = brief.replace(missing["removed_phrase"], missing["replacement_phrase"], 1)
    from bench.discover import numbers_in
    token = f"{float(missing['value']):g}"
    before, after = numbers_in(brief), numbers_in(removed)
    if token in after or after != before - {token}:
        raise ValueError(f"removal of {missing['quantity']}={token} did not remove exactly that number")
    return removed


def kind_of(choice: dict) -> tuple[str, dict]:
    b = budgets(choice)
    if b["power"]["status"] == "FAIL":
        kind = "INFEASIBLE-POWER"
    elif b["link"]["status"] == "FAIL":
        kind = "INFEASIBLE-LINK"
    elif b["preview"]:
        kind = "PREVIEW"
    else:
        kind = "FEASIBLE"
    return kind, b


def row_for(choice: dict, index: int, kind: str, missing: dict | None = None) -> dict:
    quantities = ideal_quantities(choice, missing)
    static = expected_static(quantities)
    reqs_mission = expected_reqs_mission(quantities)
    return {
        "id": f"p2-{index:04d}" + (f"-mv-{missing['quantity']}" + (f"-{missing['role']}" if missing.get("role") else "") if missing else ""),
        "kind": "MISSING-VALUE" if missing else kind,
        "base_kind": kind,
        "choice": dict(choice),
        "brief": brief_with_number_removed(choice, missing) if missing else brief_from(choice),
        "missing": missing,
        "expected": {
            "budgets": budgets(choice),
            "preview": budgets(choice)["preview"],
            "check_statuses": {**static, "TRACE": "PASS", **reqs_mission},
            "gate": {"answer": "awaiting-person",
                     "eligible_nonempty": not missing and kind in {"FEASIBLE", "PREVIEW"},
                     "tradeoffs_required": kind in {"INFEASIBLE-POWER", "INFEASIBLE-LINK"}},
        },
        "bank_seed": SEED,
    }


def validate_sample(rows: list[dict], sample_ids: list[str]) -> list[str]:
    """Cross-check the mirrored expectations against the real simulate() (OpenModelica included)."""
    from bench.discover import simulate
    problems = []
    by_id = {row["id"]: row for row in rows}
    for task_id in sample_ids:
        row = by_id[task_id]
        quantities = ideal_quantities(row["choice"], row["missing"])
        numbers = {}
        for name, value in quantities.items():
            if name == "drawW":
                numbers.update({f"Ideal::usv::dev{i}::drawW": draw for i, draw in enumerate(value)})
            else:
                numbers[f"Ideal::usv::{name}"] = float(value)
        requirements = [{"id": f"R{i}", "quantity": {"name": n, "value": v}}
                        for i, (n, v) in enumerate((k, x) for k, x in quantities.items() if k != "drawW")]
        requirements += [{"id": f"R{len(requirements) + 1 + i}", "quantity": {"name": "drawW", "value": draw}}
                         for i, draw in enumerate(quantities.get("drawW") or [])]
        checks = {c["id"]: c["status"] for c in simulate(numbers, [], requirements)}
        for key in ("POWER", "LINK", "STORE", "TRACE", "REQS", "MISSION"):
            if checks.get(key) != row["expected"]["check_statuses"][key]:
                problems.append(f"{task_id} {key}: bank {row['expected']['check_statuses'][key]} vs simulate {checks.get(key)}")
    return problems


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--sample-check", type=int, default=24, help="rows cross-checked against simulate()")
    args = parser.parse_args()
    rng = random.Random(args.seed)
    slot_names = [list(CATALOG["slots"][slot]["options"]) for slot in SLOTS]
    param_values = [CATALOG["params"][name]["choices"] for name in PARAMS]
    rows, counts = [], {"FEASIBLE": 0, "INFEASIBLE-POWER": 0, "INFEASIBLE-LINK": 0, "PREVIEW": 0, "MISSING-VALUE": 0}
    overlap = power_fail = link_fail = preview_count = all_pass = 0
    for index, combo in enumerate(itertools.product(*slot_names, *param_values)):
        choice = dict(zip(SLOTS + PARAMS, combo))
        kind, b = kind_of(choice)
        counts[kind] += 1
        power_fail += b["power"]["status"] == "FAIL"
        link_fail += b["link"]["status"] == "FAIL"
        overlap += b["power"]["status"] == "FAIL" and b["link"]["status"] == "FAIL"
        preview_count += b["preview"]
        all_pass += all(b[key]["status"] == "PASS" for key in ("power", "link", "store"))
        rows.append(row_for(choice, index, kind))
    feasible_rows = [row for row in rows if row["kind"] == "FEASIBLE"]
    for feasible in feasible_rows:
        candidates = removal_candidates(feasible["choice"], brief_from(feasible["choice"]))
        if not candidates:
            raise ValueError(f"no removable number for {feasible['id']}")
        plan = candidates[feasible_rows.index(feasible) % len(candidates)]
        missing = {"quantity": plan["quantity"], "role": plan["role"], "value": plan["value"],
                   "removed_phrase": plan["old"], "replacement_phrase": plan["new"]}
        row = row_for(feasible["choice"], int(feasible["id"].split("-")[1]), feasible["base_kind"], missing)
        rows.append(row)
        counts["MISSING-VALUE"] += 1
    sample = rng.sample([row["id"] for row in rows], min(args.sample_check, len(rows)))
    problems = validate_sample(rows, sample)
    computed = {"feasible": all_pass, "power_fail": power_fail, "link_fail": link_fail,
                "preview": preview_count, "power_and_link": overlap}
    mismatch = {key: {"computed": computed[key], "plan": PLAN_COUNTS[key]}
                for key in PLAN_COUNTS if computed[key] != PLAN_COUNTS[key]}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    out = ROOT / "analysis" / f"part2-bench-bank-{stamp}"
    out.mkdir(parents=True)
    with (out / "bank.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    selfcheck = {
        "bank": str((out / "bank.jsonl").relative_to(ROOT)), "rows": len(rows), "seed": args.seed,
        "kind_priority": "INFEASIBLE-POWER > INFEASIBLE-LINK > PREVIEW > FEASIBLE; a choice failing both power and link is INFEASIBLE-POWER (overlap reported)",
        "kind_counts": counts,
        "plan_comparison": {"computed": computed, "plan": PLAN_COUNTS, "mismatch": mismatch},
        "overlap_note": f"{overlap} of 1152 choices fail both power and link; kinds are disjoint by the priority above, "
                        "so INFEASIBLE-LINK ({}) counts only power-passing link failures".format(counts["INFEASIBLE-LINK"]),
        "missing_value_note": "MISSING-VALUE rows are derived from FEASIBLE-kind (all budgets PASS, not a preview) choices; "
                               "the removed quantity, role and value are in the row's `missing` field; ADAPT is not built",
        "simulate_sample": {"checked": sample, "problems": problems},
        "storage_note": "storage never fails in this catalogue (max 64.8 GB < smallest 128 GB); storage-failure detection untested",
    }
    (out / "selfcheck.json").write_text(json.dumps(selfcheck, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"kind_counts": counts, "computed": computed, "plan": PLAN_COUNTS, "mismatch": mismatch,
                      "rows": len(rows), "simulate_problems": problems, "out": str(out)}, indent=2))
    if mismatch or problems:
        raise SystemExit("self-check failed; bank written but not fit for use")


if __name__ == "__main__":
    main()
