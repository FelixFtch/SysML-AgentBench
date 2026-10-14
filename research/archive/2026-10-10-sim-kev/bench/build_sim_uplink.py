"""Deterministic SIM shared-uplink scheduling task generator (250 tasks, closed-form gold).

Family `sim_uplink` under bench/tasks_staging/t_sim_bank/sim_uplink/ (a new tree;
no existing file is read for writing or modified). Narrative: same synthetic
maritime ISR four-node world as the other t_sim_bank families - the USV and the
fixed-wing UAV both push their ISR products over ONE shared shore uplink
(relayed through the command ship) with total capacity C Mb/s. How the trunk is
shared is stated explicitly in every task: fixed quotas, or priority preemption
with either platform as the preempting (primary) one.

Model of the family (fluid uplink, all closed form, exact rational arithmetic):

    offered_i(t)  = unbounded while platform i has buffered data, else r_i(t)
    fixed quota   : alloc_usv = q, alloc_uav = C - q   (quotas never lend)
    preempt       : alloc_primary = C while its buffer is non-empty,
                    else min(r_primary, C);
                    alloc_secondary = C - alloc_primary
    sent_i(t)     = min(alloc_i(t), offered_i(t))                  [Mbit/s]
    d buf_i/dt    = r_i(t) - sent_i(t), clamped at zero            [Mbit/s]

Generation rates are piecewise constant (2 or 3 phases; at every phase boundary
exactly one platform changes rate), so every buffer and delivery curve is
piecewise linear and every gold number is a closed-form expression:

    demand_i      = backlog0_i + sum_phase r_i,phi * d_phi          [Mbit]
    delivered_i   = sum_segment sent_i * dt                         [Mbit]
    backlog_end_i = demand_i - delivered_i   (= buffer at window end)
    starved_i     = delivered_i < starvation_ratio * demand_i
    completion    = first time a buffer returns to zero after being
                    non-empty: t* = t0 + buf0 / (sent - rate) inside a
                    draining segment; null when no buffer clears

1 GB = 8000 Mbit. No language model is called anywhere: this file IS the answer
key. Re-running with the same seed reproduces the bank byte for byte (it wipes
only its own staging directory first). After writing, the script (a) re-simulates
every task with an independent one-second stepper that shares no event logic
with the piecewise solver and requires exact rational agreement, and (b)
re-parses every generated requirements.md and recomputes the gold from the
parsed text as a write/format check.

Acceptance margins (rejected draws are counted in manifest.json): starved
verdict at least max(0.05 GB, 3 x 2%) away from the ratio*demand edge for both
platforms; a clearing time at least 3 x 2 min from both window edges and from
the other platform's clearing time; delivered and end backlog either exactly
zero or >= 0.25 GB; demand >= 1.5 GB per platform; unique parameter vector
(normalized distance >= 0.12). The any-starved label is quota-balanced 125/125.

Each task folder SHR-NNNN/ contains:
  case.yaml, input/model.sysml, input/requirements.md,
  gold/answer.json, gold/assertions.yaml, gold/solution.md
plus manifest.json and index.jsonl in the family directory.
"""
from __future__ import annotations

import json
import math
import random
import re
import shutil
import sys
from fractions import Fraction
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "bench" / "tasks_staging" / "t_sim_bank" / "sim_uplink"

SEED = 20261010
N_TASKS = 250
N_ANY_STARVED = 125        # tasks where starved_usv or starved_uav is true

MB_PER_GB = 8000           # 1 GB = 8000 Mbit (stated in every requirements.md)
PLATFORMS = ("usv", "uav")
PLATFORM_TEXT = {"usv": "USV", "uav": "UAV"}

# --- tolerance contract (mirrored into gold/assertions.yaml) -------------------
TOL_REL = 0.02             # +/- 2 % relative on every GB quantity
TOL_GB_ABS = 0.05          # absolute floor so an exact 0 stays scoreable
TOL_TIME_MIN = 2           # +/- 2 min absolute on completion_time_min
BOOL_EXACT = True

# --- margin rules: gold must sit >= 3x the tolerance band from any decision edge
MARGIN_MULT = 3.0
MARGIN_MIN_GB = Fraction(1, 20)          # 0.05 GB absolute floor
VOLUME_FLOOR_MB = 2000                   # 0.25 GB: nonzero delivered/backlog floor
DEMAND_MIN_MB = 12000                    # 1.5 GB of demand per platform
EDGE_TIME_S = 3 * TOL_TIME_MIN * 60      # clearing >= 6 min from both window edges

# --- parameter space ------------------------------------------------------------
CAP_MIN, CAP_MAX = 10, 80                # Mb/s total uplink capacity
RATE_MIN, RATE_MAX = 2, 40               # Mb/s per platform per phase
RATE_CHANGE_GAP = 4                      # Mb/s minimum change at a boundary
WINDOW_Q_MIN, WINDOW_Q_MAX = 4, 24       # window in 15-min steps: 1.0 .. 6.0 h
PHASE_Q_MIN = 2                          # every phase >= 30 min
QUOTA_MIN = 2                            # fixed quotas leave each side >= 2 Mb/s
B0_STEP_MB, B0_MAX_STEPS = 400, 60       # initial backlog 0 .. 3.0 GB on 0.05 GB grid
B0_NONZERO_PROB = 0.6
STARVE_RATIOS = (50, 60, 70, 80)         # percent of demand, stated per task

# (scheme, n_phases, any_starved) -> quota. Totals: 250 tasks, 125 starved.
QUOTAS = {
    ("fixed", 2, True): 25, ("fixed", 2, False): 25,
    ("fixed", 3, True): 20, ("fixed", 3, False): 20,
    ("preempt_usv", 2, True): 25, ("preempt_usv", 2, False): 25,
    ("preempt_usv", 3, True): 15, ("preempt_usv", 3, False): 15,
    ("preempt_uav", 2, True): 25, ("preempt_uav", 2, False): 25,
    ("preempt_uav", 3, True): 15, ("preempt_uav", 3, False): 15,
}

DEDUP_MIN_DIST = 0.12
MAX_SAMPLES = 1_500_000

SCHEME_TEXT = {
    "fixed": "fixed quotas",
    "preempt_usv": "priority preemption (USV preempts)",
    "preempt_uav": "priority preemption (UAV preempts)",
}


# --- exact rounding helpers (Fraction -> fixed decimals, half up) ----------------
def rnd(x: Fraction, places: int) -> float:
    scaled = x * (10 ** places) + Fraction(1, 2)
    return float(math.floor(scaled)) / (10 ** places)


def f2(x: Fraction) -> str:
    return f"{rnd(x, 2):.2f}"


def gb(mb: Fraction) -> float:
    return rnd(Fraction(mb) / MB_PER_GB, 2)


def mins(seconds: Fraction) -> str:
    return f"{rnd(seconds / 60, 2):.2f}"


# --- sampling ---------------------------------------------------------------------
def sample(rng: random.Random, scheme: str, n_phases: int) -> dict:
    capacity = rng.randrange(CAP_MIN, CAP_MAX + 1)
    window_q = rng.randrange(max(WINDOW_Q_MIN, PHASE_Q_MIN * n_phases), WINDOW_Q_MAX + 1)
    if n_phases == 2:
        first = rng.randrange(PHASE_Q_MIN, window_q - PHASE_Q_MIN + 1)
        parts_q = [first, window_q - first]
    else:
        first = rng.randrange(PHASE_Q_MIN, window_q - 2 * PHASE_Q_MIN + 1)
        second = rng.randrange(PHASE_Q_MIN, window_q - first - PHASE_Q_MIN + 1)
        parts_q = [first, second, window_q - first - second]
    rates = {plat: [rng.randrange(RATE_MIN, RATE_MAX + 1)] for plat in PLATFORMS}
    for _ in range(n_phases - 1):
        changed = rng.choice(PLATFORMS)
        while True:
            new = rng.randrange(RATE_MIN, RATE_MAX + 1)
            if abs(new - rates[changed][-1]) >= RATE_CHANGE_GAP:
                break
        for plat in PLATFORMS:
            rates[plat].append(new if plat == changed else rates[plat][-1])
    p = {
        "scheme": scheme,
        "n_phases": n_phases,
        "capacity": capacity,
        "window_q": window_q,
        "parts_q": parts_q,
        "rates": rates,
        "quota_usv": rng.randrange(QUOTA_MIN, capacity - QUOTA_MIN + 1) if scheme == "fixed" else None,
        "backlog0_mb": {},
        "starve_pct": rng.choice(STARVE_RATIOS),
    }
    for plat in PLATFORMS:
        steps = rng.randrange(1, B0_MAX_STEPS + 1) if rng.random() < B0_NONZERO_PROB else 0
        p["backlog0_mb"][plat] = steps * B0_STEP_MB
    return p


# --- closed form: piecewise-linear fluid uplink ------------------------------------
def allocation(scheme: str, quota_usv: int, capacity: int, primary: str,
               buf: dict, rates_now: dict) -> dict:
    """Allocation cap per platform for the current instant (rates, buffers)."""
    if scheme == "fixed":
        return {"usv": quota_usv, "uav": capacity - quota_usv}
    secondary = "uav" if primary == "usv" else "usv"
    if buf[primary] > 0:
        return {primary: capacity, secondary: 0}
    used = min(rates_now[primary], capacity)
    return {primary: used, secondary: capacity - used}


def simulate(p: dict) -> dict:
    """Exact event-driven fluid simulation. Times in s (Fraction), volumes in Mbit."""
    scheme = p["scheme"]
    capacity = p["capacity"]
    primary = {"preempt_usv": "usv", "preempt_uav": "uav"}.get(scheme)
    durations_s = [Fraction(q * 900) for q in p["parts_q"]]
    buf = {plat: Fraction(p["backlog0_mb"][plat]) for plat in PLATFORMS}
    t = Fraction(0)
    segments = []
    drains = {"usv": [], "uav": []}
    for phase_idx in range(p["n_phases"]):
        rates_now = {plat: p["rates"][plat][phase_idx] for plat in PLATFORMS}
        t_end = t + durations_s[phase_idx]
        guard = 0
        while t < t_end:
            guard += 1
            if guard > 16:
                raise AssertionError("segment guard tripped")
            alloc = allocation(scheme, p["quota_usv"], capacity, primary, buf, rates_now)
            sent = {}
            slope = {}
            for plat in PLATFORMS:
                if buf[plat] > 0:
                    sent[plat] = alloc[plat]
                else:
                    sent[plat] = min(alloc[plat], rates_now[plat])
                slope[plat] = rates_now[plat] - sent[plat]
            hits = []
            for plat in PLATFORMS:
                if buf[plat] > 0 and slope[plat] < 0:
                    hits.append((t + buf[plat] / -slope[plat], plat))
            if hits:
                earliest = min(h for h, _ in hits)
                t_next = min(t_end, earliest)
                drained_now = [plat for h, plat in hits if h == t_next]
            else:
                t_next = t_end
                drained_now = []
            seg = {
                "phase": phase_idx + 1, "t0": t, "t1": t_next,
                "rates": dict(rates_now), "alloc": alloc, "sent": sent,
                "buf0": dict(buf), "drains": drained_now,
            }
            dt = t_next - t
            for plat in PLATFORMS:
                buf[plat] += slope[plat] * dt
                if drained_now and plat in drained_now:
                    assert buf[plat] == 0
            seg["buf1"] = dict(buf)
            segments.append(seg)
            for plat in drained_now:
                drains[plat].append(t_next)
            t = t_next

    delivered = {plat: Fraction(0) for plat in PLATFORMS}
    for seg in segments:
        dt = seg["t1"] - seg["t0"]
        for plat in PLATFORMS:
            delivered[plat] += seg["sent"][plat] * dt
    demand = {plat: Fraction(p["backlog0_mb"][plat]) for plat in PLATFORMS}
    for phase_idx in range(p["n_phases"]):
        for plat in PLATFORMS:
            demand[plat] += p["rates"][plat][phase_idx] * durations_s[phase_idx]
    for plat in PLATFORMS:
        assert buf[plat] == demand[plat] - delivered[plat], "buffer identity failed"
    ratio = Fraction(p["starve_pct"], 100)
    starved = {plat: delivered[plat] < ratio * demand[plat] for plat in PLATFORMS}
    all_drains = [(t_hit, plat) for plat in PLATFORMS for t_hit in drains[plat]]
    completion_s = min((t_hit for t_hit, _ in all_drains), default=None)
    return {
        "segments": segments, "drains": drains,
        "delivered_mb": delivered, "demand_mb": demand, "buf_end_mb": dict(buf),
        "starved": starved, "completion_s": completion_s,
        "window_s": Fraction(p["window_q"] * 900),
    }


# --- independent check: per-second recurrence, no event logic ----------------------
def stepper_check(p: dict, s: dict) -> None:
    """Independent 1-second recurrence. Within one second every rate profile is
    piecewise linear with at most one breakpoint (a buffer clearing), so each
    second integrates in closed form; this shares no event logic with the
    piecewise solver and must agree with it exactly (rational equality)."""
    scheme = p["scheme"]
    capacity = p["capacity"]
    primary = {"preempt_usv": "usv", "preempt_uav": "uav"}.get(scheme)
    secondary = "uav" if primary == "usv" else "usv"
    total_s = p["window_q"] * 900
    bounds = []
    acc = 0
    for q in p["parts_q"]:
        acc += q * 900
        bounds.append(acc)
    buf = {plat: Fraction(p["backlog0_mb"][plat]) for plat in PLATFORMS}
    delivered = {plat: Fraction(0) for plat in PLATFORMS}
    clears = {"usv": [], "uav": []}

    def plain_second(plat: str, alloc: int, rate: int) -> None:
        """One platform, allocation constant over the whole second."""
        sent = min(alloc, buf[plat] + rate)
        if buf[plat] > 0 and alloc > rate:
            drain_rate = alloc - rate
            if buf[plat] <= drain_rate:
                clears[plat].append(Fraction(sec) + buf[plat] / drain_rate)
        buf[plat] += rate - sent
        delivered[plat] += sent

    for sec in range(total_s):
        phase_idx = sum(1 for b in bounds if sec >= b)
        r = {plat: p["rates"][plat][phase_idx] for plat in PLATFORMS}
        if scheme == "fixed":
            plain_second("usv", p["quota_usv"], r["usv"])
            plain_second("uav", capacity - p["quota_usv"], r["uav"])
            continue
        if buf[primary] == 0:
            pri_sent = min(r[primary], capacity)
            delivered[primary] += pri_sent
            buf[primary] += r[primary] - pri_sent
            plain_second(secondary, capacity - pri_sent, r[secondary])
            continue
        # primary is buffered at second start
        if buf[primary] > capacity - r[primary]:
            delivered[primary] += capacity          # no clear this second
            buf[primary] += r[primary] - capacity
            buf[secondary] += r[secondary]          # secondary blocked, still sensing
            continue
        theta = buf[primary] / (capacity - r[primary])      # clear inside (0, 1]
        clears[primary].append(Fraction(sec) + theta)
        delivered[primary] += buf[primary] + r[primary]     # drain, then live
        buf[primary] = Fraction(0)
        lam = capacity - min(r[primary], capacity)          # leftover after theta
        buf_s = buf[secondary] + r[secondary] * theta
        if lam > r[secondary] and buf_s > 0 and buf_s <= (lam - r[secondary]) * (1 - theta):
            t2 = theta + buf_s / (lam - r[secondary])       # secondary clears too
            clears[secondary].append(Fraction(sec) + t2)
            delivered[secondary] += buf_s + r[secondary] * (1 - theta)
            buf[secondary] = Fraction(0)
        else:
            sent = min(lam * (1 - theta), buf_s + r[secondary] * (1 - theta))
            delivered[secondary] += sent
            # buf[secondary] still holds the start-of-second value; buf_s is the
            # value at theta, so assign (not accumulate) the post-theta balance
            buf[secondary] = buf_s + r[secondary] * (1 - theta) - sent

    for plat in PLATFORMS:
        assert delivered[plat] == s["delivered_mb"][plat], f"stepper delivered {plat}"
        assert buf[plat] == s["buf_end_mb"][plat], f"stepper backlog {plat}"
        assert (delivered[plat] < Fraction(p["starve_pct"], 100) * s["demand_mb"][plat]) == s["starved"][plat]
        assert clears[plat] == s["drains"][plat], f"stepper clears {plat}"


# --- accept / reject rules ----------------------------------------------------------
def acceptable(p: dict, s: dict, vector: list[float], accepted: list[list[float]]) -> str | None:
    ratio = Fraction(p["starve_pct"], 100)
    for plat in PLATFORMS:
        demand = s["demand_mb"][plat]
        delivered = s["delivered_mb"][plat]
        if demand < DEMAND_MIN_MB:
            return None, "demand_small"
        if delivered != 0 and delivered < VOLUME_FLOOR_MB:
            return None, "delivered_small"
        backlog = demand - delivered
        if backlog != 0 and backlog < VOLUME_FLOOR_MB:
            return None, "backlog_small"
        edge = ratio * demand
        margin = abs(delivered - edge)
        band = max(MARGIN_MIN_GB * MB_PER_GB,
                   Fraction(round(MARGIN_MULT * TOL_REL * 100), 100) * max(delivered, edge))
        if margin < band:
            return None, "margin_starved"
    completion = s["completion_s"]
    if completion is not None:
        if completion < EDGE_TIME_S or s["window_s"] - completion < EDGE_TIME_S:
            return None, "margin_time"
    both = [s["drains"][plat] for plat in PLATFORMS]
    if both[0] and both[1]:
        gap = min(abs(a - b) for a in both[0] for b in both[1])
        if gap < EDGE_TIME_S:
            return None, "clear_ambiguity"
    for other in accepted:
        dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(vector, other)))
        if dist < DEDUP_MIN_DIST:
            return None, "dedup"
    return ("true" if (s["starved"]["usv"] or s["starved"]["uav"]) else "false"), None


def param_vector(p: dict) -> list[float]:
    vec = [p["capacity"] / 80.0]
    for plat in PLATFORMS:
        rates = p["rates"][plat]
        vec += [r / 40.0 for r in rates] + [0.0] * (3 - len(rates))
    if p["scheme"] == "fixed":
        vec += [p["quota_usv"] / p["capacity"], 0.0, 0.5]
    else:
        vec += [0.5, 1.0, 1.0 if p["scheme"] == "preempt_usv" else 0.0]
    vec += [p["backlog0_mb"]["usv"] / 24000.0, p["backlog0_mb"]["uav"] / 24000.0]
    vec += [p["window_q"] / 24.0]
    bounds = []
    acc = 0
    for q in p["parts_q"]:
        acc += q
        bounds.append(acc / 24.0)
    vec += bounds + [0.0] * (3 - len(bounds))
    vec += [p["starve_pct"] / 100.0]
    return vec


# --- writers -------------------------------------------------------------------------
def scheme_rule_md(p: dict) -> str:
    capacity = p["capacity"]
    if p["scheme"] == "fixed":
        quota_uav = capacity - p["quota_usv"]
        return f"""## Allocation rule (fixed quotas, constant for the whole window)

1. The shore uplink capacity is split into two fixed quotas: the USV gets
   {p['quota_usv']} Mbit/s and the UAV gets {quota_uav} Mbit/s (the quotas sum to
   the {capacity} Mbit/s capacity). The quotas hold for the whole window and
   unused quota is never reassigned to the other platform.
2. While a platform's buffer is non-empty it transmits at exactly its quota.
3. When a platform's buffer is empty it transmits at min(quota, live rate): a
   platform cannot ship data before its sensors produce it.
4. Buffer dynamics per platform: d(buffer)/dt = live rate − transmitted rate,
   and the buffer never goes below zero."""
    primary, secondary = ("USV", "UAV") if p["scheme"] == "preempt_usv" else ("UAV", "USV")
    return f"""## Allocation rule (priority preemption, the {primary} is primary)

1. While the {primary}'s buffer is non-empty, the {primary} transmits at the
   full uplink capacity {capacity} Mbit/s and the {secondary} transmits 0 Mbit/s.
2. Once the {primary}'s buffer is empty, the {primary} transmits at
   min({capacity} Mbit/s, its live rate) and the {secondary} may use the leftover
   capacity ({capacity} Mbit/s minus what the {primary} is using).
3. A platform with a non-empty buffer transmits at its allocation; a platform
   with an empty buffer transmits at min(allocation, live rate).
4. Buffer dynamics per platform: d(buffer)/dt = live rate − transmitted rate,
   and the buffer never goes below zero.

The priority order is fixed for the whole window: primary = {primary}
(stated as a comment on `shoreUplink` in `model.sysml`)."""


def requirements_md(task_id: str, p: dict, s: dict) -> str:
    rows = []
    start = 0
    for idx, q in enumerate(p["parts_q"]):
        end = start + q * 15
        rows.append(f"| {idx + 1} | {start} | {end} | {p['rates']['usv'][idx]} | {p['rates']['uav'][idx]} |")
        start = end
    table = "\n".join(rows)
    alloc_line = (
        f"- USV uplink quota: {p['quota_usv']} Mbit/s\n- UAV uplink quota: {p['capacity'] - p['quota_usv']} Mbit/s"
        if p["scheme"] == "fixed"
        else f"- Preempting platform: {'USV' if p['scheme'] == 'preempt_usv' else 'UAV'}")
    return f"""# {task_id} — synthetic, not an RTX specification

SIM shared-uplink scheduling for the USV and the fixed-wing UAV in the maritime
ISR scenario (the four-node system: unmanned surface vessel, fixed-wing UAV,
command ship, shore station). Both platforms collect ISR data on station and
push it over the SAME shared shore uplink - the USV via the command ship relay,
the UAV via the same trunk - so the two streams compete for one capacity. This
is a closed-form piecewise-linear bookkeeping question. It does not ask you to
write or edit SysML. The file `model.sysml` in this folder carries the same
parameters as a SysML v2 model; the numbers in this document are authoritative.

## Shared shore uplink

- Total uplink capacity C: {p['capacity']} Mbit/s
- Allocation scheme: {SCHEME_TEXT[p['scheme']]}
{alloc_line}
- Mission window: 0 to {p['window_q'] * 15} min ({p['window_q'] * 15 / 60:.1f} h)
- Initial buffered data at t = 0: USV {p['backlog0_mb']['usv']} Mbit, UAV {p['backlog0_mb']['uav']} Mbit
  (collected before the window opened; 0 Mbit means the platform starts empty)
- Starvation threshold: a platform is starved iff it delivers less than {p['starve_pct']} % of its demand

## Sensor generation schedule (rates constant within each phase)

| Phase | Start (min) | End (min) | USV rate (Mbit/s) | UAV rate (Mbit/s) |
|-------|-------------|-----------|-------------------|-------------------|
{table}

{scheme_rule_md(p)}

## Quantities asked

- `delivered_usv_gb` / `delivered_uav_gb`: total Mbit each platform ships over
  the whole window, reported in GB, 2 decimals.
- Demand per platform = initial buffer + everything generated during the window.
- `starved_usv` / `starved_uav`: delivered < {p['starve_pct']} % of demand (strict).
- `backlog_end_usv_gb` / `backlog_end_uav_gb`: demand − delivered, i.e. the
  buffer content at window end, GB, 2 decimals.
- `completion_time_min`: the first time any platform's buffer returns to zero
  after having been non-empty during the window (the initial buffer or earlier
  accumulation both count as non-empty). Rounded to the nearest minute; null if
  no platform clears its buffer inside the window.

## Units and conversions

- 1 GB = 8000 Mbit.
- A rate of R Mbit/s held for m minutes moves R × 60 × m Mbit.
- Rates and quotas are in Mbit/s; volumes are Mbit divided by 8000 to get GB.

## Reply with exactly one JSON object

{{"delivered_usv_gb": <number>, "delivered_uav_gb": <number>,
  "starved_usv": <true|false>, "starved_uav": <true|false>,
  "backlog_end_usv_gb": <number>, "backlog_end_uav_gb": <number>,
  "completion_time_min": <int or null>}}
"""


def answer_json(task_id: str, p: dict, s: dict) -> str:
    completion = None
    if s["completion_s"] is not None:
        completion = int(rnd(s["completion_s"] / 60, 0))
    payload = {
        "task_id": task_id,
        "delivered_usv_gb": gb(s["delivered_mb"]["usv"]),
        "delivered_uav_gb": gb(s["delivered_mb"]["uav"]),
        "starved_usv": s["starved"]["usv"],
        "starved_uav": s["starved"]["uav"],
        "backlog_end_usv_gb": gb(s["buf_end_mb"]["usv"]),
        "backlog_end_uav_gb": gb(s["buf_end_mb"]["uav"]),
        "completion_time_min": completion,
    }
    return json.dumps(payload, indent=2) + "\n"


def assertions_yaml(task_id: str, p: dict, s: dict) -> str:
    completion = None
    if s["completion_s"] is not None:
        completion = int(rnd(s["completion_s"] / 60, 0))
    checks = {
        "task_id": task_id,
        "package": "SharedUplink",
        "family": "sim_uplink",
        "answer_mode": "json",
        "tolerances": {"gb_rel": TOL_REL, "gb_abs_zero": TOL_GB_ABS,
                       "time_abs_min": TOL_TIME_MIN, "boolean_exact": BOOL_EXACT},
        "checks": {
            "delivered_usv_gb": {"gold": gb(s["delivered_mb"]["usv"]),
                                 "rel_tol": TOL_REL, "abs_tol_gb": TOL_GB_ABS},
            "delivered_uav_gb": {"gold": gb(s["delivered_mb"]["uav"]),
                                 "rel_tol": TOL_REL, "abs_tol_gb": TOL_GB_ABS},
            "starved_usv": {"gold": s["starved"]["usv"], "exact": True},
            "starved_uav": {"gold": s["starved"]["uav"], "exact": True},
            "backlog_end_usv_gb": {"gold": gb(s["buf_end_mb"]["usv"]),
                                   "rel_tol": TOL_REL, "abs_tol_gb": TOL_GB_ABS},
            "backlog_end_uav_gb": {"gold": gb(s["buf_end_mb"]["uav"]),
                                   "rel_tol": TOL_REL, "abs_tol_gb": TOL_GB_ABS},
            "completion_time_min": {"gold": completion, "abs_tol_min": TOL_TIME_MIN,
                                    "null_exact": True},
        },
    }
    return yaml.safe_dump(checks, sort_keys=False)


def model_sysml(task_id: str, p: dict) -> str:
    quota_block = ""
    if p["scheme"] == "fixed":
        quota_block = (f"        attribute quotaUsv : BinaryDigitRateValue = {p['quota_usv']} ['Mbit/s'];\n"
                       f"        attribute quotaUav : BinaryDigitRateValue = {p['capacity'] - p['quota_usv']} ['Mbit/s'];"
                       " /* fixed quotas, sum to capacity; unused quota is not reassigned */\n")
    primary_comment = {
        "fixed": "/* fixed-quota sharing: each platform keeps its own quota */",
        "preempt_usv": "/* priority preemption: the USV is primary and preempts the UAV */",
        "preempt_uav": "/* priority preemption: the UAV is primary and preempts the USV */",
    }[p["scheme"]]
    rate_attrs = "\n".join(
        f"        attribute {plat}RatePhase{i} : BinaryDigitRateValue = {rate} ['Mbit/s'];"
        for plat in PLATFORMS for i, rate in enumerate(p["rates"][plat], start=1))
    dur_attrs = "\n".join(
        f"        attribute phase{i}Duration : TimeValue = {q * 900} [s];"
        for i, q in enumerate(p["parts_q"], start=1))
    demand_lines = []
    for plat in PLATFORMS:
        camel = "Usv" if plat == "usv" else "Uav"
        terms = "\n            + ".join(
            f"WindowVolume({plat}RatePhase{i}, phase{i}Duration)"
            for i in range(1, p["n_phases"] + 1))
        demand_lines.append(
            f"        attribute {plat}Produced : StorageCapacityValue =\n"
            f"            {terms};\n"
            f"        attribute {plat}Demand : StorageCapacityValue =\n"
            f"            TotalDemand(initialBacklog{camel}, {plat}Produced);")
    demand_block = "\n".join(demand_lines)
    return f"""package SharedUplink {{
    /* Synthetic maritime ISR SIM task (family sim_uplink). Numbers are not RTX specifications. */
    private import SI::*;
    private import ISQ::*;
    private import ISQInformation::*;

    attribute <'Mbit'> megabit : StorageCapacityUnit = 1000000 * SI::bit;
    attribute <'Mbit/s'> 'megabit per second' : BinaryDigitRateUnit = 1000000 * SI::'bit/s';

    calc def WindowVolume {{
        in rate : BinaryDigitRateValue;
        in duration : TimeValue;
        return volume : StorageCapacityValue = rate * duration;
    }}

    calc def TotalDemand {{
        in buffered : StorageCapacityValue;
        in produced : StorageCapacityValue;
        return demand : StorageCapacityValue = buffered + produced;
    }}

    part def ShoreUplink {{
        attribute capacity : BinaryDigitRateValue = {p['capacity']} ['Mbit/s'];
{quota_block}        attribute initialBacklogUsv : StorageCapacityValue = {float(p['backlog0_mb']['usv'])} ['Mbit'];
        attribute initialBacklogUav : StorageCapacityValue = {float(p['backlog0_mb']['uav'])} ['Mbit'];

{rate_attrs}

{dur_attrs}

        attribute starvationFraction : ScalarValues::Real = {p['starve_pct'] / 100:.2f};

{demand_block}
    }}

    part shoreUplink : ShoreUplink {{
        /* USV and UAV ISR products share this shore trunk via the command ship relay. */
        {primary_comment}
    }}

    requirement def FairDeliveryRequirement {{
        subject uplink : ShoreUplink;
        doc /* Each platform delivers at least the starvation fraction of its mission demand over the shared uplink. */
    }}
}}
"""


def solution_md(task_id: str, p: dict, s: dict) -> str:
    primary = {"preempt_usv": "usv", "preempt_uav": "uav"}.get(p["scheme"])
    lines = [f"# {task_id} — closed-form solution (human-checkable arithmetic)",
             "",
             "No simulation tool is needed: rates, quotas and the preemption state are",
             "piecewise constant, so both buffers and both delivery curves are piecewise",
             "linear with breakpoints only at phase boundaries and buffer-clearing",
             "instants.",
             "",
             f"- Total uplink capacity C = {p['capacity']} Mbit/s; scheme = {SCHEME_TEXT[p['scheme']]}.",
             f"- Window [0, {p['window_q'] * 15}] min; initial buffers: USV {p['backlog0_mb']['usv']} Mbit,",
             f"  UAV {p['backlog0_mb']['uav']} Mbit; starvation ratio {p['starve_pct']} % of demand.",
             "",
             "Allocation trace (one row per linear segment; alloc is the capacity cap,",
             "sent is what the platform actually transmits; buffers in Mbit):",
             "",
             "| Seg | t0 (min) | t1 (min) | USV rate | USV alloc | USV sent | UAV rate | UAV alloc | UAV sent |",
             "|-----|----------|----------|----------|-----------|----------|----------|-----------|----------|"]
    for i, seg in enumerate(s["segments"], start=1):
        lines.append(
            f"| {i} | {mins(seg['t0'])} | {mins(seg['t1'])} "
            f"| {seg['rates']['usv']} | {seg['alloc']['usv']} | {seg['sent']['usv']} "
            f"| {seg['rates']['uav']} | {seg['alloc']['uav']} | {seg['sent']['uav']} |")
    lines += ["",
              "Per-segment shipped volume (Δship = sent × Δt) and buffer evolution",
              "(d(buffer)/dt = rate − sent):",
              "",
              "| Seg | Δt (min) | Δship USV (Mbit) | Δship UAV (Mbit) | buf USV end (Mbit) | buf UAV end (Mbit) |",
              "|-----|----------|------------------|------------------|-------------------|-------------------|"]
    bufs = {"usv": Fraction(p["backlog0_mb"]["usv"]), "uav": Fraction(p["backlog0_mb"]["uav"])}
    for i, seg in enumerate(s["segments"], start=1):
        dt_s = seg["t1"] - seg["t0"]
        for plat in PLATFORMS:
            bufs[plat] += (seg["rates"][plat] - seg["sent"][plat]) * dt_s
        lines.append(
            f"| {i} | {mins(dt_s)} | {f2(seg['sent']['usv'] * dt_s)} | {f2(seg['sent']['uav'] * dt_s)} "
            f"| {f2(bufs['usv'])} | {f2(bufs['uav'])} |")
    for plat in PLATFORMS:
        delivered = s["delivered_mb"][plat]
        demand = s["demand_mb"][plat]
        edge = Fraction(p["starve_pct"], 100) * demand
        name = PLATFORM_TEXT[plat]
        lines += ["",
                  f"## {name}",
                  "",
                  f"- Demand = initial buffer + produced = {f2(demand)} Mbit = {f2(demand / MB_PER_GB)} GB.",
                  f"- Delivered = Σ sent × Δt = {f2(delivered)} Mbit → **{gb(delivered):.2f} GB**.",
                  f"- Starvation edge = {p['starve_pct']} % × demand = {f2(edge)} Mbit; delivered is "
                  f"{'below' if s['starved'][plat] else 'at or above'} it → `starved_{plat}` = "
                  f"**{str(s['starved'][plat]).lower()}**.",
                  f"- backlog_end = demand − delivered = {f2(demand - delivered)} Mbit → "
                  f"**{gb(demand - delivered):.2f} GB**."]
    lines += ["", "## Completion", ""]
    if s["completion_s"] is None:
        lines += ["No platform brings a non-empty buffer back to zero inside the window,",
                  "so `completion_time_min` = **null**."]
    else:
        plat_hits = [(t_hit, plat) for plat in PLATFORMS for t_hit in s["drains"][plat]]
        t_first, plat_first = min(plat_hits)
        for t_hit, plat in sorted(plat_hits):
            seg = next(seg for seg in s["segments"] if seg["drains"] and plat in seg["drains"]
                       and seg["t1"] == t_hit)
            drain_rate = seg["sent"][plat] - seg["rates"][plat]
            lines.append(
                f"- {PLATFORM_TEXT[plat]} buffer clears at t* = t0 + buf0/(sent − rate) = "
                f"{f2(seg['t0'])} s + {f2(seg['buf0'][plat])} Mbit / {drain_rate} Mbit/s = "
                f"{f2(t_hit)} s = {mins(t_hit)} min.")
        lines += [f"The earliest of these is the {PLATFORM_TEXT[plat_first]} at {mins(t_first)} min →",
                  f"`completion_time_min` = **{int(rnd(t_first / 60, 0))}** (rounded to the nearest minute)."]
    margins = []
    for plat in PLATFORMS:
        edge = Fraction(p["starve_pct"], 100) * s["demand_mb"][plat]
        margins.append(abs(s["delivered_mb"][plat] - edge))
    lines += ["",
              f"Margins: the smaller starvation margin is {f2(min(margins))} Mbit "
              f"({f2(min(margins) / MB_PER_GB)} GB), far outside the ±2 % tolerance band,",
              "so both verdicts are unambiguous.", ""]
    return "\n".join(lines)


def case_yaml(task_id: str) -> str:
    return yaml.safe_dump({
        "id": task_id, "type": "SIM", "scenario_family": "t_sim_bank", "split": "staging",
        "package": "SharedUplink", "synthetic": True, "status": "generated",
        "generator": "bench/build_sim_uplink.py", "seed": SEED,
        "answer_mode": "json",
    }, sort_keys=False)


# --- independent re-check: recompute gold from the written requirements.md ----------
PHASE_ROW_RE = re.compile(r"^\| (\d+) \| (\d+) \| (\d+) \| (\d+) \| (\d+) \|$")


def parse_requirements(folder: Path) -> dict:
    text = (folder / "input" / "requirements.md").read_text(encoding="utf-8")
    first = text.splitlines()[0]
    if not re.fullmatch(r"# SHR-\d{4} — synthetic, not an RTX specification", first):
        raise SystemExit(f"{folder.name}: first line is not the RTX marker: {first!r}")
    capacity = int(re.search(r"- Total uplink capacity C: (\d+) Mbit/s", text).group(1))
    window = int(re.search(r"- Mission window: 0 to (\d+) min", text).group(1))
    b0 = re.search(r"- Initial buffered data at t = 0: USV (\d+) Mbit, UAV (\d+) Mbit", text)
    ratio = int(re.search(r"delivers less than (\d+) % of its demand", text).group(1))
    quota = re.search(r"- USV uplink quota: (\d+) Mbit/s", text)
    preempt = re.search(r"- Preempting platform: (USV|UAV)", text)
    if quota:
        scheme, quota_usv = "fixed", int(quota.group(1))
    elif preempt:
        scheme = "preempt_usv" if preempt.group(1) == "USV" else "preempt_uav"
        quota_usv = None
    else:
        raise SystemExit(f"{folder.name}: no allocation rule line found")
    rates = {"usv": [], "uav": []}
    parts_q = []
    for line in text.splitlines():
        match = PHASE_ROW_RE.match(line)
        if match:
            rates["usv"].append(int(match.group(4)))
            rates["uav"].append(int(match.group(5)))
            parts_q.append((int(match.group(3)) - int(match.group(2))) // 15)
    if not parts_q or window != sum(parts_q) * 15:
        raise SystemExit(f"{folder.name}: phase table does not cover the window")
    return {
        "scheme": scheme, "n_phases": len(parts_q), "capacity": capacity,
        "window_q": window // 15, "parts_q": parts_q, "rates": rates,
        "quota_usv": quota_usv, "backlog0_mb": {"usv": int(b0.group(1)), "uav": int(b0.group(2))},
        "starve_pct": ratio,
    }


def verify_from_disk(folder: Path) -> dict:
    p = parse_requirements(folder)
    s = simulate(p)
    answer = json.loads((folder / "gold" / "answer.json").read_text(encoding="utf-8"))
    completion = None if s["completion_s"] is None else int(rnd(s["completion_s"] / 60, 0))
    rebuilt = {
        "delivered_usv_gb": gb(s["delivered_mb"]["usv"]),
        "delivered_uav_gb": gb(s["delivered_mb"]["uav"]),
        "starved_usv": s["starved"]["usv"],
        "starved_uav": s["starved"]["uav"],
        "backlog_end_usv_gb": gb(s["buf_end_mb"]["usv"]),
        "backlog_end_uav_gb": gb(s["buf_end_mb"]["uav"]),
        "completion_time_min": completion,
    }
    for field, value in rebuilt.items():
        if answer[field] != value:
            raise SystemExit(f"{folder.name}: {field} mismatch\nanswer: {answer[field]}\nrebuilt: {value}")
    # cross-check model.sysml carries the same capacity / phase durations
    model = (folder / "input" / "model.sysml").read_text(encoding="utf-8")
    if f"attribute capacity : BinaryDigitRateValue = {p['capacity']} ['Mbit/s'];" not in model:
        raise SystemExit(f"{folder.name}: model.sysml capacity mismatch")
    for i, q in enumerate(p["parts_q"], start=1):
        if f"attribute phase{i}Duration : TimeValue = {q * 900} [s];" not in model:
            raise SystemExit(f"{folder.name}: model.sysml phase{i} duration mismatch")
    return {"any_starved": rebuilt["starved_usv"] or rebuilt["starved_uav"],
            "completion": rebuilt["completion_time_min"]}


# --- main ------------------------------------------------------------------------------
def main() -> int:
    if not str(OUT).startswith(str(ROOT / "bench" / "tasks_staging")):
        raise SystemExit("refusing to write outside bench/tasks_staging")
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    rng = random.Random(SEED)
    slots = [key for key, count in QUOTAS.items() for _ in range(count)]
    rng.shuffle(slots)
    assert len(slots) == N_TASKS

    accepted_vectors: list[list[float]] = []
    tasks: list[dict] = []
    rejected: dict[str, int] = {}
    rejected_samples: list[dict] = []
    attempts = 0
    for index, (scheme, n_phases, want_starved) in enumerate(slots, start=1):
        task_id = f"SHR-{index:04d}"
        while True:
            attempts += 1
            if attempts > MAX_SAMPLES:
                raise SystemExit(f"sampling budget exhausted at {task_id}")
            p = sample(rng, scheme, n_phases)
            s = simulate(p)
            label, reason = acceptable(p, s, param_vector(p), accepted_vectors)
            if reason is not None:
                rejected[reason] = rejected.get(reason, 0) + 1
                if len(rejected_samples) < 400:
                    rejected_samples.append({"scheme": scheme, "phases": n_phases, "reason": reason})
                continue
            if (label == "true") != want_starved:
                rejected["label_mismatch"] = rejected.get("label_mismatch", 0) + 1
                continue
            accepted_vectors.append(param_vector(p))
            break
        stepper_check(p, s)

        folder = OUT / task_id
        (folder / "input").mkdir(parents=True)
        (folder / "gold").mkdir()
        (folder / "case.yaml").write_text(case_yaml(task_id), encoding="utf-8")
        (folder / "input" / "model.sysml").write_text(model_sysml(task_id, p), encoding="utf-8")
        (folder / "input" / "requirements.md").write_text(requirements_md(task_id, p, s), encoding="utf-8")
        (folder / "gold" / "answer.json").write_text(answer_json(task_id, p, s), encoding="utf-8")
        (folder / "gold" / "assertions.yaml").write_text(assertions_yaml(task_id, p, s), encoding="utf-8")
        (folder / "gold" / "solution.md").write_text(solution_md(task_id, p, s), encoding="utf-8")

        completion = None if s["completion_s"] is None else int(rnd(s["completion_s"] / 60, 0))
        tasks.append({
            "id": task_id,
            "platform": "usv+uav",
            "path": f"bench/tasks_staging/t_sim_bank/sim_uplink/{task_id}",
            "scheme": scheme,
            "params": {
                "capacity_mbps": p["capacity"],
                "quota_usv_mbps": p["quota_usv"],
                "primary": {"preempt_usv": "usv", "preempt_uav": "uav"}.get(scheme),
                "window_min": p["window_q"] * 15,
                "phase_bounds_min": [sum(p["parts_q"][:i + 1]) * 15 for i in range(p["n_phases"])],
                "rates_mbps": {"usv": p["rates"]["usv"], "uav": p["rates"]["uav"]},
                "initial_backlog_mb": dict(p["backlog0_mb"]),
                "starve_pct": p["starve_pct"],
            },
            "gold": {
                "delivered_gb": {"usv": gb(s["delivered_mb"]["usv"]), "uav": gb(s["delivered_mb"]["uav"])},
                "starved": {"usv": s["starved"]["usv"], "uav": s["starved"]["uav"]},
                "backlog_end_gb": {"usv": gb(s["buf_end_mb"]["usv"]), "uav": gb(s["buf_end_mb"]["uav"])},
                "completion_time_min": completion,
            },
            "difficulty": {
                "phases": p["n_phases"],
                "level": {("fixed", 2): "L1", ("fixed", 3): "L2",
                          ("preempt", 2): "L2", ("preempt", 3): "L3"}[
                    ("fixed" if scheme == "fixed" else "preempt", p["n_phases"])],
            },
        })

    # independent re-check of every task from disk
    for entry in tasks:
        disk = verify_from_disk(OUT / entry["id"])
        assert disk["any_starved"] == (entry["gold"]["starved"]["usv"] or entry["gold"]["starved"]["uav"])
        assert disk["completion"] == entry["gold"]["completion_time_min"]

    index_lines = [json.dumps({"id": t["id"], "type": "SIM", "platform": t["platform"],
                               "scheme": t["scheme"], "path": t["path"]})
                   for t in tasks]
    (OUT / "index.jsonl").write_text("\n".join(index_lines) + "\n", encoding="utf-8")

    n_starved = sum(1 for t in tasks if t["gold"]["starved"]["usv"] or t["gold"]["starved"]["uav"])
    scheme_hist: dict[str, int] = {}
    phase_hist: dict[int, int] = {}
    level_hist: dict[str, int] = {}
    completion_hist = {"present": 0, "null": 0}
    for t in tasks:
        scheme_hist[t["scheme"]] = scheme_hist.get(t["scheme"], 0) + 1
        phase_hist[t["difficulty"]["phases"]] = phase_hist.get(t["difficulty"]["phases"], 0) + 1
        level_hist[t["difficulty"]["level"]] = level_hist.get(t["difficulty"]["level"], 0) + 1
        completion_hist["present" if t["gold"]["completion_time_min"] is not None else "null"] += 1
    min_dist = min(
        math.sqrt(sum((a - b) ** 2 for a, b in zip(v, w)))
        for i, v in enumerate(accepted_vectors) for w in accepted_vectors[i + 1:])
    manifest = {
        "family": "sim_uplink",
        "generator": "bench/build_sim_uplink.py",
        "seed": SEED,
        "count": len(tasks),
        "narrative": {
            "scenario": "maritime ISR four-node world (unmanned surface vessel, fixed-wing UAV, command ship, shore station); the USV and the UAV share one shore uplink relayed via the command ship",
            "schemes": SCHEME_TEXT,
            "platform": "usv+uav (both platforms appear in every task)",
        },
        "closed_form": {
            "alloc_fixed": "alloc_usv = q, alloc_uav = C - q (quotas constant, never lend)",
            "alloc_preempt": "alloc_primary = C while primary buffer non-empty else min(r_primary, C); alloc_secondary = C - alloc_primary",
            "sent_i": "min(alloc_i, offered_i), offered unbounded while buffer non-empty else live rate",
            "dbuf_i_dt": "rate_i - sent_i, clamped at 0",
            "demand_i_mb": "backlog0_i + sum_phase rate_i_phi * duration_phi",
            "delivered_i_mb": "sum_segment sent_i * dt",
            "backlog_end_i": "demand_i - delivered_i",
            "starved_i": "delivered_i < starve_pct/100 * demand_i",
            "completion": "t* = t0 + buf0/(sent - rate) at the first buffer clearing; null if none",
            "gb": "Mbit / 8000",
        },
        "parameter_space": {
            "capacity_mbps": [CAP_MIN, CAP_MAX],
            "platform_rate_mbps": [RATE_MIN, RATE_MAX],
            "rate_change_gap_mbps": RATE_CHANGE_GAP,
            "rate_changes": "exactly one platform changes rate at every phase boundary",
            "window_h": [WINDOW_Q_MIN * 15 / 60, WINDOW_Q_MAX * 15 / 60],
            "window_grid_min": 15,
            "min_phase_min": PHASE_Q_MIN * 15,
            "phases": [2, 3],
            "quota_usv_mbps": ["[2, C-2]", "fixed scheme only"],
            "initial_backlog_gb": [0.0, B0_MAX_STEPS * B0_STEP_MB / MB_PER_GB],
            "backlog_grid_gb": B0_STEP_MB / MB_PER_GB,
            "starve_pct": list(STARVE_RATIOS),
            "schemes": ["fixed", "preempt_usv", "preempt_uav"],
        },
        "tolerances": {"gb_rel": TOL_REL, "gb_abs_zero": TOL_GB_ABS,
                       "time_abs_min": TOL_TIME_MIN, "boolean_exact": BOOL_EXACT},
        "constraints": {
            "dedup_min_normalized_distance": DEDUP_MIN_DIST,
            "margin_multiplier": MARGIN_MULT,
            "starved_margin_min_gb": float(MARGIN_MIN_GB),
            "completion_edge_margin_min": EDGE_TIME_S / 60,
            "clear_time_separation_min": EDGE_TIME_S / 60,
            "nonzero_volume_floor_gb": VOLUME_FLOOR_MB / MB_PER_GB,
            "demand_min_gb": DEMAND_MIN_MB / MB_PER_GB,
            "any_starved_true": n_starved,
            "any_starved_false": len(tasks) - n_starved,
            "no_llm": "all gold values computed by the closed form in this generator",
        },
        "stats": {
            "scheme": scheme_hist, "phases": phase_hist, "level": level_hist,
            "completion_time": completion_hist,
            "min_pairwise_distance": round(min_dist, 4),
            "sampling_attempts": attempts,
            "rejected": rejected,
        },
        "rejected_params": {"count": sum(rejected.values()), "reasons": rejected,
                            "samples": rejected_samples},
        "tasks": tasks,
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(f"wrote {len(tasks)} tasks to {OUT}")
    print(f"any-starved true/false: {n_starved}/{len(tasks) - n_starved}")
    print(f"scheme: {scheme_hist}")
    print(f"phases: {dict(sorted(phase_hist.items()))}  levels: {level_hist}")
    print(f"completion_time present/null: {completion_hist['present']}/{completion_hist['null']}")
    print(f"min pairwise param distance: {min_dist:.4f} (threshold {DEDUP_MIN_DIST})")
    print(f"sampling attempts: {attempts}  rejected: {rejected}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
