"""Deterministic SIM multi-hop latency task generator (250 tasks, closed-form gold).

Family `sim_latency` under bench/tasks_staging/t_sim_bank/sim_latency/ (a new tree;
nothing in bench/tasks/, FREEZE.md, or any existing file is read for writing or
modified). Narrative: the synthetic maritime ISR four-node picture (USV and
fixed-wing UAV -> command ship / shore station -> final subscriber); each task is
one sensor-to-subscriber data path whose relay transmits only on fixed windows.

Model of the family: every message follows the same chain

    t_collect -> onboard processing (constant) -> uplink propagation
      (distance / propagation speed) -> relay processing (constant)
      -> wait for the next transmit window -> downlink propagation
      -> final subscriber

so the per-message end-to-end delay is closed form:

    ready_i  = (i-1)*spacing + proc_src + prop_up + proc_relay          [s]
    k_i      = smallest k >= 0 with phase + k*period >= ready_i
    wait_i   = phase + k_i*period - ready_i                             [s]
    e2e_i    = proc_src + prop_up + proc_relay + wait_i + prop_down     [s]
    fresh_i  = e2e_i <= staleness_threshold

Gold keys (all exact rational arithmetic; only the reported values are rounded):

    mean_e2e_s      = mean of e2e_i, 1 decimal
    max_e2e_s       = max of e2e_i, 1 decimal
    fresh_ratio     = fresh_count / n_messages, 4 decimals
    meets_staleness = mean_e2e_s <= staleness_threshold (boolean)

No language model is called anywhere: this file IS the answer key. Re-running
with the same seed reproduces the bank byte for byte (it wipes only its own
staging directory first). After writing, the script re-parses every generated
requirements.md and recomputes the gold from the parsed text as an independent
write/format check.

Acceptance rules (rejects are recorded in manifest.json):
  - mix: 1 <= fresh_count <= n-1 (fresh_ratio strictly inside (0, 1), so the
    relative tolerance band is meaningful and the ratio is not trivial);
  - every message e2e sits >= 3x the 2% tolerance band from the staleness
    threshold, and so does the mean (unambiguous fresh/side classification);
  - unique parameter vector (normalized distance >= 0.12);
  - meets_staleness true/false split is slot-balanced (125/125).
Distances are multiples of 3 km so every propagation delay is a terminating
decimal (acoustic uplink delays are whole seconds). Tasks whose index is
12 mod 25 are "window boundary" constructions: the phase is derived so message 1
is ready exactly at a window opening (wait = 0), exercising the stated
"at or after" rule on the boundary.

Each task folder LAT-NNNN/ contains:
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
OUT = ROOT / "bench" / "tasks_staging" / "t_sim_bank" / "sim_latency"

SEED = 20261010
N_TASKS = 250
N_TRUE = 125           # meets_staleness true count: exactly balanced 125/125

# --- tolerance contract (mirrored into gold/assertions.yaml) -------------------
TOL_REL = 0.02         # +/- 2% relative on every seconds value
RATIO_TOL = 0.02       # +/- 2% (absolute floor 0.02) on fresh_ratio
MARGIN_FACTOR = 3      # gold must sit >= 3x the tolerance band from the threshold

# --- parameter space ------------------------------------------------------------
PROC_MIN, PROC_MAX = 1, 500            # s, per hop
PERIOD_MIN_MIN, PERIOD_MAX_MIN = 5, 30  # transmit window period, minutes
SPACING_MIN_MIN, SPACING_MAX_MIN = 1, 15  # message spacing, minutes
N_MSG_MIN, N_MSG_MAX = 3, 10
THRESH_MIN_S, THRESH_MAX_S, THRESH_STEP_S = 120, 1200, 60   # 2..20 min
SPEED_ACOUSTIC = 1500                  # m/s, underwater acoustic
SPEED_RADIO = 300_000_000              # m/s, radio
SPEED_FIBER = 200_000_000              # m/s, fiber trunk
D_ACOUSTIC = (6, 45, 3)                # km, multiples of 3 -> whole-second delays
D_RADIO_UP = (12, 300, 3)              # km
D_DOWN = (30, 300, 3)                  # km

DEDUP_MIN_DIST = 0.12
MAX_SAMPLES = 500_000

PLATFORM_TEXT = {
    "usv": "an unmanned surface vessel (USV)",
    "uav": "the fixed-wing UAV",
}
PATH_OF = {"usv": "usv-to-shore", "uav": "uav-to-command-ship"}
RELAY_OF = {"usv": "shore station", "uav": "command ship"}
SUBSCRIBER_OF = {
    "usv": "maritime operations center",
    "uav": "shore headquarters",
}
MEDIUM_TEXT = {
    "acoustic": "underwater acoustic",
    "radio": "air-to-surface radio",
    "surface_radio": "surface radio",
    "fiber": "fiber trunk",
    "hf_radio": "high-frequency radio",
}


def platform_for(index: int) -> str:
    """Deterministic USV:UAV = 6:4 split (task number mod 5 < 3 -> USV)."""
    return "usv" if index % 5 < 3 else "uav"


def boundary_for(index: int) -> bool:
    """Every 25th task (index = 12 mod 25) is a window-boundary construction."""
    return index % 25 == 12


def fmt(x: Fraction, places: int = 6) -> str:
    """Exact-looking decimal for a terminating Fraction, trailing zeros trimmed."""
    scaled = x * (10 ** places) + Fraction(1, 2)
    digits = str(math.floor(scaled)).rjust(places + 1, "0")
    text = digits[:-places] + "." + digits[-places:] if places else digits
    return text.rstrip("0").rstrip(".") if "." in text else text


def rnd(x: Fraction, places: int) -> float:
    scaled = x * (10 ** places) + Fraction(1, 2)
    return float(math.floor(scaled)) / (10 ** places)


def f1(x: Fraction) -> str:
    return f"{rnd(x, 1):.1f}"


def f4(x: Fraction) -> str:
    return f"{rnd(x, 4):.4f}"


# --- sampling --------------------------------------------------------------------
def sample(rng: random.Random, platform: str, boundary: bool) -> dict:
    up_medium = "radio" if platform == "uav" else (
        "acoustic" if boundary or rng.random() < 0.5 else "surface_radio")
    if platform == "uav":
        down_medium = "hf_radio"
    else:
        down_medium = "fiber"
    n_msg = rng.randint(N_MSG_MIN, N_MSG_MAX)
    proc_src = rng.randint(PROC_MIN, PROC_MAX)
    proc_relay = rng.randint(PROC_MIN, PROC_MAX)
    period_s = 60 * rng.randint(PERIOD_MIN_MIN, PERIOD_MAX_MIN)
    spacing_s = 60 * rng.randint(SPACING_MIN_MIN, SPACING_MAX_MIN)
    if up_medium == "acoustic":
        d_up, v_up = rng.randrange(*D_ACOUSTIC), SPEED_ACOUSTIC
    else:
        d_up, v_up = rng.randrange(*D_RADIO_UP), SPEED_RADIO
    d_down = rng.randrange(*D_DOWN)
    v_down = SPEED_RADIO if down_medium == "hf_radio" else SPEED_FIBER
    prop_up = Fraction(d_up * 1000, v_up)
    prop_down = Fraction(d_down * 1000, v_down)
    if boundary:
        # align the schedule so message 1 (collected at t = 0) is ready exactly
        # at a window opening: wait = 0 on the "at or after" boundary
        if prop_up.denominator != 1:
            raise SystemExit("boundary construction needs a whole-second uplink delay")
        phase_s = int(proc_src + prop_up + proc_relay) % period_s
    else:
        phase_s = rng.randrange(0, period_s)
    return {
        "platform": platform,
        "boundary": boundary,
        "up_medium": up_medium,
        "down_medium": down_medium,
        "n_msg": n_msg,
        "proc_src_s": proc_src,
        "proc_relay_s": proc_relay,
        "period_s": period_s,
        "phase_s": phase_s,
        "spacing_s": spacing_s,
        "d_up_km": d_up,
        "v_up": v_up,
        "d_down_km": d_down,
        "v_down": v_down,
        "prop_up_s": prop_up,
        "prop_down_s": prop_down,
    }


# --- closed form -------------------------------------------------------------------
def solve(p: dict, threshold_s: Fraction) -> dict:
    proc = Fraction(p["proc_src_s"] + p["proc_relay_s"])
    ready0 = Fraction(p["proc_src_s"]) + p["prop_up_s"] + Fraction(p["proc_relay_s"])
    period = Fraction(p["period_s"])
    phase = Fraction(p["phase_s"])
    base = ready0 + p["prop_down_s"]
    messages = []
    for i in range(p["n_msg"]):
        collect = Fraction(i * p["spacing_s"])
        ready = ready0 + collect
        k = -((phase - ready) // period)       # ceil((ready - phase)/period)
        k = max(0, k)
        wait = phase + k * period - ready
        e2e = base + wait
        messages.append({
            "i": i + 1, "collect_s": collect, "ready_s": ready,
            "window_s": phase + k * period, "k": k, "wait_s": wait, "e2e_s": e2e,
        })
    e2es = [m["e2e_s"] for m in messages]
    mean = sum(e2es, Fraction(0)) / Fraction(p["n_msg"])
    fresh = [e <= threshold_s for e in e2es]
    return {
        "base_s": base, "proc_total_s": proc, "messages": messages,
        "mean_e2e": mean, "max_e2e": max(e2es), "min_e2e": min(e2es),
        "fresh": fresh, "fresh_count": sum(fresh),
        "meets": mean <= threshold_s,
    }


def margins_ok(p: dict, s: dict, threshold_s: Fraction) -> bool:
    band = Fraction(MARGIN_FACTOR * TOL_REL)   # 3 x 2% = 6%
    if s["fresh_count"] < 1 or s["fresh_count"] > p["n_msg"] - 1:
        return False
    if any(abs(e - threshold_s) < band * e for e in (m["e2e_s"] for m in s["messages"])):
        return False
    if abs(s["mean_e2e"] - threshold_s) < band * s["mean_e2e"]:
        return False
    return True


def feasible_thresholds(p: dict) -> list[tuple[int, bool]]:
    """All staleness thresholds (2..20 min on the minute grid) that pass the
    acceptance margins, with their meets_staleness label."""
    out = []
    for t in range(THRESH_MIN_S, THRESH_MAX_S + 1, THRESH_STEP_S):
        s = solve(p, Fraction(t))
        if margins_ok(p, s, Fraction(t)):
            out.append((t, s["meets"]))
    return out


# --- accept / reject ----------------------------------------------------------------
def param_vector(p: dict, threshold_s: int) -> list[float]:
    return [
        p["proc_src_s"] / 500.0,
        p["proc_relay_s"] / 500.0,
        p["period_s"] / 1800.0,
        p["phase_s"] / 1800.0,
        p["spacing_s"] / 900.0,
        p["n_msg"] / 10.0,
        threshold_s / 1200.0,
        p["d_up_km"] / 300.0,
        p["d_down_km"] / 300.0,
        1.0 if p["up_medium"] == "acoustic" else 0.0,
        1.0 if p["down_medium"] == "fiber" else 0.0,
    ]


def acceptable(p: dict, vector: list[float], accepted: list[list[float]]) -> bool:
    for other in accepted:
        dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(vector, other)))
        if dist < DEDUP_MIN_DIST:
            return False
    return True


# --- writers ---------------------------------------------------------------------------
def model_sysml(p: dict) -> str:
    part = "usvLink" if p["platform"] == "usv" else "uavLink"
    doc = {
        "usv": "/* USV sensor data reaches the maritime operations center through the shore station relay, which transmits only on fixed windows. */",
        "uav": "/* UAV sensor data reaches the shore headquarters through the command ship relay, which transmits only on fixed windows. */",
    }[p["platform"]]
    return f"""package LatencyChain {{
    /* Synthetic maritime ISR SIM task (family sim_latency). Numbers are not RTX specifications. */
    private import SI::*;
    private import ISQ::*;

    calc def PropagationDelay {{
        in distance : LengthValue;
        in speed : SpeedValue;
        return delay : TimeValue = distance / speed;
    }}

    calc def FixedChainLatency {{
        in onboard : TimeValue;
        in uplink : TimeValue;
        in relay : TimeValue;
        in downlink : TimeValue;
        return base : TimeValue = onboard + uplink + relay + downlink;
    }}

    constraint def Freshness {{
        in meanE2E : TimeValue;
        in threshold : TimeValue;
        meanE2E <= threshold
    }}

    part def SensorToSubscriberLink {{
        attribute onboardProcessing : TimeValue = {p['proc_src_s']} [s];
        attribute relayProcessing : TimeValue = {p['proc_relay_s']} [s];
        attribute uplinkDistance : LengthValue = {p['d_up_km'] * 1000} [m];
        attribute uplinkSpeed : SpeedValue = {p['v_up']} ['m/s'];
        attribute downlinkDistance : LengthValue = {p['d_down_km'] * 1000} [m];
        attribute downlinkSpeed : SpeedValue = {p['v_down']} ['m/s'];
        attribute windowPeriod : TimeValue = {p['period_s']} [s];
        attribute windowPhase : TimeValue = {p['phase_s']} [s];
        attribute messageSpacing : TimeValue = {p['spacing_s']} [s];
        attribute messageCount : ScalarValues::Integer = {p['n_msg']};
        attribute stalenessThreshold : TimeValue = {p['threshold_s']} [s];

        attribute uplinkPropagation : TimeValue =
            PropagationDelay(uplinkDistance, uplinkSpeed);
        attribute downlinkPropagation : TimeValue =
            PropagationDelay(downlinkDistance, downlinkSpeed);
        attribute chainBase : TimeValue =
            FixedChainLatency(onboardProcessing, uplinkPropagation,
                              relayProcessing, downlinkPropagation);
    }}

    part {part} : SensorToSubscriberLink {{
        {doc}
    }}

    requirement def FreshnessDeadline {{
        subject link : SensorToSubscriberLink;
        doc /* The mean end-to-end delay of the message batch meets the staleness threshold. */
    }}
}}
"""


def requirements_md(task_id: str, p: dict, s: dict) -> str:
    relay = RELAY_OF[p["platform"]]
    subscriber = SUBSCRIBER_OF[p["platform"]]
    platform = PLATFORM_TEXT[p["platform"]]
    up_medium = MEDIUM_TEXT[p["up_medium"]]
    down_medium = MEDIUM_TEXT[p["down_medium"]]
    collects = ", ".join(str(int(m["collect_s"])) for m in s["messages"])
    window_times = ", ".join(str(int(p["phase_s"] + k * p["period_s"]))
                             for k in range(min(3, s["messages"][-1]["k"] + 1)))
    threshold = p["threshold_s"]
    return f"""# {task_id} — synthetic, not an RTX specification

SIM multi-hop link latency and message freshness for {platform} in the maritime
ISR scenario (the four-node system: unmanned surface vessel, fixed-wing UAV,
command ship, shore station). This task covers one data path:
{platform} sensors → {relay} relay → {subscriber} (path {p['platform']} → {RELAY_OF[p['platform']]}).

This is a closed-form latency bookkeeping question. It does not ask you to write
or edit SysML. The file `model.sysml` in this folder carries the same parameters
as a SysML v2 model; the numbers in this document are authoritative.

The reference time t = 0 s is the collection of the first message; every time
below is seconds after t = 0.

## Data path (sensor collection → final subscriber)

| Hop | From | To | Medium | Distance | Propagation speed |
|-----|------|----|--------|----------|-------------------|
| uplink | {platform} sensor platform | {relay} relay | {up_medium} | {p['d_up_km']} km | {p['v_up']} m/s |
| downlink | {relay} relay (at its transmit window) | {subscriber} | {down_medium} | {p['d_down_km']} km | {p['v_down']} m/s |

Processing delays (constant for every message, every hop):

- Onboard processing on the sensor platform: {p['proc_src_s']} s
- Relay processing at the {relay}: {p['proc_relay_s']} s

Propagation delay of a hop = distance / propagation speed, with the distance in
meters (so {p['d_up_km']} km = {p['d_up_km'] * 1000} m).

## Transmit windows at the relay

The {relay} relay transmits only on a fixed window schedule. A window opens
every {p['period_s']} s, the first at t = {p['phase_s']} s (so windows open at
t = {window_times}, ... s; the schedule is unlimited). A message departs the
relay on the FIRST window whose opening time is at or after (>=) the moment the
relay finishes processing it; if the relay finishes exactly at a window opening,
the message departs on that window with zero wait.

## Message batch

{p['n_msg']} messages, collected at t = {collects} s (equal spacing
{p['spacing_s']} s, first message at t = 0). Every message follows the same
chain:

onboard processing → uplink propagation → relay processing → wait for the next
transmit window → downlink propagation.

For message i (collected at t_i):

    t_ready(i)  = t_i + {p['proc_src_s']} + uplink_propagation + {p['proc_relay_s']}
    wait(i)     = (next window opening at or after t_ready(i)) − t_ready(i)
    e2e(i)      = {p['proc_src_s']} + uplink_propagation + {p['proc_relay_s']}
                  + wait(i) + downlink_propagation

measured from collection at the sensor to receipt by the {subscriber}.

## Freshness deadline

- Freshness (staleness) threshold: {threshold} s ({threshold // 60} min).
- A message is fresh iff its end-to-end delay is at most the threshold
  (e2e <= {threshold} s); otherwise it is stale.
- fresh_ratio = (number of fresh messages) / {p['n_msg']}.
- meets_staleness: true iff the MEAN end-to-end delay over the batch meets the
  deadline (mean_e2e_s <= {threshold} s).

## Units and rounding

- Times in seconds (s); 1 min = 60 s. Distances in km, speeds in m/s.
- propagation_s = distance_km × 1000 / speed_m_per_s.
- Report mean_e2e_s and max_e2e_s to 1 decimal, fresh_ratio to 4 decimals.

## Reply with exactly one JSON object

{{"mean_e2e_s": <number>, "max_e2e_s": <number>, "fresh_ratio": <number>,
  "meets_staleness": <true|false>}}

- `mean_e2e_s`: mean end-to-end delay over the {p['n_msg']} messages, seconds, 1 decimal.
- `max_e2e_s`: largest end-to-end delay of the batch, seconds, 1 decimal.
- `fresh_ratio`: fraction of messages with e2e <= {threshold} s, 4 decimals.
- `meets_staleness`: true iff mean_e2e_s <= {float(threshold):.1f} s.
"""


def answer_json(task_id: str, p: dict, s: dict) -> str:
    payload = {
        "task_id": task_id,
        "mean_e2e_s": rnd(s["mean_e2e"], 1),
        "max_e2e_s": rnd(s["max_e2e"], 1),
        "fresh_ratio": rnd(Fraction(s["fresh_count"], p["n_msg"]), 4),
        "meets_staleness": s["meets"],
    }
    return json.dumps(payload, indent=2) + "\n"


def assertions_yaml(task_id: str, p: dict, s: dict) -> str:
    checks = {
        "task_id": task_id,
        "package": "LatencyChain",
        "family": "sim_latency",
        "answer_mode": "json",
        "tolerances": {"numeric_rel": TOL_REL, "ratio_tol": RATIO_TOL,
                       "boolean_exact": True},
        "checks": {
            "mean_e2e_s": {"gold": rnd(s["mean_e2e"], 1), "rel_tol": TOL_REL},
            "max_e2e_s": {"gold": rnd(s["max_e2e"], 1), "rel_tol": TOL_REL},
            "fresh_ratio": {"gold": rnd(Fraction(s["fresh_count"], p["n_msg"]), 4),
                            "rel_tol": RATIO_TOL, "abs_tol": RATIO_TOL},
            "meets_staleness": {"gold": s["meets"], "exact": True},
        },
    }
    return yaml.safe_dump(checks, sort_keys=False)


def solution_md(task_id: str, p: dict, s: dict) -> str:
    relay = RELAY_OF[p["platform"]]
    subscriber = SUBSCRIBER_OF[p["platform"]]
    threshold = Fraction(p["threshold_s"])
    lines = [
        f"# {task_id} — closed-form solution (human-checkable arithmetic)",
        "",
        "No simulation is needed: every message sees the same fixed chain and the",
        "only per-message quantity is the wait for the next transmit window.",
        f"Path: {PLATFORM_TEXT[p['platform']]} → {relay} relay → {subscriber}.",
        "",
        "Fixed part of the chain, identical for every message:",
        "",
        f"- onboard processing {p['proc_src_s']} s",
        f"- uplink propagation {p['d_up_km'] * 1000} m / {p['v_up']} m/s = {fmt(p['prop_up_s'])} s",
        f"- relay processing {p['proc_relay_s']} s",
        f"- downlink propagation {p['d_down_km'] * 1000} m / {p['v_down']} m/s = {fmt(p['prop_down_s'])} s",
        f"- base = {p['proc_src_s']} + {fmt(p['prop_up_s'])} + {p['proc_relay_s']} + "
        f"{fmt(p['prop_down_s'])} = {fmt(s['base_s'])} s",
        "",
        f"Window schedule: openings every {p['period_s']} s starting at t = {p['phase_s']} s;",
        "a message departs on the first opening at or after its ready time"
        + (" (message 1 is ready exactly at an opening: wait 0, the boundary case)."
           if p["boundary"] else "."),
        "",
        f"Freshness threshold = {p['threshold_s']} s; a message is fresh iff e2e <= {p['threshold_s']} s.",
        "",
        "| # | collect (s) | ready at relay (s) | window used (s) | wait (s) | e2e (s) | fresh |",
        "|---|-------------|--------------------|-----------------|----------|---------|-------|",
    ]
    for m in s["messages"]:
        lines.append(
            f"| {m['i']} | {int(m['collect_s'])} | {fmt(m['ready_s'])} | {int(m['window_s'])} "
            f"| {int(m['wait_s'])} | {fmt(m['e2e_s'])} | {'yes' if m['e2e_s'] <= threshold else 'no'} |")
    n = p["n_msg"]
    fresh_count = s["fresh_count"]
    lines += [
        "",
        f"- mean_e2e = ({' + '.join(fmt(m['e2e_s']) for m in s['messages'])}) / {n}"
        f" = {fmt(s['mean_e2e'])} s → reported to 1 decimal as **{f1(s['mean_e2e'])} s**.",
        f"- max_e2e = {fmt(s['max_e2e'])} s → **{f1(s['max_e2e'])} s**.",
        f"- fresh_ratio = {fresh_count}/{n} = **{f4(Fraction(fresh_count, n))}**.",
        f"- meets_staleness: mean {f1(s['mean_e2e'])} s {'≤' if s['meets'] else '>'} "
        f"{float(p['threshold_s']):.1f} s → **{str(s['meets']).lower()}**.",
        "",
        "Tolerance check (±2% relative band, gold kept ≥ 3x the band from every",
        f"decision edge): the closest message e2e sits "
        f"{fmt(min(abs(m['e2e_s'] - threshold) / m['e2e_s'] for m in s['messages']) * 100)}% "
        f"from the threshold and the mean "
        f"{fmt(abs(s['mean_e2e'] - threshold) / s['mean_e2e'] * 100)}% (≥ 6% required),",
        "so every fresh/stale classification and the boolean are unambiguous.",
        "",
    ]
    return "\n".join(lines)


def case_yaml(task_id: str, p: dict) -> str:
    return yaml.safe_dump({
        "id": task_id, "type": "SIM", "scenario_family": "t_sim_bank", "split": "staging",
        "package": "LatencyChain", "synthetic": True, "status": "generated",
        "generator": "bench/build_sim_latency.py", "seed": SEED,
        "answer_mode": "json", "platform": p["platform"], "path": PATH_OF[p["platform"]],
    }, sort_keys=False)


# --- independent re-check: recompute gold from the written requirements.md ------------
ROW_RE = re.compile(
    r"^\| (uplink|downlink) \| .+ \| (\d+) km \| (\d+) m/s \|$")


def verify_from_disk(folder: Path) -> dict:
    text = (folder / "input" / "requirements.md").read_text(encoding="utf-8")
    first = text.splitlines()[0]
    if not re.fullmatch(r"# LAT-\d{4} — synthetic, not an RTX specification", first):
        raise SystemExit(f"{folder.name}: requirements.md first line is not the RTX marker: {first!r}")
    hops = {}
    for line in text.splitlines():
        match = ROW_RE.match(line)
        if match:
            hops[match.group(1)] = (int(match.group(2)), int(match.group(3)))
    if set(hops) != {"uplink", "downlink"}:
        raise SystemExit(f"{folder.name}: hop table incomplete: {sorted(hops)}")
    proc_src = int(re.search(r"- Onboard processing on the sensor platform: (\d+) s", text).group(1))
    platform = re.search(r"\(path (usv|uav) → (shore station|command ship)\)", text).group(1)
    relay_name = "shore station" if platform == "usv" else "command ship"
    proc_relay = int(re.search(rf"- Relay processing at the {relay_name}: (\d+) s", text).group(1))
    period, phase = (int(v) for v in
                     re.search(r"every (\d+) s, the first at t = (\d+) s", text).groups())
    spacing = int(re.search(r"collected at t = ([\d, ]+) s \(equal spacing\n(\d+) s", text).group(2))
    n_msg = int(re.search(r"^(\d+) messages, collected at", text, re.M).group(1))
    threshold = int(re.search(r"- Freshness \(staleness\) threshold: (\d+) s", text).group(1))
    collects = [int(v) for v in
                re.search(r"collected at t = ([\d, ]+) s \(equal spacing", text).group(1).split(",")]
    if len(collects) != n_msg or collects != [i * spacing for i in range(n_msg)]:
        raise SystemExit(f"{folder.name}: message list inconsistent")

    prop_up = Fraction(hops["uplink"][0] * 1000, hops["uplink"][1])
    prop_down = Fraction(hops["downlink"][0] * 1000, hops["downlink"][1])
    ready0 = Fraction(proc_src) + prop_up + Fraction(proc_relay)
    base = ready0 + prop_down
    e2es = []
    for collect in collects:
        ready = ready0 + Fraction(collect)
        k = max(0, -((Fraction(phase) - ready) // Fraction(period)))
        e2es.append(base + (Fraction(phase) + k * period - ready))
    mean = sum(e2es, Fraction(0)) / Fraction(n_msg)
    rebuilt = {
        "mean_e2e_s": rnd(mean, 1),
        "max_e2e_s": rnd(max(e2es), 1),
        "fresh_ratio": rnd(Fraction(sum(e <= threshold for e in e2es), n_msg), 4),
        "meets_staleness": mean <= Fraction(threshold),
    }
    answer = json.loads((folder / "gold" / "answer.json").read_text(encoding="utf-8"))
    for field, value in rebuilt.items():
        if answer[field] != value:
            raise SystemExit(f"{folder.name}: field {field} mismatch between requirements.md "
                             f"and answer.json\nanswer: {answer[field]}\nrebuilt: {value}")
    # cross-check the model file carries the same parameters
    model = (folder / "input" / "model.sysml").read_text(encoding="utf-8")
    for attr, value in (("onboardProcessing", proc_src), ("relayProcessing", proc_relay),
                        ("uplinkDistance", hops["uplink"][0] * 1000),
                        ("uplinkSpeed", hops["uplink"][1]),
                        ("downlinkDistance", hops["downlink"][0] * 1000),
                        ("downlinkSpeed", hops["downlink"][1]),
                        ("windowPeriod", period), ("windowPhase", phase),
                        ("messageSpacing", spacing), ("messageCount", n_msg),
                        ("stalenessThreshold", threshold)):
        if not re.search(rf"attribute {attr} : \w+(::\w+)* = {value}[ ;\[]", model):
            raise SystemExit(f"{folder.name}: model.sysml attribute {attr} = {value} not found")
    return {"mean_e2e_s": rebuilt["mean_e2e_s"], "meets_staleness": rebuilt["meets_staleness"]}


# --- main --------------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", type=int, default=0,
                        help="also run the official Pilot validator on N spread tasks")
    args = parser.parse_args()

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
    rejected: list[dict] = []
    attempts = 0
    for index, want_true in enumerate(slots, start=1):
        task_id = f"LAT-{index:04d}"
        platform = platform_for(index)
        boundary = boundary_for(index)
        while True:
            attempts += 1
            if attempts > MAX_SAMPLES:
                raise SystemExit(f"sampling budget exhausted at {task_id}")
            p = sample(rng, platform, boundary)
            options = feasible_thresholds(p)
            if not options:
                rejected.append({"reason": "no_feasible_threshold", "params": brief(p)})
                continue
            matching = [t for t, label in options if label == want_true]
            if not matching:
                rejected.append({"reason": "label_slot", "params": brief(p)})
                continue
            threshold = rng.choice(matching)
            s = solve(p, Fraction(threshold))
            if boundary and s["messages"][0]["wait_s"] != 0:
                raise SystemExit(f"{task_id}: boundary construction lost its zero wait")
            p["threshold_s"] = threshold
            vector = param_vector(p, threshold)
            if not acceptable(p, vector, accepted_vectors):
                rejected.append({"reason": "dedup", "params": brief(p)})
                continue
            accepted_vectors.append(vector)
            break

        folder = OUT / task_id
        (folder / "input").mkdir(parents=True)
        (folder / "gold").mkdir()
        (folder / "case.yaml").write_text(case_yaml(task_id, p), encoding="utf-8")
        (folder / "input" / "model.sysml").write_text(model_sysml(p), encoding="utf-8")
        (folder / "input" / "requirements.md").write_text(requirements_md(task_id, p, s), encoding="utf-8")
        (folder / "gold" / "answer.json").write_text(answer_json(task_id, p, s), encoding="utf-8")
        (folder / "gold" / "assertions.yaml").write_text(assertions_yaml(task_id, p, s), encoding="utf-8")
        (folder / "gold" / "solution.md").write_text(solution_md(task_id, p, s), encoding="utf-8")

        waits = {int(m["wait_s"]) for m in s["messages"]}
        level = "L1" if p["n_msg"] <= 4 else ("L2" if p["n_msg"] <= 6 else "L3")
        tasks.append({
            "id": task_id,
            "platform": platform,
            "path": PATH_OF[platform],
            "variant": ("window_boundary_" if boundary else "") + p["up_medium"] + "_up",
            "params": {
                "proc_src_s": p["proc_src_s"],
                "proc_relay_s": p["proc_relay_s"],
                "uplink": {"medium": p["up_medium"], "distance_km": p["d_up_km"],
                           "speed_m_per_s": p["v_up"], "prop_s": float(p["prop_up_s"])},
                "downlink": {"medium": p["down_medium"], "distance_km": p["d_down_km"],
                             "speed_m_per_s": p["v_down"], "prop_s": float(p["prop_down_s"])},
                "window": {"period_s": p["period_s"], "phase_s": p["phase_s"]},
                "messages": {"count": p["n_msg"], "spacing_s": p["spacing_s"]},
                "staleness_threshold_s": p["threshold_s"],
            },
            "gold": {"mean_e2e_s": rnd(s["mean_e2e"], 1),
                     "max_e2e_s": rnd(s["max_e2e"], 1),
                     "fresh_ratio": rnd(Fraction(s["fresh_count"], p["n_msg"]), 4),
                     "meets_staleness": s["meets"]},
            "difficulty": {"messages": p["n_msg"], "distinct_waits": len(waits),
                           "level": level, "window_boundary": boundary},
        })

    # independent re-check of every task from disk
    for entry in tasks:
        disk = verify_from_disk(OUT / entry["id"])
        assert disk["mean_e2e_s"] == entry["gold"]["mean_e2e_s"], entry["id"]
        assert disk["meets_staleness"] == entry["gold"]["meets_staleness"], entry["id"]

    index_lines = [json.dumps({"id": t["id"], "type": "SIM", "platform": t["platform"],
                               "path": f"bench/tasks_staging/t_sim_bank/sim_latency/{t['id']}"})
                   for t in tasks]
    (OUT / "index.jsonl").write_text("\n".join(index_lines) + "\n", encoding="utf-8")

    n_true = sum(t["gold"]["meets_staleness"] for t in tasks)
    def hist(key):
        out: dict = {}
        for t in tasks:
            k = t[key] if not isinstance(t[key], dict) else t["difficulty"][key]
            out[k] = out.get(k, 0) + 1
        return out
    min_dist = min(
        math.sqrt(sum((a - b) ** 2 for a, b in zip(v, w)))
        for i, v in enumerate(accepted_vectors) for w in accepted_vectors[i + 1:])
    reasons: dict = {}
    for r in rejected:
        reasons[r["reason"]] = reasons.get(r["reason"], 0) + 1
    manifest = {
        "family": "sim_latency",
        "generator": "bench/build_sim_latency.py",
        "seed": SEED,
        "count": len(tasks),
        "narrative": {
            "scenario": "maritime ISR four-node world (unmanned surface vessel, fixed-wing UAV, command ship, shore station); same world as bench/tasks/t4_maritime_isr",
            "question": "end-to-end delay and message freshness over a multi-hop data path whose relay transmits on fixed windows",
            "paths": {"usv-to-shore": "USV sensors -> shore station relay (window) -> maritime operations center",
                      "uav-to-command-ship": "UAV sensors -> command ship relay (window) -> shore headquarters"},
            "platform_split_rule": "task number mod 5 < 3 -> usv, else uav (exactly 6:4)",
            "window_rule": "a message departs on the first window opening at or after (>=) its relay-ready time; exact coincidence -> zero wait",
            "meets_staleness": "mean_e2e_s <= staleness_threshold_s",
        },
        "closed_form": {
            "t_ready(i)": "(i-1)*spacing + proc_src + prop_up + proc_relay  [s]",
            "wait(i)": "phase + k*period - t_ready(i), k = min{k>=0 : phase + k*period >= t_ready(i)}",
            "e2e(i)": "proc_src + prop_up + proc_relay + wait(i) + prop_down",
            "prop": "distance_km*1000 / speed_m_per_s",
            "fresh(i)": "e2e(i) <= staleness_threshold_s",
            "mean_e2e_s": "mean of e2e(i), 1 decimal",
            "max_e2e_s": "max of e2e(i), 1 decimal",
            "fresh_ratio": "fresh_count / n_messages, 4 decimals",
            "meets_staleness": "mean_e2e_s <= staleness_threshold_s (boolean)",
        },
        "parameter_space": {
            "proc_per_hop_s": [PROC_MIN, PROC_MAX],
            "window_period_min": [PERIOD_MIN_MIN, PERIOD_MAX_MIN],
            "window_phase_s": "0..period-1 (derived for boundary tasks so message 1 waits 0)",
            "message_count": [N_MSG_MIN, N_MSG_MAX],
            "message_spacing_min": [SPACING_MIN_MIN, SPACING_MAX_MIN],
            "staleness_threshold_min": [THRESH_MIN_S // 60, THRESH_MAX_S // 60],
            "distances_km": {"acoustic_up": list(D_ACOUSTIC), "radio_up": list(D_RADIO_UP),
                             "downlink": list(D_DOWN)},
            "speeds_m_per_s": {"underwater acoustic": SPEED_ACOUSTIC, "radio": SPEED_RADIO,
                               "fiber trunk": SPEED_FIBER},
            "media": {"usv": ["underwater acoustic or surface radio uplink", "fiber trunk downlink"],
                      "uav": ["air-to-surface radio uplink", "high-frequency radio downlink"]},
            "note": "distances are multiples of 3 km so every propagation delay is a terminating decimal",
        },
        "constraints": {
            "tolerances": {"numeric_rel": TOL_REL, "ratio_tol": RATIO_TOL, "boolean": "exact"},
            "margins": ["every message e2e >= 3x the 2% band from the staleness threshold",
                        "mean_e2e >= 3x the 2% band from the staleness threshold",
                        "1 <= fresh_count <= n-1 (fresh_ratio strictly inside (0,1))"],
            "dedup_min_normalized_distance": DEDUP_MIN_DIST,
            "meets_staleness_true": n_true,
            "meets_staleness_false": len(tasks) - n_true,
            "window_boundary_tasks": sum(t["difficulty"]["window_boundary"] for t in tasks),
            "no_llm": "all gold values computed by the closed form in this generator",
        },
        "stats": {
            "by_platform": hist("platform"),
            "by_path": hist("path"),
            "by_variant": hist("variant"),
            "by_level": {k: sum(1 for t in tasks if t["difficulty"]["level"] == k)
                         for k in ("L1", "L2", "L3")},
            "min_pairwise_distance": round(min_dist, 4),
            "sampling_attempts": attempts,
            "accepted": len(tasks),
            "rejected": len(rejected),
            "rejected_by_reason": reasons,
        },
        "rejected_params": rejected,
        "tasks": tasks,
    }

    if args.pilot:
        sys.path.insert(0, str(ROOT))
        from mvp.toolchain.validate import validate_package  # noqa: E402
        picks = [tasks[0], tasks[len(tasks) // 3], tasks[-1]][:args.pilot]
        pilot_report = []
        for task in picks:
            out = Path("/tmp") / f"latpilot-{task['id']}"
            if out.exists():
                shutil.rmtree(out)
            result = validate_package([str(OUT / task["id"] / "input" / "model.sysml")],
                                      "LatencyChain", str(out))
            pilot_report.append({"id": task["id"], "status": result["status"],
                                 "warnings": result.get("warning_count", 0)})
            print(f"pilot {task['id']}: {result['status']}")
        manifest["pilot_check"] = pilot_report
        if any(r["status"] != "PASS" for r in pilot_report):
            raise SystemExit("pilot check failed")

    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(f"wrote {len(tasks)} tasks to {OUT}")
    print(f"meets_staleness true/false: {n_true}/{len(tasks) - n_true}")
    print(f"platform usv/uav: {manifest['stats']['by_platform'].get('usv', 0)}/"
          f"{manifest['stats']['by_platform'].get('uav', 0)}")
    print(f"path: {manifest['stats']['by_path']}")
    print(f"levels: {manifest['stats']['by_level']}")
    print(f"boundary tasks: {manifest['constraints']['window_boundary_tasks']}")
    print(f"min pairwise param distance: {min_dist:.4f} (threshold {DEDUP_MIN_DIST})")
    print(f"sampling attempts: {attempts} (accepted {len(tasks)}, rejected {len(rejected)}: {reasons})")
    return 0


def brief(p: dict) -> dict:
    return {"platform": p["platform"], "boundary": p["boundary"],
            "n_msg": p["n_msg"], "period_s": p["period_s"], "phase_s": p["phase_s"],
            "spacing_s": p["spacing_s"], "proc_src_s": p["proc_src_s"],
            "proc_relay_s": p["proc_relay_s"], "d_up_km": p["d_up_km"],
            "d_down_km": p["d_down_km"], "up_medium": p["up_medium"]}


if __name__ == "__main__":
    sys.exit(main())
