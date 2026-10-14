"""Deterministic SIM solar-harvest family task generator (250 tasks, closed-form gold).

Family `sim_harvest` under bench/tasks_staging/t_sim_bank/ (a new tree next to
sim_battery; nothing in bench/tasks/, FREEZE.md, or any existing file is read for
writing or modified). Same maritime ISR four-node world as sim_battery: the
platform is a USV or a fixed-wing UAV with a solar array (deterministic ~6:4
split by task number), and duty rows use the maritime mode names.

The family's distinction from sim_battery: SoC is NOT monotone. Each duty row
carries a load draw AND a solar input, so the net power can be positive or
negative and SoC(t) rises or falls segment by segment. The question tests
piecewise bookkeeping, not monotone extrapolation:

    net_k    = solar_k - load_k                       [W]
    E(t_k)   = capacity * soc_start + sum_{i<=k} net_i * d_i   [Wh]
    soc_k(%) = 100 * E(t_k) / capacity

Because SoC is piecewise linear, the minimum sits at t = 0 or at a row
boundary, so `min_soc_pct`, its earliest time `min_soc_at_min`, and the
protection verdict `breached = (min soc < protection line)` are all closed form.

No language model is called anywhere: this file IS the answer key. Re-running
with the same seed reproduces the bank byte for byte (it wipes only its own
staging directory first). After writing, the script re-parses every generated
requirements.md duty table and recomputes the gold from the parsed text as an
independent write/format check.

Shape quotas (the family's value): >= 40 % of tasks are "dip" tasks whose
minimum is mid-mission while the end SoC recovers; the rest split into fall
(min at mission end), rise (min at t = 0) and mid_flat (mid minimum, small
recovery). Breached true/false is balanced 125/125 via a shuffled plan.

Each task folder HRV-NNNN/ contains:
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
OUT = ROOT / "bench" / "tasks_staging" / "t_sim_bank" / "sim_harvest"

SEED = 20261010
N_TASKS = 250

# --- shape plan: where the minimum sits, and the recovery split -----------------
# dip       : mid-mission minimum, soc_end - min_soc >= DIP_GAP_PP (the family's
#             distinguishing "dips mid-mission, then recovers" task)
# fall      : minimum at mission end (classic monotone-ish drain)
# rise      : minimum at t = 0 (net charging dominates later rows)
# mid_flat  : mid-mission minimum but the recovery stays below DIP_GAP_PP
SHAPE_PLAN = {"dip": 105, "fall": 65, "rise": 45, "mid_flat": 35}
SHAPE_TRUE = {"dip": 55, "fall": 40, "rise": 0, "mid_flat": 30}   # breached=true counts
DIP_GAP_PP = 4.0        # pp of recovery above the minimum required for "dip"

MODES = ("idle", "cruise", "transmit")

# --- maritime ISR narrative binding (scenario/maritime-isr four-node world) ----
MODE_LABEL = {"idle": "loiter", "cruise": "transit", "transmit": "transmit to shore"}
PLATFORM_TEXT = {
    "usv": "an unmanned surface vessel (USV) with a deck-mounted solar array",
    "uav": "the fixed-wing UAV with a wing-mounted solar array",
}
PLATFORM_BATTERY = {"usv": "USV battery bank", "uav": "UAV battery"}
PLATFORM_SOLAR = {"usv": "USV solar array", "uav": "UAV solar array"}


def platform_for(index: int) -> str:
    """Deterministic USV:UAV ~= 6:4 split (task number mod 5 < 3 -> USV)."""
    return "usv" if index % 5 < 3 else "uav"


# --- tolerance contract (mirrored into gold/assertions.yaml) -----------------
TOL_REL = 0.02        # +/- 2% relative on every SoC percent value
TOL_TIME_MIN = 2      # +/- 2 min absolute on key-point times
BOOL_EXACT = True     # breached must match exactly

# --- margin rules: gold must sit >= 3x tolerance band from any decision edge --
MARGIN_MIN_PP = 2.0       # |min_soc - protection| >= 2.0 pp ...
MARGIN_FACTOR = 3.0       # ... and >= 3 * TOL_REL * min_soc (3x the tolerance band)
ARGMIN_MIN_PP = 1.5       # second-lowest key SoC >= min + max(1.5, 3x band):
#                          the argmin vertex must be unambiguous under tolerance
SOC_FLOOR_PCT = 3         # every key-point SoC within [3, 96] %
SOC_CEIL_PCT = 96

# --- parameter space ----------------------------------------------------------
CAP_MIN, CAP_MAX, CAP_STEP = 300, 1500, 50        # Wh
SOC0_MIN, SOC0_MAX, SOC0_STEP = 40, 95, 5         # %
PROT_MIN, PROT_MAX = 5, 20                         # % protection line
P_IDLE = (5, 45)                                    # W tier loads
P_CRUISE = (40, 110)                                # W
P_TRANSMIT = (90, 150)                              # W
P_MIN_GAP = 10                                      # W between tier loads
SOLAR_MAX, SOLAR_STEP = 120, 5                      # W per-segment solar input
SOLAR_ZERO_P = 0.35                                 # per-segment night probability
DUR_STEP_H = Fraction(1, 10)                        # durations on a 0.1 h grid
DUR_MIN, DUR_MAX = 3, 35                            # grid steps: 0.3 .. 3.5 h
MISSION_MIN_H, MISSION_MAX_H = Fraction(2), Fraction(12)
SEG_CHOICES = (3, 4, 5, 6, 7)

DEDUP_MIN_DIST = 0.12   # min normalized Euclidean distance between param vectors
MAX_SAMPLES = 3_000_000

MODE_POWER_ATTR = {"idle": "idlePower", "cruise": "cruisePower", "transmit": "transmitPower"}


# --- exact rounding helpers (Fraction -> fixed decimals, half up) -------------
def rnd(x: Fraction, places: int) -> float:
    scaled = x * (10 ** places) + Fraction(1, 2)
    return float(math.floor(scaled)) / (10 ** places)


def f1(x: Fraction) -> str:
    return f"{rnd(x, 1):.1f}"


def f2(x: Fraction) -> str:
    return f"{rnd(x, 2):.2f}"


def fh(x: Fraction) -> str:
    """Duration in hours on the 0.1 h grid."""
    return f"{float(x):.1f}"


def fp(x: Fraction) -> str:
    """Signed net power / energy with an explicit '+' when positive."""
    return f"+{float(x):g}" if x > 0 else f"{float(x):g}"


# --- sampling ------------------------------------------------------------------
def sample(rng: random.Random) -> dict:
    capacity = rng.randrange(CAP_MIN, CAP_MAX + 1, CAP_STEP)
    soc0 = rng.randrange(SOC0_MIN, SOC0_MAX + 1, SOC0_STEP)
    protect = rng.randrange(PROT_MIN, PROT_MAX + 1)
    n_seg = rng.choice(SEG_CHOICES)
    p_idle = rng.randrange(*P_IDLE)
    p_cruise = rng.randrange(max(P_CRUISE[0], p_idle + P_MIN_GAP), P_CRUISE[1] + 1)
    p_tx = rng.randrange(max(P_TRANSMIT[0], p_cruise + P_MIN_GAP), P_TRANSMIT[1] + 1)
    powers = {"idle": p_idle, "cruise": p_cruise, "transmit": p_tx}
    labels = list(rng.sample(MODES, 3)) + [rng.choice(MODES) for _ in range(n_seg - 3)]
    while True:
        solar = [0 if rng.random() < SOLAR_ZERO_P
                 else SOLAR_STEP * rng.randrange(1, SOLAR_MAX // SOLAR_STEP + 1)
                 for _ in range(n_seg)]
        # every mission passes at least one zero-harvest row (night / eclipse)
        # and at least one row where the array out-harvests the load (charging)
        if any(s == 0 for s in solar) and any(s > powers[m] for s, m in zip(solar, labels)):
            break
    while True:
        steps = [rng.randrange(DUR_MIN, DUR_MAX + 1) for _ in range(n_seg)]
        total = Fraction(sum(steps), 10)
        if MISSION_MIN_H <= total <= MISSION_MAX_H:
            break
    return {
        "capacity_wh": capacity,
        "soc_start_pct": soc0,
        "protect_pct": protect,
        "n_seg": n_seg,
        "powers_w": powers,
        "solar_w": solar,
        "durations_h": [Fraction(s, 10) for s in steps],
        "labels": labels,
    }


# --- closed form ----------------------------------------------------------------
def solve(p: dict) -> dict:
    """Piecewise-linear SoC that may rise or fall. Exact rational arithmetic."""
    cap = p["capacity_wh"]
    energy = Fraction(cap) * Fraction(p["soc_start_pct"], 100)
    t_min = 0
    key_points = [(0, "start", Fraction(p["soc_start_pct"], 1))]
    per_segment = []
    for i, (mode, solar, dur) in enumerate(zip(p["labels"], p["solar_w"], p["durations_h"]), start=1):
        load = p["powers_w"][mode]
        net = Fraction(solar - load)
        seg_wh = net * dur
        energy += seg_wh
        t_min += dur * 60
        soc = 100 * energy / Fraction(cap)
        key_points.append((t_min, mode, soc))
        per_segment.append({"i": i, "mode": mode, "load_w": load, "solar_w": solar,
                            "net_w": net, "dur_h": dur, "seg_wh": seg_wh,
                            "energy_wh": energy, "t_end_min": t_min, "soc": soc})
    soc_end = key_points[-1][2]
    # piecewise linear => the minimum is at t = 0 or at a row boundary;
    # ties are impossible by the argmin-margin acceptance rule, take earliest anyway
    min_idx = min(range(len(key_points)), key=lambda k: key_points[k][2])
    min_t, min_soc = key_points[min_idx][0], key_points[min_idx][2]
    return {
        "e0_wh": Fraction(cap) * Fraction(p["soc_start_pct"], 100),
        "net_wh": sum((seg["seg_wh"] for seg in per_segment), Fraction(0)),
        "soc_end": soc_end,
        "key_points": key_points,
        "per_segment": per_segment,
        "min_soc": min_soc,
        "min_at_min": min_t,
        "min_idx": min_idx,
        "breached": min_soc < Fraction(p["protect_pct"]),
    }


# --- accept / reject rules --------------------------------------------------------
def classify(p: dict, s: dict) -> str | None:
    """Return the sample's shape if usable, else None.

    Rejects samples whose gold sits closer than 3x the tolerance band to the
    protection decision edge, samples whose minimum vertex is not unambiguous
    under the tolerance, samples whose SoC leaves the [floor, ceil] band, and
    samples whose reported minimum time could be confused with a neighbouring
    row boundary.
    """
    socs = [kp[2] for kp in s["key_points"]]
    if any(soc < SOC_FLOOR_PCT or soc > SOC_CEIL_PCT for soc in socs):
        return None
    min_soc = s["min_soc"]
    band = MARGIN_FACTOR * TOL_REL * min_soc
    if abs(min_soc - Fraction(p["protect_pct"])) + Fraction(1, 10 ** 9) < max(MARGIN_MIN_PP, band):
        return None
    second_min = min(soc for i, soc in enumerate(socs) if i != s["min_idx"])
    if second_min - min_soc < max(ARGMIN_MIN_PP, band):
        return None
    times = [kp[0] for kp in s["key_points"]]
    if any(0 < abs(s["min_at_min"] - t) < MARGIN_FACTOR * TOL_TIME_MIN for t in times):
        return None
    t_end = times[-1]
    if s["min_at_min"] == 0:
        return "rise"
    if s["min_at_min"] == t_end:
        return "fall"
    return "dip" if s["soc_end"] - min_soc >= DIP_GAP_PP else "mid_flat"


def param_vector(p: dict) -> list[float]:
    """Normalized parameter vector for dedup (fixed width, solar/durations zero-padded)."""
    vec = [
        p["capacity_wh"] / 1000.0,
        p["soc_start_pct"] / 100.0,
        p["protect_pct"] / 100.0,
        p["powers_w"]["idle"] / 100.0,
        p["powers_w"]["cruise"] / 100.0,
        p["powers_w"]["transmit"] / 100.0,
    ]
    vec += [s / 100.0 for s in p["solar_w"]]
    vec += [float(d) / 4.0 for d in p["durations_h"]]
    width = max(SEG_CHOICES)
    vec += [0.0] * (2 * width - p["n_seg"])
    return vec


# --- writers ----------------------------------------------------------------------
def model_sysml(task_id: str, p: dict, s: dict) -> str:
    seg_attrs = "\n".join(
        f"        attribute seg{i}Load : PowerValue = {p['powers_w'][mode]} [W];\n"
        f"        attribute seg{i}Solar : PowerValue = {p['solar_w'][i - 1]} [W];\n"
        f"        attribute seg{i}Duration : TimeValue = {fh(d)} [h];"
        for i, (mode, d) in enumerate(zip(p["labels"], p["durations_h"]), start=1))
    net_terms = "\n            + ".join(
        f"NetEnergy(seg{seg['i']}Load, seg{seg['i']}Solar, seg{seg['i']}Duration)"
        for seg in s["per_segment"])
    return f"""package HarvestNetEnergy {{
    private import SI::*;
    private import ISQ::*;

    calc def NetEnergy {{
        in load : PowerValue;
        in solar : PowerValue;
        in duration : TimeValue;
        return net : EnergyValue = (solar - load) * duration;
    }}

    calc def HarvestBalance {{
        in stored : EnergyValue;
        in net : EnergyValue;
        return balance : EnergyValue = stored + net;
    }}

    calc def SoC {{
        in remaining : EnergyValue;
        in capacity : EnergyValue;
        return soc : ScalarValues::Real = remaining / capacity;
    }}

    constraint def ProtectionConstraint {{
        in soc : ScalarValues::Real;
        in socMin : ScalarValues::Real;
        soc >= socMin
    }}

    part def ISRPlatform {{
        attribute capacity : EnergyValue = {p['capacity_wh']} ['W⋅h'];
        attribute socStart : ScalarValues::Real = {p['soc_start_pct'] / 100:.2f};
        attribute socProtect : ScalarValues::Real = {p['protect_pct'] / 100:.2f};

        attribute idlePower : PowerValue = {p['powers_w']['idle']} [W];
        attribute cruisePower : PowerValue = {p['powers_w']['cruise']} [W];
        attribute transmitPower : PowerValue = {p['powers_w']['transmit']} [W];

{seg_attrs}

        attribute netEnergy : EnergyValue =
            {net_terms};
        attribute socEnd : ScalarValues::Real =
            SoC(HarvestBalance(capacity * socStart, netEnergy), capacity);

        assert constraint protection : ProtectionConstraint {{
            in soc = socEnd;
            in socMin = ISRPlatform::socProtect;
        }}
    }}

    requirement def ProtectionRequirement {{
        subject platform : ISRPlatform;
        attribute soc : ScalarValues::Real;
        attribute socMin : ScalarValues::Real;
        require constraint {{ soc >= socMin }}
    }}

    analysis def NetEnergyAnalysis {{
        subject platform : ISRPlatform;
        requirement protection : ProtectionRequirement;
        return socEnd : ScalarValues::Real;
        objective protectionObjective {{
            require protection {{
                :>> soc = NetEnergyAnalysis::socEnd;
                :>> socMin = platform.socProtect;
            }}
        }}
    }}
}}
"""


def requirements_md(task_id: str, p: dict, s: dict, platform: str) -> str:
    rows = []
    start = Fraction(0)
    for seg in s["per_segment"]:
        rows.append(f"| {seg['i']} | {MODE_LABEL[seg['mode']]} | {seg['load_w']} | {seg['solar_w']} | "
                    f"{int(start)} | {int(seg['t_end_min'])} | {fh(seg['dur_h'])} |")
        start = seg["t_end_min"]
    table = "\n".join(rows)
    platform_sentence = (
        f"This task covers only the {PLATFORM_BATTERY[platform]} and its "
        f"{PLATFORM_SOLAR[platform]}; the command ship and the shore station "
        "appear as the downlink destinations in the mission story."
        if platform == "usv" else
        "This task covers only the UAV battery and its solar array; the command "
        "ship and the shore station appear as the downlink destinations in the "
        "mission story.")
    return f"""# {task_id} — synthetic, not an RTX specification

SIM net-energy bookkeeping with solar harvesting for {PLATFORM_TEXT[platform]} in
the maritime ISR scenario (the four-node system: unmanned surface vessel,
fixed-wing UAV, command ship, shore station). {platform_sentence}

This is a closed-form energy bookkeeping question. It does not ask you to write
or edit SysML. The file `model.sysml` in this folder carries the same parameters
as a SysML v2 model; the numbers in this document are authoritative.

## Battery and solar array

- Capacity: {p['capacity_wh']} Wh
- Initial SoC at t = 0: {p['soc_start_pct']} % of capacity ({p['soc_start_pct'] / 100:.2f})
- Protection line: {p['protect_pct']} % of capacity. SoC must never fall below
  this line at any instant of the mission; crossing it even once means the
  protection line is breached and the platform must be recovered.

## Mission duty cycle (rows are sequential; the mission starts at t = 0 min)

| # | Mode               | Load (W) | Solar (W) | Start (min) | End (min) | Duration (h) |
|---|--------------------|----------|-----------|-------------|-----------|--------------|
{table}

Mode names (maritime ISR wording) map one-to-one to the electrical tiers and to
the attribute names in `model.sysml`: loiter = minimal station-keeping draw
(`idlePower`), transit = cruise draw (`cruisePower`), transmit to shore =
downlink draw while imagery is relayed to the command ship and shore station
(`transmitPower`). `Load` is the power the platform draws from the battery
during that row; `Solar` is the electrical power the solar array feeds into the
battery during that row (0 = night or eclipse: the array delivers nothing).

## Units and conversion rules

- Energy is in watt-hours (Wh). During one row the battery gains
  (solar − load) × duration Wh; the net is negative while the load outruns the
  array and positive while the array out-harvests the load. Minutes convert at
  1 h = 60 min.
- SoC is stored energy as a percent of capacity:
  `soc_pct(t) = 100 × (E(0) + harvested_net(0..t)) / capacity`, with
  `E(0) = capacity × initial_soc`.
- SoC is NOT monotone here: it rises during rows where solar exceeds the load
  and falls during the others, so do not extrapolate a single trend. The
  battery is an ideal energy tank: no rate limits, no self-discharge, no
  clipping below full. Power is constant during each row and changes only at
  row boundaries, so SoC(t) is piecewise linear.
- The minimum SoC is therefore attained at t = 0 or at the end of some row.
- Round `soc_end_pct` to 1 decimal, `min_soc_pct` to 2 decimals, and report
  times as whole minutes after mission start.

## Reply with exactly one JSON object

{{"soc_end_pct": <number>, "min_soc_pct": <number>, "min_soc_at_min": <int>,
  "breached": <true|false>,
  "key_points": [{{"t_min": <int>, "mode": "<start or mode name>", "soc_pct": <number>}}, ...]}}

- `soc_end_pct`: SoC at the end of the last duty row, percent, 1 decimal.
- `min_soc_pct`: the lowest SoC reached at any instant of the mission, percent,
  2 decimals.
- `min_soc_at_min`: the earliest time (whole minutes after mission start) at
  which that lowest SoC is attained.
- `breached`: true iff the SoC fell strictly below {float(p['protect_pct']):.1f} %
  at any instant of the mission (equivalently, iff `min_soc_pct` is below the
  protection line).
- `key_points`: one entry at t = 0 with mode "start", then one entry at the end
  of every duty row (mode = that row's mode name), in time order, each with the
  SoC at that instant. That is {p['n_seg'] + 1} entries.
"""


def answer_json(task_id: str, p: dict, s: dict) -> str:
    payload = {
        "task_id": task_id,
        "soc_end_pct": rnd(s["soc_end"], 1),
        "min_soc_pct": rnd(s["min_soc"], 2),
        "min_soc_at_min": int(s["min_at_min"]),
        "breached": s["breached"],
        "key_points": [
            {"t_min": int(t), "mode": MODE_LABEL.get(mode, mode), "soc_pct": rnd(soc, 2)}
            for t, mode, soc in s["key_points"]
        ],
    }
    return json.dumps(payload, indent=2) + "\n"


def assertions_yaml(task_id: str, p: dict, s: dict) -> str:
    checks = {
        "task_id": task_id,
        "package": "HarvestNetEnergy",
        "family": "sim_harvest",
        "answer_mode": "json",
        "tolerances": {"soc_rel": TOL_REL, "time_abs_min": TOL_TIME_MIN, "boolean_exact": BOOL_EXACT},
        "checks": {
            "soc_end_pct": {"gold": rnd(s["soc_end"], 1), "rel_tol": TOL_REL},
            "min_soc_pct": {"gold": rnd(s["min_soc"], 2), "rel_tol": TOL_REL},
            "min_soc_at_min": {"gold": int(s["min_at_min"]), "abs_tol_min": TOL_TIME_MIN},
            "breached": {"gold": s["breached"], "exact": True},
            "key_points": [
                {"t_min": {"gold": int(t), "abs_tol_min": TOL_TIME_MIN},
                 "soc_pct": {"gold": rnd(soc, 2), "rel_tol": TOL_REL}}
                for t, _mode, soc in s["key_points"]
            ],
            "key_point_count": {"gold": p["n_seg"] + 1, "exact": True},
        },
    }
    return yaml.safe_dump(checks, sort_keys=False)


def solution_md(task_id: str, p: dict, s: dict) -> str:
    cap = p["capacity_wh"]
    e0 = s["e0_wh"]
    lines = [f"# {task_id} — closed-form solution (human-checkable arithmetic)",
             "",
             "No simulation is needed: net power is constant inside each row, so",
             "SoC(t) is piecewise linear and every extremum sits at t = 0 or at a",
             "row boundary. Here the SoC is NOT monotone: rows with solar > load",
             "charge the battery, the others drain it.",
             "",
             f"- Capacity C = {cap} Wh; initial SoC = {p['soc_start_pct']} % →",
             f"  E(0) = C × {p['soc_start_pct'] / 100:.2f} = {f1(e0)} Wh.",
             f"- Protection line = {p['protect_pct']} % of capacity.",
             "",
             "Per-row bookkeeping: net = solar − load, ΔE = net × duration, then the",
             "running stored energy and SoC = 100 × E / C:",
             "",
             "| # | Mode | Load (W) | Solar (W) | Net (W) | d (h) | ΔE (Wh) | E (Wh) | SoC (%) | t_end (min) |",
             "|---|------|----------|-----------|---------|-------|---------|--------|---------|-------------|"]
    for seg in s["per_segment"]:
        lines.append(
            f"| {seg['i']} | {MODE_LABEL[seg['mode']]} | {seg['load_w']} | {seg['solar_w']} "
            f"| {fp(seg['net_w'])} | {fh(seg['dur_h'])} | {fp(seg['seg_wh'])} | {f1(seg['energy_wh'])} "
            f"| {f2(seg['soc'])} | {int(seg['t_end_min'])} |")
    net_total = s["net_wh"]
    lines += [
        "",
        f"Total net energy = {f1(net_total)} Wh (sum of the ΔE column; each term is",
        "(solar − load) × hours, so charging rows carry a plus and draining rows a minus).",
        f"E at mission end = E(0) + total = {f1(e0)} {fp(net_total)} = {f1(e0 + net_total)} Wh.",
        f"soc_end = 100 × {f1(e0 + net_total)} / {cap} = {f2(s['soc_end'])} % → reported to 1 decimal as "
        f"**{f1(s['soc_end'])} %**.",
        "",
        "Minimum: SoC is piecewise linear, so the minimum is one of the vertices",
        "(t = 0 or a row end). Scanning the SoC column and t = 0:",
        "",
        "| t (min) | Mode | SoC (%) |",
        "|---------|------|---------|"]
    for t, mode, soc in s["key_points"]:
        marker = "  ← minimum" if (t, mode, soc) == s["key_points"][s["min_idx"]] else ""
        lines.append(f"| {int(t)} | {MODE_LABEL.get(mode, mode)} | {f2(soc)}{marker} |")
    if s["min_idx"] == 0:
        min_sentence = (f"min_soc = **{f2(s['min_soc'])} %**, first attained at t = **0 min** "
                        "(the start itself: every later vertex is higher).")
    else:
        min_sentence = (f"min_soc = **{f2(s['min_soc'])} %**, first attained at t = "
                        f"**{int(s['min_at_min'])} min** (the end of row {s['min_idx']} of {p['n_seg']}).")
    second_min = min(soc for i, (_t, _m, soc) in enumerate(s["key_points"]) if i != s["min_idx"])
    lines += [
        "",
        min_sentence,
        "",
        f"breached: {f2(s['min_soc'])} % {'<' if s['breached'] else '≥'} "
        f"{float(p['protect_pct']):.1f} % → **{str(s['breached']).lower()}**.",
        "",
        "Check against the tolerance contract: |min_soc − protection| = "
        f"{f2(abs(s['min_soc'] - Fraction(p['protect_pct'])))} pp and the second-lowest "
        f"vertex sits {f2(second_min - s['min_soc'])} pp above the minimum, both well "
        "clear of the ±2% relative band, so the protection verdict and the argmin "
        "vertex are unambiguous.",
        "",
    ]
    return "\n".join(lines)


def case_yaml(task_id: str) -> str:
    return yaml.safe_dump({
        "id": task_id, "type": "SIM", "scenario_family": "t_sim_bank", "split": "staging",
        "package": "HarvestNetEnergy", "synthetic": True, "status": "generated",
        "generator": "bench/build_sim_harvest.py", "seed": SEED,
        "answer_mode": "json",
    }, sort_keys=False)


# --- independent re-check: recompute gold from the written requirements.md --------
ROW_RE = re.compile(
    r"^\| (\d+) \| (transmit to shore|loiter|transit) \| (\d+) \| (\d+) \| (\d+) \| (\d+) \| (\d+\.\d) \|$")


def verify_from_disk(folder: Path) -> dict:
    text = (folder / "input" / "requirements.md").read_text(encoding="utf-8")
    first = text.splitlines()[0]
    if not re.fullmatch(r"# HRV-\d{4} — synthetic, not an RTX specification", first):
        raise SystemExit(f"{folder.name}: requirements.md first line is not the RTX marker: {first!r}")
    cap = int(re.search(r"- Capacity: (\d+) Wh", text).group(1))
    soc0 = int(re.search(r"- Initial SoC at t = 0: (\d+) %", text).group(1))
    protect = int(re.search(r"- Protection line: (\d+) %", text).group(1))
    rows = []
    for line in text.splitlines():
        match = ROW_RE.match(line)
        if match:
            label = match.group(2)
            load, solar = int(match.group(3)), int(match.group(4))
            start, end = int(match.group(5)), int(match.group(6))
            dur = Fraction(match.group(7))
            rows.append((label, load, solar, start, end, dur))
    # start/end bookkeeping must be contiguous from 0
    t = 0
    for i, (_label, _load, _solar, start, end, dur) in enumerate(rows, start=1):
        if start != t or end != t + dur * 60:
            raise SystemExit(f"{folder.name}: row {i} time bookkeeping broken ({start}..{end} at t={t})")
        t = end
    energy = Fraction(cap) * Fraction(soc0, 100)
    keys = [(0, Fraction(soc0))]
    for label, load, solar, _start, end, dur in rows:
        energy += Fraction(solar - load) * dur
        keys.append((int(end), 100 * energy / Fraction(cap)))
    min_idx = min(range(len(keys)), key=lambda k: keys[k][1])
    answer = json.loads((folder / "gold" / "answer.json").read_text(encoding="utf-8"))
    rebuilt = {
        "soc_end_pct": rnd(keys[-1][1], 1),
        "min_soc_pct": rnd(keys[min_idx][1], 2),
        "min_soc_at_min": keys[min_idx][0],
        "breached": keys[min_idx][1] < Fraction(protect),
        "key_points": [{"t_min": kt, "mode": km, "soc_pct": rnd(kv, 2)}
                       for kt, km, kv in zip([k[0] for k in keys],
                                             ["start"] + [r[0] for r in rows],
                                             [k[1] for k in keys])],
    }
    for field in ("soc_end_pct", "min_soc_pct", "min_soc_at_min", "breached", "key_points"):
        if answer[field] != rebuilt[field]:
            raise SystemExit(f"{folder.name}: field {field} mismatch between requirements.md and answer.json\n"
                             f"answer: {answer[field]}\nrebuilt: {rebuilt[field]}")
    # cross-check the model file's net-energy expression matches the duty table order
    model = (folder / "input" / "model.sysml").read_text(encoding="utf-8")
    loads = dict(re.findall(r"attribute seg(\d+)Load : PowerValue = (\d+) \[W\]", model))
    solars = dict(re.findall(r"attribute seg(\d+)Solar : PowerValue = (\d+) \[W\]", model))
    if sorted(loads, key=int) != [str(i) for i in range(1, len(rows) + 1)]:
        raise SystemExit(f"{folder.name}: model.sysml segment count does not match duty table")
    for i, (_label, load, solar, *_rest) in enumerate(rows, start=1):
        if int(loads[str(i)]) != load or int(solars[str(i)]) != solar:
            raise SystemExit(f"{folder.name}: model.sysml seg{i} load/solar does not match duty table")
    return {"soc_end_pct": rebuilt["soc_end_pct"], "breached": rebuilt["breached"]}


# --- main ---------------------------------------------------------------------------
def main() -> int:
    if not str(OUT).startswith(str(ROOT / "bench" / "tasks_staging")):
        raise SystemExit("refusing to write outside bench/tasks_staging")
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    rng = random.Random(SEED)
    plan: list[tuple[str, bool]] = []
    for shape, total in SHAPE_PLAN.items():
        n_true = SHAPE_TRUE[shape]
        plan += [(shape, True)] * n_true + [(shape, False)] * (total - n_true)
    assert len(plan) == N_TASKS
    rng.shuffle(plan)  # deterministic (shape, breached) slot order

    accepted_vectors: list[list[float]] = []
    tasks: list[dict] = []
    shape_hist: dict[str, int] = {}
    attempts = 0
    for index, (want_shape, want_breach) in enumerate(plan, start=1):
        task_id = f"HRV-{index:04d}"
        while True:
            attempts += 1
            if attempts > MAX_SAMPLES:
                raise SystemExit(f"sampling budget exhausted at {task_id} (want {want_shape}/breached={want_breach})")
            p = sample(rng)
            s = solve(p)
            shape = classify(p, s)
            if shape != want_shape or s["breached"] != want_breach:
                continue
            vector = param_vector(p)
            if any(math.sqrt(sum((a - b) ** 2 for a, b in zip(vector, other))) < DEDUP_MIN_DIST
                   for other in accepted_vectors):
                continue
            accepted_vectors.append(vector)
            break
        shape_hist[shape] = shape_hist.get(shape, 0) + 1

        folder = OUT / task_id
        platform = platform_for(index)
        (folder / "input").mkdir(parents=True)
        (folder / "gold").mkdir()
        (folder / "case.yaml").write_text(case_yaml(task_id), encoding="utf-8")
        (folder / "input" / "model.sysml").write_text(model_sysml(task_id, p, s), encoding="utf-8")
        (folder / "input" / "requirements.md").write_text(requirements_md(task_id, p, s, platform), encoding="utf-8")
        (folder / "gold" / "answer.json").write_text(answer_json(task_id, p, s), encoding="utf-8")
        (folder / "gold" / "assertions.yaml").write_text(assertions_yaml(task_id, p, s), encoding="utf-8")
        (folder / "gold" / "solution.md").write_text(solution_md(task_id, p, s), encoding="utf-8")

        min_location = {0: "start"}.get(s["min_idx"], "mid" if s["min_idx"] < p["n_seg"] else "end")
        level = {3: "L1", 4: "L2", 5: "L2", 6: "L3", 7: "L3"}[p["n_seg"]]
        tasks.append({
            "id": task_id,
            "platform": platform,
            "params": {
                "capacity_wh": p["capacity_wh"],
                "soc_start_pct": p["soc_start_pct"],
                "protect_pct": p["protect_pct"],
                "powers_w": p["powers_w"],
                "duty": [{"mode": m, "load_w": p["powers_w"][m], "solar_w": sv, "dur_h": float(d)}
                         for m, sv, d in zip(p["labels"], p["solar_w"], p["durations_h"])],
                "mission_h": float(sum(p["durations_h"], Fraction(0))),
            },
            "gold": {"soc_end_pct": rnd(s["soc_end"], 1), "min_soc_pct": rnd(s["min_soc"], 2),
                     "min_soc_at_min": int(s["min_at_min"]), "breached": s["breached"]},
            "difficulty": {"segments": p["n_seg"], "shape": shape, "min_location": min_location,
                           "level": level},
        })

    # independent re-check of every task from disk
    for entry in tasks:
        folder = OUT / entry["id"]
        disk = verify_from_disk(folder)
        assert disk["soc_end_pct"] == entry["gold"]["soc_end_pct"], entry["id"]
        assert disk["breached"] == entry["gold"]["breached"], entry["id"]

    index_lines = [json.dumps({"id": t["id"], "type": "SIM", "platform": t["platform"],
                               "path": f"bench/tasks_staging/t_sim_bank/sim_harvest/{t['id']}"})
                   for t in tasks]
    (OUT / "index.jsonl").write_text("\n".join(index_lines) + "\n", encoding="utf-8")

    n_true = sum(t["gold"]["breached"] for t in tasks)
    n_dip = shape_hist.get("dip", 0)
    seg_hist: dict[int, int] = {}
    level_hist: dict[str, int] = {}
    loc_hist: dict[str, int] = {}
    platform_hist: dict[str, int] = {}
    for t in tasks:
        seg_hist[t["difficulty"]["segments"]] = seg_hist.get(t["difficulty"]["segments"], 0) + 1
        level_hist[t["difficulty"]["level"]] = level_hist.get(t["difficulty"]["level"], 0) + 1
        loc_hist[t["difficulty"]["min_location"]] = loc_hist.get(t["difficulty"]["min_location"], 0) + 1
        platform_hist[t["platform"]] = platform_hist.get(t["platform"], 0) + 1
    min_dist = min(
        math.sqrt(sum((a - b) ** 2 for a, b in zip(v, w)))
        for i, v in enumerate(accepted_vectors) for w in accepted_vectors[i + 1:])
    margins = [abs(t["gold"]["min_soc_pct"] - t["params"]["protect_pct"]) for t in tasks]
    manifest = {
        "family": "sim_harvest",
        "generator": "bench/build_sim_harvest.py",
        "seed": SEED,
        "count": len(tasks),
        "narrative": {
            "scenario": "maritime ISR four-node world (unmanned surface vessel, fixed-wing UAV, command ship, shore station); same world as bench/tasks/t4_maritime_isr",
            "mode_labels": MODE_LABEL,
            "platform_split_rule": "task number mod 5 < 3 -> usv, else uav (target 6:4)",
            "distinction_from_sim_battery": "SoC is non-monotone: per-row solar input can exceed the load, so segments may charge or drain; questions test piecewise bookkeeping (end SoC, mid-mission minimum and its time, protection breach), not monotone extrapolation",
        },
        "closed_form": {
            "e0_wh": "capacity * soc_start",
            "net_k_wh": "sum_{i<=k} (solar_i - load_i) * duration_i",
            "soc_k_pct": "100 * (e0 + net_k) / capacity",
            "soc_end_pct": "soc_n",
            "min_soc_pct": "min over t = 0 and all row ends (piecewise linear => vertex minimum), earliest vertex on ties",
            "min_soc_at_min": "time of that vertex, whole minutes",
            "breached": "min_soc_pct < protect_pct",
        },
        "parameter_space": {
            "capacity_wh": [CAP_MIN, CAP_MAX, CAP_STEP],
            "soc_start_pct": [SOC0_MIN, SOC0_MAX, SOC0_STEP],
            "protect_pct": [PROT_MIN, PROT_MAX],
            "load_w": {"idle": list(P_IDLE), "cruise": list(P_CRUISE), "transmit": list(P_TRANSMIT)},
            "solar_w": [0, SOLAR_MAX, SOLAR_STEP],
            "solar_zero_rule": "every mission has >= 1 zero-solar row (night) and >= 1 row where solar > load (charging)",
            "duration_grid_h": 0.1,
            "segment_duration_h": [float(DUR_MIN) / 10, float(DUR_MAX) / 10],
            "mission_total_h": [float(MISSION_MIN_H), float(MISSION_MAX_H)],
            "segments": list(SEG_CHOICES),
        },
        "constraints": {
            "dedup_min_normalized_distance": DEDUP_MIN_DIST,
            "shape_plan": SHAPE_PLAN,
            "shape_counts": shape_hist,
            "dip_share": n_dip / len(tasks),
            "breached_true": n_true,
            "breached_false": len(tasks) - n_true,
            "min_margin_pp": float(min(margins)),
            "argmin_min_gap_pp": ARGMIN_MIN_PP,
            "soc_band_pct": [SOC_FLOOR_PCT, SOC_CEIL_PCT],
            "time_margin_min": MARGIN_FACTOR * TOL_TIME_MIN,
            "no_llm": "all gold values computed by the closed form in this generator",
        },
        "stats": {"segments": seg_hist, "shape": shape_hist, "min_location": loc_hist,
                  "level": level_hist, "platform": platform_hist,
                  "min_pairwise_distance": round(min_dist, 4), "sampling_attempts": attempts},
        "tasks": tasks,
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(f"wrote {len(tasks)} tasks to {OUT}")
    print(f"breached true/false: {n_true}/{len(tasks) - n_true}")
    print(f"shapes: {shape_hist}  (dip share {n_dip / len(tasks):.0%}, target >= 40%)")
    print(f"min location: {loc_hist}")
    print(f"platform usv/uav: {platform_hist.get('usv', 0)}/{platform_hist.get('uav', 0)}")
    print(f"segments: {dict(sorted(seg_hist.items()))}  levels: {level_hist}")
    print(f"min pairwise param distance: {min_dist:.4f} (threshold {DEDUP_MIN_DIST})")
    print(f"min |min_soc - protect| margin: {float(min(margins)):.2f} pp")
    print(f"sampling attempts: {attempts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
