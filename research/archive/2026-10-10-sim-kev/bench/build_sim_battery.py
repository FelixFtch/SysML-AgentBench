"""Deterministic SIM battery-family task generator (350 tasks, closed-form gold).

Family `sim_battery` under bench/tasks_staging/t_sim_bank/ (a new tree; nothing in
bench/tasks/, FREEZE.md, or any existing file is read for writing or modified).
Narrative: same maritime ISR four-node world as bench/tasks/t4_maritime_isr —
the battery platform is a USV or a fixed-wing UAV (deterministic ~6:4 split by
task number), and duty rows use maritime mode names (loiter / transit /
transmit to shore) mapped one-to-one to the electrical tiers.

Model of the family: an ISR platform battery is an ideal energy tank. The duty
cycle is a table of piecewise-constant power phases, so SoC(t) is piecewise
linear and every gold number is a closed-form expression:

    E(0)      = capacity * soc_start                     [Wh]
    spent_k   = sum_{i<=k} P_i * d_i                     [Wh]   (P in W, d in h)
    soc_k(%)  = 100 * (E(0) - spent_k) / capacity
    soc_end   = soc_n ;  meets_reserve = soc_end >= reserve_pct

No language model is called anywhere: this file IS the answer key. Re-running
with the same seed reproduces the bank byte for byte (it wipes only its own
staging directory first). After writing, the script re-parses every generated
requirements.md duty table and recomputes the gold from the parsed text as an
independent write/format check.

Each task folder BAT-NNNN/ contains:
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
OUT = ROOT / "bench" / "tasks_staging" / "t_sim_bank" / "sim_battery"

SEED = 20261010
N_TASKS = 350
N_TRUE = 193          # meets_reserve true count; 193/350 = 55.1% (target ~55/45)

MODES = ("idle", "cruise", "transmit")

# --- maritime ISR narrative binding (scenario/maritime-isr four-node world) ----
# Scenario vocabulary: unmanned surface vessel (USV), fixed-wing UAV, command
# ship, shore station. Duty rows use maritime mission mode names; the mapping
# to the electrical tiers (and to the untouched model.sysml attribute names) is
# fixed and stated in every requirements.md:
MODE_LABEL = {"idle": "loiter", "cruise": "transit", "transmit": "transmit to shore"}
PLATFORM_TEXT = {
    "usv": "an unmanned surface vessel (USV)",
    "uav": "the fixed-wing UAV",
}
PLATFORM_BATTERY = {
    "usv": "USV battery bank",
    "uav": "UAV battery",
}


def platform_for(index: int) -> str:
    """Deterministic USV:UAV ~= 6:4 split (task number mod 5 < 3 -> USV)."""
    return "usv" if index % 5 < 3 else "uav"


# --- tolerance contract (mirrored into gold/assertions.yaml) -----------------
TOL_REL = 0.02        # +/- 2% relative on every SoC percent value
TOL_TIME_MIN = 2      # +/- 2 min absolute on key-point times
BOOL_EXACT = True     # meets_reserve must match exactly

# --- margin rules: gold must sit >= 3x tolerance band from any decision edge --
MARGIN_MIN_PP = 2.0   # |soc_end_pct - reserve_pct| >= 2.0 percentage points ...
MARGIN_FACTOR = 3.0   # ... and >= 3 * TOL_REL * soc_end_pct (3x the tolerance band)
SOC_FLOOR_PCT = 5     # every key-point SoC within [5, 96] % so relative
SOC_CEIL_PCT = 96     # tolerance is meaningful far from 0/100

# --- parameter space ----------------------------------------------------------
CAP_MIN, CAP_MAX, CAP_STEP = 400, 2400, 50        # Wh
SOC0_MIN, SOC0_MAX, SOC0_STEP = 70, 95, 5         # %
RES_MIN, RES_MAX = 10, 30                          # % of capacity
P_IDLE = (5, 40)                                    # W
P_CRUISE = (25, 120)                                # W
P_TRANSMIT = (90, 200)                              # W
P_MIN_GAP = 10                                      # W between mode powers
DUR_STEP_H = Fraction(1, 10)                        # durations on a 0.1 h grid
DUR_MIN, DUR_MAX = 3, 35                            # grid steps: 0.3 .. 3.5 h
MISSION_MIN_H, MISSION_MAX_H = Fraction(2), Fraction(12)
SEG_CHOICES = (3, 4, 5, 6)

DEDUP_MIN_DIST = 0.12   # min normalized Euclidean distance between param vectors
MAX_SAMPLES = 500_000

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


# --- sampling ------------------------------------------------------------------
def sample(rng: random.Random) -> dict:
    capacity = rng.randrange(CAP_MIN, CAP_MAX + 1, CAP_STEP)
    soc0 = rng.randrange(SOC0_MIN, SOC0_MAX + 1, SOC0_STEP)
    reserve = rng.randrange(RES_MIN, RES_MAX + 1)
    n_seg = rng.choice(SEG_CHOICES)
    p_idle = rng.randrange(*P_IDLE)
    p_cruise = rng.randrange(max(P_CRUISE[0], p_idle + P_MIN_GAP), P_CRUISE[1] + 1)
    p_tx = rng.randrange(max(P_TRANSMIT[0], p_cruise + P_MIN_GAP), P_TRANSMIT[1] + 1)
    while True:
        steps = [rng.randrange(DUR_MIN, DUR_MAX + 1) for _ in range(n_seg)]
        total = Fraction(sum(steps), 10)
        if MISSION_MIN_H <= total <= MISSION_MAX_H:
            break
    labels = list(rng.sample(MODES, 3)) + [rng.choice(MODES) for _ in range(n_seg - 3)]
    powers = {"idle": p_idle, "cruise": p_cruise, "transmit": p_tx}
    return {
        "capacity_wh": capacity,
        "soc_start_pct": soc0,
        "reserve_pct": reserve,
        "n_seg": n_seg,
        "powers_w": powers,
        "durations_h": [Fraction(s, 10) for s in steps],
        "labels": labels,
    }


# --- closed form ----------------------------------------------------------------
def solve(p: dict) -> dict:
    """Piecewise-linear SoC. Exact rational arithmetic; no floats in the chain."""
    cap = p["capacity_wh"]
    e0 = Fraction(cap) * Fraction(p["soc_start_pct"], 100)
    spent = Fraction(0)
    t_min = 0
    key_points = [(0, "start", Fraction(p["soc_start_pct"], 1))]
    per_segment = []
    for i, (mode, dur) in enumerate(zip(p["labels"], p["durations_h"]), start=1):
        power = p["powers_w"][mode]
        seg_wh = Fraction(power) * dur
        spent += seg_wh
        t_min += dur * 60
        soc = 100 * (e0 - spent) / Fraction(cap)
        key_points.append((t_min, mode, soc))
        per_segment.append({"i": i, "mode": mode, "power_w": power, "dur_h": dur,
                            "seg_wh": seg_wh, "cum_wh": spent, "t_end_min": t_min, "soc": soc})
    soc_end = key_points[-1][2]
    return {
        "e0_wh": e0,
        "spent_wh": spent,
        "soc_end": soc_end,
        "meets_reserve": soc_end >= Fraction(p["reserve_pct"]),
        "key_points": key_points,
        "per_segment": per_segment,
    }


# --- accept / reject rules --------------------------------------------------------
def acceptable(p: dict, s: dict, vector: list[float], accepted: list[list[float]]) -> str | None:
    """Return 'true'/'false' if the sample is usable, else None.

    Rejects samples whose gold sits closer than 3x the tolerance band to the
    reserve decision edge, samples whose SoC leaves the [SOC_FLOOR, SOC_CEIL]
    band, and samples too close in parameter space to an accepted task.
    """
    socs = [kp[2] for kp in s["key_points"]]
    if any(soc < SOC_FLOOR_PCT or soc > SOC_CEIL_PCT for soc in socs):
        return None
    soc_end = rnd(s["soc_end"], 1)
    margin_pp = abs(soc_end - p["reserve_pct"])
    if margin_pp + 1e-9 < max(MARGIN_MIN_PP, MARGIN_FACTOR * TOL_REL * soc_end):
        return None
    for other in accepted:
        dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(vector, other)))
        if dist < DEDUP_MIN_DIST:
            return None
    return "true" if s["meets_reserve"] else "false"


def param_vector(p: dict) -> list[float]:
    """Normalized parameter vector for dedup (fixed width, durations zero-padded)."""
    vec = [
        p["capacity_wh"] / 1000.0,
        p["soc_start_pct"] / 100.0,
        p["reserve_pct"] / 100.0,
        p["powers_w"]["idle"] / 100.0,
        p["powers_w"]["cruise"] / 100.0,
        p["powers_w"]["transmit"] / 100.0,
    ]
    vec += [float(d) / 4.0 for d in p["durations_h"]]
    vec += [0.0] * (max(SEG_CHOICES) - p["n_seg"])
    return vec


# --- writers ----------------------------------------------------------------------
def model_sysml(task_id: str, p: dict, s: dict) -> str:
    seg_attrs = "\n".join(
        f"        attribute seg{i}Duration : TimeValue = {fh(d)} [h];"
        for i, d in enumerate(p["durations_h"], start=1))
    spent_terms = "\n            + ".join(
        f"ModeEnergy({MODE_POWER_ATTR[seg['mode']]}, seg{seg['i']}Duration)"
        for seg in s["per_segment"])
    return f"""package BatteryDischarge {{
    private import SI::*;
    private import ISQ::*;

    calc def ModeEnergy {{
        in power : PowerValue;
        in duration : TimeValue;
        return energy : EnergyValue = power * duration;
    }}

    calc def RemainingEnergy {{
        in capacity : EnergyValue;
        in spent : EnergyValue;
        return remaining : EnergyValue = capacity - spent;
    }}

    calc def SoC {{
        in remaining : EnergyValue;
        in capacity : EnergyValue;
        return soc : ScalarValues::Real = remaining / capacity;
    }}

    constraint def ReserveConstraint {{
        in soc : ScalarValues::Real;
        in socMin : ScalarValues::Real;
        soc >= socMin
    }}

    part def ISRPlatform {{
        attribute capacity : EnergyValue = {p['capacity_wh']} ['W⋅h'];
        attribute socStart : ScalarValues::Real = {p['soc_start_pct'] / 100:.2f};
        attribute socMin : ScalarValues::Real = {p['reserve_pct'] / 100:.2f};

        attribute idlePower : PowerValue = {p['powers_w']['idle']} [W];
        attribute cruisePower : PowerValue = {p['powers_w']['cruise']} [W];
        attribute transmitPower : PowerValue = {p['powers_w']['transmit']} [W];

{seg_attrs}

        attribute spent : EnergyValue =
            {spent_terms};
        attribute socEnd : ScalarValues::Real =
            SoC(RemainingEnergy(capacity * socStart, spent), capacity);

        assert constraint reserve : ReserveConstraint {{
            in soc = socEnd;
            in socMin = ISRPlatform::socMin;
        }}
    }}

    requirement def EnduranceRequirement {{
        subject platform : ISRPlatform;
        attribute socEnd : ScalarValues::Real;
        attribute socMin : ScalarValues::Real;
        require constraint {{ socEnd >= socMin }}
    }}

    analysis def EnduranceAnalysis {{
        subject platform : ISRPlatform;
        requirement endurance : EnduranceRequirement;
        return socEnd : ScalarValues::Real;
        objective enduranceObjective {{
            require endurance {{
                :>> socEnd = EnduranceAnalysis::socEnd;
                :>> socMin = platform.socMin;
            }}
        }}
    }}
}}
"""


def requirements_md(task_id: str, p: dict, s: dict, platform: str) -> str:
    rows = []
    start = Fraction(0)
    for seg in s["per_segment"]:
        rows.append(f"| {seg['i']} | {MODE_LABEL[seg['mode']]} | {seg['power_w']} | {int(start)} | "
                    f"{int(seg['t_end_min'])} | {fh(seg['dur_h'])} |")
        start = seg["t_end_min"]
    table = "\n".join(rows)
    platform_sentence = (
        f"This task covers only the {PLATFORM_BATTERY[platform]}; the command ship and the "
        "shore station appear as the downlink destinations in the mission story."
        if platform == "usv" else
        "This task covers only the UAV battery; the command ship and the shore "
        "station appear as the downlink destinations in the mission story.")
    return f"""# {task_id} — synthetic, not an RTX specification

SIM battery endurance for {PLATFORM_TEXT[platform]} in the maritime ISR scenario
(the four-node system: unmanned surface vessel, fixed-wing UAV, command ship,
shore station). {platform_sentence}

This is a closed-form energy bookkeeping question. It does not ask you to write
or edit SysML. The file `model.sysml` in this folder carries the same parameters
as a SysML v2 model; the numbers in this document are authoritative.

## Battery

- Capacity: {p['capacity_wh']} Wh
- Initial SoC at t = 0: {p['soc_start_pct']} % of capacity ({p['soc_start_pct'] / 100:.2f})
- Reserve threshold: {p['reserve_pct']} % of capacity. The reserve requirement is met
  only if the SoC at mission end (end of the last duty row) is at least this
  value; below it the platform must be recovered before it loses station.

## Mission duty cycle (rows are sequential; the mission starts at t = 0 min)

| # | Mode               | Power (W) | Start (min) | End (min) | Duration (h) |
|---|--------------------|-----------|-------------|-----------|--------------|
{table}

Mode names (maritime ISR wording) map one-to-one to the electrical tiers and to
the attribute names in `model.sysml`: loiter = minimal station-keeping draw
(`idlePower`), transit = cruise draw (`cruisePower`), transmit to shore =
downlink draw while imagery is relayed to the command ship and shore station
(`transmitPower`).

## Units and conversion rules

- Energy is in watt-hours (Wh). A constant power of P watts applied for d hours
  spends P × d Wh; minutes convert at 1 h = 60 min.
- SoC is remaining energy as a percent of capacity:
  `soc_pct(t) = 100 × (E(0) − spent(0..t)) / capacity`, with
  `E(0) = capacity × initial_soc`.
- The battery is an ideal energy tank: no rate limits, no self-discharge, no
  nonlinearity. Power is constant during each row and changes only at row
  boundaries, so SoC(t) is piecewise linear.
- Round `soc_end_pct` to 1 decimal, key-point SoC values to 2 decimals, and
  report times as whole minutes after mission start.

## Reply with exactly one JSON object

{{"soc_end_pct": <number>, "meets_reserve": <true|false>,
  "key_points": [{{"t_min": <int>, "mode": "<start or mode name>", "soc_pct": <number>}}, ...]}}

- `soc_end_pct`: SoC at the end of the last duty row, percent, 1 decimal.
- `meets_reserve`: true iff `soc_end_pct` >= {float(p['reserve_pct']):.1f}.
- `key_points`: one entry at t = 0 with mode "start", then one entry at the end
  of every duty row (mode = that row's mode name), in time order, each with the
  SoC at that instant. That is {p['n_seg'] + 1} entries.
"""


def answer_json(task_id: str, p: dict, s: dict) -> str:
    payload = {
        "task_id": task_id,
        "soc_end_pct": rnd(s["soc_end"], 1),
        "meets_reserve": s["meets_reserve"],
        "key_points": [
            {"t_min": int(t), "mode": MODE_LABEL.get(mode, mode), "soc_pct": rnd(soc, 2)}
            for t, mode, soc in s["key_points"]
        ],
    }
    return json.dumps(payload, indent=2) + "\n"


def assertions_yaml(task_id: str, p: dict, s: dict) -> str:
    checks = {
        "task_id": task_id,
        "package": "BatteryDischarge",
        "family": "sim_battery",
        "answer_mode": "json",
        "tolerances": {"soc_rel": TOL_REL, "time_abs_min": TOL_TIME_MIN, "boolean_exact": BOOL_EXACT},
        "checks": {
            "soc_end_pct": {"gold": rnd(s["soc_end"], 1), "rel_tol": TOL_REL},
            "meets_reserve": {"gold": s["meets_reserve"], "exact": True},
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
             "No simulation is needed: SoC(t) is piecewise linear because each duty row",
             "draws constant power from an ideal energy tank.",
             "",
             f"- Capacity C = {cap} Wh; initial SoC = {p['soc_start_pct']} % →",
             f"  E(0) = C × {p['soc_start_pct'] / 100:.2f} = {f1(e0)} Wh.",
             f"- Reserve threshold = {p['reserve_pct']} % of capacity.",
             "",
             "Per-row energy (ΔE = power × duration), cumulative spend, remaining energy,",
             "and SoC = 100 × (E(0) − spent) / C:",
             "",
             "| # | Mode | P (W) | d (h) | ΔE (Wh) | Σ spent (Wh) | E left (Wh) | SoC (%) | t_end (min) |",
             "|---|------|-------|-------|---------|--------------|-------------|---------|-------------|"]
    for seg in s["per_segment"]:
        lines.append(
            f"| {seg['i']} | {MODE_LABEL[seg['mode']]} | {seg['power_w']} | {fh(seg['dur_h'])} "
            f"| {f1(seg['seg_wh'])} | {f1(seg['cum_wh'])} | {f1(e0 - seg['cum_wh'])} "
            f"| {f2(seg['soc'])} | {int(seg['t_end_min'])} |")
    total = s["spent_wh"]
    lines += [
        "",
        f"Total spent = {f1(total)} Wh (sum of the ΔE column; each term is power × hours).",
        f"E at mission end = E(0) − total = {f1(e0)} − {f1(total)} = {f1(e0 - total)} Wh.",
        f"soc_end = 100 × {f1(e0 - total)} / {cap} = {f2(s['soc_end'])} % → reported to 1 decimal as "
        f"**{f1(s['soc_end'])} %**.",
        f"meets_reserve: {f1(s['soc_end'])} % {'≥' if s['meets_reserve'] else '<'} "
        f"{float(p['reserve_pct']):.1f} % → **{str(s['meets_reserve']).lower()}**.",
        "",
        "Key points (t = 0 plus the end of every row):",
        "",
        "| t (min) | Mode | SoC (%) |",
        "|---------|------|---------|"]
    for t, mode, soc in s["key_points"]:
        lines.append(f"| {int(t)} | {MODE_LABEL.get(mode, mode)} | {f2(soc)} |")
    lines += ["",
              f"Check against the tolerance contract: |soc_end − reserve| = "
              f"{f1(abs(s['soc_end'] - Fraction(p['reserve_pct'])))} pp, well clear of the "
              f"±{TOL_REL:.0%} relative band, so the reserve verdict is unambiguous.",
              ""]
    return "\n".join(lines)


def case_yaml(task_id: str) -> str:
    return yaml.safe_dump({
        "id": task_id, "type": "SIM", "scenario_family": "t_sim_bank", "split": "staging",
        "package": "BatteryDischarge", "synthetic": True, "status": "generated",
        "generator": "bench/build_sim_battery.py", "seed": SEED,
        "answer_mode": "json",
    }, sort_keys=False)


# --- independent re-check: recompute gold from the written requirements.md --------
LABEL_TO_MODE = {v: k for k, v in MODE_LABEL.items()}
ROW_RE = re.compile(r"^\| (\d+) \| (transmit to shore|loiter|transit) \| (\d+) \| (\d+) \| (\d+) \| (\d+\.\d) \|$")


def verify_from_disk(folder: Path) -> dict:
    text = (folder / "input" / "requirements.md").read_text(encoding="utf-8")
    first = text.splitlines()[0]
    if not re.fullmatch(r"# BAT-\d{4} — synthetic, not an RTX specification", first):
        raise SystemExit(f"{folder.name}: requirements.md first line is not the RTX marker: {first!r}")
    cap = int(re.search(r"- Capacity: (\d+) Wh", text).group(1))
    soc0 = int(re.search(r"- Initial SoC at t = 0: (\d+) %", text).group(1))
    reserve = int(re.search(r"- Reserve threshold: (\d+) %", text).group(1))
    rows = []
    powers: dict[str, int] = {}
    for line in text.splitlines():
        match = ROW_RE.match(line)
        if match:
            label, power = match.group(2), int(match.group(3))
            powers[label] = power
            rows.append((label, Fraction(match.group(6))))
    e0 = Fraction(cap) * Fraction(soc0, 100)
    spent = Fraction(0)
    t = 0
    keys = [(0, Fraction(soc0))]
    for label, dur in rows:
        spent += Fraction(powers[label]) * dur
        t += dur * 60
        keys.append((int(t), 100 * (e0 - spent) / Fraction(cap)))
    answer = json.loads((folder / "gold" / "answer.json").read_text(encoding="utf-8"))
    rebuilt = {"soc_end_pct": rnd(keys[-1][1], 1),
               "meets_reserve": keys[-1][1] >= Fraction(reserve),
               "key_points": [{"t_min": kt, "mode": km, "soc_pct": rnd(kv, 2)}
                              for kt, km, kv in zip([k[0] for k in keys],
                                                    ["start"] + [m for m, _ in rows],
                                                    [k[1] for k in keys])]}
    for field in ("soc_end_pct", "meets_reserve", "key_points"):
        if answer[field] != rebuilt[field]:
            raise SystemExit(f"{folder.name}: field {field} mismatch between requirements.md and answer.json\n"
                             f"answer: {answer[field]}\nrebuilt: {rebuilt[field]}")
    # cross-check the model file's spent expression matches the duty table order
    model = (folder / "input" / "model.sysml").read_text(encoding="utf-8")
    terms = re.findall(r"ModeEnergy\((idlePower|cruisePower|transmitPower), seg(\d+)Duration\)", model)
    if [t[0] for t in terms] != [MODE_POWER_ATTR[LABEL_TO_MODE[m]] for m, _ in rows]:
        raise SystemExit(f"{folder.name}: model.sysml spent order does not match duty table")
    return {"soc_end_pct": rebuilt["soc_end_pct"], "meets_reserve": rebuilt["meets_reserve"]}


# --- main ---------------------------------------------------------------------------
def main() -> int:
    if not str(OUT).startswith(str(ROOT / "bench" / "tasks_staging")):
        raise SystemExit("refusing to write outside bench/tasks_staging")
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    rng = random.Random(SEED)
    slots = [True] * N_TRUE + [False] * (N_TASKS - N_TRUE)
    rng.shuffle(slots)  # deterministic label order

    accepted_vectors: list[list[float]] = []
    tasks: list[dict] = []
    attempts = 0
    for index, want_true in enumerate(slots, start=1):
        task_id = f"BAT-{index:04d}"
        while True:
            attempts += 1
            if attempts > MAX_SAMPLES:
                raise SystemExit(f"sampling budget exhausted at {task_id}")
            p = sample(rng)
            s = solve(p)
            vector = param_vector(p)
            label = acceptable(p, s, vector, accepted_vectors)
            if label is None:
                continue
            if (label == "true") != want_true:
                continue
            accepted_vectors.append(vector)
            break

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

        crossing = "none"
        if not s["meets_reserve"]:
            # monotone decreasing: crossing happened before the final segment ends
            # iff some key point strictly before the end is already below reserve
            earlier_below = any(soc < Fraction(p["reserve_pct"]) for _t, _m, soc in s["key_points"][:-1])
            crossing = "earlier" if earlier_below else "final_segment"
        level = {3: "L1", 4: "L2", 5: "L2", 6: "L3"}[p["n_seg"]]
        tasks.append({
            "id": task_id,
            "platform": platform,
            "params": {
                "capacity_wh": p["capacity_wh"],
                "soc_start_pct": p["soc_start_pct"],
                "reserve_pct": p["reserve_pct"],
                "powers_w": p["powers_w"],
                "duty": [{"mode": m, "dur_h": float(d)} for m, d in zip(p["labels"], p["durations_h"])],
                "mission_h": float(sum(p["durations_h"], Fraction(0))),
            },
            "gold": {"soc_end_pct": rnd(s["soc_end"], 1), "meets_reserve": s["meets_reserve"]},
            "difficulty": {"segments": p["n_seg"], "reserve_crossing": crossing, "level": level},
        })

    # independent re-check of every task from disk
    for entry in tasks:
        folder = OUT / entry["id"]
        disk = verify_from_disk(folder)
        assert disk["soc_end_pct"] == entry["gold"]["soc_end_pct"], entry["id"]
        assert disk["meets_reserve"] == entry["gold"]["meets_reserve"], entry["id"]

    index_lines = [json.dumps({"id": t["id"], "type": "SIM", "platform": t["platform"],
                               "path": f"bench/tasks_staging/t_sim_bank/sim_battery/{t['id']}"})
                   for t in tasks]
    (OUT / "index.jsonl").write_text("\n".join(index_lines) + "\n", encoding="utf-8")

    n_true = sum(t["gold"]["meets_reserve"] for t in tasks)
    seg_hist: dict[int, int] = {}
    cross_hist: dict[str, int] = {}
    level_hist: dict[str, int] = {}
    platform_hist: dict[str, int] = {}
    for t in tasks:
        seg_hist[t["difficulty"]["segments"]] = seg_hist.get(t["difficulty"]["segments"], 0) + 1
        cross_hist[t["difficulty"]["reserve_crossing"]] = cross_hist.get(t["difficulty"]["reserve_crossing"], 0) + 1
        level_hist[t["difficulty"]["level"]] = level_hist.get(t["difficulty"]["level"], 0) + 1
        platform_hist[t["platform"]] = platform_hist.get(t["platform"], 0) + 1
    min_dist = min(
        math.sqrt(sum((a - b) ** 2 for a, b in zip(v, w)))
        for i, v in enumerate(accepted_vectors) for w in accepted_vectors[i + 1:])
    margins = [abs(t["gold"]["soc_end_pct"] - t["params"]["reserve_pct"]) for t in tasks]
    manifest = {
        "family": "sim_battery",
        "generator": "bench/build_sim_battery.py",
        "seed": SEED,
        "count": len(tasks),
        "narrative": {
            "scenario": "maritime ISR four-node world (unmanned surface vessel, fixed-wing UAV, command ship, shore station); same world as bench/tasks/t4_maritime_isr",
            "mode_labels": MODE_LABEL,
            "platform_split_rule": "task number mod 5 < 3 -> usv, else uav (target 6:4)",
        },
        "closed_form": {
            "e0_wh": "capacity * soc_start",
            "spent_k_wh": "sum_{i<=k} power_i * duration_i",
            "soc_k_pct": "100 * (e0 - spent_k) / capacity",
            "meets_reserve": "soc_end_pct >= reserve_pct",
        },
        "parameter_space": {
            "capacity_wh": [CAP_MIN, CAP_MAX, CAP_STEP],
            "soc_start_pct": [SOC0_MIN, SOC0_MAX, SOC0_STEP],
            "reserve_pct": [RES_MIN, RES_MAX],
            "power_w": {"idle": list(P_IDLE), "cruise": list(P_CRUISE), "transmit": list(P_TRANSMIT)},
            "duration_grid_h": 0.1,
            "segment_duration_h": [float(DUR_MIN) / 10, float(DUR_MAX) / 10],
            "mission_total_h": [float(MISSION_MIN_H), float(MISSION_MAX_H)],
            "segments": list(SEG_CHOICES),
        },
        "constraints": {
            "dedup_min_normalized_distance": DEDUP_MIN_DIST,
            "meets_reserve_true": n_true,
            "meets_reserve_false": len(tasks) - n_true,
            "min_margin_pp": float(min(margins)),
            "soc_band_pct": [SOC_FLOOR_PCT, SOC_CEIL_PCT],
            "no_llm": "all gold values computed by the closed form in this generator",
        },
        "stats": {"segments": seg_hist, "reserve_crossing": cross_hist, "level": level_hist,
                  "platform": platform_hist,
                  "min_pairwise_distance": round(min_dist, 4), "sampling_attempts": attempts},
        "tasks": tasks,
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(f"wrote {len(tasks)} tasks to {OUT}")
    print(f"meets_reserve true/false: {n_true}/{len(tasks) - n_true}")
    print(f"platform usv/uav: {platform_hist.get('usv', 0)}/{platform_hist.get('uav', 0)}")
    print(f"segments: {dict(sorted(seg_hist.items()))}  levels: {level_hist}")
    print(f"reserve_crossing: {cross_hist}")
    print(f"min pairwise param distance: {min_dist:.4f} (threshold {DEDUP_MIN_DIST})")
    print(f"min |soc_end - reserve| margin: {float(min(margins)):.1f} pp")
    print(f"sampling attempts: {attempts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
