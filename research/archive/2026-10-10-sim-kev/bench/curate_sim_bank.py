"""Deterministic curation of the SIM bank task families (kept/archived splits).

Bank  : bench/tasks_staging/t_sim_bank/
Batch 1 (legacy, already applied):  sim_battery 350->175, sim_backlog 350->175,
     sim_thermal 300->150 (audit: verification/boundary.json).
Batch 2 (this extension):           sim_uplink 250->125, sim_latency 250->125,
     sim_storage 250->125, sim_harvest 250->125 (audit:
     verification-families2/boundary.json).
Unselected task directories are MOVED (never deleted) to
     bench/tasks_staging/t_sim_bank/_archive_unselected/<family>/ ,
each family manifest.json gains per-task `selected` (bool) and `selection`
(status + distance to nearest kept task) fields plus a top-level `curation`
block, and SELECTION.md documents method and before/after statistics (batch 1
chapter first — byte-identical to the original — then the batch 2 chapter).

Method per family (fixed quota):
  1. Audit exclusion: tight-margin tasks (`tight_below_3x_tol` rows of the
     family's boundary.json) are dropped from the candidate pool in principle.
     An exception is kept only if the tight task is ISOLATION_FACTOR x more
     isolated from every kept task than the most isolated ordinary dropped
     task of its family; exceptions replace the nearest kept task of the same
     stratum so quotas still hold.
  1b. Near-duplicate avoidance (batch 2): for every pair in the audit's
     `near_duplicate_param_pairs`, at most ONE member may be kept; during
     selection a candidate is skipped while its pair-mate is already kept.
  2. Stratification (per family spec): quota split across strata by
     largest-remainder proportional allocation on ORIGINAL stratum sizes,
     floored at 1 and capped by each stratum's eligible count.
  3. Farthest-point selection: greedy max-min (farthest-point sampling) over
     the min-max normalized joint parameter space, constrained to the
     per-stratum quotas; ties broken by smallest task id; first seed is the
     eligible task closest to the family centroid.

No randomness is used anywhere, so re-running reproduces byte-identical
manifests and SELECTION.md; SEED is provenance only. The script never deletes
a file and never edits a task's own files (case.yaml, input/, gold/). Run with
--apply to act; without it, only a dry-run summary is printed. Idempotent.
Batch 1 results are never re-derived differently: recomputation is checked
against the stored `selected` flags and legacy manifest bytes must not change.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BANK = ROOT / "bench" / "tasks_staging" / "t_sim_bank"
ARCHIVE = BANK / "_archive_unselected"

SEED = 20261010          # provenance only; the algorithm below is deterministic
EPS = 1e-12

# A tight-margin task is kept despite the audit exclusion only if it is
# dramatically more isolated (ISOLATION_FACTOR x) than the most isolated
# ordinary dropped task of its family, i.e. its parameter region would be a
# genuinely unique hole. A marginal gap (a few %) means the same-size hole is
# already accepted elsewhere for ordinary diversity reasons, so the audit risk
# wins and the task stays archived.
ISOLATION_FACTOR = 1.5


# ---------------------------------------------------------------------------
# Family registry: quota, audit file, stratum extractor, hist fields, and the
# normalized joint parameter vector (min-max over generator grid ranges; absent
# optional slots are zero-padded, mirroring the generators' own dedup vectors).
# ---------------------------------------------------------------------------
def _b(x) -> str:
    return str(bool(x)).lower()


def stratum_battery(t): return (t["platform"], _b(t["gold"]["meets_reserve"]), t["difficulty"]["level"])
def stratum_backlog(t): return (t["platform"], _b(t["gold"]["overflows"]), t["difficulty"].split("/")[0])
def stratum_thermal(t): return (t["platform"], _b(t["gold"]["exceeds_limit"]), t["difficulty"])
def stratum_uplink(t):
    return (t["scheme"], f"{t['difficulty']['phases']}p",
            "comp" if t["gold"]["completion_time_min"] is not None else "nocomp")
def stratum_latency(t): return (t["platform"], _b(t["gold"]["meets_staleness"]), t["difficulty"]["level"])
def stratum_storage(t):
    return (t["platform"], _b(t["gold"]["meets_target"] if t["variant"] == "retention"
                              else t["gold"]["feasible"]), t["variant"])
def stratum_harvest(t): return (t["platform"], _b(t["gold"]["breached"]), t["difficulty"]["level"])


def hist_battery(t): return {"platform": t["platform"], "gold_bool": _b(t["gold"]["meets_reserve"]),
                             "difficulty": t["difficulty"]["level"]}
def hist_backlog(t): return {"platform": t["platform"], "gold_bool": _b(t["gold"]["overflows"]),
                             "difficulty": t["difficulty"].split("/")[0]}
def hist_thermal(t): return {"platform": t["platform"], "gold_bool": _b(t["gold"]["exceeds_limit"]),
                             "difficulty": t["difficulty"]}
def hist_uplink(t): return {"scheme": t["scheme"], "phases": f"{t['difficulty']['phases']}p",
                            "completion": "comp" if t["gold"]["completion_time_min"] is not None else "nocomp"}
def hist_latency(t): return {"platform": t["platform"], "gold_bool": _b(t["gold"]["meets_staleness"]),
                             "difficulty": t["difficulty"]["level"]}
def hist_storage(t): return {"platform": t["platform"],
                             "gold_bool": _b(t["gold"]["meets_target"] if t["variant"] == "retention"
                                             else t["gold"]["feasible"]),
                             "difficulty": t["variant"]}
def hist_harvest(t): return {"platform": t["platform"], "gold_bool": _b(t["gold"]["breached"]),
                             "difficulty": t["difficulty"]["level"]}


def _n(v: float, lo: float, hi: float) -> float:
    return (v - lo) / (hi - lo)


def vec_battery(t: dict) -> list[float]:
    p = t["params"]
    durs = [float(w["dur_h"]) for w in p["duty"]] + [0.0] * (6 - len(p["duty"]))
    return [
        _n(p["capacity_wh"], 400, 2400), _n(p["soc_start_pct"], 70, 95), _n(p["reserve_pct"], 10, 30),
        _n(p["powers_w"]["idle"], 5, 40), _n(p["powers_w"]["cruise"], 25, 120),
        _n(p["powers_w"]["transmit"], 90, 200),
    ] + [_n(d, 0.3, 3.5) for d in durs]


def vec_backlog(t: dict) -> list[float]:
    p = t["params"]
    mission = float(p["mission_min"])
    wins = sorted(p["windows"], key=lambda w: w["start_min"])
    flat: list[float] = []
    for i in range(2):
        if i < len(wins):
            flat += [float(wins[i]["start_min"]), float(wins[i]["duration_min"])]
        else:
            flat += [0.0, 0.0]
    outage_frac = sum(float(w["duration_min"]) for w in wins) / mission
    return [
        _n(p["sensor_mbps"], 2, 50), _n(p["link_mbps"], 1, 80), _n(mission, 120, 720),
        _n(p["capacity_gb"], 1, 220),
        _n(flat[0], 0, 720), _n(flat[1], 10, 180), _n(flat[2], 0, 720), _n(flat[3], 10, 180),
        outage_frac,
    ]


def vec_thermal(t: dict) -> list[float]:
    p = t["params"]
    return [
        _n(p["power_w"], 10, 80), _n(p["rth_k_per_w"], 0.30, 2.00), _n(p["c_j_per_k"], 200, 2000),
        _n(p["tamb_c"], 15, 30), _n(p["tmax_c"], 45, 70), _n(float(p.get("n_min", 0)), 2, 280),
    ]


def vec_uplink(t: dict) -> list[float]:
    p = t["params"]
    """14 dims: capacity, quota fraction (0-pad for preempt), window, phase
    bounds (b2 zero-padded for 2-phase), per-phase rates x2 platforms (3 slots,
    zero-padded), initial backlogs x2, starve threshold."""
    cap = float(p["capacity_mbps"])
    quota_frac = float(p["quota_usv_mbps"]) / cap if p.get("quota_usv_mbps") is not None else 0.0
    bounds = [float(x) for x in p["phase_bounds_min"]]
    b1, b2 = (bounds[0], bounds[1]) if len(bounds) == 3 else (bounds[0], 0.0)
    ru = [float(x) for x in p["rates_mbps"]["usv"]] + [0.0] * (3 - len(p["rates_mbps"]["usv"]))
    ra = [float(x) for x in p["rates_mbps"]["uav"]] + [0.0] * (3 - len(p["rates_mbps"]["uav"]))
    return ([_n(cap, 10, 80), quota_frac, _n(float(p["window_min"]), 60, 360),
             _n(b1, 0, 360), _n(b2, 0, 360)]
            + [_n(x, 2, 40) for x in ru] + [_n(x, 2, 40) for x in ra]
            + [_n(float(p["initial_backlog_mb"]["usv"]), 0, 24000),
               _n(float(p["initial_backlog_mb"]["uav"]), 0, 24000),
               _n(float(p["starve_pct"]), 50, 80)])


def vec_latency(t: dict) -> list[float]:
    p = t["params"]
    """10 dims: hop processing times, uplink propagation (0..30 s covers the
    acoustic 4..30 s band; radio lands ~0), downlink distance + medium flag,
    window period and phase fraction, message count, spacing, staleness."""
    up, down, win, msg = p["uplink"], p["downlink"], p["window"], p["messages"]
    return [
        _n(p["proc_src_s"], 1, 500), _n(p["proc_relay_s"], 1, 500),
        _n(float(up["prop_s"]), 0, 30),
        _n(float(down["distance_km"]), 30, 300),
        1.0 if down["medium"] == "hf_radio" else 0.0,
        _n(float(win["period_s"]), 300, 1800),
        float(win["phase_s"]) / float(win["period_s"]),
        _n(float(msg["count"]), 3, 10), _n(float(msg["spacing_s"]), 60, 900),
        _n(float(p["staleness_threshold_s"]), 240, 1200),
    ]


def vec_storage(t: dict) -> list[float]:
    p = t["params"]
    """7 dims: R/S/T grids, compression/decimation factor and preview ratio
    (each min-max normalized; zero-padded outside their variants), variant
    one-hot (choice, preview)."""
    factor = float(p.get("factor", 0) or 0)
    ratio = float(p.get("preview_ratio_p", 0) or 0)
    variant = t.get("variant")           # task-level, not inside params
    mode = p.get("mode") or t.get("mode")
    return [
        _n(p["raw_rate_mbps"], 4, 50), _n(p["capacity_gb"], 10, 500),
        _n(p["target_retention_h"], 2, 24), _n(factor, 1, 16), _n(ratio, 0.1, 0.5),
        1.0 if variant == "choice" else 0.0,
        1.0 if mode == "preview" else 0.0,
    ]


def vec_harvest(t: dict) -> list[float]:
    p = t["params"]
    """20 dims: battery tank + protection line, tier loads, 7 duty durations and
    7 per-segment solar inputs (both zero-padded beyond the segment count)."""
    n_seg = len(p["duty"])
    durs = [float(w["dur_h"]) for w in p["duty"]] + [0.0] * (7 - n_seg)
    solar = [float(w["solar_w"]) for w in p["duty"]] + [0.0] * (7 - n_seg)
    return ([
        _n(p["capacity_wh"], 300, 1500), _n(p["soc_start_pct"], 40, 95), _n(p["protect_pct"], 5, 20),
        _n(p["powers_w"]["idle"], 5, 45), _n(p["powers_w"]["cruise"], 40, 110),
        _n(p["powers_w"]["transmit"], 90, 150),
    ] + [_n(d, 0.3, 3.5) for d in durs] + [_n(s, 0, 120) for s in solar])


DIMS = {
    "sim_battery": ["capacity_wh", "soc_start_pct", "reserve_pct", "power_idle_w", "power_cruise_w",
                    "power_transmit_w"] + [f"dur_{i+1}_h" for i in range(6)],
    "sim_backlog": ["sensor_mbps", "link_mbps", "mission_min", "capacity_gb", "win1_start_min",
                    "win1_dur_min", "win2_start_min", "win2_dur_min", "outage_frac"],
    "sim_thermal": ["power_w", "rth_k_per_w", "c_j_per_k", "tamb_c", "tmax_c", "n_min"],
    "sim_uplink": ["capacity_mbps", "quota_frac", "window_min", "phase1_end_min", "phase2_end_min",
                   "rate_usv_1", "rate_usv_2", "rate_usv_3", "rate_uav_1", "rate_uav_2", "rate_uav_3",
                   "backlog0_usv_mb", "backlog0_uav_mb", "starve_pct"],
    "sim_latency": ["proc_src_s", "proc_relay_s", "prop_up_s", "down_dist_km", "down_is_hf_radio",
                    "window_period_s", "window_phase_frac", "message_count", "message_spacing_s",
                    "staleness_threshold_s"],
    "sim_storage": ["raw_rate_mbps", "capacity_gb", "target_retention_h", "factor", "preview_ratio_p",
                    "is_choice", "is_preview"],
    "sim_harvest": ["capacity_wh", "soc_start_pct", "protect_pct", "power_idle_w", "power_cruise_w",
                    "power_transmit_w"] + [f"dur_{i+1}_h" for i in range(7)] \
                   + [f"solar_{i+1}_w" for i in range(7)],
}

FAMILIES = {
    # ---- batch 1 (legacy; selection already applied, must not change) -------
    "sim_battery": {"batch": 1, "quota": 175, "boundary": "verification/boundary.json",
                    "axes": "platform x gold-boolean x difficulty tier",
                    "stratum": stratum_battery, "hist": hist_battery, "vec": vec_battery},
    "sim_backlog": {"batch": 1, "quota": 175, "boundary": "verification/boundary.json",
                    "axes": "platform x gold-boolean x difficulty tier",
                    "stratum": stratum_backlog, "hist": hist_backlog, "vec": vec_backlog},
    "sim_thermal": {"batch": 1, "quota": 150, "boundary": "verification/boundary.json",
                    "axes": "platform x gold-boolean x difficulty tier",
                    "stratum": stratum_thermal, "hist": hist_thermal, "vec": vec_thermal},
    # ---- batch 2 -------------------------------------------------------------
    "sim_uplink": {"batch": 2, "quota": 125, "boundary": "verification-families2/boundary.json",
                   "axes": "scheme x phases x completion-time present (dual-platform tasks)",
                   "stratum": stratum_uplink, "hist": hist_uplink, "vec": vec_uplink},
    "sim_latency": {"batch": 2, "quota": 125, "boundary": "verification-families2/boundary.json",
                    "axes": "platform x gold-boolean x difficulty tier",
                    "stratum": stratum_latency, "hist": hist_latency, "vec": vec_latency},
    "sim_storage": {"batch": 2, "quota": 125, "boundary": "verification-families2/boundary.json",
                    "axes": "platform x gold-boolean x variant",
                    "stratum": stratum_storage, "hist": hist_storage, "vec": vec_storage},
    "sim_harvest": {"batch": 2, "quota": 125, "boundary": "verification-families2/boundary.json",
                    "axes": "platform x gold-boolean x difficulty tier",
                    "stratum": stratum_harvest, "hist": hist_harvest, "vec": vec_harvest},
}
LEGACY = [f for f, s in FAMILIES.items() if s["batch"] == 1]
NEW = [f for f, s in FAMILIES.items() if s["batch"] == 2]


def dist(a: list[float], b: list[float]) -> float:
    s = 0.0
    for x, y in zip(a, b):
        d = x - y
        s += d * d
    return s ** 0.5


# --- stratified proportional allocation (largest remainder, deterministic) -----
def allocate_quotas(strata: dict[tuple, list[dict]], quota: int) -> dict[tuple, int]:
    """Split `quota` over strata proportionally to ORIGINAL stratum sizes.

    Guarantees: every stratum with eligible tasks keeps >= 1, no stratum is
    allocated more than its eligible count, and the sum equals `quota`.
    Deterministic: strata processed in sorted key order, ties by key.
    """
    keys = sorted(strata, key=lambda k: tuple(str(x) for x in k))
    total = sum(len(strata[k]) for k in keys)
    exact = {k: quota * len(strata[k]) / total for k in keys}
    elig = {k: sum(1 for t in strata[k] if t["eligible"]) for k in keys}
    alloc = {}
    for k in keys:
        a = max(1, int(exact[k] // 1)) if elig[k] else 0
        alloc[k] = min(a, elig[k])
    order = sorted(keys, key=lambda k: (-(exact[k] - int(exact[k] // 1)), tuple(str(x) for x in k)))
    while sum(alloc.values()) < quota:
        progressed = False
        for k in order:
            if sum(alloc.values()) >= quota:
                break
            if alloc[k] < elig[k]:
                alloc[k] += 1
                progressed = True
        if not progressed:
            raise SystemExit("cannot satisfy family quota with eligible pool")
    if sum(alloc.values()) > quota:                # min-1 floor overshot; trim
        for k in sorted(keys, key=lambda k: (alloc[k] - exact[k], tuple(str(x) for x in k))):
            if sum(alloc.values()) <= quota:
                break
            if alloc[k] > 1:
                alloc[k] -= 1
    return alloc


# --- quota-constrained greedy farthest-point selection --------------------------
def farthest_point_select(tasks: list[dict], quota: int, pair_of: dict[str, str]) -> list[str]:
    """Greedy max-min FPS restricted to per-stratum quotas. A candidate is
    skipped while its near-duplicate pair-mate (pair_of) is already selected."""
    remaining: dict[tuple, int] = {}
    pool: list[dict] = []
    for t in tasks:
        if t["eligible"]:
            pool.append(t)
            remaining[t["stratum"]] = remaining.get(t["stratum"], 0) + 1
    alloc = allocate_quotas({k: [t for t in tasks if t["stratum"] == k] for k in remaining}, quota)
    remaining = {k: alloc.get(k, 0) for k in {t["stratum"] for t in tasks}}

    pool.sort(key=lambda t: t["id"])
    centroid = [sum(t["vec"][i] for t in pool) / len(pool) for i in range(len(pool[0]["vec"]))]
    selected: list[dict] = []
    sel_vecs: list[list[float]] = []
    sel_ids: set[str] = set()
    while len(selected) < quota:
        best: dict | None = None
        best_d = -1.0
        for t in pool:
            if remaining[t["stratum"]] <= 0:
                continue
            if pair_of.get(t["id"]) in sel_ids:
                continue                     # near-duplicate mate already kept
            if not sel_vecs:
                d = -dist(t["vec"], centroid)      # seed: nearest to centroid
            else:
                d = min(dist(t["vec"], sv) for sv in sel_vecs)
            if d > best_d + EPS:
                best, best_d = t, d
        assert best is not None
        selected.append(best)
        sel_vecs.append(best["vec"])
        sel_ids.add(best["id"])
        remaining[best["stratum"]] -= 1
    return [t["id"] for t in selected]


# --- statistics helpers ---------------------------------------------------------
def pairwise_min_dist(vecs: list[list[float]]) -> float:
    best = float("inf")
    for i, a in enumerate(vecs):
        for b in vecs[i + 1:]:
            d = dist(a, b)
            if d < best:
                best = d
    return best


def nn_distances(vecs: list[list[float]]) -> list[float]:
    return [min(dist(a, b) for j, b in enumerate(vecs) if j != i) for i, a in enumerate(vecs)]


def dim_coverage(vecs: list[list[float]]) -> list[float]:
    if not vecs:
        return [0.0] * 1
    return [max(v[i] for v in vecs) - min(v[i] for v in vecs) for i in range(len(vecs[0]))]


def hist_of(tasks: list[dict], spec: dict) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for t in tasks:
        for k, v in spec["hist"](t["raw"]).items():
            out.setdefault(k, {})
            out[k][str(v)] = out[k].get(str(v), 0) + 1
    return {k: dict(sorted(v.items())) for k, v in out.items()}


def id_ranges(ids: list[str]) -> str:
    """Compact 'BAT-0001~BAT-0004, BAT-0007' style ranges (deterministic)."""
    if not ids:
        return "(none)"
    prefix = ids[0].rsplit("-", 1)[0]
    nums = sorted(int(i.rsplit("-", 1)[1]) for i in ids)
    parts, start, prev = [], nums[0], nums[0]
    for n in nums[1:]:
        if n == prev + 1:
            prev = n
            continue
        parts.append((start, prev))
        start = prev = n
    parts.append((start, prev))
    chunks = [f"{prefix}-{a:04d}" if a == b else f"{prefix}-{a:04d}~{prefix}-{b:04d}" for a, b in parts]
    return ", ".join(chunks)


# --- per-family curation ---------------------------------------------------------
def curate_family(family: str, tasks_raw: list[dict], tight_ids: set[str],
                  near_pairs: list[tuple[str, str]]) -> dict:
    spec = FAMILIES[family]
    quota = spec["quota"]
    tasks = []
    for t in sorted(tasks_raw, key=lambda t: t["id"]):
        tasks.append({
            "id": t["id"],
            "raw": t,
            "stratum": tuple(str(x) for x in spec["stratum"](t)),
            "vec": spec["vec"](t),
            "tight": t["id"] in tight_ids,
            "eligible": t["id"] not in tight_ids,
        })
    eligible = [t for t in tasks if t["eligible"]]
    pair_of: dict[str, str] = {}
    for a, b in near_pairs:
        pair_of[a] = b
        pair_of[b] = a

    selected_ids = farthest_point_select(tasks, quota, pair_of)
    selected = [t for t in tasks if t["id"] in set(selected_ids)]
    assert not any(pair_of.get(t["id"]) in {s["id"] for s in selected} for t in selected), \
        f"{family}: near-duplicate pair both selected"

    # audit-exclusion exception test: a tight task is kept only if it is
    # ISOLATION_FACTOR x more isolated (distance to nearest kept task) than
    # the most isolated ordinary dropped task of the family.
    sel_by_id = {t["id"]: t for t in selected}
    dropped_clean_nn = 0.0
    for t in tasks:
        if t["eligible"] and t["id"] not in sel_by_id:
            d = min(dist(t["vec"], s["vec"]) for s in selected)
            dropped_clean_nn = max(dropped_clean_nn, d)
    exceptions = []
    tight_nn: dict[str, float] = {}
    for t in tasks:
        if not t["tight"]:
            continue
        d = min(dist(t["vec"], s["vec"]) for s in selected)
        tight_nn[t["id"]] = d
        if t["id"] not in sel_by_id and d > dropped_clean_nn * ISOLATION_FACTOR + EPS:
            exceptions.append((t["id"], d))
    replaced: dict[str, str] = {}
    for tid, _d in exceptions:
        tight_t = next(t for t in tasks if t["id"] == tid)
        same_stratum = [s for s in selected if s["stratum"] == tight_t["stratum"]]
        victim = min(same_stratum, key=lambda s: (dist(s["vec"], tight_t["vec"]), s["id"]))
        sel_by_id.pop(victim["id"])
        selected = [s for s in selected if s["id"] != victim["id"]]
        selected.append(tight_t)
        sel_by_id[tid] = tight_t
        replaced[victim["id"]] = tid
    selected = [t for t in tasks if t["id"] in sel_by_id]

    # distances: for kept tasks, nearest OTHER kept task; else nearest kept task
    min_dist_selected: dict[str, float] = {}
    for t in tasks:
        others = [s for s in selected if s["id"] != t["id"]]
        min_dist_selected[t["id"]] = min(dist(t["vec"], s["vec"]) for s in others)

    sel_ids = set(sel_by_id)
    status: dict[str, str] = {}
    for t in tasks:
        if t["id"] in sel_ids:
            status[t["id"]] = "selected_tight_exception" if t["tight"] else "selected"
        elif t["id"] in replaced:
            status[t["id"]] = "archived_replaced_by_tight"
        elif t["tight"]:
            status[t["id"]] = "archived_tight"
        elif t["id"] in pair_of and pair_of[t["id"]] in sel_ids:
            status[t["id"]] = "archived_near_duplicate"
        else:
            status[t["id"]] = "archived_diversity"

    closest_tight_call: dict = {}
    if tight_nn:
        cid = max(tight_nn, key=lambda k: (tight_nn[k], k))
        closest_tight_call = {"id": cid, "dist_to_nearest_selected": round(tight_nn[cid], 4)}
    before_vecs = [t["vec"] for t in tasks]
    after_vecs = [t["vec"] for t in selected]
    stats = {
        "n_total": len(tasks),
        "n_eligible": len(eligible),
        "n_tight": sum(t["tight"] for t in tasks),
        "n_selected": len(selected),
        "n_archived": len(tasks) - len(selected),
        "archived_tight": sum(1 for s in status.values() if s == "archived_tight"),
        "archived_diversity": sum(1 for s in status.values() if s == "archived_diversity"),
        "archived_replaced": len(replaced),
        "tight_exceptions": {tid: round(d, 4) for tid, d in exceptions},
        "tight_isolation_threshold": round(dropped_clean_nn * ISOLATION_FACTOR, 4),
        "closest_tight_call": closest_tight_call,
        "min_pairwise_dist_before": round(pairwise_min_dist(before_vecs), 4),
        "min_pairwise_dist_after": round(pairwise_min_dist(after_vecs), 4),
        "mean_nn_dist_before": round(sum(nn_distances(before_vecs)) / len(before_vecs), 4),
        "mean_nn_dist_after": round(sum(nn_distances(after_vecs)) / len(after_vecs), 4),
        "dim_coverage_before": [round(c, 3) for c in dim_coverage(before_vecs)],
        "dim_coverage_after": [round(c, 3) for c in dim_coverage(after_vecs)],
        "hist_before": hist_of(tasks, spec),
        "hist_after": hist_of(selected, spec),
        "strata_selected": {"/".join(k): sum(1 for s in selected if s["stratum"] == k)
                            for k in sorted({t["stratum"] for t in tasks})},
        "strata_total": {"/".join(k): sum(1 for t in tasks if t["stratum"] == k)
                         for k in sorted({t["stratum"] for t in tasks})},
    }
    if near_pairs:
        stats["archived_near_duplicate"] = sum(1 for s in status.values() if s == "archived_near_duplicate")
        stats["near_dup_pairs"] = [
            {"a": a, "b": b,
             "kept": a if a in sel_ids else (b if b in sel_ids else None)}
            for a, b in near_pairs]
    return {
        "tasks": tasks,
        "selected_ids": [t["id"] for t in selected],
        "status": status,
        "min_dist_selected": min_dist_selected,
        "tight_nn": tight_nn,
        "stats": stats,
    }


# --- manifest rewriting (byte-safe: only additive fields) ------------------------
def dump_json(manifest: dict) -> str:
    return json.dumps(manifest, indent=2) + "\n"


def update_manifest(family: str, result: dict) -> dict:
    spec = FAMILIES[family]
    path = BANK / family / "manifest.json"
    original = path.read_text(encoding="utf-8")
    manifest = json.loads(original)
    if dump_json(manifest) != original:
        raise SystemExit(f"{family}/manifest.json: canonical re-dump differs from disk; refusing to rewrite")
    if "curation" in manifest and family in LEGACY:
        # legacy guard: recompute must match the stored batch-1 flags exactly
        stored = {t["id"]: t["selected"] for t in manifest["tasks"]}
        recomputed = {t["id"]: result["status"][t["id"]].startswith("selected")
                      for t in manifest["tasks"]}
        if stored != recomputed:
            raise SystemExit(f"{family}: recomputed selection differs from stored curation; refusing to change it")
    for t in manifest["tasks"]:
        tid = t["id"]
        t["selected"] = result["status"][tid].startswith("selected")
        t["selection"] = {
            "status": result["status"][tid],
            "min_dist_to_selected": round(result["min_dist_selected"][tid], 6),
        }
    s = result["stats"]
    manifest["curation"] = {
        "tool": "bench/curate_sim_bank.py",
        "seed": SEED,
        "method": ("stratified farthest-point selection: strata = " + spec["axes"]
                   + "; quota split by largest-remainder proportional allocation on "
                   "original stratum sizes; greedy max-min farthest-point sampling in the min-max "
                   "normalized joint parameter space (dims: " + ", ".join(DIMS[family]) + "); "
                   "audit tight-margin tasks (" + spec["boundary"] + ") excluded, kept only if "
                   f"{ISOLATION_FACTOR}x more isolated than the most isolated ordinary dropped "
                   "task of the family"
                   + ("; near-duplicate pairs kept at most one per pair" if s.get("near_dup_pairs") else "")),
        "quota": spec["quota"],
        "pool_total": s["n_total"],
        "pool_eligible": s["n_eligible"],
        "tight_excluded": s["archived_tight"] + s["archived_replaced"],
        "tight_exceptions": s["tight_exceptions"],
        "selected_count": s["n_selected"],
        "archived_count": s["n_archived"],
        "archive_path": f"bench/tasks_staging/t_sim_bank/_archive_unselected/{family}",
        "stats": {k: v for k, v in s.items() if k not in ("hist_before", "hist_after")},
        "hist_before": s["hist_before"],
        "hist_after": s["hist_after"],
    }
    return manifest


# --- SELECTION.md -----------------------------------------------------------------
def pct(n: int, total: int) -> str:
    return f"{100.0 * n / total:.1f}%"


HIST_LABELS = {
    "platform": "platform", "gold_bool": "真假判定", "difficulty": "难度档",
    "scheme": "scheme", "phases": "相位数", "completion": "完成时刻",
}


def _family_stats_blocks(fam: str, results: dict) -> list[str]:
    """Per-family before/after bullet block (shared by both chapter renderers)."""
    s = results[fam]["stats"]
    L = [f"### {fam}（{s['n_total']} → {s['n_selected']}）", ""]
    for field in results[fam]["stats"]["hist_before"]:
        before, after = s["hist_before"][field], s["hist_after"][field]
        keys = sorted(set(before) | set(after))
        L.append(f"- {HIST_LABELS.get(field, field)}：" + "；".join(
            f"{k} {before.get(k, 0)}({pct(before.get(k, 0), s['n_total'])}) → "
            f"{after.get(k, 0)}({pct(after.get(k, 0), s['n_selected'])})" for k in keys))
    L.append(f"- 分层保留/原数：" + "；".join(
        f"{k} {v}/{s['strata_total'][k]}" for k, v in s["strata_selected"].items()))
    L.append(f"- 最小两两参数距离：{s['min_pairwise_dist_before']} → "
             f"**{s['min_pairwise_dist_after']}**（提升 "
             f"{s['min_pairwise_dist_after'] / s['min_pairwise_dist_before']:.2f}×）")
    L.append(f"- 平均最近邻距离：{s['mean_nn_dist_before']} → {s['mean_nn_dist_after']}")
    cov = list(zip(DIMS[fam], s["dim_coverage_before"], s["dim_coverage_after"]))
    L.append("- 参数空间覆盖（归一化维度极差，原库 → 精选库）：" + "；".join(
        f"{n} {b:.2f}→{a:.2f}" for n, b, a in cov))
    covered = sum(1 for _n, b, a in cov if a >= 0.9)
    L.append(f"  - 覆盖率 ≥0.9 的维度：{covered}/{len(cov)}（精选库仍铺满各维主体范围）")
    return L


def selection_md_batch1(results: dict) -> str:
    """Chapter 1: the original three-family curation (1000 -> 500). The text is
    the original SELECTION.md content, unchanged."""
    L: list[str] = []
    L.append("# SIM 题库精选 500 题说明（SELECTION）")
    L.append("")
    L.append("- 工具：`bench/curate_sim_bank.py`（确定性，无随机数；SEED="
             f"{SEED} 仅为记录，重跑逐字节一致）")
    L.append("- 对象：`bench/tasks_staging/t_sim_bank/`（sim_battery 350 + sim_backlog 350 + "
             "sim_thermal 300 = 1000 题）")
    L.append("- 结果：保留 500 题（族配额 电池 175 / 断链 175 / 热 150），其余 500 题目录"
             "原样移动至 `_archive_unselected/<族>/`；未删除、未改写任何题目文件"
             "（case.yaml、input/、gold/ 一字未动），仅在三个族 manifest.json 中追加"
             "每题 `selected` 布尔字段与 `selection`（状态 + 与最近保留题的距离）字段。")
    L.append("")
    L.append("## 方法")
    L.append("")
    L.append("1. **贴边题剔除（审计联动）**：全量审计（`verification/boundary.json`）发现 43 题"
             "（BLG 23、BAT 20、THM 0）的 gold 数值距判定边缘不足 3×容差。这些题原则上"
             "不进入候选池；仅当某贴边题与全部保留题的最近距离超过该族最孤立普通落选题"
             "的 1.5×（即其参数区域是独一无二的空穴）时才破例保留，并替换同分层内最近的"
             "一题以维持配额；若只是略高（量级与普通去相似落选留下的空穴相当），则审计"
             "风险优先，仍然归档。")
    L.append("2. **分层**：每族按 `platform × 真假判定 × 难度档` 分层"
             "（电池：meets_reserve × L1/L2/L3；断链：overflows × 1win/2win；"
             "热：exceeds_limit × steady_state/duty_cycle）。族配额按各层原始规模做"
             "最大余数法比例分配（保住生成时的 6:4 平台比与真假比），每层至少 1 题、"
             "不超过该层非贴边题数，富余额按余数大小补给有余量的层。")
    L.append("3. **最远点选择**：在每族归一化联合参数空间（各参数按生成器网格 min-max "
             "归一到 [0,1]，缺省槽位补零，维度见下表）内做受配额约束的贪心最大-最小"
             "距离采样（farthest-point sampling）：每轮从尚有配额的层中选出与已保留题集"
             "最近距离最大的题（并列取小 ID），首种子取候选池质心最近题。该贪心直接"
             "最大化保留题之间的最小两两距离，即剔除参数空间中的相似题。")
    L.append("")
    dims_tbl = ["| 族 | 参数维度（归一化联合空间） |", "|---|---|"]
    for fam in LEGACY:
        dims_tbl.append(f"| {fam} | {', '.join(DIMS[fam])} |")
    L += dims_tbl
    L.append("")
    L.append("注：缺省槽位（电池第 4–6 段时长、断链第二中断窗、steady_state 的 n_min）补零；"
             "补零值经 min-max 归一后落在个别维度下界之下（故后文个别覆盖维度极差略大于 1），"
             "这是对槽位有无的有意区分，原库与精选库统计口径一致。")
    L.append("")
    L.append("## 分族配额与贴边剔除")
    L.append("")
    L.append("| 族 | 原题数 | 贴边题 | 非贴边候选 | 配额（保留） | 归档 | 归档-贴边 | 归档-去相似 | 破例保留贴边 |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    tot = [0] * 8
    for fam in LEGACY:
        s = results[fam]["stats"]
        row = [s["n_total"], s["n_tight"], s["n_eligible"], s["n_selected"], s["n_archived"],
               s["archived_tight"], s["archived_diversity"], len(s["tight_exceptions"])]
        tot = [a + b for a, b in zip(tot, row)]
        L.append(f"| {fam} | {row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]} | {row[5]} | {row[6]} | {row[7]} |")
    L.append(f"| **合计** | {tot[0]} | {tot[1]} | {tot[2]} | {tot[3]} | {tot[4]} | {tot[5]} | {tot[6]} | {tot[7]} |")
    L.append("")
    parts = [f"{fam} {results[fam]['stats']['n_total']}→{results[fam]['stats']['n_eligible']}"
             for fam in LEGACY]
    if tot[7] == 0:
        calls = "；".join(
            f"{fam} 最接近破例 {results[fam]['stats']['closest_tight_call']['id']}"
            f"（距最近保留题 {results[fam]['stats']['closest_tight_call']['dist_to_nearest_selected']}，"
            f"门槛 {results[fam]['stats']['tight_isolation_threshold']}）"
            for fam in LEGACY if results[fam]["stats"]["closest_tight_call"])
        L.append(f"贴边题剔除前后对比：候选池 1000 → {tot[2]}（{('，'.join(parts))}），"
                 f"{tot[1]} 道贴边题全部未入选（破例 0 题）。判定说明：{calls}——"
                 "与最近保留题的差距均未达到 1.5× 破例门槛（普通去相似落选留下的空穴"
                 "与之同量级），不足以构成参数独特性，审计风险优先。最险的 BLG-0114、"
                 "BLG-0310（溢出时刻恰落在窗口端点、裕度 0.0×）均已归档。")
    else:
        exc = "；".join(f"{fam}: {', '.join(f'{tid}(距最近保留 {d})' for tid, d in results[fam]['stats']['tight_exceptions'].items())}"
                        for fam in LEGACY if results[fam]["stats"]["tight_exceptions"])
        L.append(f"贴边题剔除前后对比：候选池 1000 → {tot[2]}（{('，'.join(parts))}）；"
                 f"{tot[1]} 道贴边题中 {tot[7]} 题因参数区域无任何保留题覆盖而破例保留"
                 f"（已替换同分层内最近保留题以维持配额）：{exc}。其余贴边题全部归档。")
    L.append("")
    L.append("## 保留前后统计对比（分族）")
    for fam in LEGACY:
        L.append("")
        L += _family_stats_blocks(fam, results)
    L.append("")
    L.append("## 每题结果与距离")
    L.append("")
    L.append("每题的被选/未选状态、归档原因（贴边剔除/去相似）与该题到最近保留题的距离，"
             "记录在各族 `manifest.json` 每题的 `selected` 与 `selection.status`、"
             "`selection.min_dist_to_selected` 字段。保留题 ID 清单：")
    for fam in LEGACY:
        L.append("")
        L.append(f"- **{fam} 保留 {len(results[fam]['selected_ids'])} 题**："
                 f"{id_ranges(results[fam]['selected_ids'])}")
    L.append("")
    L.append("## 归档位置与自检")
    L.append("")
    L.append("- 未选题目目录原样移动至 `bench/tasks_staging/t_sim_bank/_archive_unselected/"
             "{sim_battery,sim_backlog,sim_thermal}/`（仅移动，不改内容）。")
    L.append("- 各族根目录的 `manifest.json`（含 curation 块）与 `index.jsonl`（生成期产物，"
             "仍列全部 1000 题）保留在原位；精选过滤以 manifest 的 `selected` 字段为准。")
    L.append("- 自检：移动前后题库文件总数守恒（1000 = 500 active + 500 archived，逐文件 "
             "sha256 仅三个 manifest.json 变化）；`python3 bench/freeze.py --check` 不受影响"
             "（freeze 只覆盖 bench/tasks/ 与代码清单）。")
    L.append("")
    return "\n".join(L)


def selection_md_batch2(results: dict) -> str:
    """Chapter 2 (appended): the four new families, each 250 -> 125."""
    L: list[str] = []
    L.append("---")
    L.append("")
    L.append("# 第二批精选：新四族（sim_uplink / sim_latency / sim_storage / sim_harvest）")
    L.append("")
    L.append("- 对象：四族各 250 题，共 1000 题；每族配额 125，共保留 500 题，其余 500 题目录"
             "原样移动至 `_archive_unselected/<族>/`。工具与老三族一致："
             "`bench/curate_sim_bank.py`（确定性、幂等；老三族精选结果不改动）。")
    L.append("- 审计联动：全量审计在 `verification-families2/boundary.json`（贴边 49 行 / 40 题；"
             "近重复参数 4 对）。每族 manifest.json 同样追加每题 `selected` 与 `selection`"
             "（状态 + 距最近保留题距离）字段及 `curation` 块。")
    L.append("")
    L.append("## 方法（与老三族一致，两点扩展）")
    L.append("")
    L.append("1. **贴边避让**：40 道贴边题（SHR 3、CMP 4、HRV 33、LAT 0）原则上全部不选，"
             "破例门槛与老库相同（距最近保留题 > 该族最孤立普通落选题的 1.5× 才破例，"
             "破例需替换同分层最近保留题以维持配额）。最险：SHR-0067 完成时刻 0.0×、"
             "HRV-0131/0036 关键点贴保护线 0.13×/0.18×。")
    L.append("2. **近重复避让（新增）**：审计报出 4 对近重复参数（CMP-0003~CMP-0109 等，"
             "归一化距离 0.010–0.016），约束为每对至多保留 1 题——选择过程中某题一旦"
             "入选，其配对题即不再参与候选。")
    L.append("3. **分层**：HRV/LAT/CMP 按 platform(usv/uav) × 真假 × 难度档/变体分层"
             "（HRV：breached × L1/L2/L3；LAT：meets_staleness × L1/L2/L3；CMP："
             "meets_target/feasible × retention/choice）；SHR 为双平台（usv+uav）任务，"
             "按 scheme(fixed/preempt_usv/preempt_uav) × 相位数(2/3) × completion"
             "（完成时刻有/无）分层，platform 不参与。配额仍按各层原始规模最大余数法"
             "比例分配，每层保底 1 题。")
    L.append("4. **最远点选择**：与老库相同——归一化联合参数空间内受配额约束的贪心最大-"
             "最小距离采样，并列取小 ID，首种子取质心最近题。")
    L.append("")
    dims_tbl = ["| 族 | 配额 | 分层轴 | 参数维度（归一化联合空间） |", "|---|---|---|---|"]
    for fam in NEW:
        dims_tbl.append(f"| {fam} | {FAMILIES[fam]['quota']} | {FAMILIES[fam]['axes']} | {', '.join(DIMS[fam])} |")
    L += dims_tbl
    L.append("")
    L.append("注：与老库相同，缺省槽位补零（SHR 的 quota 槽/第三相位率、CMP 的 factor/"
             "preview_ratio 槽等），补零值可能落在维度下界之下，属对槽位有无的有意区分。")
    L.append("")
    L.append("## 分族配额与贴边/近重复剔除")
    L.append("")
    L.append("| 族 | 原题数 | 贴边题 | 非贴边候选 | 配额（保留） | 归档 | 归档-贴边 | 归档-近重复 | 归档-去相似 | 破例保留贴边 |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    tot = [0] * 9
    for fam in NEW:
        s = results[fam]["stats"]
        row = [s["n_total"], s["n_tight"], s["n_eligible"], s["n_selected"], s["n_archived"],
               s["archived_tight"], s.get("archived_near_duplicate", 0), s["archived_diversity"],
               len(s["tight_exceptions"])]
        tot = [a + b for a, b in zip(tot, row)]
        L.append(f"| {fam} | {row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]} | {row[5]} | {row[6]} | {row[7]} | {row[8]} |")
    L.append(f"| **合计** | {tot[0]} | {tot[1]} | {tot[2]} | {tot[3]} | {tot[4]} | {tot[5]} | {tot[6]} | {tot[7]} | {tot[8]} |")
    L.append("")
    parts = [f"{fam} {results[fam]['stats']['n_total']}→{results[fam]['stats']['n_eligible']}" for fam in NEW]
    if tot[8] == 0:
        calls = "；".join(
            f"{fam} 最接近破例 {results[fam]['stats']['closest_tight_call']['id']}"
            f"（距最近保留题 {results[fam]['stats']['closest_tight_call']['dist_to_nearest_selected']}，"
            f"门槛 {results[fam]['stats']['tight_isolation_threshold']}）"
            for fam in NEW if results[fam]["stats"]["closest_tight_call"])
        L.append(f"贴边题剔除前后对比：候选池 1000 → {tot[2]}（{('，'.join(parts))}），"
                 f"{tot[1]} 道贴边题全部未入选（破例 0 题）；判定说明：{calls}——均未达到 "
                 "1.5× 破例门槛，不足以构成参数独特性。")
    else:
        exc = "；".join(f"{fam}: {', '.join(f'{tid}(距最近保留 {d})' for tid, d in results[fam]['stats']['tight_exceptions'].items())}"
                        for fam in NEW if results[fam]["stats"]["tight_exceptions"])
        L.append(f"贴边题剔除前后对比：候选池 1000 → {tot[2]}（{('，'.join(parts))}）；"
                 f"{tot[1]} 道贴边题中 {tot[8]} 题破例保留（已替换同分层内最近保留题）：{exc}。")
    nd = []
    for fam in NEW:
        for pr in results[fam]["stats"].get("near_dup_pairs", []):
            nd.append(f"{pr['a']}~{pr['b']}（保留 {pr['kept'] if pr['kept'] else '两题皆未选'}）")
    if nd:
        L.append("")
        L.append("近重复对处理（每对至多保 1 题）：" + "；".join(nd) + "。")
    L.append("")
    L.append("## 保留前后统计对比（分族）")
    for fam in NEW:
        L.append("")
        L += _family_stats_blocks(fam, results)
    L.append("## 每题结果与距离")
    L.append("")
    L.append("每题状态与距离同样记录在各族 `manifest.json` 的 `selected` / `selection` 字段"
             "（状态含 archived_tight / archived_near_duplicate / archived_diversity）。保留题 ID：")
    for fam in NEW:
        L.append("")
        L.append(f"- **{fam} 保留 {len(results[fam]['selected_ids'])} 题**："
                 f"{id_ranges(results[fam]['selected_ids'])}")
    L.append("")
    L.append("## 归档位置与自检")
    L.append("")
    L.append("- 未选题目目录原样移动至 `_archive_unselected/{sim_uplink,sim_latency,"
             "sim_storage,sim_harvest}/`（仅移动，不改内容）。")
    L.append("- 自检：每族 250 = 125 active + 125 archived；全库 2000 = 1000 active + 1000 "
             "archived（两批合计）；逐文件 sha256 守恒（仅四个新族 manifest.json 与本文件"
             "变化，老三族 manifest 字节不变）；`python3 bench/freeze.py --check` 不受影响。")
    L.append("")
    return "\n".join(L)


# --- main ---------------------------------------------------------------------------
def load_boundary(rel: str) -> tuple[set[str], list[tuple[str, str, str]]]:
    """Return (tight task ids, [(family, id_a, id_b)] near-duplicate pairs)."""
    path = BANK / rel
    if not path.is_file():
        raise SystemExit(f"missing audit file: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    tight = {r["id"] for r in data["tight_below_3x_tol"]}
    pairs = [(p["family"], p["a"], p["b"]) for p in data.get("near_duplicate_param_pairs", [])]
    return tight, pairs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true",
                        help="perform manifest updates, directory moves and SELECTION.md write "
                             "(default: dry-run, print summary only)")
    args = parser.parse_args()

    families = list(FAMILIES)        # all families, always: selection is pure
                                     # recomputation and SELECTION.md covers both batches

    results: dict[str, dict] = {}
    audits: dict[str, tuple[set[str], list[tuple[str, str, str]]]] = {}
    for family in families:
        spec = FAMILIES[family]
        if spec["boundary"] not in audits:
            audits[spec["boundary"]] = load_boundary(spec["boundary"])
        tight_ids, all_pairs = audits[spec["boundary"]]
        near_pairs = [(a, b) for fam, a, b in all_pairs if fam == family]
        manifest = json.loads((BANK / family / "manifest.json").read_text(encoding="utf-8"))
        results[family] = curate_family(family, manifest["tasks"], tight_ids, near_pairs)

    total_selected = sum(len(r["selected_ids"]) for r in results.values())
    n_tight = sum(r["stats"]["archived_tight"] + r["stats"]["archived_replaced"] for r in results.values())
    n_exc = sum(len(r["stats"]["tight_exceptions"]) for r in results.values())
    print(f"selected {total_selected} tasks; tight excluded: {n_tight}; exceptions: {n_exc}")
    for family in families:
        s = results[family]["stats"]
        print(f"  {family}: {s['n_selected']} kept / {s['n_archived']} archived "
              f"(tight {s['archived_tight']}, near-dup {s.get('archived_near_duplicate', 0)}, "
              f"diversity {s['archived_diversity']}); "
              f"min pairwise dist {s['min_pairwise_dist_before']} -> {s['min_pairwise_dist_after']}")

    if not args.apply:
        print("dry-run only; re-run with --apply to move directories and write manifests/SELECTION.md")
        return 0

    # snapshot hashes for the byte-conservation self-check, scoped to the paths
    # this tool touches (family dirs, archive, SELECTION.md). The verification*/
    # and pilot_check/ trees belong to other processes and may change concurrently.
    scopes = [BANK / fam for fam in FAMILIES] + [ARCHIVE, BANK / "SELECTION.md"]

    def file_hashes() -> dict[str, str]:
        out: dict[str, str] = {}
        for scope in scopes:
            if scope.is_file():
                out[str(scope.relative_to(BANK))] = hashlib.sha256(scope.read_bytes()).hexdigest()
            elif scope.is_dir():
                for p in sorted(scope.rglob("*")):
                    if p.is_file():
                        out[str(p.relative_to(BANK))] = hashlib.sha256(p.read_bytes()).hexdigest()
        return out
    before_hashes = file_hashes()

    manifests = {}
    for family in families:
        manifests[family] = update_manifest(family, results[family])

    # moves first (so a crash before manifest write leaves disk content untouched).
    # Both directions are handled: archive unselected tasks, and RESTORE tasks the
    # (possibly corrected) selection now keeps.
    moved = restored = 0
    for family in families:
        fam_dir = BANK / family
        dst_root = ARCHIVE / family
        dst_root.mkdir(parents=True, exist_ok=True)
        prefix = results[family]["tasks"][0]["id"].split("-")[0]
        for task in results[family]["tasks"]:
            tid = task["id"]
            keep = results[family]["status"][tid].startswith("selected")
            src = fam_dir / tid
            dst = dst_root / tid
            if keep:
                if src.is_dir():
                    pass
                elif dst.is_dir():
                    shutil.move(str(dst), str(src))
                    restored += 1
                else:
                    raise SystemExit(f"task directory missing both active and archived: {tid}")
            else:
                if src.is_dir():
                    if dst.exists():
                        raise SystemExit(f"archive target already exists: {dst}")
                    shutil.move(str(src), str(dst))
                    moved += 1
                elif dst.is_dir():
                    pass            # already archived by a previous run (idempotent)
                else:
                    raise SystemExit(f"task directory missing both active and archived: {tid}")
        active = sum(1 for p in fam_dir.iterdir() if p.is_dir() and p.name.startswith(prefix + "-"))
        archived = sum(1 for p in (ARCHIVE / family).iterdir() if p.is_dir())
        if active + archived != results[family]["stats"]["n_total"]:
            raise SystemExit(f"{family}: dir count mismatch {active}+{archived} "
                             f"!= {results[family]['stats']['n_total']}")
        if active != results[family]["stats"]["n_selected"]:
            raise SystemExit(f"{family}: active {active} != selected {results[family]['stats']['n_selected']}")
    print(f"moved {moved} task directories to {ARCHIVE}; restored {restored} back to family dirs")

    # write manifests after successful moves
    for family in families:
        (BANK / family / "manifest.json").write_text(dump_json(manifests[family]), encoding="utf-8")
    (BANK / "SELECTION.md").write_text(
        selection_md_batch1(results) + "\n" + selection_md_batch2(results) + "\n",
        encoding="utf-8")

    # self-check: file-count and hash conservation. Task files may RELOCATE
    # between the family dir and the archive (moves); their (task id, path
    # inside the task dir) and sha256 must be conserved. Non-task files must
    # not disappear; only the family manifests may change content and only
    # SELECTION.md may appear; legacy manifests must never change.
    after_hashes = file_hashes()

    task_re = re.compile(r"^(BAT|BLG|THM|SHR|LAT|CMP|HRV)-\d{4}$")

    def split(h: dict[str, str]) -> tuple[dict[tuple[str, str], str], dict[str, str]]:
        tasks: dict[tuple[str, str], str] = {}
        others: dict[str, str] = {}
        for rel, sha in h.items():
            parts = Path(rel).parts
            tid = sub = None
            if len(parts) >= 3 and not parts[0].startswith("_") and task_re.match(parts[1]):
                tid, sub = parts[1], "/".join(parts[2:])
            elif len(parts) >= 4 and parts[0] == "_archive_unselected" and task_re.match(parts[2]):
                tid, sub = parts[2], "/".join(parts[3:])
            if tid:
                tasks[(tid, sub)] = sha
            else:
                others[rel] = sha
        return tasks, others

    b_tasks, b_others = split(before_hashes)
    a_tasks, a_others = split(after_hashes)
    if len(before_hashes) != len(after_hashes):
        raise SystemExit(f"file count changed: {len(before_hashes)} -> {len(after_hashes)}")
    if b_tasks != a_tasks:
        diff = [k for k in set(b_tasks) | set(a_tasks) if b_tasks.get(k) != a_tasks.get(k)]
        raise SystemExit(f"task file content/path changed during moves (sample): {sorted(diff)[:10]}")
    disappeared = set(b_others) - set(a_others)
    appeared = set(a_others) - set(b_others) - {"SELECTION.md"}
    if disappeared or appeared:
        raise SystemExit(f"non-task files appeared/disappeared unexpectedly: "
                         f"{sorted(disappeared | appeared)}")
    allowed = {f"{fam}/manifest.json" for fam in families} | {"SELECTION.md"}
    changed = {p for p in b_others if b_others[p] != a_others.get(p)}
    if not changed <= allowed:
        raise SystemExit(f"unexpected content changes: {sorted(changed - allowed)}")
    legacy_changed = [p for p in changed if p.split("/")[0] in LEGACY and p.endswith("manifest.json")]
    if legacy_changed:
        raise SystemExit(f"legacy manifests must not change: {sorted(legacy_changed)}")
    n_active = sum(1 for fam in FAMILIES for p in (BANK / fam).iterdir() if p.is_dir()
                   and p.name.split("-")[0] in ("BAT", "BLG", "THM", "SHR", "LAT", "CMP", "HRV"))
    n_archived = sum(1 for fam in FAMILIES for p in (ARCHIVE / fam).iterdir() if p.is_dir())
    print(f"self-check OK: scoped files {len(after_hashes)} == {len(before_hashes)}; "
          f"tasks {n_active} active + {n_archived} archived = {n_active + n_archived}; "
          f"content changed only in: {sorted(changed)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
