"""Deterministic SIM link-outage backlog task generator (350 tasks, closed-form gold).

Family `sim_backlog` under bench/tasks_staging/t_sim_bank/sim_backlog/ (a new tree;
nothing in bench/tasks/, FREEZE.md, or any existing file is read for writing or
modified). The narrative is the synthetic maritime ISR four-node picture (USV and
fixed-wing UAV -> command ship -> shore archive); outage reasons are maritime
(link degradation / beyond-line-of-sight window / weather outage).

Model of the family: one relay path buffers sensor data and drains it over a
downlink. The link is up except during outage windows, so backlog(t) in Mbit is
piecewise linear with integer slopes:

    link up,   buffer non-empty:  dB/dt = 60 * (sensor - link)   [Mbit/min]
    link up,   buffer empty:      dB/dt = max(0, 60 * (sensor - link))   (clamp at 0)
    outage window:                dB/dt = 60 * sensor            [Mbit/min]
    B(0) = 0 ;  1 GB = 8000 Mbit

Gold keys (all closed form, exact integer arithmetic in Mbit; only the reported
crossing minute is a rational):

    overflows       = max B over [0, mission] > 8000 * capacity_gb   (strict)
    overflow_at_min = ceil(t*), t* = first time B(t) = capacity     (null if no overflow)
    max_backlog_gb  = max B / 8000
    end_backlog_gb  = B(mission) / 8000
    end_headroom_gb = capacity_gb - end_backlog_gb

No language model is called anywhere: this file IS the answer key. Re-running with
the same seed reproduces the bank byte for byte (it wipes only its own staging
directory first). After writing, the script (a) re-simulates every task with an
independent one-second integer stepper and requires exact agreement, and (b)
re-parses every generated requirements.md and recomputes the gold from the parsed
text, as write/format checks.

Acceptance margins (a task is rejected and recorded in manifest.json when any
fails): |peak - capacity| >= 3 x 2% of capacity; crossing time >= 3 x 2 min from
both mission edges; max_backlog >= 0.5 GB; end backlog either exactly 0 or
>= 0.25 GB; unique parameter vector. Overflow/no-overflow split is quota-balanced.

Each task folder BLG-NNNN/ contains:
  case.yaml, input/model.sysml, input/requirements.md,
  gold/answer.json, gold/assertions.yaml, gold/solution.md
plus manifest.json and index.jsonl in the family directory.
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

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "bench" / "tasks_staging" / "t_sim_bank" / "sim_backlog"
SEED = 20261010
N_TARGET = 350
MB_PER_GB = 8000
TOL_REL = 0.02          # numeric tolerance: +/- 2 % relative
TOL_MIN = 2             # time tolerance: +/- 2 minutes
MARGIN_MULT = 3         # gold must sit >= 3x tolerance from every decision band edge
MAX_ATTEMPTS = 60000

# (link_case, n_windows, overflows) -> quota. Totals: 350 tasks, 174 overflow / 176 safe.
QUOTAS = {
    ("ge", 1, True): 55, ("ge", 1, False): 60,
    ("ge", 2, True): 55, ("ge", 2, False): 60,
    ("lt", 1, True): 32, ("lt", 1, False): 28,
    ("lt", 2, True): 32, ("lt", 2, False): 28,
}
REASONS = ["link degradation", "beyond-line-of-sight window", "weather outage"]
PLATFORMS = {"usv": ("usvRelay", "usv", "usv-to-shore"),
             "uav": ("uavRelay", "uav", "uav-to-command-ship")}


# ---------------------------------------------------------------- closed form

def simulate(sensor: int, link: int, mission: int, windows: list[tuple[int, int]]):
    """Exact piecewise-linear backlog. Times in minutes (ints), backlog in Mbit (ints).

    Returns (rows, max_b, end_b) where rows = [t0, t1, regime, slope_mbit_per_min,
    b0, b1] covering [0, mission] in order, split at outage edges and at any
    zero-clamp instant.
    """
    marks = {0, mission}
    for start, dur in windows:
        marks.add(start)
        marks.add(start + dur)
    ts = sorted(m for m in marks if 0 <= m <= mission)
    rows: list[list] = []
    backlog = 0
    for t0, t1 in zip(ts, ts[1:]):
        if t1 <= t0:
            continue
        mid = Fraction(t0 + t1, 2)
        if any(start < mid < start + dur for start, dur in windows):
            slope, regime = 60 * sensor, "outage"
        else:
            slope, regime = 60 * (sensor - link), "link-up"
        end_value = backlog + slope * (t1 - t0)
        if end_value < 0 and backlog > 0:
            hit = t0 + Fraction(backlog, -slope)  # exact zero-clamp instant
            rows.append([t0, hit, regime, slope, backlog, 0])
            rows.append([hit, t1, "link-up-empty", 0, 0, 0])
            backlog = 0
        elif end_value < 0 and backlog == 0:
            rows.append([t0, t1, "link-up-empty", 0, 0, 0])
        else:
            rows.append([t0, t1, regime, slope, backlog, end_value])
            backlog = end_value
    if not rows:  # degenerate mission of length 0 cannot happen (mission >= 120)
        rows = [[0, 0, "link-up-empty", 0, 0, 0]]
    max_b = max(row[5] for row in rows)
    return rows, max_b, rows[-1][5]


def first_crossing(rows, cap_mb: int):
    """First exact time B(t) = cap_mb on a rising row; None if never reached."""
    for t0, t1, _regime, _slope, b0, b1 in rows:
        if b1 > b0 and b0 <= cap_mb < b1:
            return t0 + Fraction(cap_mb - b0, b1 - b0) * (t1 - t0)
    return None


def gold_of(sensor: int, link: int, mission: int, windows: list[tuple[int, int]], cap_gb: float):
    cap_mb = int(round(cap_gb * MB_PER_GB))
    rows, max_b, end_b = simulate(sensor, link, mission, windows)
    overflows = max_b > cap_mb
    t_star = first_crossing(rows, cap_mb) if overflows else None
    overflow_at = math.ceil(t_star) if t_star is not None else None
    return {"rows": rows, "max_b": max_b, "end_b": end_b, "cap_mb": cap_mb,
            "overflows": overflows, "t_star": t_star, "overflow_at_min": overflow_at}


def gb(mbit: int) -> float:
    """Mbit -> GB, rounded half-up to 2 decimals (deterministic)."""
    return math.floor(mbit / MB_PER_GB * 100 + 0.5) / 100


# ------------------------------------------------- independent self-check sim

def sim_seconds(sensor: int, link: int, mission: int, windows: list[tuple[int, int]], cap_mb: int):
    """Brute-force one-second integer stepper, an independent implementation."""
    outs = [(s * 60, (s + d) * 60) for s, d in windows]
    total_s = mission * 60

    def down(sec):
        return any(a <= sec < b for a, b in outs)

    backlog = 0
    max_b = 0
    crossed_at_minute = None
    for t in range(total_s):
        slope = sensor if down(t) else sensor - link
        backlog += slope
        if backlog < 0:
            backlog = 0
        if backlog > max_b:
            max_b = backlog
        if crossed_at_minute is None and backlog >= cap_mb:
            crossed_at_minute = math.ceil((t + 1) / 60)
    return max_b, backlog, max_b > cap_mb, crossed_at_minute


# ------------------------------------------------------------------ rendering

def model_sysml(platform: str, sensor: int, link: int, mission: int,
                windows: list[tuple[int, int]], cap_mb: int) -> str:
    usage, _plat, _path = PLATFORMS[platform]
    comment = {
        "usv": "USV buffers EO/IR imagery and AIS tracks and downlinks them via the "
               "command ship to the shore archive.",
        "uav": "UAV buffers search-radar tracks and EO imagery and relays them over "
               "its radio link to the command ship.",
    }[platform]
    w = list(windows) + [(0, 0)] * (2 - len(windows))
    outage2_note = "0.0 means there is no second outage window"
    return f"""package MaritimeBacklog {{
    /* Synthetic maritime ISR SIM task (family sim_backlog). Numbers are not RTX specifications. */
    private import SI::*;
    private import ISQ::*;
    private import ISQInformation::*;

    attribute <'Mbit'> megabit : StorageCapacityUnit = 1000000 * SI::bit;
    attribute <'Mbit/s'> 'megabit per second' : BinaryDigitRateUnit = 1000000 * SI::'bit/s';

    calc def OutageGrowth {{
        in source : BinaryDigitRateValue;
        in outage : TimeValue;
        return growth : StorageCapacityValue = source * outage;
    }}

    calc def NetDrainRate {{
        in source : BinaryDigitRateValue;
        in downlink : BinaryDigitRateValue;
        return net : BinaryDigitRateValue = downlink - source;
    }}

    constraint def BufferFits {{
        in peak : StorageCapacityValue;
        in capacity : StorageCapacityValue;
        peak <= capacity
    }}

    part def RelayBuffer {{
        attribute sensorRate : BinaryDigitRateValue = {sensor} ['Mbit/s'];
        attribute downlinkRate : BinaryDigitRateValue = {link} ['Mbit/s'];
        attribute missionMin : ScalarValues::Real = {float(mission):.1f};
        attribute outage1StartMin : ScalarValues::Real = {float(w[0][0]):.1f};
        attribute outage1DurationMin : ScalarValues::Real = {float(w[0][1]):.1f};
        attribute outage2StartMin : ScalarValues::Real = {float(w[1][0]):.1f}; /* {outage2_note} */
        attribute outage2DurationMin : ScalarValues::Real = {float(w[1][1]):.1f};
        attribute bufferCapacity : StorageCapacityValue = {cap_mb} ['Mbit'];
    }}

    part {usage} : RelayBuffer {{
        /* {comment} */
    }}

    requirement def BufferNoOverflow {{
        subject relay : RelayBuffer;
        doc /* The relay backlog stays at or below the buffer capacity during the whole mission. */
    }}
}}
"""


NARRATIVE = {
    "usv": ("USV `usv`", "The USV buffers EO/IR imagery and AIS tracks on board and downlinks "
            "them over its radio link — through the command ship — to the shore archive "
            "(path usv → shore)."),
    "uav": ("fixed-wing UAV `uav`", "The UAV buffers search-radar tracks and EO imagery on "
            "board and relays them over its radio link to the command ship fusion node "
            "(path uav → command ship)."),
}


def requirements_md(task_id: str, platform: str, sensor: int, link: int, mission: int,
                    windows: list[tuple[int, int]], reasons: list[str], cap_gb: float,
                    cap_mb: int) -> str:
    plat, story = NARRATIVE[platform]
    why = "; ".join(f"window {i + 1}: {reasons[i]}" for i in range(len(windows)))
    hours = mission / 60
    win_lines = "\n".join(
        f"- Outage window {i + 1}: start {s} min, duration {d} min ({reasons[i]})"
        for i, (s, d) in enumerate(windows))
    return f"""# {task_id} — SIM link-outage backlog (synthetic; not an RTX specification)

This is a closed-form data-backlog bookkeeping question over one relay path of the
synthetic maritime ISR four-node picture (USV and fixed-wing UAV → command ship →
shore archive). It does not ask you to write or edit SysML. The file `model.sysml`
in this folder carries the same parameters as a SysML v2 model; the numbers in
this document are authoritative.

## Relay path

Platform: {plat}. {story}
During the outage window(s) below the link is down ({why}). While the link is
down the sensors keep writing to the buffer; when the link is up it drains the
buffer and also carries the live stream.

## Parameters

- Sensor data rate (whole mission, constant): {sensor} Mbit/s
- Downlink rate while the link is up: {link} Mbit/s
- Mission length: {mission} min ({hours:.1f} h)
- Buffer capacity: {cap_mb} Mbit = {cap_gb:g} GB
{win_lines}

All times are minutes after mission start; the buffer starts empty at t = 0.

## Backlog rules (piecewise linear)

1. During an outage window the backlog grows at the sensor rate: `60 x sensor` Mbit per minute.
2. While the link is up and the buffer is non-empty, the backlog changes at `60 x (sensor - link)` Mbit per minute (negative when the downlink is faster).
3. The backlog never goes below 0: once it reaches 0 it stays 0 while the link is up and the downlink can carry the live stream (sensor <= downlink). If the sensor rate exceeds the downlink rate, the backlog grows at `60 x (sensor - link)` Mbit per minute even from empty.
4. The backlog is not capped in this calculation: once it passes the capacity, data is lost and the backlog keeps growing.

## Units and conversions

- 1 GB = 8000 Mbit (so {cap_gb:g} GB = {cap_mb} Mbit).
- A rate of R Mbit/s held for m minutes moves `R x 60 x m` Mbit.

## Reply with exactly one JSON object

{{"overflows": <true|false>, "overflow_at_min": <int or null>,
 "max_backlog_gb": <number>, "end_backlog_gb": <number>, "end_headroom_gb": <number>}}

- `overflows`: true iff the backlog exceeds the buffer capacity at any time in [0, mission].
- `overflow_at_min`: the first whole minute at which the backlog is at or above the capacity (ceiling of the exact crossing time); null if it never overflows.
- `max_backlog_gb`: maximum backlog over the mission, GB, 2 decimals.
- `end_backlog_gb`: backlog at mission end, GB, 2 decimals.
- `end_headroom_gb`: capacity minus backlog at mission end, GB (negative when over capacity), 2 decimals.
"""


def solution_md(task_id: str, platform: str, sensor: int, link: int, mission: int,
                windows: list[tuple[int, int]], reasons: list[str], cap_gb: float,
                gold: dict) -> str:
    plat, _story = NARRATIVE[platform]
    rows = gold["rows"]
    cap_mb = gold["cap_mb"]
    max_b, end_b = gold["max_b"], gold["end_b"]
    hours = mission / 60
    head = [
        f"# {task_id} — closed-form solution (human-checkable arithmetic)",
        "",
        f"No simulation loop is needed: the backlog is piecewise linear because the sensor",
        f"rate and the downlink rate are constant and the outage windows have sharp edges.",
        f"Platform {plat}; sensor {sensor} Mbit/s; downlink {link} Mbit/s while up;",
        f"mission {mission} min ({hours:.1f} h); capacity {cap_mb} Mbit = {cap_gb:g} GB"
        f" (1 GB = 8000 Mbit).",
        "",
        "Slopes in Mbit per minute: outage `60 x {s} = {so}`; link up "
        "`60 x ({s} - {l}) = {su}`.".format(s=sensor, l=link, so=60 * sensor,
                                            su=60 * (sensor - link)),
        "",
        "Segments (backlog in Mbit, integer arithmetic):",
        "",
        "| # | from (min) | to (min) | regime | slope (Mbit/min) | B at start | B at end |",
        "|---|-----------|----------|--------|------------------|-----------|----------|",
    ]
    for i, (t0, t1, regime, slope, b0, b1) in enumerate(rows, 1):
        f_t0 = float(t0)
        f_t1 = float(t1)
        name = {"outage": "outage window", "link-up": "link up",
                "link-up-empty": "link up, buffer empty (stays 0)"}[regime]
        head.append(f"| {i} | {f_t0:g} | {f_t1:g} | {name} | {slope:+d} | {b0} | {b1} |")
    for i, (s, d) in enumerate(windows):
        head.append(f"\nOutage window {i + 1}: [{s}, {s + d}] min ({reasons[i]}), "
                    f"duration {d} min, adds {60 * sensor} x {d} = {60 * sensor * d} Mbit if it starts empty.")
    head += [
        "",
        f"- Maximum backlog = **{max_b} Mbit** = {max_b} / 8000 = **{gb(max_b):.2f} GB** "
        f"(reached at t = {float(rows[[r[5] for r in rows].index(max_b)][1]):g} min).",
        f"- Backlog at mission end t = {mission} min = {end_b} Mbit = {gb(end_b):.2f} GB.",
        f"- end_headroom_gb = {cap_gb:g} - {gb(end_b):.2f} = "
        f"{math.floor((cap_mb - end_b) / MB_PER_GB * 100 + 0.5) / 100:.2f} GB.",
    ]
    if gold["overflows"]:
        t_star = gold["t_star"]
        i = next(k for k, (t0, t1, _r, _s, b0, b1) in enumerate(rows)
                 if b1 > b0 and b0 <= cap_mb < b1)
        t0, t1, _r, slope, b0, b1 = rows[i]
        head += [
            "",
            f"Overflow crossing (segment {i + 1}, slope {slope:+d} Mbit/min):",
            f"t* = {t0} + ({cap_mb} - {b0}) / {slope:+d} = {t0} + "
            f"{Fraction(cap_mb - b0, slope)} = {float(t_star):.3f} min,",
            f"so the first whole minute at or above capacity is "
            f"ceil({float(t_star):.3f}) = **{gold['overflow_at_min']}**.",
            f"- overflows: peak {max_b} Mbit > capacity {cap_mb} Mbit → **true**.",
            "",
            f"Tolerance contract (numeric ±2 % relative, times ±2 min): the peak is "
            f"{abs(max_b - cap_mb) / cap_mb:.1%} of capacity away from it "
            f"(>= {MARGIN_MULT * TOL_REL:.0%} required); the crossing at "
            f"{float(t_star):.3f} min is {float(t_star):.1f} min from mission start and "
            f"{mission - float(t_star):.1f} min from mission end (>= {MARGIN_MULT * TOL_MIN} required).",
        ]
    else:
        head += [
            "",
            f"- overflows: peak {max_b} Mbit <= capacity {cap_mb} Mbit → **false**; "
            f"overflow_at_min = **null**.",
            "",
            f"Tolerance contract (numeric ±2 % relative): the peak is "
            f"{abs(max_b - cap_mb) / cap_mb:.1%} of capacity away from it "
            f"(>= {MARGIN_MULT * TOL_REL:.0%} required), so the verdict is unambiguous.",
        ]
    return "\n".join(head) + "\n"


def write_task(folder: Path, task_id: str, platform: str, sensor: int, link: int,
               mission: int, windows: list[tuple[int, int]], reasons: list[str],
               cap_gb: float, gold: dict) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    cap_mb = gold["cap_mb"]
    case = {
        "id": task_id, "type": "SIM", "scenario_family": "t_sim_bank", "split": "staging",
        "package": "MaritimeBacklog", "synthetic": True, "status": "generated",
        "generator": "bench/build_sim_backlog.py", "seed": SEED, "answer_mode": "json",
        "platform": platform, "path": PLATFORMS[platform][2],
    }
    (folder / "case.yaml").write_text(yaml.safe_dump(case, sort_keys=False), encoding="utf-8")
    (folder / "input").mkdir(parents=True, exist_ok=True)
    (folder / "gold").mkdir(parents=True, exist_ok=True)
    (folder / "input" / "model.sysml").write_text(
        model_sysml(platform, sensor, link, mission, windows, cap_mb), encoding="utf-8")
    (folder / "input" / "requirements.md").write_text(
        requirements_md(task_id, platform, sensor, link, mission, windows, reasons, cap_gb, cap_mb),
        encoding="utf-8")
    answer = {
        "task_id": task_id,
        "overflows": gold["overflows"],
        "overflow_at_min": gold["overflow_at_min"],
        "max_backlog_gb": gb(gold["max_b"]),
        "end_backlog_gb": gb(gold["end_b"]),
        "end_headroom_gb": math.floor((gold["cap_mb"] - gold["end_b"]) / MB_PER_GB * 100 + 0.5) / 100,
    }
    (folder / "gold" / "answer.json").write_text(
        json.dumps(answer, indent=2) + "\n", encoding="utf-8")
    checks: dict = {
        "overflows": {"gold": gold["overflows"], "exact": True},
        "overflow_at_min": ({"gold": gold["overflow_at_min"], "exact": True}
                            if gold["overflow_at_min"] is None
                            else {"gold": gold["overflow_at_min"], "abs_tol_min": TOL_MIN}),
        "max_backlog_gb": {"gold": answer["max_backlog_gb"], "rel_tol": TOL_REL, "abs_tol_gb": 0.05},
        "end_backlog_gb": {"gold": answer["end_backlog_gb"], "rel_tol": TOL_REL, "abs_tol_gb": 0.05},
        "end_headroom_gb": {"gold": answer["end_headroom_gb"], "rel_tol": TOL_REL, "abs_tol_gb": 0.05},
    }
    assertions = {"task_id": task_id, "package": "MaritimeBacklog", "family": "sim_backlog",
                  "answer_mode": "json",
                  "tolerances": {"numeric_rel": TOL_REL, "time_abs_min": TOL_MIN,
                                 "boolean_exact": True, "abs_floor_gb": 0.05},
                  "checks": checks}
    (folder / "gold" / "assertions.yaml").write_text(
        yaml.safe_dump(assertions, sort_keys=False), encoding="utf-8")
    (folder / "gold" / "solution.md").write_text(
        solution_md(task_id, platform, sensor, link, mission, windows, reasons, cap_gb, gold),
        encoding="utf-8")


# ------------------------------------------------------------------- sampling

def sample_params(rng: random.Random, link_case: str, n_windows: int):
    sensor = rng.randint(2, 50)
    if link_case == "ge":
        link = rng.randint(sensor, min(80, sensor + max(4, round(0.8 * sensor))))
    else:
        link = rng.randint(max(1, math.ceil(sensor / 3)), sensor - 1)
    mission = 30 * rng.randint(4, 24)  # 120..720 min = 2..12 h
    windows: list[tuple[int, int]] = []
    for _ in range(50):  # placement attempts
        cand = []
        for _ in range(n_windows):
            dur = 5 * rng.randint(2, min(36, mission // 5))  # 10..180 min, fits the mission
            start = 5 * rng.randint(0, (mission - dur) // 5)
            cand.append((start, dur))
        cand.sort()
        ok = all(cand[i + 1][0] - (cand[i][0] + cand[i][1]) >= 30 for i in range(len(cand) - 1))
        if ok:
            windows = cand
            break
    if not windows:
        return None
    outage_min = sum(d for _s, d in windows)
    if link_case == "lt":
        rough_peak = 60 * (sensor - link) * (mission - outage_min) + 60 * sensor * outage_min
    else:
        rough_peak = 60 * sensor * outage_min  # upper bound: ignores drain between windows
    factor = math.exp(rng.uniform(math.log(0.55), math.log(1.6)))
    cap_gb = max(1.0, round(2 * rough_peak * factor / MB_PER_GB) / 2)
    return sensor, link, mission, windows, cap_gb


def margin_verdict(sensor, link, mission, windows, cap_gb) -> tuple[dict | None, str | None]:
    """Return (gold, None) if every acceptance margin holds, else (None, reason)."""
    gold = gold_of(sensor, link, mission, windows, cap_gb)
    max_b, end_b, cap_mb = gold["max_b"], gold["end_b"], gold["cap_mb"]
    if abs(max_b - cap_mb) < MARGIN_MULT * TOL_REL * cap_mb:
        return None, "margin_capacity"
    if gold["overflows"]:
        t_star = float(gold["t_star"])
        if t_star < MARGIN_MULT * TOL_MIN or t_star > mission - MARGIN_MULT * TOL_MIN:
            return None, "margin_time"
    if max_b / MB_PER_GB < 0.5:
        return None, "tiny_max"
    if 0 < end_b / MB_PER_GB < 0.25:
        return None, "tiny_end"
    return gold, None


# ----------------------------------------------------------------- self-checks

RX = {
    "sensor": re.compile(r"Sensor data rate \(whole mission, constant\): (\d+) Mbit/s"),
    "link": re.compile(r"Downlink rate while the link is up: (\d+) Mbit/s"),
    "mission": re.compile(r"Mission length: (\d+) min"),
    "cap": re.compile(r"Buffer capacity: (\d+) Mbit = ([0-9.]+) GB"),
    "window": re.compile(r"Outage window (\d): start (\d+) min, duration (\d+) min"),
}


def reparse_requirements(text: str):
    sensor = int(RX["sensor"].search(text).group(1))
    link = int(RX["link"].search(text).group(1))
    mission = int(RX["mission"].search(text).group(1))
    cap_mb = int(RX["cap"].search(text).group(1))
    windows = sorted((int(m.group(2)), int(m.group(3))) for m in RX["window"].finditer(text))
    return sensor, link, mission, windows, cap_mb


def verify_bank(tasks: list[dict]) -> None:
    for task in tasks:
        folder = OUT / task["id"]
        gold = gold_of(task["sensor"], task["link"], task["mission"], task["windows"], task["cap_gb"])
        # (a) independent one-second stepper, exact agreement required
        s_max, s_end, s_ovf, s_min = sim_seconds(
            task["sensor"], task["link"], task["mission"], task["windows"], gold["cap_mb"])
        assert s_max == gold["max_b"], (task["id"], "sim max", s_max, gold["max_b"])
        assert s_end == gold["end_b"], (task["id"], "sim end")
        assert s_ovf == gold["overflows"], (task["id"], "sim overflow")
        assert s_min == gold["overflow_at_min"], (task["id"], "sim minute", s_min, gold["overflow_at_min"])
        # (b) re-parse the generated requirements.md and recompute from the text
        text = (folder / "input" / "requirements.md").read_text(encoding="utf-8")
        p_sensor, p_link, p_mission, p_windows, p_cap = reparse_requirements(text)
        assert (p_sensor, p_link, p_mission) == (task["sensor"], task["link"], task["mission"])
        assert p_windows == [tuple(w) for w in task["windows"]] and p_cap == gold["cap_mb"]
        regold = gold_of(p_sensor, p_link, p_mission, p_windows, p_cap / MB_PER_GB)
        assert regold["overflows"] == gold["overflows"] and regold["max_b"] == gold["max_b"]
        assert regold["end_b"] == gold["end_b"]
        assert regold["overflow_at_min"] == gold["overflow_at_min"]
        # (c) answer.json carries the same numbers as the recomputed gold
        answer = json.loads((folder / "gold" / "answer.json").read_text(encoding="utf-8"))
        assert answer["overflows"] == gold["overflows"]
        assert answer["overflow_at_min"] == gold["overflow_at_min"]
        assert answer["max_backlog_gb"] == gb(gold["max_b"])
        assert answer["end_backlog_gb"] == gb(gold["end_b"])


def pilot_check(tasks: list[dict], n: int) -> list[dict]:
    """Run the official Pilot validator on n spread model.sysml files (read-only)."""
    sys.path.insert(0, str(ROOT))
    from mvp.toolchain.validate import validate_package  # noqa: E402
    picks = [tasks[0], tasks[len(tasks) // 3], tasks[2 * len(tasks) // 3], tasks[-1]][:n]
    report = []
    for task in picks:
        out = Path("/tmp") / f"pilot-{task['id']}"
        if out.exists():
            shutil.rmtree(out)
        result = validate_package([str(OUT / task["id"] / "input" / "model.sysml")],
                                  "MaritimeBacklog", str(out))
        report.append({"id": task["id"], "status": result["status"],
                       "warnings": result.get("warning_count", 0)})
        print(f"pilot {task['id']}: {result['status']}")
    return report


# ----------------------------------------------------------------------- main

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", type=int, default=0,
                        help="also run the official Pilot validator on N spread tasks")
    args = parser.parse_args()

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    rng = random.Random(SEED)
    open_cells = dict(QUOTAS)
    platforms = ["usv"] * 210 + ["uav"] * 140  # 6:4 mix per family brief
    rng.shuffle(platforms)
    tasks: list[dict] = []
    rejected: list[dict] = []
    seen: set[tuple] = set()
    attempts = 0
    while any(v > 0 for v in open_cells.values()):
        attempts += 1
        if attempts > MAX_ATTEMPTS:
            raise SystemExit(f"sampling exhausted, cells left: {open_cells}")
        cell_keys = [k for k, v in open_cells.items() if v > 0]
        cell = cell_keys[rng.randrange(len(cell_keys))]
        link_case, n_windows, want_ovf = cell
        sample = sample_params(rng, link_case, n_windows)
        if sample is None:
            rejected.append({"cell": list(cell), "reason": "window_layout"})
            continue
        sensor, link, mission, windows, cap_gb = sample
        params = {"cell": list(cell), "sensor_mbps": sensor, "link_mbps": link,
                  "mission_min": mission, "windows": [list(w) for w in windows],
                  "capacity_gb": cap_gb}
        key = (sensor, link, mission, tuple(windows), cap_gb)
        if key in seen:
            rejected.append({**params, "reason": "duplicate"})
            continue
        gold, reason = margin_verdict(sensor, link, mission, windows, cap_gb)
        if gold is None:
            rejected.append({**params, "reason": reason})
            continue
        if gold["overflows"] != want_ovf:
            rejected.append({**params, "reason": "cell_full"})
            continue
        seen.add(key)
        open_cells[cell] -= 1
        reasons = rng.sample(REASONS, n_windows)
        tasks.append({"id": f"BLG-{len(tasks) + 1:04d}", **params, "reasons": reasons,
                      "sensor": sensor, "link": link, "mission": mission,
                      "windows": [tuple(w) for w in windows], "cap_gb": cap_gb})
    if len(tasks) != N_TARGET:
        raise SystemExit(f"expected {N_TARGET} tasks, got {len(tasks)}")

    for task, platform in zip(tasks, platforms):
        task["platform"] = platform
        gold = gold_of(task["sensor"], task["link"], task["mission"], task["windows"], task["cap_gb"])
        task["gold"] = gold
        write_task(OUT / task["id"], task["id"], platform, task["sensor"], task["link"],
                   task["mission"], task["windows"], task["reasons"], task["cap_gb"], gold)

    verify_bank(tasks)

    index_lines = [json.dumps({"id": t["id"], "type": "SIM",
                               "path": f"bench/tasks_staging/t_sim_bank/sim_backlog/{t['id']}"})
                   for t in tasks]
    (OUT / "index.jsonl").write_text("\n".join(index_lines) + "\n", encoding="utf-8")

    manifest_tasks = []
    for t in tasks:
        manifest_tasks.append({
            "id": t["id"], "platform": t["platform"], "path": PLATFORMS[t["platform"]][2],
            "params": {"sensor_mbps": t["sensor"], "link_mbps": t["link"],
                       "link_case": "ge" if t["link"] >= t["sensor"] else "lt",
                       "mission_min": t["mission"],
                       "windows": [{"start_min": s, "duration_min": d, "reason": r}
                                   for (s, d), r in zip(t["windows"], t["reasons"])],
                       "capacity_gb": t["cap_gb"]},
            "gold": {"overflows": t["gold"]["overflows"],
                     "overflow_at_min": t["gold"]["overflow_at_min"],
                     "max_backlog_gb": gb(t["gold"]["max_b"]),
                     "end_backlog_gb": gb(t["gold"]["end_b"]),
                     "end_headroom_gb": math.floor((t["gold"]["cap_mb"] - t["gold"]["end_b"])
                                                   / MB_PER_GB * 100 + 0.5) / 100},
            "difficulty": f"{len(t['windows'])}win/" + ("overflow" if t["gold"]["overflows"] else "safe"),
        })
    by_difficulty: dict[str, int] = {}
    by_platform: dict[str, int] = {}
    by_path: dict[str, int] = {}
    by_case: dict[str, int] = {}
    for entry in manifest_tasks:
        by_difficulty[entry["difficulty"]] = by_difficulty.get(entry["difficulty"], 0) + 1
        by_platform[entry["platform"]] = by_platform.get(entry["platform"], 0) + 1
        by_path[entry["path"]] = by_path.get(entry["path"], 0) + 1
        by_case[entry["params"]["link_case"]] = by_case.get(entry["params"]["link_case"], 0) + 1
    reason_counts: dict[str, int] = {}
    for r in rejected:
        reason_counts[r["reason"]] = reason_counts.get(r["reason"], 0) + 1
    manifest = {
        "family": "sim_backlog",
        "generator": "bench/build_sim_backlog.py",
        "seed": SEED,
        "count": len(tasks),
        "closed_form": {
            "backlog": ["link up, non-empty buffer: dB/dt = 60*(sensor-link) Mbit/min",
                        "link up, empty buffer: dB/dt clamped at 0",
                        "outage window: dB/dt = 60*sensor Mbit/min",
                        "B(0) = 0, 1 GB = 8000 Mbit"],
            "overflows": "max B over [0,mission] > 8000*capacity_gb (strict)",
            "overflow_at_min": "ceil(t*) with t* the first time B(t) = 8000*capacity_gb; null if no overflow",
            "max_backlog_gb": "max B / 8000",
            "end_backlog_gb": "B(mission) / 8000",
            "end_headroom_gb": "capacity_gb - end_backlog_gb",
        },
        "parameter_space": {
            "sensor_mbps": "2..50 integer", "link_mbps": "integer; ge case link>=sensor (cap 80), lt case ceil(sensor/3)..sensor-1",
            "mission_min": "120..720 in 30-min steps", "outage_windows": "1 or 2; each 10..180 min in 5-min steps; starts on 5-min grid; two windows separated by >=30 min",
            "capacity_gb": "multiple of 0.5, >=1.0, drawn as log-uniform factor 0.55..1.6 of a rough analytic peak",
            "platform": "usv 210 / uav 140 (6:4)", "outage_reasons": REASONS,
        },
        "constraints": {
            "tolerances": {"numeric_rel": TOL_REL, "time_abs_min": TOL_MIN, "boolean": "exact",
                           "abs_floor_gb": 0.05},
            "margins": ["|peak-capacity| >= 3*2% of capacity", "crossing >= 3*2 min from both mission edges",
                        "max_backlog >= 0.5 GB", "end backlog exactly 0 or >= 0.25 GB",
                        "unique parameter vector"],
            "overflow_balance": {"overflow": sum(1 for e in manifest_tasks if e["gold"]["overflows"]),
                                 "safe": sum(1 for e in manifest_tasks if not e["gold"]["overflows"])},
        },
        "stats": {"by_difficulty": by_difficulty, "by_platform": by_platform, "by_path": by_path,
                  "by_link_case": by_case, "sampling_attempts": attempts,
                  "accepted": len(tasks), "rejected": len(rejected),
                  "rejected_by_reason": reason_counts},
        "tasks": manifest_tasks,
        "rejected_params": rejected,
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"{len(tasks)} tasks in {OUT}")
    print(f"attempts={attempts} rejected={len(rejected)} by_reason={reason_counts}")
    print(f"difficulty={by_difficulty} platform={by_platform}")
    if args.pilot:
        pilot_report = pilot_check(tasks, args.pilot)
        manifest["pilot_check"] = pilot_report
        (OUT / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if any(r["status"] != "PASS" for r in pilot_report):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
