"""Generate the deterministic SIM storage-retention task family (250 tasks).

Family t_sim_bank/sim_storage, ids CMP-0001..CMP-0250. Narrative: the maritime ISR
four-node world (USV, fixed-wing UAV, command ship, shore station). A platform records
its observation stream (raw rate R Mbit/s) into a recorder of S GB (decimal: 1 GB =
8000 Mbit) and must retain it for T hours. The stored rate can be reduced either by a
compression tier k in {1, 2, 4, 8, 16} or by recording only the preview substream
(1 frame in N, p = 1/N of the raw rate, N in {2,3,4,5,6,8,10} -> p in [0.1, 0.5]).
The P2 preview-replacement background from the MVP (the shore receives a preview while
the platform records locally; sending only a preview needs explicit human approval) is
narrative only: every gold number is pure arithmetic, no model and no judge is called.

    rate_eff   = R/k (compression) or R/N (preview)                [Mbit/s]
    retention  = S*8000 / (3600*rate_eff)                          [h]
    headroom   = S - 0.45*rate_eff*T                               [GB]
    meets      = retention >= T            (exact, before rounding)

Two question variants:
  retention (A)  the reduction factor is fixed; ask retention_h, meets_target, headroom_gb
  choice    (B)  the target T is fixed; ask the minimal tier chosen_k in {1,2,4,8,16}
                 whose retention reaches T, its retention_h, and feasible (false when
                 even k = 16 falls short; then chosen_k is null and retention_h is the
                 k = 16 value)

Sampling rules (enforced per task, written into manifest constraints):
  - parameters deduplicated: exact (variant, mode, R, factor, S, T) tuple, exact
    effective-rate signature (R, rate_eff, S, T), and >= 0.04 normalized Euclidean
    distance inside each variant/mode bucket
  - boolean balance: A-compress 35 true / 35 false, A-preview 30/30, B 60 feasible /
    60 infeasible (125/125 overall); platform split 150 USV / 100 UAV
  - variant A: |retention - T| >= 3 x 2% x max(retention, T) and |headroom| >= 3 x 0.05 GB
  - variant B: unique minimal tier with no tie under tolerance - retention(chosen) - T
    >= 3 x 2% x retention(chosen) and (when a lower tier exists) T - retention(next
    lower tier) >= 3 x 2% x T; infeasible tasks need T - retention(k=16) >= 3 x 2% x T

Output: bench/tasks_staging/t_sim_bank/sim_storage/CMP-NNNN/ with case.yaml,
input/model.sysml, input/requirements.md, gold/answer.json, gold/assertions.yaml,
gold/solution.md, plus manifest.json (per-task platform field) and index.jsonl at the
family root, and pilot evidence under sim_storage/pilot_check/. Nothing outside that
new tree is written.

Run:  python3 bench/build_sim_storage.py            # build + disk re-parse self-check
      python3 bench/build_sim_storage.py --check    # independent full audit from disk
"""
from __future__ import annotations

import argparse
import json
import math
import random
import re
import shutil
import sys
from fractions import Fraction
from pathlib import Path

import yaml

SEED = 20261010
COUNT = 250
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "bench" / "tasks_staging" / "t_sim_bank" / "sim_storage"
FAMILY = "t_sim_bank/sim_storage"
PACKAGE = "StorageRetention"
ID_PREFIX = "CMP"

# ---------------------------------------------------------------- parameter space
R_MIN, R_MAX = 4, 50                    # raw rate, integer Mbit/s
K_LADDER = (1, 2, 4, 8, 16)             # compression tiers (discrete choice)
N_CHOICES = (2, 3, 4, 5, 6, 8, 10)      # preview decimation; p = 1/N in [0.1, 0.5]
S_HALF_STEPS = (20, 1000)               # capacity 10 .. 500 GB on a 0.5 GB grid
T_HALF_STEPS = (4, 48)                  # target retention 2 .. 24 h on a 0.5 h grid

MBIT_PER_GB = 8000                      # decimal gigabyte, as in sim_backlog
SEC_PER_H = 3600
GB_PER_H_PER_MBPS = Fraction(SEC_PER_H, MBIT_PER_GB)   # 3600/8000 = 0.45 GB per (Mbit/s)-hour

TOL_REL = Fraction(2, 100)              # +/-2 % relative on retention_h / headroom_gb
HEADROOM_ABS_FLOOR = Fraction(5, 100)   # 0.05 GB absolute floor on headroom
MARGIN_FACTOR = 3                       # gold must sit >= 3x the band from any edge
DEDUP_MIN_DIST = 0.04                   # normalized Euclidean distance inside a bucket
MAX_ATTEMPTS = 500_000

PLATFORM_SHARE = {"usv": 150, "uav": 100}

PLATFORMS = {
    "usv": {
        "def": "USVMissionRecorder",
        "header": "SIM storage retention for an unmanned surface vessel (USV) in the "
                  "maritime ISR scenario (the four-node system: unmanned surface vessel, "
                  "fixed-wing UAV, command ship, shore station). This task covers only the "
                  "USV mission recorder; the command ship and the shore station appear as "
                  "the downlink destinations in the mission story.",
        "sensor": "electro-optical surface search stream",
        "cond4": "needs the sensor survey profile",
        "cond8": "needs sea state <= 5",
        "cond16": "needs the EO camera in survey fps",
        "cond_note": "the sea is calm and the sensor runs its survey profile on this leg",
    },
    "uav": {
        "def": "UAVMissionRecorder",
        "header": "SIM storage retention for the fixed-wing UAV in the maritime ISR "
                  "scenario (the four-node system: unmanned surface vessel, fixed-wing "
                  "UAV, command ship, shore station). This task covers only the UAV "
                  "mission recorder; the command ship and the shore station appear as "
                  "the downlink destinations in the mission story.",
        "sensor": "electro-optical/infrared sensor ball stream",
        "cond4": "needs the sensor survey profile",
        "cond8": "needs steady air away from the turbulent layer",
        "cond16": "needs the sensor in survey fps",
        "cond_note": "the air is smooth and the sensor runs its survey profile on this "
                     "sortie",
    },
}

BACKGROUND = (
    "Background: in the mission design this family comes from, the platform records its\n"
    "observation stream locally while the shore station receives a preview substream -\n"
    "the P2 preview-replacement decision, which needs explicit human approval before a\n"
    "sortie. That approval gate is background only. This task is closed-form storage\n"
    "arithmetic: it does not ask you to write or edit SysML, and it does not ask for any\n"
    "approval decision."
)


# ---------------------------------------------------------------- exact arithmetic
def rnd(x: Fraction, places: int) -> float:
    """Round half away from zero to `places` decimals (Fraction in, float out)."""
    scale = 10 ** places
    scaled = abs(x) * scale + Fraction(1, 2)
    value = Fraction(math.floor(scaled), scale)
    return float(-value if x < 0 else value)


def num(x: Fraction) -> str:
    """Plain number string for a Fraction on a 0.5 grid / terminating decimal."""
    text = format(float(x), "f").rstrip("0").rstrip(".")
    return text if text else "0"


def approx(x: Fraction, places: int = 6) -> str:
    return f"{float(x):.{places}f}"


def rate_str(r: Fraction) -> str:
    """Rate display: exact decimal when terminating, else fraction + approximation."""
    if r.denominator == 1:
        return f"{r.numerator} Mbit/s"
    twos = 0
    d = r.denominator
    while d % 2 == 0:
        d //= 2
        twos += 1
    if d == 1 and twos <= 16:
        return f"{num(r)} Mbit/s"
    return f"{r.numerator}/{r.denominator} Mbit/s (about {approx(r)} Mbit/s)"


def rate_of(params: dict) -> Fraction:
    """Effective stored rate in Mbit/s."""
    if params["mode"] == "preview":
        return Fraction(params["R"], params["factor"])
    return Fraction(params["R"]) / Fraction(params["factor"])


def retention_hours(capacity_gb: Fraction, rate: Fraction) -> Fraction:
    return capacity_gb * MBIT_PER_GB / (rate * SEC_PER_H)


def headroom_gb(capacity_gb: Fraction, rate: Fraction, target_h: Fraction) -> Fraction:
    return capacity_gb - rate * target_h * GB_PER_H_PER_MBPS


def solve_a(params: dict) -> dict:
    rate = rate_of(params)
    retention = retention_hours(params["S"], rate)
    head = headroom_gb(params["S"], rate, params["T"])
    return {
        "rate": rate,
        "retention": retention,
        "headroom": head,
        "meets": retention >= params["T"],
        "retention_h": rnd(retention, 2),
        "headroom_gb": rnd(head, 2),
    }


def solve_b(params: dict) -> dict:
    """Minimal tier whose retention reaches T; infeasible falls back to k = 16."""
    per_tier = {k: retention_hours(params["S"], Fraction(params["R"], k)) for k in K_LADDER}
    chosen = None
    for k in K_LADDER:
        if per_tier[k] >= params["T"]:
            chosen = k
            break
    retention = per_tier[chosen if chosen is not None else K_LADDER[-1]]
    return {
        "per_tier": per_tier,
        "chosen_k": chosen,
        "feasible": chosen is not None,
        "retention": retention,
        "retention_h": rnd(retention, 2),
    }


# ------------------------------------------------------------------- accept rules
def margins_a(params: dict, s: dict) -> bool:
    gap_h = abs(s["retention"] - params["T"])
    need_h = MARGIN_FACTOR * TOL_REL * max(s["retention"], params["T"])
    if gap_h < need_h:
        return False
    return abs(s["headroom"]) >= MARGIN_FACTOR * HEADROOM_ABS_FLOOR


def margins_b(params: dict, s: dict) -> bool:
    if s["feasible"]:
        chosen = s["chosen_k"]
        if s["retention"] - params["T"] < MARGIN_FACTOR * TOL_REL * s["retention"]:
            return False
        if chosen > K_LADDER[0]:
            lower = s["per_tier"][K_LADDER[K_LADDER.index(chosen) - 1]]
            if params["T"] - lower < MARGIN_FACTOR * TOL_REL * params["T"]:
                return False
        return True
    return params["T"] - s["retention"] >= MARGIN_FACTOR * TOL_REL * params["T"]


def param_vector(params: dict) -> list[float]:
    """Normalized vector for near-duplicate rejection (bucket-local)."""
    return [
        params["R"] / 50.0,
        float(params["S"]) / 500.0,
        float(params["T"]) / 24.0,
        float(rate_of(params)) / 50.0,
    ]


def signature(params: dict) -> tuple:
    """Variant-agnostic arithmetic signature: same (R, rate, S, T) = same numbers."""
    return (params["R"], rate_of(params), params["S"], params["T"])


def sample(rng: random.Random, slot: dict) -> dict:
    s_half = rng.randint(*S_HALF_STEPS)
    t_half = rng.randint(*T_HALF_STEPS)
    params = {
        "variant": slot["variant"],
        "mode": slot["mode"],
        "R": rng.randint(R_MIN, R_MAX),
        "S": Fraction(s_half, 2),
        "T": Fraction(t_half, 2),
        "factor": rng.choice(N_CHOICES) if slot["mode"] == "preview" else rng.choice(K_LADDER),
    }
    return params


# --------------------------------------------------------------------- model.sysml
MODEL_HEAD = """package StorageRetention {
    /* Synthetic maritime ISR SIM task (family sim_storage). Numbers are not RTX specifications. */
    private import SI::*;
    private import ISQ::*;
    private import ISQInformation::*;

    attribute <'Mbit'> megabit : StorageCapacityUnit = 1000000 * SI::bit;
    attribute <'Mbit/s'> 'megabit per second' : BinaryDigitRateUnit = 1000000 * SI::'bit/s';

    calc def StoredRate {
        in raw : BinaryDigitRateValue;
        in factor : ScalarValues::Real;
        return stored : BinaryDigitRateValue = raw / factor;
    }

    calc def RetentionHours {
        in capacity : StorageCapacityValue;
        in rate : BinaryDigitRateValue;
        return hours : ScalarValues::Real = capacity / (rate * 3600.0 [s]);
    }

    calc def UsedCapacity {
        in rate : BinaryDigitRateValue;
        in hours : TimeValue;
        return used : StorageCapacityValue = rate * hours;
    }

    constraint def MeetsRetention {
        in retention : ScalarValues::Real;
        in target : ScalarValues::Real;
        retention >= target
    }

    part def RECORDERDEF {
        attribute sensorRate : BinaryDigitRateValue = @R@ ['Mbit/s'];
        attribute capacity : StorageCapacityValue = @CAP_MB@ ['Mbit']; /* @S@ GB = @S@ * 8000 Mbit */
        attribute targetHours : ScalarValues::Real = @T@;
"""

MODEL_TAIL = """    }

    requirement def RetentionRequirement {
        subject recorder : RECORDERDEF;
        attribute retentionHours : ScalarValues::Real;
        attribute targetHours : ScalarValues::Real;
        require constraint { retentionHours >= targetHours }
    }

    analysis def RetentionAnalysis {
        subject recorder : RECORDERDEF;
        requirement retention : RetentionRequirement;
        return retentionHours : ScalarValues::Real;
        objective retentionObjective {
            require retention {
                :>> retentionHours = RetentionAnalysis::retentionHours;
                :>> targetHours = recorder.targetHours;
            }
        }
    }
}
"""


def model_sysml(params: dict, platform: str) -> str:
    recorder = PLATFORMS[platform]["def"]
    head = (MODEL_HEAD
            .replace("@R@", str(params["R"]))
            .replace("@CAP_MB@", str(int(params["S"] * MBIT_PER_GB)))
            .replace("@S@", num(params["S"]))
            .replace("@T@", num(params["T"]))
            .replace("RECORDERDEF", recorder))
    body = []
    if params["variant"] == "retention":
        if params["mode"] == "preview":
            body.append(f"        attribute reductionFactor : ScalarValues::Real = {params['factor']}; "
                        f"/* preview substream: 1 frame in {params['factor']} kept (P2 approved) */")
        else:
            body.append(f"        attribute reductionFactor : ScalarValues::Real = {params['factor']}; "
                        f"/* compression tier k = {params['factor']} */")
        body += [
            "",
            "        attribute storedRate : BinaryDigitRateValue = StoredRate(sensorRate, reductionFactor);",
            "        attribute retentionHours : ScalarValues::Real = RetentionHours(capacity, storedRate);",
            f"        attribute usedAtTarget : StorageCapacityValue = "
            f"UsedCapacity(storedRate, {int(params['T'] * SEC_PER_H)} [s]); /* T = {num(params['T'])} h */",
            "",
            "        assert constraint meets : MeetsRetention {",
            "            in retention = retentionHours;",
            f"            in target = {recorder}::targetHours;",
            "        }",
        ]
    else:
        tier_lines = []
        for k in K_LADDER:
            tier_lines.append(f"        attribute rateK{k} : BinaryDigitRateValue = "
                              f"StoredRate(sensorRate, {k}); /* tier T{k} */")
        for k in K_LADDER:
            tier_lines.append(f"        attribute retentionK{k} : ScalarValues::Real = "
                              f"RetentionHours(capacity, rateK{k});")
        body += tier_lines + [
            f"        attribute usedAtTargetBest : StorageCapacityValue = "
            f"UsedCapacity(rateK16, {int(params['T'] * SEC_PER_H)} [s]); /* T = {num(params['T'])} h at k = 16 */",
            "",
            "        /* feasibility check at the highest tier; the minimal reaching tier is chosen in the analysis */",
            "        assert constraint bestTierMeets : MeetsRetention {",
            "            in retention = retentionK16;",
            f"            in target = {recorder}::targetHours;",
            "        }",
        ]
    tail = MODEL_TAIL.replace("RECORDERDEF", recorder)
    return head + "\n".join(body) + "\n" + tail


# ----------------------------------------------------------------- requirements.md
def tier_table(params: dict) -> str:
    rows = ["| Tier | factor k | stored rate |", "|---|---|---|"]
    for k in K_LADDER:
        rows.append(f"| T{k} | {k} | {rate_str(Fraction(params['R'], k))} |")
    return "\n".join(rows)


def applicability(platform: str) -> str:
    meta = PLATFORMS[platform]
    return (f"Applicability: T1 (raw pass-through) is always available; T2 (lossless frame "
            f"differencing) is always available; T4 (lossy inter-frame codec) {meta['cond4']}; "
            f"T8 (high-ratio lossy codec) {meta['cond8']}; T16 (frame-stack still-capture "
            f"mode) {meta['cond16']}. All of these conditions hold on this leg "
            f"({meta['cond_note']}), so every tier is applicable.")


def requirements_md(task_id: str, params: dict, platform: str) -> str:
    meta = PLATFORMS[platform]
    R, S, T = params["R"], num(params["S"]), num(params["T"])
    units_a = f"""## Units and arithmetic rules

- Storage uses decimal gigabytes: 1 GB = 8000 Mbit; 1 h = 3600 s.
- At a stored rate of r Mbit/s the recorder fills 3600 x r Mbit = 0.45 x r GB per hour,
  and the capacity lasts `retention_h = S x 8000 / (3600 x r)` hours.
- Round retention_h and headroom_gb to two decimals (half away from zero).
"""
    units_b = f"""## Units and arithmetic rules

- Storage uses decimal gigabytes: 1 GB = 8000 Mbit; 1 h = 3600 s.
- At a stored rate of r Mbit/s the recorder fills 3600 x r Mbit = 0.45 x r GB per hour,
  and the capacity lasts `retention_h = S x 8000 / (3600 x r)` hours.
- Round retention_h to two decimals (half away from zero).
"""
    if params["variant"] == "retention":
        if params["mode"] == "compress":
            k = params["factor"]
            middle = f"""## Compression tiers

{tier_table(params)}

{applicability(platform)} The mission plan fixes tier T{k} (k = {k}) for this recording.
"""
            rate_line = (f"1. Stored rate: r = R/k = {R}/{k} = {rate_str(Fraction(R, k))}.")
        else:
            N = params["factor"]
            preview_rate = Fraction(R, N)
            middle = f"""## Preview substream

The operator has approved the P2 preview-replacement decision for this sortie (in the
live system that approval is a human gate; here it is given). The recorder keeps
1 frame in {N} of the raw stream in long-term storage, so the stored preview rate is
r = {R}/{N} = {rate_str(preview_rate)} (p = 1/{N} of the raw rate). The full-rate scratch
buffer is recycled hourly and is not part of the retention record.
"""
            rate_line = (f"1. Stored rate: r = R/N = {R}/{N} = {rate_str(preview_rate)} "
                         f"(p = 1/{N}).")
        ask = f"""## Reply with exactly one JSON object

{{"retention_h": <number>, "meets_target": <true|false>, "headroom_gb": <number>}}

- `retention_h`: how many hours the capacity lasts at the stored rate fixed above.
- `meets_target`: true iff retention_h >= T = {T}.
- `headroom_gb`: S minus what storing for T hours consumes at that rate; negative is the
  shortfall in GB.
"""
        footer = f"""Answer three questions:

{rate_line}
2. `retention_h` at that stored rate, in hours.
3. `meets_target` against T = {T} h, and `headroom_gb` = {S} - 0.45 x r x {T} GB.

{units_a}
{ask}"""
    else:
        per_h = params["S"] * MBIT_PER_GB / (Fraction(R) * SEC_PER_H)
        middle = f"""## Compression tiers

{tier_table(params)}

{applicability(platform)}

Choose the storage plan for this recording: report the smallest tier factor k whose
retention reaches the target.

## Retention per tier

With S = {S} GB and R = {R} Mbit/s, tier k stores at R/k Mbit/s, so
`retention_h(k) = k x S x 8000 / (3600 x R) = k x {approx(per_h, 6)} hours`.
"""
        ask = f"""## Reply with exactly one JSON object

{{"chosen_k": <integer or null>, "retention_h": <number>, "feasible": <true|false>}}

- `chosen_k`: the smallest tier factor k in {{1, 2, 4, 8, 16}} whose retention_h >= T = {T};
  null if no tier reaches T.
- `retention_h`: retention at chosen_k; if chosen_k is null, the retention at the highest
  tier (k = 16).
- `feasible`: true iff some tier reaches T.
"""
        footer = f"""Answer three questions:

1. `chosen_k`, the minimal sufficient tier factor (unique: the ladder is strictly
   increasing, so exactly one tier is the smallest that reaches T = {T} h).
2. `retention_h` at that tier (or at k = 16 when no tier reaches T).
3. `feasible`, whether any tier reaches T.

{units_b}
{ask}"""
    return (
        f"# {task_id} — synthetic, not an RTX specification\n\n"
        f"{meta['header']}\n\n{BACKGROUND}\n\n"
        "This is a closed-form storage question. The file `model.sysml` in this folder "
        "carries the same parameters as a SysML v2 model; the numbers in this document "
        "are authoritative.\n\n"
        f"## Recorder\n\n"
        f"- Raw {meta['sensor']} rate R: {R} Mbit/s (constant over the whole recording window)\n"
        f"- Recorder capacity S: {S} GB (decimal units: 1 GB = 8000 Mbit)\n"
        f"- Required retention T: {T} h (the recording must stay stored without overwrite)\n\n"
        f"{middle}\n{footer}"
    )


# --------------------------------------------------------------------- gold files
def answer_payload(task_id: str, params: dict, s: dict) -> dict:
    if params["variant"] == "retention":
        return {
            "task_id": task_id,
            "retention_h": s["retention_h"],
            "meets_target": s["meets"],
            "headroom_gb": s["headroom_gb"],
        }
    return {
        "task_id": task_id,
        "chosen_k": s["chosen_k"],
        "retention_h": s["retention_h"],
        "feasible": s["feasible"],
    }


def assertions_dict(params: dict, s: dict, platform: str) -> dict:
    if params["variant"] == "retention":
        checks = {
            "retention_h": {"gold": s["retention_h"], "rel_tol": float(TOL_REL)},
            "meets_target": {"gold": s["meets"], "exact": True},
            "headroom_gb": {"gold": s["headroom_gb"], "rel_tol": float(TOL_REL),
                            "abs_floor": float(HEADROOM_ABS_FLOOR)},
        }
        margin = {
            "rule": "|retention - T| >= 3 x 2% x max(retention, T); |headroom| >= 3 x 0.05 GB",
            "retention_gap_h": float(abs(s["retention"] - params["T"])),
            "required_gap_h": float(MARGIN_FACTOR * TOL_REL * max(s["retention"], params["T"])),
            "headroom_abs_gb": float(abs(s["headroom"])),
        }
    else:
        checks = {
            "chosen_k": {"gold": s["chosen_k"], "exact": True},
            "retention_h": {"gold": s["retention_h"], "rel_tol": float(TOL_REL)},
            "feasible": {"gold": s["feasible"], "exact": True},
        }
        if s["feasible"]:
            lower = (K_LADDER[K_LADDER.index(s["chosen_k"]) - 1]
                     if s["chosen_k"] > K_LADDER[0] else None)
            margin = {
                "rule": "unique minimal tier: retention(chosen) - T >= 3 x 2% x "
                        "retention(chosen); T - retention(next lower) >= 3 x 2% x T (no tie)",
                "pass_margin_h": float(s["retention"] - params["T"]),
                "fail_margin_h": (float(params["T"] - s["per_tier"][lower]) if lower else None),
            }
        else:
            margin = {
                "rule": "infeasible: T - retention(k=16) >= 3 x 2% x T",
                "fail_margin_h": float(params["T"] - s["retention"]),
            }
    return {
        "package": PACKAGE,
        "family": FAMILY,
        "platform": platform,
        "variant": params["variant"],
        "mode": params["mode"],
        "answer_mode": "json",
        "tolerances": {"retention_rel": float(TOL_REL),
                       "headroom_rel": float(TOL_REL),
                       "headroom_abs_floor_gb": float(HEADROOM_ABS_FLOOR),
                       "boolean_exact": True,
                       "chosen_k_exact": True},
        "checks": checks,
        "margin_rule": margin,
        "formula": "rate = R/k or R/N; retention_h = S*8000/(3600*rate); "
                   "headroom_gb = S - 0.45*rate*T",
    }


def solution_md(task_id: str, params: dict, s: dict) -> str:
    R, S, T = params["R"], params["S"], params["T"]
    cap_mb = S * MBIT_PER_GB
    lines = [
        f"# {task_id} - closed-form solution (no simulation, no model called)",
        "",
        f"Parameters: R = {R} Mbit/s, S = {num(S)} GB, T = {num(T)} h"
        + (f", factor = {params['factor']} ({params['mode']})."
           if params["variant"] == "retention" else "."),
        "",
        "Unit base: 1 GB = 8000 Mbit and 1 h = 3600 s, so the recorder holds "
        f"{num(S)} x 8000 = {num(cap_mb)} Mbit and one hour at r Mbit/s stores "
        "3600 x r Mbit = 0.45 x r GB.",
        "",
    ]
    if params["variant"] == "retention":
        rate = s["rate"]
        hour_mb = rate * SEC_PER_H
        lines += [
            f"1. Stored rate r = {rate_str(rate)}.",
            f"2. One hour at that rate = 3600 x r = {num(hour_mb)} Mbit.",
            f"3. retention_h = {num(cap_mb)} / {num(hour_mb)} = "
            f"{approx(s['retention'], 6)} -> **{s['retention_h']:.2f} h** (two decimals, half away from zero).",
            f"4. Target check: {s['retention_h']:.2f} vs T = {num(T)}: retention "
            f"{'>=' if s['meets'] else '<'} T, so meets_target = **{str(s['meets']).lower()}** "
            f"(exact margin {approx(abs(s['retention'] - T), 4)} h, clear of the 2% band).",
            f"5. Stored during T hours = 0.45 x r x {num(T)} = {approx(rate * T * GB_PER_H_PER_MBPS, 6)} GB,",
            f"   headroom_gb = {num(S)} - {approx(rate * T * GB_PER_H_PER_MBPS, 6)} = "
            f"{approx(s['headroom'], 6)} -> **{s['headroom_gb']:.2f} GB** "
            f"({'spare capacity' if s['headroom'] > 0 else 'shortfall'}).",
        ]
    else:
        per_h = cap_mb / (Fraction(R) * SEC_PER_H)
        lines += [
            f"1. Retention scales linearly with the tier factor: retention_h(k) = k x {num(cap_mb)} / (3600 x {R}) "
            f"= k x {approx(per_h, 6)} h.",
            "",
            "| tier k | stored rate | retention_h(k) | vs T |",
            "|---|---|---|---|",
        ]
        for k in K_LADDER:
            ret = s["per_tier"][k]
            verdict = "reaches" if ret >= T else "short"
            mark = ""
            if s["feasible"] and k == s["chosen_k"]:
                mark = " <- chosen (smallest that reaches)"
            if not s["feasible"] and k == K_LADDER[-1]:
                mark = " <- best tier still short"
            lines.append(f"| {k} | {rate_str(Fraction(R, k))} | {approx(ret, 6)} | {verdict}{mark} |")
        if s["feasible"]:
            chosen = s["chosen_k"]
            lower = K_LADDER[K_LADDER.index(chosen) - 1] if chosen > K_LADDER[0] else None
            lines += [
                "",
                f"2. Smallest tier reaching T = {num(T)} h: k = {chosen} "
                f"(retention {approx(s['retention'], 6)} h), so chosen_k = **{chosen}** and "
                f"feasible = **true**.",
                f"3. retention_h = **{s['retention_h']:.2f} h**.",
            ]
            if lower:
                lines += [
                    f"4. No tie: the next lower tier k = {lower} retains only "
                    f"{approx(s['per_tier'][lower], 6)} h, missing T by "
                    f"{approx(T - s['per_tier'][lower], 6)} h (>= 3 x the 2% band of T), and "
                    f"k = {chosen} clears T by {approx(s['retention'] - T, 6)} h (>= 3 x the "
                    "2% band of retention), so the minimal tier is unique under the tolerance.",
                ]
            else:
                lines += [
                    "4. No tie: the lowest tier k = 1 already reaches T by "
                    f"{approx(s['retention'] - T, 6)} h (>= 3 x the 2% band of retention).",
                ]
        else:
            lines += [
                "",
                f"2. Even the best tier k = 16 retains only {approx(s['retention'], 6)} h, "
                f"short of T = {num(T)} h by {approx(T - s['retention'], 6)} h (>= 3 x the 2% "
                "band of T), so feasible = **false** and chosen_k = **null**.",
                f"3. retention_h (reported at k = 16) = **{s['retention_h']:.2f} h**.",
            ]
    lines += [
        "",
        "Final answers (answer.json): "
        + json.dumps({k: v for k, v in answer_payload(task_id, params, s).items()
                      if k != "task_id"}),
        "",
    ]
    return "\n".join(lines)


def case_yaml(task_id: str, params: dict, platform: str, difficulty: str) -> str:
    return yaml.safe_dump({
        "id": task_id,
        "type": "SIM",
        "scenario_family": "t_sim_bank",
        "split": "staging",
        "package": PACKAGE,
        "synthetic": True,
        "platform": platform,
        "variant": params["variant"],
        "mode": params["mode"],
        "difficulty": difficulty,
        "generator": "bench/build_sim_storage.py",
        "seed": SEED,
        "answer_mode": "json",
        "status": "generated-closed-form",
    }, sort_keys=False, allow_unicode=False)


# ---------------------------------------------------------------------- sampling
def plan_slots(rng: random.Random) -> list[dict]:
    quota = (
        [("retention", "compress", True, None)] * 35
        + [("retention", "compress", False, None)] * 35
        + [("retention", "preview", True, None)] * 30
        + [("retention", "preview", False, None)] * 30
    )
    # feasible choice tasks: spread the minimal tier evenly over the ladder so the
    # discrete decision is not dominated by the trivial k = 1 corner
    for k in K_LADDER:
        quota += [("choice", "ladder", True, k)] * (60 // len(K_LADDER))
    quota += [("choice", "ladder", False, None)] * 60
    slots = [{"variant": v, "mode": m, "want": w, "chosen": c} for v, m, w, c in quota]
    rng.shuffle(slots)
    platforms = ["usv"] * PLATFORM_SHARE["usv"] + ["uav"] * PLATFORM_SHARE["uav"]
    rng.shuffle(platforms)
    for slot, platform in zip(slots, platforms):
        slot["platform"] = platform
    return slots


def build_bank() -> tuple[list[dict], dict]:
    rng = random.Random(SEED)
    slots = plan_slots(rng)
    used_tuples: set = set()
    used_signatures: set = set()
    buckets: dict[tuple, list[list[float]]] = {}
    tasks: list[dict] = []
    rejected = {"dedup": 0, "margin": 0, "label": 0}
    attempts = 0

    for index, slot in enumerate(slots, start=1):
        task_id = f"{ID_PREFIX}-{index:04d}"
        while True:
            attempts += 1
            if attempts > MAX_ATTEMPTS:
                raise SystemExit(f"sampling budget exhausted at {task_id}")
            params = sample(rng, slot)
            key = (params["variant"], params["mode"], params["R"], params["factor"],
                   params["S"], params["T"])
            if key in used_tuples or signature(params) in used_signatures:
                rejected["dedup"] += 1
                continue
            vector = param_vector(params)
            bucket = buckets.setdefault((params["variant"], params["mode"]), [])
            if any(math.dist(vector, other) < DEDUP_MIN_DIST for other in bucket):
                rejected["dedup"] += 1
                continue
            solution = solve_a(params) if params["variant"] == "retention" else solve_b(params)
            ok_margin = margins_a(params, solution) if params["variant"] == "retention" \
                else margins_b(params, solution)
            if not ok_margin:
                rejected["margin"] += 1
                continue
            boolean = solution["meets"] if params["variant"] == "retention" \
                else solution["feasible"]
            if boolean != slot["want"]:
                rejected["label"] += 1
                continue
            if params["variant"] == "choice" and solution["chosen_k"] != slot["chosen"]:
                rejected["tier"] = rejected.get("tier", 0) + 1
                continue
            used_tuples.add(key)
            used_signatures.add(signature(params))
            bucket.append(vector)
            break

        if params["variant"] == "retention":
            difficulty = f"retention/{params['mode']}"
        else:
            difficulty = "choice/feasible" if solution["feasible"] else "choice/infeasible"
        manifest_params = {
            "raw_rate_mbps": params["R"],
            "capacity_gb": float(params["S"]),
            "target_retention_h": float(params["T"]),
        }
        if params["variant"] == "retention":
            manifest_params["mode"] = params["mode"]
            manifest_params["factor"] = params["factor"]
            if params["mode"] == "preview":
                manifest_params["preview_ratio_p"] = float(Fraction(1, params["factor"]))
            manifest_params["stored_rate_mbps"] = float(solution["rate"])
        else:
            manifest_params["k_ladder"] = list(K_LADDER)
        gold_manifest = dict(answer_payload(task_id, params, solution))
        gold_manifest.pop("task_id")
        tasks.append({
            "id": task_id,
            "platform": slot["platform"],
            "variant": params["variant"],
            "mode": params["mode"],
            "difficulty": difficulty,
            "params": manifest_params,
            "gold": gold_manifest,
            "_params": params,
            "_solution": solution,
        })

    stats_extra = {
        "sampling_attempts": attempts,
        "rejected_by_reason": dict(sorted(rejected.items())),
        "min_pairwise_distance": {
            f"{v}|{m}": round(min(math.dist(a, b)
                                  for i, a in enumerate(vecs) for b in vecs[i + 1:]), 4)
            for (v, m), vecs in sorted(buckets.items())
        },
    }
    return tasks, stats_extra


# ------------------------------------------------------------------------- build
def write_bank(tasks: list[dict]) -> None:
    if OUT.exists():
        if not (OUT / "manifest.json").is_file() and any(OUT.iterdir()):
            raise SystemExit(f"refusing to remove unexpected directory {OUT}")
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    for task in tasks:
        params, solution = task["_params"], task["_solution"]
        folder = OUT / task["id"]
        (folder / "input").mkdir(parents=True)
        (folder / "gold").mkdir()
        (folder / "case.yaml").write_text(
            case_yaml(task["id"], params, task["platform"], task["difficulty"]),
            encoding="utf-8")
        (folder / "input" / "model.sysml").write_text(
            model_sysml(params, task["platform"]), encoding="utf-8")
        (folder / "input" / "requirements.md").write_text(
            requirements_md(task["id"], params, task["platform"]), encoding="utf-8")
        (folder / "gold" / "answer.json").write_text(
            json.dumps(answer_payload(task["id"], params, solution), indent=2) + "\n",
            encoding="utf-8")
        (folder / "gold" / "assertions.yaml").write_text(
            yaml.safe_dump(assertions_dict(params, solution, task["platform"]),
                           sort_keys=False, allow_unicode=False),
            encoding="utf-8")
        (folder / "gold" / "solution.md").write_text(
            solution_md(task["id"], params, solution), encoding="utf-8")


# ------------------------------------------- disk re-parse (independent of writers)
RX = {
    "first": re.compile(r"# CMP-\d{4} — synthetic, not an RTX specification"),
    "rate": re.compile(r"rate R: (\d+) Mbit/s"),
    "cap": re.compile(r"capacity S: (\d+(?:\.\d+)?) GB"),
    "target": re.compile(r"retention T: (\d+(?:\.\d+)?) h"),
    "tier_fixed": re.compile(r"mission plan fixes tier T\d+ \(k = (\d+)\) for this recording"),
    "frame": re.compile(r"keeps\s+1 frame in (\d+) of the raw stream"),
}


def reparse(folder: Path) -> tuple[dict, dict]:
    """Recompute gold from the written requirements.md alone."""
    text = (folder / "input" / "requirements.md").read_text(encoding="utf-8")
    if not RX["first"].match(text):
        raise SystemExit(f"{folder.name}: first line is not the RTX synthetic marker")
    R = int(RX["rate"].search(text).group(1))
    S = Fraction(RX["cap"].search(text).group(1))
    T = Fraction(RX["target"].search(text).group(1))
    fixed = RX["tier_fixed"].search(text)
    frame = RX["frame"].search(text)
    if fixed is not None:
        params = {"variant": "retention", "mode": "compress", "R": R, "S": S, "T": T,
                  "factor": int(fixed.group(1))}
    elif frame is not None:
        params = {"variant": "retention", "mode": "preview", "R": R, "S": S, "T": T,
                  "factor": int(frame.group(1))}
    else:
        params = {"variant": "choice", "mode": "ladder", "R": R, "S": S, "T": T, "factor": 1}
    solution = solve_a(params) if params["variant"] == "retention" else solve_b(params)
    return params, solution


def verify_from_disk(tasks: list[dict]) -> None:
    for task in tasks:
        folder = OUT / task["id"]
        params, solution = reparse(folder)
        answer = json.loads((folder / "gold" / "answer.json").read_text(encoding="utf-8"))
        rebuilt = answer_payload(task["id"], params, solution)
        if answer != rebuilt:
            raise SystemExit(f"{task['id']}: answer.json disagrees with re-parsed "
                             f"requirements.md\n{answer}\n{rebuilt}")
        # the model must carry the same raw numbers as the requirements
        model = (folder / "input" / "model.sysml").read_text(encoding="utf-8")
        for literal in (f"= {params['R']} ['Mbit/s']", f"= {int(params['S'] * MBIT_PER_GB)} ['Mbit']"):
            if literal not in model:
                raise SystemExit(f"{task['id']}: model.sysml misses literal {literal!r}")


# -------------------------------------------------------------------------- pilot
def pilot_check(tasks: list[dict], n: int) -> list[dict]:
    sys.path.insert(0, str(ROOT))
    from mvp.toolchain.validate import validate_package  # noqa: E402
    # one model per question shape (compress / preview / ladder choice), taken from
    # the start / middle / end of that shape's occurrences so the picks also spread
    shapes = [("retention", "compress"), ("retention", "preview"), ("choice", "ladder")]
    positions = [0, 1, -1]
    picks = []
    for (variant, mode), pos in zip(shapes[:n], positions):
        occurrences = [t["id"] for t in tasks
                       if t["variant"] == variant and t["mode"] == mode]
        picks.append(occurrences[pos])
    picks = sorted(set(picks))
    report = []
    for task_id in picks:
        out = OUT / "pilot_check" / task_id
        if out.exists():
            shutil.rmtree(out)
        result = validate_package([str(OUT / task_id / "input" / "model.sysml")],
                                  PACKAGE, str(out))
        report.append({"id": task_id, "status": result["status"],
                       "adapter": result.get("adapter"),
                       "warnings": result.get("warning_count", 0)})
        print(f"pilot {task_id}: {result['status']}")
    if any(r["status"] != "PASS" for r in report):
        raise SystemExit("pilot check failed")
    return report


# -------------------------------------------------------------------------- build
def build() -> None:
    tasks, stats_extra = build_bank()
    write_bank(tasks)
    verify_from_disk(tasks)

    index_lines = [json.dumps({"id": t["id"], "type": "SIM", "platform": t["platform"],
                               "variant": t["variant"],
                               "path": f"bench/tasks_staging/t_sim_bank/sim_storage/{t['id']}"})
                   for t in tasks]
    (OUT / "index.jsonl").write_text("\n".join(index_lines) + "\n", encoding="utf-8")

    cross: dict[str, int] = {}
    chosen_hist: dict[int, int] = {}
    factor_hist: dict[str, int] = {}
    for t in tasks:
        if t["variant"] == "retention":
            boolean = "meets=true" if t["gold"]["meets_target"] else "meets=false"
            factor_hist[f"{t['mode']}|{t['params']['factor']}"] = \
                factor_hist.get(f"{t['mode']}|{t['params']['factor']}", 0) + 1
        else:
            boolean = "feasible=true" if t["gold"]["feasible"] else "feasible=false"
            if t["gold"]["chosen_k"] is not None:
                chosen_hist[t["gold"]["chosen_k"]] = \
                    chosen_hist.get(t["gold"]["chosen_k"], 0) + 1
        key = f"{t['variant']}|{t['mode']}|{boolean}"
        cross[key] = cross.get(key, 0) + 1
    retentions = [t["gold"]["retention_h"] for t in tasks]
    manifest = {
        "family": FAMILY,
        "generator": "bench/build_sim_storage.py",
        "seed": SEED,
        "count": len(tasks),
        "package": PACKAGE,
        "scenario": "synthetic maritime ISR (USV, fixed-wing UAV, command ship, shore "
                    "station); recorder = USV or UAV mission recorder; the P2 "
                    "preview-replacement decision (shore receives a preview substream, "
                    "needs human approval) is narrative background only - every gold is "
                    "closed-form arithmetic",
        "closed_form": {
            "stored_rate": "R/k (compression tier) or R/N (preview substream, p = 1/N)",
            "retention_h": "S*8000/(3600*rate)",
            "headroom_gb": "S - 0.45*rate*T",
            "meets_target": "retention_h >= T (exact, before rounding)",
            "chosen_k": "smallest k in {1,2,4,8,16} with retention_h(k) >= T; null if k=16 still short",
            "feasible": "chosen_k exists",
        },
        "parameter_space": {
            "raw_rate_mbps": [R_MIN, R_MAX, 1],
            "compression_ladder": list(K_LADDER),
            "preview_decimation_n": list(N_CHOICES),
            "preview_ratio_p": ["1/10 .. 1/2", "0.1 .. 0.5"],
            "capacity_gb": [10, 500, 0.5],
            "target_retention_h": [2, 24, 0.5],
            "units": "1 GB = 8000 Mbit (decimal), 1 h = 3600 s",
            "platform": {"usv": PLATFORM_SHARE["usv"], "uav": PLATFORM_SHARE["uav"]},
        },
        "constraints": [
            "parameters deduplicated: exact (variant, mode, R, factor, S, T) tuple and "
            "exact variant-agnostic signature (R, stored_rate, S, T)",
            f"near-duplicate rejection: normalized Euclidean distance >= {DEDUP_MIN_DIST} "
            "inside each variant/mode bucket (vector R/50, S/500, T/24, rate/50)",
            "boolean balance: A-compress 35/35, A-preview 30/30, B feasible/infeasible "
            "60/60 (125/125 overall)",
            f"feasible choice tasks spread evenly over the ladder: {60 // len(K_LADDER)} "
            "tasks per minimal tier k in {1,2,4,8,16}",
            "variant A margins: |retention - T| >= 3 x 2% x max(retention, T) and "
            "|headroom_gb| >= 3 x 0.05 GB",
            "variant B unique minimal tier (no tie): retention(chosen) - T >= 3 x 2% x "
            "retention(chosen) and, when a lower tier exists, T - retention(next lower) "
            ">= 3 x 2% x T - rejection condition on every sampled task",
            "variant B infeasible: T - retention(k=16) >= 3 x 2% x T",
            "no LLM anywhere: this generator is the answer key; same seed rebuilds the "
            "same bytes",
        ],
        "tolerances": {"retention_rel": 0.02, "headroom_rel": 0.02,
                       "headroom_abs_floor_gb": 0.05, "boolean": "exact",
                       "chosen_k": "exact"},
        "stats": {
            "count": len(tasks),
            "by_variant": {v: sum(1 for t in tasks if t["variant"] == v)
                           for v in ("retention", "choice")},
            "by_platform": {pf: sum(1 for t in tasks if t["platform"] == pf)
                            for pf in ("usv", "uav")},
            "by_platform_variant": {
                f"{pf}|{v}": sum(1 for t in tasks
                                 if t["platform"] == pf and t["variant"] == v)
                for pf in ("usv", "uav") for v in ("retention", "choice")},
            "cross": dict(sorted(cross.items())),
            "chosen_k_hist_feasible": {str(k): chosen_hist.get(k, 0) for k in K_LADDER},
            "a_factor_hist": dict(sorted(factor_hist.items())),
            "retention_h_range": [min(retentions), max(retentions)],
            **stats_extra,
        },
        "tasks": [{k: v for k, v in t.items() if not k.startswith("_")} for t in tasks],
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"{len(tasks)} tasks in {OUT}")
    print(json.dumps({k: manifest["stats"][k] for k in
                      ("by_variant", "by_platform", "cross", "chosen_k_hist_feasible")},
                     indent=2))
    print(f"sampling: {stats_extra['sampling_attempts']} attempts, "
          f"rejected {stats_extra['rejected_by_reason']}")
    print(f"min pairwise distance per bucket: {stats_extra['min_pairwise_distance']}")


# -------------------------------------------------------------------------- check
def check() -> None:
    """Independent audit: re-derive every gold from disk with float arithmetic."""
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    tasks = manifest["tasks"]
    problems: list[str] = []
    if len(tasks) != COUNT:
        problems.append(f"expected {COUNT} tasks, manifest lists {len(tasks)}")
    seen_tuples: set = set()
    seen_sig: set = set()
    for index, task in enumerate(tasks, start=1):
        tid = f"{ID_PREFIX}-{index:04d}"
        if task["id"] != tid:
            problems.append(f"{task['id']}: id out of order")
            continue
        folder = OUT / tid
        for rel in ("case.yaml", "input/model.sysml", "input/requirements.md",
                    "gold/answer.json", "gold/assertions.yaml", "gold/solution.md"):
            if not (folder / rel).is_file():
                problems.append(f"{tid}: missing {rel}")
        if problems and problems[-1].startswith(f"{tid}: missing"):
            continue
        params, solution = reparse(folder)
        case = yaml.safe_load((folder / "case.yaml").read_text(encoding="utf-8"))
        answer = json.loads((folder / "gold" / "answer.json").read_text(encoding="utf-8"))
        asserts = yaml.safe_load((folder / "gold" / "assertions.yaml").read_text(encoding="utf-8"))
        # independent float re-derivation
        R = float(params["R"])
        rate = R / params["factor"] if params["variant"] == "retention" else None
        if params["variant"] == "retention":
            ref_ret = float(params["S"]) * MBIT_PER_GB / (SEC_PER_H * rate)
            ref_head = float(params["S"]) - 0.45 * rate * float(params["T"])
            if abs(answer["retention_h"] - ref_ret) > 0.011:
                problems.append(f"{tid}: retention_h {answer['retention_h']} vs {ref_ret:.4f}")
            if abs(answer["headroom_gb"] - ref_head) > 0.011:
                problems.append(f"{tid}: headroom_gb {answer['headroom_gb']} vs {ref_head:.4f}")
            if answer["meets_target"] != (ref_ret >= float(params["T"])):
                problems.append(f"{tid}: meets_target mismatch")
            if (answer["headroom_gb"] >= 0) != answer["meets_target"]:
                problems.append(f"{tid}: headroom sign inconsistent with meets_target")
            if abs(answer["retention_h"] - float(params["T"])) < \
                    0.06 * max(answer["retention_h"], float(params["T"])):
                problems.append(f"{tid}: retention margin rule violated")
            if abs(ref_head) < 3 * float(HEADROOM_ABS_FLOOR):
                problems.append(f"{tid}: headroom margin rule violated")
        else:
            refs = {k: float(params["S"]) * MBIT_PER_GB * k / (SEC_PER_H * R) for k in K_LADDER}
            chosen = next((k for k in K_LADDER if refs[k] >= float(params["T"])), None)
            if answer["chosen_k"] != chosen:
                problems.append(f"{tid}: chosen_k {answer['chosen_k']} vs {chosen}")
            if abs(answer["retention_h"] - refs[chosen or 16]) > 0.011:
                problems.append(f"{tid}: retention_h {answer['retention_h']} vs "
                                f"{refs[chosen or 16]:.4f}")
            if answer["feasible"] != (chosen is not None):
                problems.append(f"{tid}: feasible mismatch")
            if chosen is not None:
                if refs[chosen] - float(params["T"]) < 0.06 * refs[chosen]:
                    problems.append(f"{tid}: B pass margin violated")
                if chosen > 1 and float(params["T"]) - refs[K_LADDER[K_LADDER.index(chosen) - 1]] \
                        < 0.06 * float(params["T"]):
                    problems.append(f"{tid}: B no-tie margin violated")
            elif float(params["T"]) - refs[16] < 0.06 * float(params["T"]):
                problems.append(f"{tid}: B infeasible margin violated")
        if case.get("platform") != task.get("platform") or \
                asserts.get("platform") != task.get("platform"):
            problems.append(f"{tid}: platform mismatch")
        if case.get("variant") != task["variant"] or case.get("mode") != task["mode"]:
            problems.append(f"{tid}: case.yaml variant/mode mismatch")
        model = (folder / "input" / "model.sysml").read_text(encoding="utf-8")
        if f"part def {PLATFORMS[task['platform']]['def']} {{" not in model:
            problems.append(f"{tid}: model recorder definition does not match platform")
        other = "uav" if task["platform"] == "usv" else "usv"
        if PLATFORMS[other]["def"] in model:
            problems.append(f"{tid}: model mentions the other platform")
        sol = (folder / "gold" / "solution.md").read_text(encoding="utf-8")
        for value in (answer["retention_h"],):
            if f"{value:.2f}" not in sol:
                problems.append(f"{tid}: solution.md does not carry the gold retention")
                break
        key = (task["variant"], task["mode"], params["R"], params["factor"],
               params["S"], params["T"])
        sig_rate = (Fraction(params["R"], params["factor"])
                    if params["variant"] == "retention" else Fraction(params["R"]))
        sig = (params["R"], sig_rate, params["S"], params["T"])
        if key in seen_tuples:
            problems.append(f"{tid}: duplicate parameter tuple")
        if sig in seen_sig:
            problems.append(f"{tid}: duplicate effective-rate signature")
        seen_tuples.add(key)
        seen_sig.add(sig)
    quotas = {
        "retention|compress|meets=true": 35, "retention|compress|meets=false": 35,
        "retention|preview|meets=true": 30, "retention|preview|meets=false": 30,
        "choice|ladder|feasible=true": 60, "choice|ladder|feasible=false": 60,
    }
    for key, want in quotas.items():
        got = manifest["stats"]["cross"].get(key, 0)
        if got != want:
            problems.append(f"quota {key}: expected {want}, manifest says {got}")
    per_tier = 60 // len(K_LADDER)
    for k, got in manifest["stats"]["chosen_k_hist_feasible"].items():
        if got != per_tier:
            problems.append(f"chosen_k {k}: expected {per_tier}, manifest says {got}")
    for pf, want in PLATFORM_SHARE.items():
        got = sum(1 for t in tasks if t.get("platform") == pf)
        if got != want:
            problems.append(f"platform {pf}: expected {want}, manifest has {got}")
    index_lines = (OUT / "index.jsonl").read_text(encoding="utf-8").splitlines()
    if len(index_lines) != COUNT:
        problems.append(f"index.jsonl has {len(index_lines)} lines")
    if problems:
        for line in problems[:20]:
            print("FAIL", line)
        raise SystemExit(1)
    print(f"check ok: {len(tasks)} tasks, {len(seen_tuples)} distinct parameter tuples, "
          f"{len(seen_sig)} distinct arithmetic signatures")
    print(json.dumps({k: manifest["stats"][k] for k in
                      ("cross", "by_platform", "chosen_k_hist_feasible")}, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="independent recomputation audit of the bank on disk")
    parser.add_argument("--pilot", type=int, default=0,
                        help="also run the official Pilot validator on N spread tasks "
                             "(evidence under sim_storage/pilot_check/)")
    args = parser.parse_args()
    if args.check:
        check()
        return 0
    build()
    if args.pilot:
        tasks = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))["tasks"]
        report = pilot_check(tasks, args.pilot)
        manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
        manifest["pilot_check"] = report
        (OUT / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
