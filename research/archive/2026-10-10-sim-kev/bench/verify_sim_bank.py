"""Machine audit of the staged SIM task bank (bench/tasks_staging/t_sim_bank).

Five audits over the generated tasks; no model judges (decision 025): every numeric
verdict below is recomputed mechanically from the task parameters.

  A structure    : required files per task, JSON/YAML parse, answer/assertions key
                   correspondence (and gold-value agreement where the key carries one),
                   manifest count vs on-disk reality, platform fields, cross-family
                   duplicate ids, backlog rejected-params bookkeeping.
  B boundary     : distance of every numeric gold to its decision edges (reserve
                   threshold / buffer capacity / temperature limit / band bounds),
                   requiring >= 3x tolerance; boolean side distribution; near-duplicate
                   parameter pairs in the joint per-family parameter space.
  C pilot sample : every Nth task's model.sysml through the official SysML v2 Pilot
                   (mvp/toolchain/validate.py), per-task timeout, incremental writes.
  D modelica     : stratified random sample (>= 5% per family and variant), task
                   parameters substituted into /tmp/omtest/RTRC.mo (MaritimeBattery /
                   BufferFill / ThermalNode), simulated with the pinned OpenModelica
                   in tools/om (dassl, tol 1e-8), and compared with the gold closed
                   form: both |omc - gold| and |verifier-closed-form - gold| must be
                   under half the task tolerance, else RED.
  E scenario     : the "synthetic, not an RTX specification" declaration, the maritime
                   four-node vocabulary, and the platform/path distribution.

The bank is read-only: every artifact goes to <bank>/verification/. Safe to rerun
while generation is in progress; each audit writes its own JSON. --self-test builds
10 synthetic tasks in the real schema (independent closed-form golds, planted
defects) under /tmp, audits and deletes them; it never touches the staging bank.

Usage:
  python3 bench/verify_sim_bank.py                     # full audit A-E
  python3 bench/verify_sim_bank.py --audits A,B,E      # cheap subset
  python3 bench/verify_sim_bank.py --self-test         # prove the auditor itself
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_BANK = ROOT / "bench" / "tasks_staging" / "t_sim_bank"
OM_HOME = ROOT / "tools" / "om"
OMC = OM_HOME / "bin" / "omc"
RTRC_MO = Path("/tmp/omtest/RTRC.mo")

REQUIRED_FILES = ("input/model.sysml", "input/requirements.md", "gold/answer.json",
                  "gold/assertions.yaml", "gold/solution.md", "case.yaml")
RTX_DECLARATION = "synthetic, not an RTX specification"
MARITIME_VOCAB = ("usv", "unmanned surface vessel", "uav", "command ship", "shore station")
NEAR_DUP_EPS = 0.02      # normalised parameter-space distance for "near duplicate"
MARGIN_FACTOR = 3.0      # gold must sit >= 3 x tolerance from every decision edge
HALF = 0.5               # crosscheck verdict threshold: tolerance / 2

FAMILY_DIRS = {"sim_battery": "battery", "sim_backlog": "buffer", "sim_thermal": "thermal",
               "sim_harvest": "harvest", "sim_latency": "latency", "sim_storage": "storage",
               "sim_uplink": "uplink"}

# ---------------------------------------------------------------- tolerant readers


def _first(mapping, *keys):
    for key in keys:
        if isinstance(mapping, dict) and mapping.get(key) is not None:
            return mapping[key]
    return None


def _float(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in {"true", "false", "yes", "no"}:
        return value.strip().lower() in {"true", "yes"}
    return None


def graded_checks(assertions) -> dict:
    """Normalise assertions.yaml into {answer_key: {gold, rel, abs, exact}}.

    Handles both bank layouts: checks: {key: {gold, rel_tol|abs_tol_*|exact}}
    and tolerance: {key: {type, rel|abs}}.
    """
    if not isinstance(assertions, dict):
        return {}
    for band in ("checks", "tolerance", "assertions"):
        entries = assertions.get(band)
        if not isinstance(entries, dict):
            continue
        out = {}
        for key, value in entries.items():
            if not isinstance(value, dict):
                continue
            gold = _float(value.get("gold"))
            rel = _float(_first(value, "rel_tol", "rel"))
            abst = _float(_first(value, "abs_tol_min", "abs_tol_gb", "abs_tol", "abs"))
            exact = bool(value.get("exact")) or str(value.get("type", "")).lower() == "bool"
            if gold is not None or rel is not None or abst is not None or exact:
                out[str(key)] = {"gold": gold, "rel": rel, "abs": abst, "exact": exact}
        if out:
            return out
    return {}


def answer_payload(answer: dict) -> dict:
    """Top-level graded entries of answer.json (metadata keys dropped)."""
    skip = {"task_id", "id", "family", "variant", "package"}
    out = {}
    for key, value in (answer or {}).items():
        if key in skip:
            continue
        out[key] = value
    return out


def tol_of(check: dict, gold: float) -> float:
    candidates = []
    if check.get("rel") is not None:
        candidates.append(abs(check["rel"]) * abs(gold))
    if check.get("abs") is not None:
        candidates.append(abs(check["abs"]))
    return max(candidates) if candidates else abs(gold) * 0.02


class Task:
    def __init__(self, path: Path, family_dir: str):
        self.path = path
        self.id = path.name
        self.family_dir = family_dir          # sim_battery / sim_backlog / sim_thermal / ""
        self.family = FAMILY_DIRS.get(family_dir, "")  # battery / buffer / thermal / ""
        self.answer: dict | None = None
        self.assertions: dict | None = None
        self.case: dict | None = None
        self.error: str | None = None
        self.text: str | None = None
        self._parsed = None

    def load(self):
        try:
            answer_path = self.path / "gold" / "answer.json"
            if answer_path.is_file():
                self.answer = json.loads(answer_path.read_text(encoding="utf-8"))
            assertions_path = self.path / "gold" / "assertions.yaml"
            if assertions_path.is_file():
                self.assertions = yaml.safe_load(assertions_path.read_text(encoding="utf-8"))
            case_path = self.path / "case.yaml"
            if case_path.is_file():
                self.case = yaml.safe_load(case_path.read_text(encoding="utf-8"))
            requirements = self.path / "input" / "requirements.md"
            self.text = requirements.read_text(encoding="utf-8", errors="ignore") if requirements.is_file() else ""
        except (json.JSONDecodeError, yaml.YAMLError, OSError) as exc:
            self.error = f"{type(exc).__name__}: {exc}"
        return self

    def checks(self):
        return graded_checks(self.assertions)

    def params(self):
        """Family-specific parameters parsed mechanically from requirements.md."""
        if self._parsed is None:
            parser = {"battery": parse_battery, "buffer": parse_backlog, "thermal": parse_thermal,
                      "harvest": parse_harvest, "latency": parse_latency,
                      "storage": parse_storage, "uplink": parse_uplink}.get(self.family)
            self._parsed = parser(self.text) if parser and self.text is not None else None
        return self._parsed


# ---------------------------------------------------------------- family parsers
TABLE_ROW = re.compile(r"^\|\s*\d+\s*\|[^|]+\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|", re.M)
TABLE_ROW_NET = re.compile(r"^\|\s*\d+\s*\|[^|]+\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|", re.M)


def parse_battery(text: str) -> dict | None:
    capacity = re.search(r"Capacity:\s*([\d.]+)\s*Wh", text)
    soc = re.search(r"SoC at t = 0:\s*([\d.]+)\s*%", text)
    reserve = re.search(r"[Rr]eserve threshold:\s*([\d.]+)\s*%", text)
    rows = [{"power": float(m[0]), "start": float(m[1]), "end": float(m[2])}
            for m in TABLE_ROW.findall(text)]
    if not (capacity and soc and rows):
        return None
    return {"capacity_wh": float(capacity.group(1)), "soc_start_pct": float(soc.group(1)),
            "reserve_pct": float(reserve.group(1)) if reserve else None, "rows": rows}


def parse_backlog(text: str) -> dict | None:
    sensor = re.search(r"[Ss]ensor data rate[^:\n]*:\s*([\d.]+)\s*Mbit/s", text)
    link = re.search(r"[Dd]ownlink rate[^:\n]*:\s*([\d.]+)\s*Mbit/s", text)
    mission = re.search(r"[Mm]ission length:\s*([\d.]+)\s*min", text)
    capacity = re.search(r"[Bb]uffer capacity:\s*([\d.]+)\s*Mbit\s*=\s*([\d.]+)\s*GB", text)
    windows = [(float(a), float(b)) for a, b in
               re.findall(r"Outage window \d+:\s*start\s*([\d.]+)\s*min,\s*duration\s*([\d.]+)\s*min", text)]
    if not (sensor and link and mission and capacity and windows):
        return None
    return {"sensor": float(sensor.group(1)), "link": float(link.group(1)),
            "mission_min": float(mission.group(1)), "capacity_mbit": float(capacity.group(1)),
            "capacity_gb": float(capacity.group(2)), "windows": sorted(windows)}


def parse_thermal(text: str) -> dict | None:
    p = re.search(r"dissipation P = ([\d.]+) W", text)
    rth = re.search(r"thermal resistance Rth = ([\d.]+) K/W", text)
    cth = re.search(r"thermal capacity Cth = ([\d.]+) J/K", text)
    tamb = re.search(r"ambient temperature Tamb = ([\d.]+) degC", text)
    tmax = re.search(r"temperature limit Tmax = ([\d.]+) degC", text)
    peak = re.search(r"T\(([\d.]+)\s*min\)", text)
    if not (p and rth and cth and tamb and tmax):
        return None
    return {"P": float(p.group(1)), "Rth": float(rth.group(1)), "Cth": float(cth.group(1)),
            "Tamb": float(tamb.group(1)), "Tmax": float(tmax.group(1)),
            "N_min": float(peak.group(1)) if peak else None}


def parse_harvest(text: str) -> dict | None:
    capacity = re.search(r"Capacity:\s*([\d.]+)\s*Wh", text)
    soc = re.search(r"SoC at t = 0:\s*([\d.]+)\s*%", text)
    protection = re.search(r"[Pp]rotection line:\s*([\d.]+)\s*%", text)
    rows = [{"load": float(m[0]), "solar": float(m[1]), "start": float(m[2]), "end": float(m[3])}
            for m in TABLE_ROW_NET.findall(text)]
    if not (capacity and soc and protection and rows):
        return None
    return {"capacity_wh": float(capacity.group(1)), "soc_start_pct": float(soc.group(1)),
            "protection_pct": float(protection.group(1)), "rows": rows}


def parse_latency(text: str) -> dict | None:
    hops = re.findall(r"^\|\s*(uplink|downlink)\s*\|[^|]+\|[^|]+\|[^|]+\|\s*([\d.]+)\s*km\s*\|\s*([\d.]+)\s*m/s\s*\|", text, re.M)
    onboard = re.search(r"Onboard processing[^:\n]*:\s*([\d.]+)\s*s", text)
    relay = re.search(r"Relay processing[^:\n]*:\s*([\d.]+)\s*s", text)
    window = re.search(r"every\s+([\d.]+)\s+s,\s*the first at t\s*=\s*([\d.]+)\s+s", text)
    batch = re.search(r"(\d+) messages, collected at t\s*=\s*([\d.,\s]+?)\s*s", text)
    threshold = re.search(r"threshold:\s*([\d.]+)\s*s", text)
    if not (len(hops) == 2 and onboard and relay and window and batch and threshold):
        return None
    times = [float(x) for x in re.split(r"[,\s]+", batch.group(2).strip()) if x]
    uplink_row = re.search(r"^\|\s*uplink\b.*$", text, re.M)
    return {"d_up": float(hops[0][1]), "v_up": float(hops[0][2]),
            "d_down": float(hops[1][1]), "v_down": float(hops[1][2]),
            "onboard": float(onboard.group(1)), "relay": float(relay.group(1)),
            "period": float(window.group(1)), "first": float(window.group(2)),
            "t_collect": times, "threshold": float(threshold.group(1)),
            "medium": "acoustic" if (uplink_row and "acoustic" in uplink_row.group(0).lower()) else "radio"}


def parse_storage(text: str) -> dict | None:
    rate = re.search(r"stream rate R:\s*([\d.]+)\s*Mbit/s", text)
    capacity = re.search(r"capacity S:\s*([\d.]+)\s*GB", text)
    target = re.search(r"retention T:\s*([\d.]+)\s*h", text)
    frame = re.search(r"1 frame in (\d+) of the raw stream", text)
    fixed_tier = re.search(r"fixes tier T\d+ \(k = (\d+)\)", text)
    if not (rate and capacity and target):
        return None
    base = {"R": float(rate.group(1)), "S": float(capacity.group(1)), "T": float(target.group(1))}
    if frame:
        base.update(variant="retention", mode="preview", N=int(frame.group(1)))
    elif fixed_tier:
        base.update(variant="retention", mode="compress", N=int(fixed_tier.group(1)))
    elif "smallest tier factor" in text or "Compression tiers" in text:
        base.update(variant="choice", mode="ladder", tiers=(1, 2, 4, 8, 16))
    else:
        return None
    return base


def parse_uplink(text: str) -> dict | None:
    capacity = re.search(r"Total uplink capacity C:\s*([\d.]+)\s*Mbit/s", text)
    window = re.search(r"Mission window: 0 to ([\d.]+) min", text)
    initial = re.search(r"USV\s+([\d.]+)\s*Mbit,\s*UAV\s+([\d.]+)\s*Mbit", text)
    starve = re.search(r"less than ([\d.]+)\s*%\s*of its demand", text)
    phases = [{"start": float(m[0]), "end": float(m[1]), "rate_usv": float(m[2]), "rate_uav": float(m[3])}
              for m in re.findall(r"^\|\s*\d+\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|", text, re.M)]
    if not (capacity and window and initial and starve and phases):
        return None
    out = {"C": float(capacity.group(1)), "mission_min": float(window.group(1)),
           "init_usv": float(initial.group(1)), "init_uav": float(initial.group(2)),
           "starve_pct": float(starve.group(1)), "phases": phases}
    if "fixed quotas" in text:
        out["scheme"] = "fixed"
        out["quota_usv"] = float(re.search(r"USV uplink quota:\s*([\d.]+)\s*Mbit/s", text).group(1))
        out["quota_uav"] = float(re.search(r"UAV uplink quota:\s*([\d.]+)\s*Mbit/s", text).group(1))
    else:
        preempt = re.search(r"Preempting platform:\s*(USV|UAV)", text)
        if not preempt:
            return None
        out["scheme"] = f"preempt_{'uav' if preempt.group(1) == 'UAV' else 'usv'}"
        out["primary"] = "uav" if preempt.group(1) == "UAV" else "usv"
    return out


# ---------------------------------------------------------------- closed forms
def cf_battery_soc_pct(p: dict, t_min: float) -> float:
    """SoC in percent at t minutes for the ideal energy tank defined by the rows."""
    spent_wh, prev = 0.0, 0.0
    for row in p["rows"]:
        span = max(0.0, min(t_min, row["end"]) - prev)
        spent_wh += row["power"] * (span / 60.0)
        prev = max(prev, min(t_min, row["end"]))
        if t_min <= row["end"]:
            break
    remaining_pct = 100.0 * (p["capacity_wh"] * p["soc_start_pct"] / 100.0 - spent_wh) / p["capacity_wh"]
    return remaining_pct


def cf_backlog(p: dict) -> dict:
    """Backlog trajectory summary per the task rules, by piecewise walk over events.

    Rates are Mbit/s and times minutes (task rule: R Mbit/s held for m minutes
    moves R x 60 x m Mbit), so net rates below carry the 60 factor per minute.
    """
    sensor, link, mission, cap = p["sensor"], p["link"], p["mission_min"], p["capacity_mbit"]
    events = sorted({0.0, mission, *[s for s, _ in p["windows"]], *[s + d for s, d in p["windows"]]})
    events = [e for e in events if 0.0 <= e <= mission]

    def rate(t: float) -> float:
        for start, duration in p["windows"]:
            if start <= t < start + duration:
                return 60.0 * sensor          # outage: sensors write, link down
        return 60.0 * (sensor - link)         # link up (clamped at zero below when draining)

    value, overflow_at, kinks = 0.0, None, {0.0: 0.0}
    for a, b in zip(events, events[1:]):
        r = rate(a)
        new = value + r * (b - a)
        if r < 0:
            new = max(0.0, new)
        if overflow_at is None and r > 0 and value < cap <= new:
            overflow_at = a + (cap - value) / r
        value = new
        kinks[b] = value
    max_mbit = max(kinks.values())
    return {"end_mbit": value, "max_mbit": max_mbit, "end_gb": value / 8000.0,
            "max_gb": max_mbit / 8000.0, "overflow_at_min": overflow_at,
            "overflows": max_mbit >= cap or overflow_at is not None,
            "headroom_gb": p["capacity_gb"] - value / 8000.0}


def cf_thermal(p: dict) -> dict:
    tau = p["Rth"] * p["Cth"]
    rise = p["P"] * p["Rth"]
    out = {"steady_c": p["Tamb"] + rise, "t95_min": 3.0 * tau / 60.0, "tau_s": tau, "rise_c": rise}
    if p.get("N_min") is not None:
        out["peak_c"] = p["Tamb"] + rise * (1.0 - math.exp(-p["N_min"] * 60.0 / tau))
    return out


def cf_harvest_soc_pct(p: dict, t_min: float) -> float:
    """SoC percent at t minutes: net (solar − load) energy bookkeeping per row."""
    net_wh, prev = 0.0, 0.0
    for row in p["rows"]:
        span = max(0.0, min(t_min, row["end"]) - prev)
        net_wh += (row["solar"] - row["load"]) * (span / 60.0)
        prev = max(prev, min(t_min, row["end"]))
        if t_min <= row["end"]:
            break
    return 100.0 * (p["capacity_wh"] * p["soc_start_pct"] / 100.0 + net_wh) / p["capacity_wh"]


def cf_harvest(p: dict) -> dict:
    kinks = [0.0] + [row["end"] for row in p["rows"]]
    values = {t: cf_harvest_soc_pct(p, t) for t in kinks}
    t_min = min(values, key=lambda t: (values[t], t))
    end = p["rows"][-1]["end"]
    minimum = values[t_min]
    return {"soc_end_pct": values[end], "min_soc_pct": minimum, "min_soc_at_min": t_min,
            "breached": minimum < p["protection_pct"],
            "key_points": [{"t_min": t, "soc_pct": values[t]} for t in kinks]}


def cf_latency(p: dict) -> dict:
    prop_up = p["d_up"] * 1000.0 / p["v_up"]
    prop_down = p["d_down"] * 1000.0 / p["v_down"]
    fixed = p["onboard"] + prop_up + p["relay"]
    e2e = []
    for t_i in p["t_collect"]:
        ready = t_i + fixed
        k = math.ceil((ready - p["first"]) / p["period"] - 1e-9)
        k = max(k, 0.0)
        wait = (p["first"] + k * p["period"]) - ready
        e2e.append(fixed + wait + prop_down)
    mean = sum(e2e) / len(e2e)
    return {"mean_e2e_s": mean, "max_e2e_s": max(e2e),
            "fresh_ratio": sum(1 for x in e2e if x <= p["threshold"]) / len(e2e),
            "meets_staleness": mean <= p["threshold"]}


def cf_storage(p: dict) -> dict:
    if p["variant"] == "retention":
        rate = p["R"] / p["N"]
        retention = p["S"] * 8000.0 / (3600.0 * rate)
        return {"retention_h": retention, "meets_target": retention >= p["T"],
                "headroom_gb": p["S"] - 0.45 * rate * p["T"]}
    retention = {k: k * p["S"] * 8000.0 / (3600.0 * p["R"]) for k in p["tiers"]}
    chosen = next((k for k in p["tiers"] if retention[k] >= p["T"]), None)
    return {"chosen_k": chosen, "retention_h": retention[chosen] if chosen else retention[p["tiers"][-1]],
            "feasible": chosen is not None,
            "retention_by_tier": retention,
            "prev_retention": max([retention[k] for k in p["tiers"] if retention[k] < p["T"]], default=0.0)}


def cf_uplink(p: dict) -> dict:
    """Exact event-driven walk of the two-buffer schedule. Rates are Mbit/s and
    the walk advances in minutes, so every rate term below carries the 60 factor."""
    mission = p["mission_min"]
    boundaries = sorted({ph["end"] for ph in p["phases"]} | {0.0, mission})

    def rates_at(t):
        for ph in p["phases"]:
            if ph["start"] <= t < ph["end"]:
                return ph["rate_usv"], ph["rate_uav"]
        return p["phases"][-1]["rate_usv"], p["phases"][-1]["rate_uav"]

    def allocation(b_usv, b_uav, r_usv, r_uav):
        if p["scheme"] == "fixed":
            tx_usv = p["quota_usv"] if b_usv > 0 else min(p["quota_usv"], r_usv)
            tx_uav = p["quota_uav"] if b_uav > 0 else min(p["quota_uav"], r_uav)
            return tx_usv, tx_uav
        primary, secondary = ("uav", "usv") if p["primary"] == "uav" else ("usv", "uav")
        b_p, b_s = (b_uav, b_usv) if primary == "uav" else (b_usv, b_uav)
        r_p, r_s = (r_uav, r_usv) if primary == "uav" else (r_usv, r_uav)
        if b_p > 0:
            tx_p, tx_s = p["C"], 0.0
        else:
            tx_p = min(p["C"], r_p)
            tx_s = (p["C"] - tx_p) if b_s > 0 else min(p["C"] - tx_p, r_s)
        return (tx_s, tx_p) if primary == "uav" else (tx_p, tx_s)

    t, b_usv, b_uav = 0.0, p["init_usv"], p["init_uav"]
    delivered = {"usv": 0.0, "uav": 0.0}
    completion = None
    while t < mission - 1e-12:
        r_usv, r_uav = rates_at(t)
        tx_usv, tx_uav = allocation(b_usv, b_uav, r_usv, r_uav)
        d_usv, d_uav = 60.0 * (r_usv - tx_usv), 60.0 * (r_uav - tx_uav)
        dt = min([e for e in boundaries if e > t + 1e-12] + [mission]) - t
        for buffer, drain in ((b_usv, d_usv), (b_uav, d_uav)):
            if buffer > 1e-12 and drain < 0:
                dt = min(dt, buffer / -drain)
        step = dt
        was_nonempty = (b_usv > 1e-12, b_uav > 1e-12)
        b_usv = max(0.0, b_usv + d_usv * step)
        b_uav = max(0.0, b_uav + d_uav * step)
        delivered["usv"] += 60.0 * tx_usv * step
        delivered["uav"] += 60.0 * tx_uav * step
        t += step
        if completion is None:
            for was, now in zip(was_nonempty, (b_usv, b_uav)):
                if was and now <= 1e-9:
                    completion = t
                    break
    demand = {"usv": p["init_usv"] + sum((ph["end"] - ph["start"]) * 60.0 * ph["rate_usv"] for ph in p["phases"]),
              "uav": p["init_uav"] + sum((ph["end"] - ph["start"]) * 60.0 * ph["rate_uav"] for ph in p["phases"])}
    frac = p["starve_pct"] / 100.0
    return {"delivered_usv_gb": delivered["usv"] / 8000.0, "delivered_uav_gb": delivered["uav"] / 8000.0,
            "backlog_end_usv_gb": b_usv / 8000.0, "backlog_end_uav_gb": b_uav / 8000.0,
            "starved_usv": delivered["usv"] < frac * demand["usv"],
            "starved_uav": delivered["uav"] < frac * demand["uav"],
            "completion_time_min": completion,
            "demand_mbit": demand, "delivered_mbit": delivered}


# ---------------------------------------------------------------- discovery


def discover(bank: Path, families: set[str] | None = None) -> list[Task]:
    """Task directories of the selected families; '_'-prefixed dirs (archives) are skipped."""
    tasks: list[Task] = []
    if not bank.is_dir():
        return tasks
    for entry in sorted(p for p in bank.iterdir()
                        if p.is_dir() and not p.name.startswith(("_", "verification"))):
        if families and entry.name not in families:
            continue
        if (entry / "input").is_dir() or (entry / "gold").is_dir():
            tasks.append(Task(entry, "").load())
            continue
        for sub in sorted(entry.iterdir()):
            if sub.is_dir() and ((sub / "input").is_dir() or (sub / "gold").is_dir()):
                tasks.append(Task(sub, entry.name).load())
    return tasks


def read_manifests(bank: Path, families: set[str] | None = None) -> list[dict]:
    manifests = []
    if not bank.is_dir():
        return manifests
    for directory in [bank] + sorted(d for d in bank.iterdir()
                                     if d.is_dir() and not d.name.startswith(("_", "verification"))
                                     and (not families or d.name in families or d == bank)):
        for name in ("manifest.json", "manifest.yaml", "index.jsonl"):
            path = directory / name
            if not path.is_file():
                continue
            entry = {"path": str(path.relative_to(bank)), "dir": directory.name, "entries": [],
                     "count_declared": None, "error": None}
            try:
                if path.suffix == ".jsonl":
                    entry["entries"] = [json.loads(line) for line in
                                        path.read_text(encoding="utf-8").splitlines() if line.strip()]
                else:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(payload, dict):
                        entry["entries"] = payload.get("tasks") or []
                        entry["count_declared"] = _float(payload.get("count") or payload.get("task_count"))
                        entry["stats"] = payload.get("stats")
                        entry["rejected_params"] = payload.get("rejected_params")
                        entry["extra_keys"] = sorted(k for k in payload if k not in
                                                      {"family", "generator", "seed", "count", "tasks",
                                                       "closed_form", "parameter_space", "narrative",
                                                       "stats", "rejected_params", "scenario", "package",
                                                       "tolerances", "constraints", "pilot_check"})
            except (json.JSONDecodeError, yaml.YAMLError, OSError) as exc:
                entry["error"] = f"{type(exc).__name__}: {exc}"
            manifests.append(entry)
    return manifests


def atomic_write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    if isinstance(payload, str):
        temporary.write_text(payload, encoding="utf-8")
    else:
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- audit A
def audit_structure(bank: Path, tasks: list[Task], manifests: list[dict], out: Path) -> dict:
    missing, bad_parse, key_problems, gold_mismatch, duplicates = [], {}, {}, {}, {}
    rows = []
    seen: dict[str, list[str]] = {}
    for task in tasks:
        row = {"id": task.id, "family": task.family_dir, "problems": []}
        if task.error:
            row["problems"].append(f"gold unparsable: {task.error}")
            bad_parse[task.id] = task.error
        for required in REQUIRED_FILES:
            if not (task.path / required).is_file():
                row["problems"].append(f"missing {required}")
                missing.append(f"{task.id}:{required}")
        answers = answer_payload(task.answer) if task.answer is not None else None
        if answers is None:
            row["problems"].append("answer.json missing or unparsable")
        else:
            checks = task.checks()
            if not checks:
                row["problems"].append("assertions.yaml schema not recognised (no checks/tolerance band)")
            else:
                answer_keys = set(answers)
                check_keys = set(checks)
                unmatched = sorted(k for k in answer_keys - check_keys
                                   if k != "key_points")  # shape key graded via key_point_count
                one_sided = sorted(k for k in check_keys - answer_keys
                                   if not k.endswith("_count") and not k.startswith("key_point"))
                if unmatched or one_sided:
                    key_problems[task.id] = {"answer_without_check": unmatched, "check_without_answer": one_sided}
                    row["problems"].append(f"key mismatch: {unmatched[:4]} / {one_sided[:4]}")
                for key, check in checks.items():
                    gold = check.get("gold")
                    value = answers.get(key)
                    if gold is not None and value is not None and not isinstance(value, (list, dict)):
                        if _float(value) is None or abs(_float(value) - gold) > 1e-9:
                            gold_mismatch[task.id] = gold_mismatch.get(task.id, {})
                            gold_mismatch[task.id][key] = {"answer": value, "assertions_gold": gold}
                            row["problems"].append(f"answer/assertions gold differ on {key}")
        seen.setdefault(task.id, []).append(f"{task.family_dir}/{task.id}" if task.family_dir else task.id)
        rows.append({"id": row["id"], "family": row["family"], "problems": row["problems"]})
    for task_id, where in seen.items():
        if len(where) > 1:
            duplicates[task_id] = where
    manifest_rows, platform_rows = [], {}
    for manifest in manifests:
        row = {k: v for k, v in manifest.items() if k != "entries"}
        scope = tasks if manifest["dir"] == bank.name else [t for t in tasks if t.family_dir == manifest["dir"]]
        ids = {str(_first(e, "id", "name") or "") for e in manifest["entries"]}
        row["count_listed"] = len(manifest["entries"])
        row["actual_task_dirs"] = len(scope)
        listed_ok = row["count_listed"] == row["actual_task_dirs"] if manifest["entries"] else True
        declared_ok = row["count_declared"] is None or row["count_declared"] == row["actual_task_dirs"]
        row["count_ok"] = listed_ok and declared_ok
        row["ids_missing_on_disk"] = sorted(i for i in ids if i and i not in {t.id for t in scope})[:10]
        no_platform = [str(_first(e, "id", "name") or f"entry[{i}]")
                       for i, e in enumerate(manifest["entries"])
                       if isinstance(e, dict) and _first(e, "platform") is None]
        row["entries_missing_platform"] = no_platform[:10]
        row["entries_missing_platform_count"] = len(no_platform)
        if manifest["dir"] in FAMILY_DIRS and not manifest["entries"]:
            covered = sum(1 for t in scope if isinstance(t.assertions, dict) and t.assertions.get("platform"))
            row["platform_covered_by_task_assertions"] = f"{covered}/{len(scope)}"
        manifest_rows.append(row)
    # rejected-params bookkeeping (backlog: list of dicts; uplink/latency: {count, reasons, samples})
    rejected = {}
    for manifest in manifests:
        rp = manifest.get("rejected_params")
        if not rp:
            continue
        stats = manifest.get("stats") or {}
        if isinstance(rp, dict):
            list_len, reasons = rp.get("count"), dict(rp.get("reasons") or {})
        else:
            list_entries = [r for r in rp if isinstance(r, dict)]
            list_len, reasons = len(rp), dict(Counter(r.get("reason") for r in list_entries))
        declared = stats.get("rejected_by_reason") if isinstance(stats, dict) else None
        if not declared and isinstance(stats.get("rejected"), dict):
            declared = stats["rejected"]
        rejected_total = sum(declared.values()) if isinstance(declared, dict) else declared
        attempts = stats.get("sampling_attempts")
        accepted = stats.get("accepted")
        if accepted is None and attempts is not None and rejected_total is not None:
            accepted = attempts - rejected_total
        rejected[manifest["path"]] = {
            "list_len": list_len, "reasons": reasons, "declared_reasons": declared,
            "list_matches_declared": reasons == (declared or {}),
            "sampling_attempts": attempts, "accepted": accepted, "rejected_total": rejected_total,
            "attempts_minus_rejected_equals_accepted":
                attempts is not None and rejected_total is not None and attempts - rejected_total == accepted,
            "accepted_equals_task_count": accepted == row_count(manifest, tasks)}
    report = {
        "generated_at": stamp(), "tasks_seen": len(tasks),
        "families": dict(Counter(t.family_dir for t in tasks)),
        "missing_files": missing, "unparsable_gold": bad_parse,
        "answer_assertions_key_mismatches": key_problems,
        "answer_assertions_gold_mismatches": gold_mismatch,
        "cross_family_duplicate_ids": duplicates,
        "manifests": manifest_rows,
        "rejected_params": rejected,
        "tasks": rows,
    }
    problems = bool(missing or bad_parse or key_problems or gold_mismatch or duplicates
                    or any(not m["count_ok"] or m["ids_missing_on_disk"] for m in manifest_rows)
                    or any(not r["list_matches_declared"] or not r["attempts_minus_rejected_equals_accepted"]
                           or not r["accepted_equals_task_count"] for r in rejected.values()))
    report["status"] = "RED" if (missing or bad_parse) else ("WARN" if problems else "PASS")
    atomic_write(out / "structure.json", report)
    return report


def row_count(manifest, tasks) -> int:
    return len([t for t in tasks if t.family_dir == manifest["dir"]])


# ---------------------------------------------------------------- audit B
def numeric_gold_items(task: Task) -> list[dict]:
    """(key, gold, tol, check) for every scalar numeric answer of a task."""
    out = []
    if task.answer is None:
        return out
    answers = answer_payload(task.answer)
    checks = task.checks()
    for key, value in answers.items():
        number = _float(value)
        if number is None:
            continue
        check = checks.get(key) or {}
        out.append({"key": key, "gold": number, "tol": tol_of(check, number) or abs(number) * 0.02})
    for point in answers.get("key_points") or []:
        if isinstance(point, dict) and _float(point.get("soc_pct")) is not None:
            number = _float(point["soc_pct"])
            out.append({"key": f"soc@{point.get('t_min')}", "gold": number, "tol": 0.02 * abs(number)})
    return out


def audit_boundary(tasks: list[Task], out: Path) -> dict:
    margins, booleans, parse_failures, inconsistencies = [], {}, [], []
    vectors: list[tuple[str, str, dict]] = []
    for task in tasks:
        params = task.params()
        if params is None:
            if task.text:
                parse_failures.append(task.id)
            continue
        answers = answer_payload(task.answer) if task.answer is not None else {}
        checks = task.checks()
        items = numeric_gold_items(task)

        def edge_row(key, gold, tol, edge_name, edge_value, kind="decision", family_dir=task.family_dir, id_=task.id):
            # decision edges: distance is |gold - edge|; the sign only decides a boolean.
            # bound edges: crossing the single edge is itself invalid.
            # interval edges: distance to the nearer end of the valid interval.
            if kind == "interval":
                lo, hi = edge_value
                distance = min(gold - lo, hi - gold)
            elif kind == "bound":
                distance = gold - edge_value
            else:
                distance = abs(gold - edge_value)
            margins.append({"id": id_, "family": family_dir, "key": key, "gold": gold, "tol": round(tol, 6),
                            "edge": edge_name, "edge_value": list(edge_value) if kind == "interval" else edge_value,
                            "kind": kind,
                            "margin": round(distance, 6),
                            "margin_over_tol": round(distance / tol, 2) if tol else None,
                            "verdict": ("outside" if distance < 0 else
                                        "ok" if distance >= MARGIN_FACTOR * tol else "tight")})

        if task.family == "battery":
            reserve = params["reserve_pct"]
            for item in items:
                edge_row(item["key"], item["gold"], item["tol"], "soc_interval_pct", (0.0, 100.0), kind="interval")
                if reserve is not None:
                    edge_row(item["key"], item["gold"], item["tol"], "reserve_pct", reserve)
            boolean = _bool(answers.get("meets_reserve"))
            if boolean is not None:
                booleans.setdefault(f"{task.family_dir}/meets_reserve", {"true": 0, "false": 0})[str(boolean).lower()] += 1
                end_item = next((i for i in items if i["key"] == "soc_end_pct"), None)
                if reserve is not None and end_item:
                    edge_row("meets_reserve", end_item["gold"], end_item["tol"], "reserve_pct", reserve)
                recomputed = cf_battery_soc_pct(params, params["rows"][-1]["end"]) >= reserve
                if boolean != recomputed:
                    inconsistencies.append({"id": task.id, "key": "meets_reserve",
                                            "gold": boolean, "recomputed": recomputed})
            vectors.append((task.family_dir, task.id, {
                "capacity": params["capacity_wh"], "soc0": params["soc_start_pct"],
                **{f"p{i+1}": r["power"] for i, r in enumerate(params["rows"])},
                **{f"d{i+1}": r["end"] - r["start"] for i, r in enumerate(params["rows"])}}))
        elif task.family == "buffer":
            cap_gb = params["capacity_gb"]
            for item in items:
                if item["key"] in {"max_backlog_gb", "end_backlog_gb"}:
                    edge_row(item["key"], item["gold"], item["tol"], "capacity_gb", cap_gb)
                elif item["key"] == "end_headroom_gb":
                    edge_row(item["key"], item["gold"], item["tol"], "zero", 0.0)
                elif item["key"] == "overflow_at_min" and item["gold"] is not None:
                    for name, edge in ([(f"window{w+1}_end", s + d) for w, (s, d) in enumerate(params["windows"])]
                                       + [("mission_end", params["mission_min"])]):
                        edge_row(item["key"], item["gold"], item["tol"], name, edge)
            boolean = _bool(answers.get("overflows"))
            if boolean is not None:
                booleans.setdefault(f"{task.family_dir}/overflows", {"true": 0, "false": 0})[str(boolean).lower()] += 1
                recomputed = cf_backlog(params)
                if boolean != recomputed["overflows"]:
                    inconsistencies.append({"id": task.id, "key": "overflows",
                                            "gold": boolean, "recomputed": recomputed["overflows"]})
                gold_cross = answers.get("overflow_at_min")
                if recomputed["overflows"] != (gold_cross is not None):
                    inconsistencies.append({"id": task.id, "key": "overflow_at_min",
                                            "gold": gold_cross, "recomputed": recomputed["overflow_at_min"]})
                elif gold_cross is not None and abs(_float(gold_cross) - recomputed["overflow_at_min"]) > 2.0:
                    inconsistencies.append({"id": task.id, "key": "overflow_at_min",
                                            "gold": gold_cross, "recomputed": round(recomputed["overflow_at_min"], 3)})
            vectors.append((task.family_dir, task.id, {
                "sensor": params["sensor"], "link": params["link"], "capacity_gb": params["capacity_gb"],
                "mission": params["mission_min"],
                **{f"w{s}_start": s for s, d in params["windows"]},
                **{f"w{i}_dur": d for i, (s, d) in enumerate(params["windows"])}}))
        elif task.family == "thermal":
            tmax = params["Tmax"]
            for item in items:
                if item["key"] in {"steady_state_c", "peak_temp_c"}:
                    edge_row(item["key"], item["gold"], item["tol"], "Tmax", tmax)
            boolean = _bool(answers.get("exceeds_limit"))
            if boolean is not None:
                booleans.setdefault(f"{task.family_dir}/exceeds_limit", {"true": 0, "false": 0})[str(boolean).lower()] += 1
                recomputed = cf_thermal(params)
                temperature = recomputed.get("peak_c", recomputed["steady_c"])
                if boolean != (temperature > tmax):
                    inconsistencies.append({"id": task.id, "key": "exceeds_limit",
                                            "gold": boolean, "recomputed": temperature > tmax})
                t_item = next((i for i in items if i["key"] in {"steady_state_c", "peak_temp_c"}), None)
                if t_item:
                    edge_row("exceeds_limit", t_item["gold"], t_item["tol"], "Tmax", tmax)
            vectors.append((task.family_dir, task.id, {"P": params["P"], "Rth": params["Rth"],
                                                       "Cth": params["Cth"], "Tamb": params["Tamb"], "Tmax": tmax}))
        elif task.family == "harvest":
            protection = params["protection_pct"]
            for item in items:
                if item["key"].endswith("_pct") or item["key"].startswith("soc@"):
                    edge_row(item["key"], item["gold"], item["tol"], "soc_interval_pct", (0.0, 100.0), kind="interval")
                if item["key"] in {"soc_end_pct", "min_soc_pct"} or item["key"].startswith("soc@"):
                    edge_row(item["key"], item["gold"], item["tol"], "protection_pct", protection)
            boolean = _bool(answers.get("breached"))
            if boolean is not None:
                booleans.setdefault(f"{task.family_dir}/breached", {"true": 0, "false": 0})[str(boolean).lower()] += 1
                recomputed = cf_harvest(params)
                if boolean != recomputed["breached"]:
                    inconsistencies.append({"id": task.id, "key": "breached",
                                            "gold": boolean, "recomputed": recomputed["breached"]})
                min_item = next((i for i in items if i["key"] == "min_soc_pct"), None)
                if min_item:
                    edge_row("breached", min_item["gold"], min_item["tol"], "protection_pct", protection)
            vectors.append((task.family_dir, task.id, {
                "capacity": params["capacity_wh"], "soc0": params["soc_start_pct"],
                "protection": protection,
                **{f"load{i+1}": r["load"] for i, r in enumerate(params["rows"])},
                **{f"solar{i+1}": r["solar"] for i, r in enumerate(params["rows"])},
                **{f"d{i+1}": r["end"] - r["start"] for i, r in enumerate(params["rows"])}}))
        elif task.family == "latency":
            threshold = params["threshold"]
            for item in items:
                if item["key"] in {"mean_e2e_s", "max_e2e_s"}:
                    edge_row(item["key"], item["gold"], item["tol"], "staleness_threshold_s", threshold)
                elif item["key"] == "fresh_ratio":
                    edge_row(item["key"], item["gold"], item["tol"], "ratio_interval", (0.0, 1.0), kind="interval")
            boolean = _bool(answers.get("meets_staleness"))
            if boolean is not None:
                booleans.setdefault(f"{task.family_dir}/meets_staleness", {"true": 0, "false": 0})[str(boolean).lower()] += 1
                recomputed = cf_latency(params)
                if boolean != recomputed["meets_staleness"]:
                    inconsistencies.append({"id": task.id, "key": "meets_staleness",
                                            "gold": boolean, "recomputed": recomputed["meets_staleness"]})
                mean_item = next((i for i in items if i["key"] == "mean_e2e_s"), None)
                if mean_item:
                    edge_row("meets_staleness", mean_item["gold"], mean_item["tol"],
                             "staleness_threshold_s", threshold)
            vectors.append((task.family_dir, task.id, {
                "onboard": params["onboard"], "relay": params["relay"],
                "d_up": params["d_up"], "v_up": params["v_up"],
                "d_down": params["d_down"], "v_down": params["v_down"],
                "period": params["period"], "first": params["first"],
                "spacing": params["t_collect"][1] - params["t_collect"][0] if len(params["t_collect"]) > 1 else 0.0,
                "n_msgs": float(len(params["t_collect"])), "threshold": threshold}))
        elif task.family == "storage":
            recomputed = cf_storage(params)
            for item in items:
                if item["key"] == "retention_h":
                    edge_row(item["key"], item["gold"], item["tol"], "target_h", params["T"])
                elif item["key"] == "headroom_gb":
                    edge_row(item["key"], item["gold"], item["tol"], "zero", 0.0)
            boolean = _bool(answers.get("meets_target") if params["variant"] == "retention" else answers.get("feasible"))
            if boolean is not None:
                key = "meets_target" if params["variant"] == "retention" else "feasible"
                booleans.setdefault(f"{task.family_dir}/{key}", {"true": 0, "false": 0})[str(boolean).lower()] += 1
                if boolean != recomputed[key]:
                    inconsistencies.append({"id": task.id, "key": key, "gold": boolean,
                                            "recomputed": recomputed[key]})
                if params["variant"] == "choice":
                    gold_k = answers.get("chosen_k")
                    if gold_k != recomputed["chosen_k"]:
                        inconsistencies.append({"id": task.id, "key": "chosen_k",
                                                "gold": gold_k, "recomputed": recomputed["chosen_k"]})
                    # the choice boundary: the target must sit clear of the tiers on both sides
                    ret_item = next((i for i in items if i["key"] == "retention_h"), None)
                    tol = ret_item["tol"] if ret_item else 0.02 * abs(recomputed["retention_h"])
                    edge_row("chosen_k", params["T"], tol, "prev_tier_retention_h", recomputed["prev_retention"])
                    top = recomputed["retention_by_tier"][max(params["tiers"])]
                    if recomputed["chosen_k"] is not None:
                        edge_row("chosen_k", params["T"], tol, "chosen_tier_retention_h",
                                 recomputed["retention_by_tier"][recomputed["chosen_k"]])
                    else:
                        edge_row("chosen_k", params["T"], tol, "tier16_retention_h", top)
                else:
                    ret_item = next((i for i in items if i["key"] == "retention_h"), None)
                    if ret_item:
                        edge_row(key, ret_item["gold"], ret_item["tol"], "target_h", params["T"])
            vectors.append((task.family_dir, task.id, {
                "R": params["R"], "S": params["S"], "T": params["T"],
                **({"N": float(params["N"])} if params["variant"] == "retention" else {})}))
        elif task.family == "uplink":
            recomputed = cf_uplink(params)
            fraction = params["starve_pct"] / 100.0
            for item in items:
                if item["key"] in {"delivered_usv_gb", "delivered_uav_gb"}:
                    platform = "usv" if "usv" in item["key"] else "uav"
                    edge_row(item["key"], item["gold"], item["tol"], "starvation_threshold_gb",
                             fraction * recomputed["demand_mbit"][platform] / 8000.0)
                elif item["key"] == "completion_time_min" and item["gold"] is not None:
                    for phase in params["phases"]:
                        edge_row(item["key"], item["gold"], item["tol"],
                                 f"phase_end_{int(phase['end'])}", phase["end"])
                    edge_row(item["key"], item["gold"], item["tol"], "mission_end", params["mission_min"])
            for key in ("starved_usv", "starved_uav"):
                boolean = _bool(answers.get(key))
                if boolean is None:
                    continue
                booleans.setdefault(f"{task.family_dir}/{key}", {"true": 0, "false": 0})[str(boolean).lower()] += 1
                if boolean != recomputed[key]:
                    inconsistencies.append({"id": task.id, "key": key, "gold": boolean,
                                            "recomputed": recomputed[key]})
            gold_completion = answers.get("completion_time_min")
            if recomputed["completion_time_min"] is not None and gold_completion is not None:
                if abs(_float(gold_completion) - recomputed["completion_time_min"]) > 2.0:
                    inconsistencies.append({"id": task.id, "key": "completion_time_min",
                                            "gold": gold_completion,
                                            "recomputed": round(recomputed["completion_time_min"], 3)})
            elif (recomputed["completion_time_min"] is None) != (gold_completion is None):
                inconsistencies.append({"id": task.id, "key": "completion_time_min",
                                        "gold": gold_completion,
                                        "recomputed": recomputed["completion_time_min"]})
            vectors.append((task.family_dir, task.id, {
                "C": params["C"], "init_usv": params["init_usv"], "init_uav": params["init_uav"],
                "starve_pct": params["starve_pct"], "mission": params["mission_min"],
                **{f"quota_{k}": params[k] for k in ("quota_usv", "quota_uav") if k in params},
                **{f"rate_usv{i+1}": ph["rate_usv"] for i, ph in enumerate(params["phases"])},
                **{f"rate_uav{i+1}": ph["rate_uav"] for i, ph in enumerate(params["phases"])},
                **{f"pdur{i+1}": ph["end"] - ph["start"] for i, ph in enumerate(params["phases"])}}))

    near_pairs = near_duplicate_pairs(vectors)
    tight = [m for m in margins if m["verdict"] == "tight"]
    outside = [m for m in margins if m["verdict"] == "outside"]
    one_sided = {k: v for k, v in booleans.items() if not (v["true"] and v["false"])}
    report = {
        "generated_at": stamp(),
        "tasks_with_parameters": len(vectors), "requirement_parse_failures": parse_failures,
        "numeric_margin_rows": len(margins),
        "tight_below_3x_tol": tight, "outside_band": outside,
        "boolean_distribution": booleans, "boolean_one_sided": one_sided,
        "boolean_gold_inconsistencies": inconsistencies,
        "near_duplicate_param_pairs": near_pairs, "near_duplicate_pair_count": len(near_pairs),
    }
    report["status"] = "RED" if (outside or inconsistencies) else \
                       ("WARN" if (tight or one_sided or near_pairs or parse_failures) else "PASS")
    atomic_write(out / "boundary.json", report)
    return report


def near_duplicate_pairs(vectors: list[tuple[str, str, dict]]) -> list[dict]:
    pairs = []
    by_family: dict[str, list[tuple[str, dict]]] = {}
    for family, task_id, params in vectors:
        by_family.setdefault(family, []).append((task_id, params))
    for family, members in by_family.items():
        names = sorted({n for _, p in members for n in p})
        spans = {}
        for name in names:
            values = [p[name] for _, p in members if name in p]
            spans[name] = max(values) - min(values) if len(values) > 1 else 0.0
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                (id_a, pa), (id_b, pb) = members[i], members[j]
                shared = set(pa) & set(pb)
                if len(shared) < 3:
                    continue
                worst = 0.0
                for name in shared:
                    if spans.get(name, 0.0) > 0:
                        worst = max(worst, abs(pa[name] - pb[name]) / spans[name])
                if worst < NEAR_DUP_EPS:
                    pairs.append({"family": family, "a": id_a, "b": id_b,
                                  "normalised_distance": round(worst, 5), "shared_params": sorted(shared)})
    return pairs


# ---------------------------------------------------------------- audit C
def package_name_of(model_path: Path) -> str | None:
    match = re.search(r"\bpackage\s+([A-Za-z_][A-Za-z0-9_]*)",
                      model_path.read_text(encoding="utf-8", errors="ignore"))
    return match.group(1) if match else None


def audit_pilot(tasks: list[Task], out: Path, stride: int, timeout: int) -> dict:
    from mvp.toolchain.validate import validate_package  # lazy: JVM path only
    sampled = tasks[::stride] if stride > 0 else []
    results = []
    for index, task in enumerate(sampled):
        model = task.path / "input" / "model.sysml"
        record = {"id": task.id, "family": task.family_dir, "status": "NOT_RUN", "diagnostics": []}
        if not model.is_file():
            record.update(status="SKIP", diagnostics=[{"code": "NO_MODEL_FILE"}])
        else:
            package = package_name_of(model) or (task.case or {}).get("package")
            if not package:
                record.update(status="SKIP", diagnostics=[{"code": "NO_PACKAGE_DECL"}])
            else:
                record["package"] = package
                work = out / "work" / "pilot" / f"{index:03d}-{re.sub(r'[^A-Za-z0-9_.-]', '_', task.id)}"
                if work.exists():
                    shutil.rmtree(work)
                try:
                    result = validate_package([str(model)], package, str(work), timeout=timeout)
                    record["status"] = result["status"]
                    record["wall_seconds"] = result.get("wall_seconds")
                    record["diagnostics"] = [d.get("code") or f"{d.get('severity')}: {(d.get('message') or '')[:140]}"
                                             for d in (result.get("diagnostics") or [])][:5]
                    # keep validation.json (status, diagnostics, input hashes) but drop the
                    # ~29 MB/task official exports: reproducible from the hashed inputs
                    for bulky in ("model.json", "ast-elements.json"):
                        (work / bulky).unlink(missing_ok=True)
                except Exception as exc:  # noqa: BLE001 (record, never crash the sweep)
                    record.update(status="ERROR", diagnostics=[{"code": type(exc).__name__, "message": str(exc)[:300]}])
        results.append(record)
        atomic_write(out / "pilot-sample.json",
                     {"generated_at": stamp(), "stride": stride, "timeout_s": timeout,
                      "sampled": len(sampled), "completed": len(results),
                      "status": ("RED" if any(r["status"] in {"FAIL", "ERROR"} for r in results)
                                 else "PASS" if results else "EMPTY"),
                      "results": results})
    report = {"generated_at": stamp(), "stride": stride, "timeout_s": timeout,
              "tasks_seen": len(tasks), "sampled": len(sampled),
              "pass": sum(1 for r in results if r["status"] == "PASS"),
              "fail": [r for r in results if r["status"] == "FAIL"],
              "error": [r for r in results if r["status"] in {"ERROR", "SKIP"}],
              "status": "RED" if any(r["status"] in {"FAIL", "ERROR"} for r in results)
                        else ("PASS" if results else "EMPTY"),
              "results": results}
    atomic_write(out / "pilot-sample.json", report)
    return report


# ---------------------------------------------------------------- audit D
def omc_run(work: Path, model: str, overrides: dict, simulations: list[dict]) -> dict:
    """Simulate a parameterised wrapper of a RTRC.mo model; return per-sim values."""
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    shutil.copy(RTRC_MO, work / "RTRC.mo")
    override_text = ", ".join(f"{name} = {value!r}" for name, value in sorted(overrides.items()))
    (work / "SimCase.mo").write_text(
        f"within RTRC;\nmodel SimCase extends RTRC.{model}({override_text});\nend SimCase;\n", encoding="utf-8")
    lines = ["setCommandLineOptions(\"--sim-flag=-r=%s_res.csv\"); getErrorString();",
             f"loadFile(\"{work}/RTRC.mo\"); getErrorString();",
             f"loadFile(\"{work}/SimCase.mo\"); getErrorString();"]
    for index, sim in enumerate(simulations):
        intervals = max(2, int(sim["stop"] / sim.get("step", 5.0))) if sim["stop"] > 0 else 1
        lines.append(f"simulate(RTRC.SimCase, startTime=0, stopTime={sim['stop']}, tolerance=1e-8, "
                     f"numberOfIntervals={intervals}, method=\"dassl\", outputFormat=\"csv\", "
                     f"fileNamePrefix=\"q{index}\"); getErrorString();")
    (work / "run.mos").write_text("\n".join(lines) + "\n", encoding="utf-8")
    environment = dict(os.environ)
    environment["PATH"] = f"{OM_HOME / 'bin'}:{environment.get('PATH', '')}"
    completed = subprocess.run([str(OMC), "run.mos"], cwd=str(work), env=environment,
                               capture_output=True, text=True, timeout=240)
    values = []
    for index, sim in enumerate(simulations):
        csv_path = work / f"q{index}_res.csv"
        if not csv_path.is_file():
            values.append(None)
            continue
        rows = list(csv.reader(csv_path.read_text(encoding="utf-8").splitlines()))
        header = [h.strip().strip('"') for h in rows[0]] if rows else []
        column = next((c for c in header if c.lower() == sim["variable"].lower()), None)
        if column is None or len(rows) < 2:
            values.append(None)
            continue
        try:
            series = [(float(r[0]), float(r[header.index(column)])) for r in rows[1:] if len(r) > header.index(column) and r[0]]
            values.append(series)
        except (ValueError, IndexError):
            values.append(None)
    return {"series": values, "return_code": completed.returncode,
            "log_tail": (completed.stdout or "")[-300:]}


def series_value(series, t: float) -> float | None:
    if not series:
        return None
    return min(series, key=lambda point: abs(point[0] - t))[1]


def series_crossing(series, level: float) -> float | None:
    """First time the series reaches `level`, linear between grid points."""
    if not series:
        return None
    for (t0, v0), (t1, v1) in zip(series, series[1:]):
        if v0 < level <= v1:
            return t0 + (level - v0) * (t1 - t0) / (v1 - v0) if v1 != v0 else t1
    return series[-1][0] if series[-1][1] >= level else None


def crosscheck_battery(task: Task, params: dict, work: Path) -> dict:
    rows = params["rows"]
    mappable = len(rows) <= 4 and rows[0]["start"] == 0.0
    record = {"id": task.id, "family": "battery", "status": "PASS",
              "params": {k: params[k] for k in ("capacity_wh", "soc_start_pct")},
              "duty_rows": len(rows), "queries": []}
    if not mappable:
        record["reason"] = (f"{len(rows)} duty rows exceed the four tiers of RTRC.mo MaritimeBattery; "
                            "closed-form comparison only")
    queries = [q for q in (task.answer or {}).get("key_points", []) if _float(q.get("t_min") or 0) > 0]
    end_min = rows[-1]["end"]
    omc_series = []
    if mappable:
        overrides = {"E_cap_wh": params["capacity_wh"], "soc_start": params["soc_start_pct"] / 100.0}
        for i in range(3):
            overrides[f"t_sw{i+1}"] = (rows[i]["end"] if i < len(rows) else end_min + i + 1) * 60.0
            overrides[{0: "P_acquire", 1: "P_record", 2: "P_transmit"}[i]] = \
                rows[i]["power"] if i < len(rows) else 0.0
        overrides["P_idle"] = rows[3]["power"] if len(rows) == 4 else 0.0
        sims = [{"stop": end_min * 60.0, "variable": "soc", "step": 5.0}]
        sims += [{"stop": q["t_min"] * 60.0, "variable": "soc", "step": 5.0} for q in queries]
        omc_series = omc_run(work, "MaritimeBattery", overrides, sims)["series"]

    def compare(key, gold, tol, omc_value, cf):
        tol = max(tol, 1e-6)  # a gold of exactly 0 still needs a checkable tolerance
        row = {"key": key, "gold": gold, "tol": round(tol, 6), "omc": omc_value, "closed_form": cf,
               "abs_omc_gold": abs(omc_value - gold) if omc_value is not None else None,
               "abs_cf_gold": abs(cf - gold) if cf is not None else None}
        cf_bad = cf is None or abs(cf - gold) >= HALF * tol
        omc_bad = omc_value is not None and abs(omc_value - gold) >= HALF * tol
        row["status"] = "RED" if (cf_bad or omc_bad) else ("OK" if omc_value is not None else "CF_ONLY")
        record["queries"].append(row)

    end_gold = _float((task.answer or {}).get("soc_end_pct"))
    if end_gold:
        end_value = series_value(omc_series[0], end_min * 60.0) if omc_series else None
        compare("soc_end_pct", end_gold, 0.02 * abs(end_gold),
                100.0 * end_value if end_value is not None else None,
                cf_battery_soc_pct(params, end_min))
    for index, q in enumerate(queries, start=1):
        gold = _float(q.get("soc_pct"))
        if gold is None:
            continue
        value = series_value(omc_series[index], q["t_min"] * 60.0) if omc_series else None
        compare(f"soc@{q['t_min']}", gold, 0.02 * abs(gold),
                100.0 * value if value is not None else None,
                cf_battery_soc_pct(params, q["t_min"]))
    if any(q["status"] == "RED" for q in record["queries"]):
        record["status"] = "RED"
    elif not mappable or any(q["status"] == "CF_ONLY" for q in record["queries"]) or not record["queries"]:
        record["status"] = "WARN"   # closed form verified; omc not applicable to this variant
    return record


def crosscheck_backlog(task: Task, params: dict, work: Path) -> dict:
    """Compare end/max/headroom golds with the closed form, and with omc when the
    task fits RTRC.mo's BufferFill: single outage window AND sensor <= downlink.
    The model's noEvent zero-switch makes backlog == 0 absorbing, so a sensor that
    outruns the link never grows from empty (verified numerically on BLG-0183);
    such tasks and multi-window tasks are checked against the closed form only."""
    mappable = len(params["windows"]) == 1 and params["sensor"] <= params["link"]
    series = None
    if mappable:
        start, duration = params["windows"][0]
        overrides = {"r_data": params["sensor"], "r_link": params["link"],
                     "t_break": start * 60.0, "t_repair": (start + duration) * 60.0}
        omc = omc_run(work, "BufferFill", overrides,
                      [{"stop": params["mission_min"] * 60.0, "variable": "backlog", "step": 1.0}])
        series = omc["series"][0] or None
    answers = task.answer or {}
    cf = cf_backlog(params)
    record = {"id": task.id, "family": "buffer", "status": "PASS",
              "params": {k: params[k] for k in ("sensor", "link", "mission_min", "capacity_gb")},
              "windows": len(params["windows"]), "queries": []}
    if not mappable:
        reason = (f"{len(params['windows'])} outage windows: RTRC.mo BufferFill has one"
                  if len(params["windows"]) != 1 else
                  "sensor > downlink: RTRC.mo BufferFill cannot grow from an empty buffer")
        record["reason"] = f"{reason}; closed form only"

    def compare(key, gold, tol, omc_value, cf_value):
        row = {"key": key, "gold": gold, "tol": round(tol, 6),
               "omc": round(omc_value, 6) if omc_value is not None else None,
               "closed_form": round(cf_value, 6),
               "abs_omc_gold": abs(omc_value - gold) if omc_value is not None else None,
               "abs_cf_gold": abs(cf_value - gold)}
        cf_bad = cf_value is None or abs(cf_value - gold) >= HALF * tol
        omc_bad = omc_value is not None and abs(omc_value - gold) >= HALF * tol
        row["status"] = "RED" if (cf_bad or omc_bad) else ("OK" if omc_value is not None else "CF_ONLY")
        record["queries"].append(row)

    end_omc = series[-1][1] / 8000.0 if series else None
    max_omc = max(v for _, v in series) / 8000.0 if series else None
    for key, cf_key, omc_value in (("end_backlog_gb", "end_gb", end_omc), ("max_backlog_gb", "max_gb", max_omc)):
        gold = _float(answers.get(key))
        if gold is None:
            continue
        compare(key, gold, max(0.02 * abs(gold), 0.05), omc_value, cf[cf_key])
    headroom = _float(answers.get("end_headroom_gb"))
    if headroom is not None:
        compare("end_headroom_gb", headroom, max(0.02 * abs(headroom), 0.05),
                (params["capacity_gb"] - end_omc) if end_omc is not None else None,
                cf["headroom_gb"])
    crossing = _float(answers.get("overflow_at_min"))
    if crossing is not None and cf["overflow_at_min"] is not None:
        compare("overflow_at_min", crossing, 2.0, None, cf["overflow_at_min"])
    if any(q["status"] == "RED" for q in record["queries"]):
        record["status"] = "RED"
    elif not mappable or any(q["status"] == "CF_ONLY" for q in record["queries"]) or not record["queries"]:
        record["status"] = "WARN"   # closed form verified; omc not applicable to this variant
    return record


def crosscheck_thermal(task: Task, params: dict, work: Path) -> dict:
    cf = cf_thermal(params)
    tau = cf["tau_s"]
    answers = task.answer or {}
    sims, targets = [], []
    steady_gold = _float(answers.get("steady_state_c"))
    if steady_gold is not None:
        sims.append({"stop": 10.0 * tau, "variable": "T", "step": max(1.0, tau / 100.0)})
        targets.append(("steady_state_c", steady_gold, 0.02 * abs(steady_gold), cf["steady_c"], "K"))
    peak_gold = _float(answers.get("peak_temp_c"))
    if peak_gold is not None and params.get("N_min") is not None:
        sims.append({"stop": params["N_min"] * 60.0, "variable": "T", "step": max(1.0, tau / 100.0)})
        targets.append(("peak_temp_c", peak_gold, 0.02 * abs(peak_gold), cf["peak_c"], "K"))
    t95_gold = _float(answers.get("t95_min"))
    if t95_gold is not None:
        sims.append({"stop": 4.0 * tau, "variable": "T", "step": max(1.0, tau / 200.0)})
        targets.append(("t95_min", t95_gold, 2.0, cf["t95_min"], "min"))
    if not sims:
        return {"status": "WARN", "id": task.id, "family": "thermal", "reason": "no crosscheckable answers"}
    overrides = {"C": params["Cth"], "Rth": params["Rth"], "P_w": params["P"],
                 "T_amb": params["Tamb"] + 273.15}
    omc = omc_run(work, "ThermalNode", overrides, sims)
    record = {"id": task.id, "family": "thermal", "status": "PASS",
              "params": {k: params[k] for k in ("P", "Rth", "Cth", "Tamb")}, "queries": []}
    for index, (key, gold, tol, cf_value, mode) in enumerate(targets):
        series = omc["series"][index]
        if not series:
            record["queries"].append({"key": key, "status": "WARN", "reason": "omc produced no series"})
            continue
        if mode == "min":  # t95: first time within 5 percent of the steady rise
            level = params["Tamb"] + 273.15 + 0.95 * cf["rise_c"]
            omc_value = series_crossing(series, level)
            omc_value = omc_value / 60.0 if omc_value is not None else None
        else:
            omc_value = series[-1][1] - 273.15  # T at stop time, degC
        row = {"key": key, "gold": gold, "tol": round(tol, 6),
               "omc": round(omc_value, 6) if omc_value is not None else None,
               "closed_form": round(cf_value, 6),
               "abs_omc_gold": abs(omc_value - gold) if omc_value is not None else None,
               "abs_cf_gold": abs(cf_value - gold)}
        row["status"] = ("OK" if omc_value is not None
                         and abs(omc_value - gold) < HALF * tol and abs(cf_value - gold) < HALF * tol
                         else "RED" if omc_value is not None else "WARN")
        record["queries"].append(row)
    record["status"] = ("RED" if any(q["status"] == "RED" for q in record["queries"])
                        else "PASS" if record["queries"] and all(q["status"] == "OK" for q in record["queries"])
                        else "WARN" if record["queries"] else "WARN")
    return record


def crosscheck_harvest(task: Task, params: dict, work: Path) -> dict:
    """omc crosscheck via a per-task generated Modelica model (RTRC.mo untouched):
    an if-else chain over the row net powers integrates soc, dassl tol 1e-8."""
    rows = params["rows"]
    end_min = rows[-1]["end"]
    chain, prev = [], 0.0
    for row in rows:
        net = row["load"] - row["solar"]
        chain.append(f"{'if' if not chain else 'elseif'} time < {row['end'] * 60.0!r} then {-net!r}")
        prev = row["end"]
    chain.append(f"else {-(rows[-1]['load'] - rows[-1]['solar'])!r}")
    body = "\n        ".join(chain)
    model = (f"model HRVCase\n"
             f"  parameter Real E_cap_wh = {params['capacity_wh']!r};\n"
             f"  parameter Real soc_start = {params['soc_start_pct'] / 100.0!r};\n"
             f"  Real soc(start = soc_start);\n"
             f"equation\n"
             f"  der(soc) = (\n        {body}\n        ) / (3600.0 * E_cap_wh);\n"
             f"end HRVCase;\n")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    (work / "HRVCase.mo").write_text(model, encoding="utf-8")
    step = 5.0
    (work / "run.mos").write_text(
        "setCommandLineOptions(\"--sim-flag=-r=%s_res.csv\"); getErrorString();\n"
        f"loadFile(\"{work}/HRVCase.mo\"); getErrorString();\n"
        f"simulate(HRVCase, startTime=0, stopTime={end_min * 60.0!r}, tolerance=1e-8, "
        f"numberOfIntervals={max(2, int(end_min * 60.0 / step))}, method=\"dassl\", "
        f"outputFormat=\"csv\", fileNamePrefix=\"soc\"); getErrorString();\n", encoding="utf-8")
    environment = dict(os.environ)
    environment["PATH"] = f"{OM_HOME / 'bin'}:{environment.get('PATH', '')}"
    completed = subprocess.run([str(OMC), "run.mos"], cwd=str(work), env=environment,
                               capture_output=True, text=True, timeout=240)
    csv_path = work / "soc_res.csv"
    series = []
    if csv_path.is_file():
        parsed = list(csv.reader(csv_path.read_text(encoding="utf-8").splitlines()))
        if len(parsed) > 1:
            header = [h.strip().strip('"') for h in parsed[0]]
            if "soc" in header:
                column = header.index("soc")
                try:
                    series = [(float(r[0]), 100.0 * float(r[column])) for r in parsed[1:] if r and r[0]]
                except (ValueError, IndexError):
                    series = []
    record = {"id": task.id, "family": "harvest", "status": "PASS",
              "params": {k: params[k] for k in ("capacity_wh", "soc_start_pct", "protection_pct")},
              "duty_rows": len(rows), "omc_return_code": completed.returncode, "queries": []}
    cf = cf_harvest(params)
    answers = task.answer or {}

    def compare(key, gold, tol, omc_value, cf_value):
        row = {"key": key, "gold": gold, "tol": round(tol, 6),
               "omc": round(omc_value, 6) if omc_value is not None else None,
               "closed_form": round(cf_value, 6) if cf_value is not None else None,
               "abs_omc_gold": abs(omc_value - gold) if omc_value is not None else None,
               "abs_cf_gold": abs(cf_value - gold) if cf_value is not None else None}
        cf_bad = cf_value is None or abs(cf_value - gold) >= HALF * tol
        omc_bad = omc_value is not None and abs(omc_value - gold) >= HALF * tol
        row["status"] = "RED" if (cf_bad or omc_bad) else ("OK" if omc_value is not None else "CF_ONLY")
        record["queries"].append(row)

    if series:
        omc_end = series[-1][1]
        omc_min = min(series, key=lambda point: point[1])
        compare("soc_end_pct", _float(answers.get("soc_end_pct")), 0.02 * abs(_float(answers.get("soc_end_pct")) or 1.0),
                omc_end, cf["soc_end_pct"])
        compare("min_soc_pct", _float(answers.get("min_soc_pct")), 0.02 * abs(_float(answers.get("min_soc_pct")) or 1.0),
                omc_min[1], cf["min_soc_pct"])
        compare("min_soc_at_min", _float(answers.get("min_soc_at_min")), 2.0,
                omc_min[0] / 60.0, cf["min_soc_at_min"])
    else:
        record["omc_error"] = (completed.stdout or "")[-200:]
    for point in answers.get("key_points") or []:
        gold = _float(point.get("soc_pct"))
        t_min = _float(point.get("t_min") or 0)
        if gold is None or t_min is None:
            continue
        omc_value = series_value(series, t_min * 60.0) if series else None
        compare(f"soc@{t_min}", gold, 0.02 * abs(gold), omc_value, cf_harvest_soc_pct(params, t_min))
    if any(q["status"] == "RED" for q in record["queries"]):
        record["status"] = "RED"
    elif not series or any(q["status"] == "CF_ONLY" for q in record["queries"]):
        record["status"] = "WARN"
    return record


def crosscheck_closed_form(task: Task, params: dict, family: str) -> dict:
    """Families without a differential-model counterpart in RTRC.mo (latency,
    storage, uplink): every numeric gold and boolean is checked against the
    verifier's independent closed form at half tolerance."""
    cf = {"latency": cf_latency, "storage": cf_storage, "uplink": cf_uplink}[family](params)
    key_map = {"latency": {"mean_e2e_s": "mean_e2e_s", "max_e2e_s": "max_e2e_s", "fresh_ratio": "fresh_ratio"},
               "storage": {"retention_h": "retention_h", "headroom_gb": "headroom_gb"},
               "uplink": {"delivered_usv_gb": "delivered_usv_gb", "delivered_uav_gb": "delivered_uav_gb",
                          "backlog_end_usv_gb": "backlog_end_usv_gb", "backlog_end_uav_gb": "backlog_end_uav_gb",
                          "completion_time_min": "completion_time_min"}}
    bool_map = {"latency": {"meets_staleness": "meets_staleness"},
                "storage": {"meets_target": "meets_target", "feasible": "feasible"},
                "uplink": {"starved_usv": "starved_usv", "starved_uav": "starved_uav"}}
    record = {"id": task.id, "family": family, "status": "PASS",
              "reason": "no RTRC.mo counterpart: verified against the independent closed form",
              "queries": []}
    answers = task.answer or {}
    checks = task.checks()
    for answer_key, cf_key in key_map[family].items():
        gold = _float(answers.get(answer_key))
        if gold is None:
            continue
        cf_value = cf.get(cf_key)
        if cf_value is None:
            continue
        check = checks.get(answer_key) or {}
        tol = max(tol_of(check, gold), 1e-6)  # a gold of exactly 0 still needs a checkable tolerance
        row = {"key": answer_key, "gold": gold, "tol": round(tol, 6),
               "closed_form": round(cf_value, 6), "abs_cf_gold": abs(cf_value - gold)}
        row["status"] = "OK" if abs(cf_value - gold) < HALF * tol else "RED"
        record["queries"].append(row)
    for answer_key, cf_key in bool_map[family].items():
        boolean = _bool(answers.get(answer_key))
        if boolean is None or cf_key not in cf:
            continue
        row = {"key": answer_key, "gold": boolean, "closed_form": cf[cf_key]}
        row["status"] = "OK" if boolean == cf[cf_key] else "RED"
        record["queries"].append(row)
    if family == "storage" and params["variant"] == "choice":
        row = {"key": "chosen_k", "gold": answers.get("chosen_k"), "closed_form": cf["chosen_k"]}
        row["status"] = "OK" if answers.get("chosen_k") == cf["chosen_k"] else "RED"
        record["queries"].append(row)
    record["status"] = ("RED" if any(q["status"] == "RED" for q in record["queries"])
                        else "PASS" if record["queries"] else "WARN")
    return record


def audit_modelica(tasks: list[Task], out: Path, sample_pct: float, seed: int) -> dict:
    if not OMC.is_file() or not RTRC_MO.is_file():
        report = {"generated_at": stamp(), "status": "WARN",
                  "reason": f"omc={OMC.is_file()} RTRC.mo={RTRC_MO.is_file()}"}
        atomic_write(out / "modelica-crosscheck.json", report)
        return report
    rng = random.Random(seed)
    strata: dict[str, list[Task]] = {}
    for task in tasks:
        if task.family not in {"battery", "buffer", "thermal", "harvest", "latency", "storage", "uplink"}:
            continue
        params = task.params()
        if params is None:
            continue
        if task.family == "buffer" and (len(params["windows"]) != 1 or params["sensor"] > params["link"]):
            stratum = "buffer_multiwindow_or_ge"    # closed form only (see crosscheck_backlog)
        elif task.family == "battery":
            stratum = "battery_4tier" if len(params["rows"]) <= 4 else "battery_extended"
        elif task.family == "thermal":
            stratum = f"thermal_{'duty' if params.get('N_min') is not None else 'steady'}"
        elif task.family == "latency":
            stratum = f"latency_{params['medium']}"
        elif task.family == "storage":
            stratum = f"storage_{params['variant']}"
        elif task.family == "uplink":
            stratum = f"uplink_{params['scheme']}"
        else:
            stratum = task.family
        strata.setdefault(stratum, []).append(task)
    sampled = []
    for stratum in sorted(strata):
        pool = sorted(strata[stratum], key=lambda t: t.id)
        take = min(len(pool), max(1, round(len(pool) * sample_pct / 100.0)))
        sampled.extend((stratum, task) for task in rng.sample(pool, take))
    results, red = [], []
    for stratum, task in sorted(sampled, key=lambda p: p[1].id):
        params = task.params()
        work = out / "work" / "om" / f"{task.family}-{re.sub(r'[^A-Za-z0-9_.-]', '_', task.id)}"
        try:
            if task.family == "battery":
                record = crosscheck_battery(task, params, work)
            elif task.family == "buffer":
                record = crosscheck_backlog(task, params, work)
            elif task.family == "thermal":
                record = crosscheck_thermal(task, params, work)
            elif task.family == "harvest":
                record = crosscheck_harvest(task, params, work)
            else:
                record = crosscheck_closed_form(task, params, task.family)
        except Exception as exc:  # noqa: BLE001
            record = {"id": task.id, "family": task.family, "status": "WARN",
                      "reason": f"{type(exc).__name__}: {exc}"}
        results.append(record)
        if record.get("status") == "RED":
            red.append(task.id)
        atomic_write(out / "modelica-crosscheck.json",
                     {"generated_at": stamp(), "sample_pct": sample_pct, "seed": seed,
                      "strata": {k: len(v) for k, v in sorted(strata.items())},
                      "sampled_ids": [t.id for _, t in sampled], "red_ids": sorted(set(red)),
                      "status": "RED" if red else ("PASS" if results else "EMPTY"), "results": results})
    report = {"generated_at": stamp(), "sample_pct": sample_pct, "seed": seed,
              "tasks_seen": len(tasks), "strata": {k: len(v) for k, v in sorted(strata.items())},
              "sampled": [t.id for _, t in sorted(sampled, key=lambda p: p[1].id)],
              "red_ids": sorted(set(red)),
              "warn_ids": sorted(r["id"] for r in results if r.get("status") == "WARN"),
              "status": "RED" if red else ("PASS" if results else "EMPTY"), "results": results}
    atomic_write(out / "modelica-crosscheck.json", report)
    return report


# ---------------------------------------------------------------- audit E
def audit_scenario(tasks: list[Task], manifests: list[dict], out: Path) -> dict:
    missing_declaration, loose_declaration, missing_vocab = [], [], []
    platforms_by_task: dict[tuple[str, str], str] = {}
    manifest_entries = 0
    for manifest in manifests:
        for entry in manifest.get("entries", []):
            if isinstance(entry, dict) and entry.get("platform") is not None:
                platforms_by_task.setdefault((manifest["dir"], str(_first(entry, "id", "name") or "")),
                                             str(entry["platform"]).lower())
                manifest_entries += 1
    for task in tasks:
        text = (task.text or "").lower()
        if RTX_DECLARATION.lower() not in text:
            normalised = re.sub(r"[;,\u2013\u2014-]+", ",", text)
            if RTX_DECLARATION.lower() in normalised.replace(" , ", ", "):
                loose_declaration.append(task.id)  # same words, different punctuation
            else:
                missing_declaration.append(task.id)
        if not any(word in text for word in MARITIME_VOCAB):
            missing_vocab.append(task.id)
        if isinstance(task.assertions, dict) and task.assertions.get("platform"):
            platforms_by_task.setdefault((task.family_dir or "unknown", task.id),
                                         str(task.assertions["platform"]).lower())
    platforms: dict[str, dict[str, int]] = {}
    for (family, _), platform in platforms_by_task.items():
        bucket = platforms.setdefault(family, {})
        bucket[platform] = bucket.get(platform, 0) + 1
    report = {
        "generated_at": stamp(),
        "rtx_declaration": {"required_line": RTX_DECLARATION,
                            "missing_count": len(missing_declaration), "missing_ids": missing_declaration[:50],
                            "punctuation_variant_count": len(loose_declaration),
                            "punctuation_variant_ids": loose_declaration[:50]},
        "maritime_vocabulary": {"any_of": list(MARITIME_VOCAB),
                                "missing_count": len(missing_vocab), "missing_ids": missing_vocab[:50]},
        "platform_distribution": platforms,
        "platform_sources": {"tasks_covered": len(platforms_by_task),
                             "manifest_entry_rows_seen": manifest_entries},
        "status": "WARN" if (missing_declaration or missing_vocab) else "PASS",
    }
    atomic_write(out / "scenario-binding.json", report)
    return report


# ---------------------------------------------------------------- summary
def write_summary(out: Path, bank: Path, tasks, reports: dict, args) -> None:
    lines = ["# SIM bank verification summary", "",
             f"- generated: {stamp()}",
             f"- bank: `{bank}` — {len(tasks)} task directories"
             f" ({', '.join(f'{k}={v}' for k, v in sorted(Counter(t.family_dir for t in tasks).items())) or 'absent'})",
             f"- audits run: {', '.join(sorted(reports))}",
             f"- pilot stride={reports.get('pilot', {}).get('stride', args.stride)}"
             f" (timeout {reports.get('pilot', {}).get('timeout_s', args.pilot_timeout)}s, sampled"
             f" {reports.get('pilot', {}).get('sampled', '?')}/{reports.get('pilot', {}).get('tasks_seen', '?')});"
             f" crosscheck {reports.get('modelica', {}).get('sample_pct', args.sample_pct)}% stratified"
             f" (seed {reports.get('modelica', {}).get('seed', args.seed)},"
             f" {len(reports.get('modelica', {}).get('sampled', []))} tasks)",
             ""]
    verdicts = {}
    for name in sorted(reports):
        report = reports[name]
        status = report.get("status", "EMPTY")
        verdicts[name] = status
        lines.append(f"## {name.upper()} — {status}")
        if name == "structure":
            lines += [f"- tasks seen: {report['tasks_seen']} by family: {report['families']}",
                      f"- missing required files: {len(report['missing_files'])}",
                      f"- unparsable gold: {len(report['unparsable_gold'])}",
                      f"- answer/assertions key mismatches: {len(report['answer_assertions_key_mismatches'])}",
                      f"- answer/assertions gold mismatches: {len(report['answer_assertions_gold_mismatches'])}",
                      f"- cross-family duplicate ids: {len(report['cross_family_duplicate_ids'])}"]
            for manifest in report["manifests"]:
                extra = ""
                if manifest.get("platform_covered_by_task_assertions"):
                    extra = f", platform via task assertions {manifest['platform_covered_by_task_assertions']}"
                lines.append(f"- manifest `{manifest['path']}`: listed {manifest['count_listed']}"
                             f" (declared {manifest['count_declared']}) vs on-disk {manifest['actual_task_dirs']}"
                             f" — match {manifest['count_ok']}; entries lacking platform: "
                             f"{manifest.get('entries_missing_platform_count', 0)}{extra}")
            for path, rejected in (report.get("rejected_params") or {}).items():
                lines += [f"- rejected_params `{path}`: {rejected['list_len']} records, "
                          f"attempts {rejected['sampling_attempts']} / accepted {rejected['accepted']} / "
                          f"rejected {rejected['rejected_total']}",
                          f"  reasons {json.dumps(rejected['reasons'], ensure_ascii=False)} — "
                          f"matches declared {rejected['list_matches_declared']}; "
                          f"attempts−rejected=accepted {rejected['attempts_minus_rejected_equals_accepted']}; "
                          f"accepted=task count {rejected['accepted_equals_task_count']}"]
        elif name == "boundary":
            tight = report["tight_below_3x_tol"]
            tight_ids = sorted({row["id"] for row in tight})
            lines += [f"- tasks with parsed parameters: {report['tasks_with_parameters']}"
                      f" (requirement parse failures: {len(report['requirement_parse_failures'])})",
                      f"- numeric margin rows: {report['numeric_margin_rows']}",
                      f"- tight (<{MARGIN_FACTOR:.0f}x tol from an edge): {len(tight)} rows over {len(tight_ids)} tasks",
                      f"- outside acceptance band (RED): {len(report['outside_band'])}",
                      f"- boolean gold vs recomputed closed form: {len(report['boolean_gold_inconsistencies'])} inconsistencies",
                      f"- boolean distribution: {json.dumps(report['boolean_distribution'])}"
                      f"{' — ONE-SIDED: ' + str(list(report['boolean_one_sided'])) if report['boolean_one_sided'] else ''}",
                      f"- near-duplicate parameter pairs (<{NEAR_DUP_EPS} normalised): {report['near_duplicate_pair_count']}"]
            for pair in report["near_duplicate_param_pairs"][:10]:
                lines.append(f"  - {pair['a']} ~ {pair['b']} ({pair['family']}, dist {pair['normalised_distance']})")
            lines.append(f"  - tight-margin tasks (worst first, for the human review): "
                         + ", ".join(f"{row['id']}({row['key']}@{row['edge']}:{row['margin_over_tol']}x)"
                                     for row in sorted(tight, key=lambda r: r["margin_over_tol"] or 0)[:12]))
        elif name == "pilot":
            lines += [f"- sampled {report['sampled']} of {report['tasks_seen']} (stride {report['stride']})",
                      f"- PASS {report['pass']}, FAIL {len(report['fail'])}, ERROR/SKIP {len(report['error'])}",
                      f"- families sampled: {json.dumps(dict(Counter(r['family'] for r in report['results'])), ensure_ascii=False)}"]
        elif name == "modelica":
            results = report.get("results", [])
            omc_verified = [r for r in results if any(q.get("omc") is not None for q in r.get("queries", []))]
            cf_only = [r for r in results if r.get("status") == "WARN"]
            lines += [f"- strata: {json.dumps(report.get('strata', {}))}",
                      f"- sampled {len(report.get('sampled', []))}: {', '.join(report.get('sampled', []))}",
                      f"- verified with omc (dassl, tol 1e-8): {len(omc_verified)}; "
                      f"verified against the independent closed form only: {len(results) - len(omc_verified)}",
                      f"- PASS {sum(1 for r in results if r['status'] == 'PASS')}, "
                      f"closed-form-only WARN (variant not expressible in RTRC.mo): {len(cf_only)}",
                      f"- RED ids: {report.get('red_ids') or 'none'}",
                      f"- closed-form-only ids: {report.get('warn_ids') or 'none'}"]
        elif name == "scenario":
            lines += [f"- tasks missing the exact RTX declaration line: {report['rtx_declaration']['missing_count']}"
                      + (f" (punctuation variants: {report['rtx_declaration']['punctuation_variant_count']})" if report['rtx_declaration']['punctuation_variant_count'] else ""),
                      f"- tasks missing maritime vocabulary: {report['maritime_vocabulary']['missing_count']}",
                      f"- platform distribution: {json.dumps(report['platform_distribution'], ensure_ascii=False)}"]
        lines.append("")
    red = [n for n, s in verdicts.items() if s == "RED"]
    warn = [n for n, s in verdicts.items() if s == "WARN"]
    lines += ["## Verdict", f"- audit statuses: {json.dumps(verdicts)}"]
    if not tasks:
        lines.append("- No task directories found. Nothing to submit; rerun once generation lands.")
    elif red:
        lines.append(f"- RED in {', '.join(red)}. **Not ready for human review or a freeze r3** — fix the RED items and rerun.")
    elif warn:
        lines.append(f"- No RED; WARN in {', '.join(warn)}. Submit for human review only after the warnings are "
                     "accepted or cleared; a freeze r3 can include the bank once review passes.")
    else:
        lines.append("- All audits PASS. **Recommended: submit for human review; on review pass, fold the bank into freeze r3.**")
    atomic_write(out / "SUMMARY.md", "\n".join(lines) + "\n")


# ---------------------------------------------------------------- self-test (real-schema fixtures)
def _battery_fixture(task_id, params, rows, reserve, planted=None):
    capacity, soc0 = params
    dir_path = Path(task_id)
    (dir_path / "input").mkdir(parents=True, exist_ok=True)
    (dir_path / "gold").mkdir(parents=True, exist_ok=True)
    table = "\n".join(f"| {i+1} | mode{i+1} | {p} | {int(s)} | {int(e)} | {(e-s)/60:.1f} |"
                      for i, (p, s, e) in enumerate(rows))
    (dir_path / "input" / "requirements.md").write_text(
        f"# {dir_path.name} — synthetic, not an RTX specification\n\nUSV battery endurance (command ship, shore station).\n\n"
        f"## Battery\n\n- Capacity: {capacity} Wh\n- Initial SoC at t = 0: {int(soc0)} % of capacity (0.{int(soc0)})\n"
        f"- Reserve threshold: {int(reserve)} % of capacity.\n\n"
        f"## Mission duty cycle\n\n| # | Mode | Power (W) | Start (min) | End (min) | Duration (h) |\n|---|---|---|---|---|---|\n{table}\n",
        encoding="utf-8")
    (dir_path / "input" / "model.sysml").write_text(
        f"package Case{re.sub(r'[^A-Za-z0-9_]', '_', dir_path.name)} {{\n    private import ScalarValues::*;\n"
        f"    attribute capacity : ScalarValues::Real = {capacity};\n}}\n", encoding="utf-8")
    (dir_path / "case.yaml").write_text(f"id: {dir_path.name}\ntype: SIM\npackage: Case{dir_path.name}\n", encoding="utf-8")
    key_points, prev = [], 0.0
    spent = 0.0
    for i, (p, s, e) in enumerate(rows):
        spent += p * (e - prev) / 60.0
        prev = e
        key_points.append({"t_min": int(e), "mode": f"mode{i+1}",
                           "soc_pct": round(100.0 * (capacity * soc0 / 100.0 - spent) / capacity, 2)})
    soc_end = round(100.0 * (capacity * soc0 / 100.0 - spent) / capacity, 1)
    if planted == "gold":
        soc_end = round(soc_end * 1.2, 1)  # ~20% off: must trip audit D
    answer = {"task_id": dir_path.name, "soc_end_pct": soc_end,
              "meets_reserve": soc_end >= reserve,
              "key_points": [{"t_min": 0, "mode": "start", "soc_pct": float(soc0)}] + key_points}
    (dir_path / "gold" / "answer.json").write_text(json.dumps(answer, indent=2) + "\n", encoding="utf-8")
    checks = {"soc_end_pct": {"gold": soc_end, "rel_tol": 0.02},
              "meets_reserve": {"gold": soc_end >= reserve, "exact": True},
              "key_point_count": {"gold": len(answer["key_points"]), "exact": True}}
    (dir_path / "gold" / "assertions.yaml").write_text(
        f"task_id: {dir_path.name}\npackage: Case{dir_path.name}\nchecks:\n" +
        "".join(f"  {k}:\n    gold: {json.dumps(v['gold'])}\n" +
                ("    rel_tol: 0.02\n" if v.get("rel_tol") else "    exact: true\n")
                for k, v in checks.items() if k != "key_points"), encoding="utf-8")
    if planted != "no_solution":
        (dir_path / "gold" / "solution.md").write_text(f"# {dir_path.name}\n\nPiecewise energy bookkeeping.\n", encoding="utf-8")
    return {"id": dir_path.name, "platform": "usv"}


def run_selftest(args) -> bool:
    temporary = Path(tempfile.mkdtemp(prefix="verify_sim_selftest_"))
    print(f"[self-test] building 10 real-schema tasks in {temporary}")
    try:
        bank = temporary / "t_sim_bank"
        entries = []
        (bank / "sim_battery").mkdir(parents=True)
        base_rows = [(16, 0, 180), (129, 180, 300), (114, 300, 444), (114, 444, 552)]
        battery_specs = {  # BAT-0003/0004 differ by 0.2%: the planted near-duplicate pair
            1: ((1300, 75), base_rows, 23, "gold"),
            2: ((2000, 90), [(p * 1.5, s, e) for p, s, e in base_rows], 25, "no_solution"),
            3: ((1000, 80), [(p * 0.8, s, e) for p, s, e in base_rows], 20, None),
            4: ((1000, 80), [(p * 0.8016, s, e) for p, s, e in base_rows], 20, "dup"),
        }
        for i in range(1, 5):
            (capacity_soc), rows, reserve, planted = battery_specs[i]
            entries.append(_battery_fixture(bank / "sim_battery" / f"BAT-{i:04d}", capacity_soc, rows, reserve, planted))
        entries[-1]["platform"] = "uav"
        (bank / "sim_backlog").mkdir(parents=True)
        for i, (sensor, link, mission, cap_gb, windows, planted) in enumerate(
                [(35, 60, 420, 32.5, [(120, 85)], None),
                 (40, 10, 300, 5.0, [(60, 30)], "no_synth"),   # ge: grows from empty, cf-only
                 (20, 50, 240, 0.2, [(30, 200)], None)], start=1):  # BLG-0003 overflows (lt)
            task_dir = bank / "sim_backlog" / f"BLG-{i:04d}"
            (task_dir / "input").mkdir(parents=True)
            (task_dir / "gold").mkdir(parents=True)
            cap_mbit = cap_gb * 8000
            window_text = "\n".join(f"- Outage window {w+1}: start {s} min, duration {d} min"
                                    for w, (s, d) in enumerate(windows))
            declaration = "" if planted == "no_synth" else "# synthetic, not an RTX specification\n\n"
            (task_dir / "input" / "requirements.md").write_text(
                f"{declaration}UAV relay backlog to the command ship (USV, shore station world).\n\n"
                f"- Sensor data rate (whole mission, constant): {sensor} Mbit/s\n- Downlink rate while the link is up: {link} Mbit/s\n"
                f"- Mission length: {mission} min\n- Buffer capacity: {int(cap_mbit)} Mbit = {cap_gb} GB\n{window_text}\n", encoding="utf-8")
            (task_dir / "input" / "model.sysml").write_text(
                f"package CaseBLG_{i:04d} {{\n    private import ScalarValues::*;\n    attribute x : ScalarValues::Real = 1.0;\n}}\n", encoding="utf-8")
            (task_dir / "case.yaml").write_text(f"id: BLG-{i:04d}\ntype: SIM\n", encoding="utf-8")
            params = parse_backlog((task_dir / "input" / "requirements.md").read_text())
            cf = cf_backlog(params)
            answer = {"task_id": f"BLG-{i:04d}",
                      "overflows": cf["overflows"],
                      "overflow_at_min": (math.ceil(cf["overflow_at_min"]) if cf["overflow_at_min"] else None),
                      "max_backlog_gb": round(cf["max_gb"], 2),
                      "end_backlog_gb": round(cf["end_gb"], 2),
                      "end_headroom_gb": round(cf["headroom_gb"], 2)}
            (task_dir / "gold" / "answer.json").write_text(json.dumps(answer, indent=2) + "\n", encoding="utf-8")
            (task_dir / "gold" / "assertions.yaml").write_text(
                f"task_id: BLG-{i:04d}\nchecks:\n" + "".join(
                    f"  {k}:\n    gold: {json.dumps(v)}\n    " +
                    ("exact: true\n" if isinstance(v, bool) or v is None else
                     ("abs_tol_min: 2\n" if "min" in k else "rel_tol: 0.02\n    abs_tol_gb: 0.05\n"))
                    for k, v in answer.items() if k != "task_id"), encoding="utf-8")
            (task_dir / "gold" / "solution.md").write_text("# solution\n\nPiecewise backlog.\n", encoding="utf-8")
            entries.append({"id": f"BLG-{i:04d}", "platform": "uav"})
        (bank / "sim_thermal").mkdir(parents=True)
        thermal_specs = [(27.5, 0.65, 1350, 19, 67, None), (43.5, 0.85, 1300, 15, 54, "gold"), (30.0, 1.0, 900, 20, 60, "no_vocab")]
        for i, (P, Rth, Cth, Tamb, Tmax, planted) in enumerate(thermal_specs, start=1):
            task_dir = bank / "sim_thermal" / f"THM-{i:04d}"
            (task_dir / "input").mkdir(parents=True)
            (task_dir / "gold").mkdir(parents=True)
            vocab = "" if planted == "no_vocab" else "USV below-deck bay relaying imagery to the command ship and shore station.\n"
            (task_dir / "input" / "requirements.md").write_text(
                f"# synthetic, not an RTX specification\n\n{vocab}\n- dissipation P = {P} W\n"
                f"- thermal resistance Rth = {Rth} K/W\n- thermal capacity Cth = {Cth} J/K\n"
                f"- ambient temperature Tamb = {Tamb} degC\n- temperature limit Tmax = {Tmax} degC\n", encoding="utf-8")
            (task_dir / "input" / "model.sysml").write_text(
                f"package CaseTHM_{i:04d} {{\n    private import ScalarValues::*;\n    attribute y : ScalarValues::Real = 2.0;\n}}\n", encoding="utf-8")
            (task_dir / "case.yaml").write_text(f"id: THM-{i:04d}\ntype: SIM\n", encoding="utf-8")
            params = parse_thermal((task_dir / "input" / "requirements.md").read_text())
            cf = cf_thermal(params)
            steady = round(cf["steady_c"], 2)
            if planted == "gold":
                steady = round(steady * 1.1, 2)
            answer = {"steady_state_c": steady, "exceeds_limit": steady > Tmax, "t95_min": round(cf["t95_min"], 2)}
            (task_dir / "gold" / "answer.json").write_text(json.dumps(answer, indent=2) + "\n", encoding="utf-8")
            (task_dir / "gold" / "assertions.yaml").write_text(
                f"task_id: THM-{i:04d}\nplatform: usv\ntolerance:\n  steady_state_c:\n    type: float\n    rel: 0.02\n"
                f"  exceeds_limit:\n    type: bool\n    exact: true\n  t95_min:\n    type: float\n    abs: 2.0\n", encoding="utf-8")
            (task_dir / "gold" / "solution.md").write_text("# solution\n\nFirst-order thermal step.\n", encoding="utf-8")
            entries.append({"id": f"THM-{i:04d}", "platform": "usv"})
        entries[4].pop("platform", None)  # one index entry without platform: A/E4 must flag it

        # ---- new-family fixtures (harvest / latency / storage / uplink) ----
        def write_task(family, task_id, requirements, answers, checks_yaml, platform="usv", package=None):
            task_dir = bank / family / task_id
            (task_dir / "input").mkdir(parents=True)
            (task_dir / "gold").mkdir(parents=True)
            (task_dir / "input" / "requirements.md").write_text(requirements, encoding="utf-8")
            (task_dir / "input" / "model.sysml").write_text(
                f"package Case{task_id.replace('-', '_')} {{\n    private import ScalarValues::*;\n"
                f"    attribute x : ScalarValues::Real = 1.0;\n}}\n", encoding="utf-8")
            (task_dir / "case.yaml").write_text(
                f"id: {task_id}\ntype: SIM\npackage: Case{task_id.replace('-', '_')}\n", encoding="utf-8")
            (task_dir / "gold" / "answer.json").write_text(json.dumps(
                {"task_id": task_id, **answers}, indent=2) + "\n", encoding="utf-8")
            (task_dir / "gold" / "assertions.yaml").write_text(
                f"task_id: {task_id}\nchecks:\n{checks_yaml}", encoding="utf-8")
            (task_dir / "gold" / "solution.md").write_text("# solution\n\nClosed-form bookkeeping.\n", encoding="utf-8")
            entries.append({"id": task_id, "platform": platform})

        def checks_of(answers, tol_spec):
            lines = []
            for key, value in answers.items():
                spec = tol_spec.get(key, "rel")
                if isinstance(value, bool):
                    lines.append(f"  {key}:\n    gold: {str(value).lower()}\n    exact: true\n")
                elif value is None:
                    lines.append(f"  {key}:\n    gold: null\n    exact: true\n")
                elif spec == "min":
                    lines.append(f"  {key}:\n    gold: {value}\n    abs_tol_min: 2\n")
                elif spec == "gb":
                    lines.append(f"  {key}:\n    gold: {value}\n    rel_tol: 0.02\n    abs_tol_gb: 0.05\n")
                else:
                    lines.append(f"  {key}:\n    gold: {value}\n    rel_tol: 0.02\n")
            return "".join(lines)

        def harvest_fixture(task_id, cap, soc0, prot, rows, planted=None):
            table = "\n".join(f"| {i+1} | mode{i+1} | {load} | {solar} | {int(s)} | {int(e)} | {(e-s)/60:.1f} |"
                              for i, (load, solar, s, e) in enumerate(rows))
            text = (f"# {task_id} — synthetic, not an RTX specification\n\nUSV solar harvesting (command ship, shore station).\n\n"
                    f"## Battery and solar array\n\n- Capacity: {cap} Wh\n- Initial SoC at t = 0: {int(soc0)} % of capacity (0.{int(soc0)})\n"
                    f"- Protection line: {int(prot)} % of capacity. SoC must never fall below this line.\n\n"
                    f"## Mission duty cycle (rows are sequential; the mission starts at t = 0 min)\n\n"
                    f"| # | Mode | Load (W) | Solar (W) | Start (min) | End (min) | Duration (h) |\n|---|---|---|---|---|---|---|\n{table}\n")
            params = parse_harvest(text)
            cf = cf_harvest(params)
            answers = {"soc_end_pct": round(cf["soc_end_pct"], 1), "min_soc_pct": round(cf["min_soc_pct"], 2),
                       "min_soc_at_min": int(cf["min_soc_at_min"]), "breached": cf["breached"],
                       "key_points": [{"t_min": int(k["t_min"]), "mode": "row", "soc_pct": round(k["soc_pct"], 2)}
                                      for k in cf["key_points"]]}
            if planted == "gold":
                answers["min_soc_pct"] = round(answers["min_soc_pct"] * 1.15, 2)
            tol = {k: ("min" if k == "min_soc_at_min" else "rel") for k in answers if k != "key_points"}
            write_task("sim_harvest", task_id, text, answers, checks_of({k: v for k, v in answers.items() if k != "key_points"}, tol))

        harvest_fixture("HRV-0001", 900, 90, 16,
                        [(51, 25, 0, 54), (12, 0, 54, 162), (142, 95, 162, 198),
                         (142, 0, 198, 300), (51, 0, 300, 426), (51, 105, 426, 516)])
        harvest_fixture("HRV-0002", 700, 60, 55, [(60, 0, 0, 120), (120, 0, 120, 240)], planted="gold")

        def latency_fixture(task_id, d_up, v_up, d_down, onboard, relay, period, first, spacing, n_msgs, threshold, planted=None):
            times = ", ".join(str(int(spacing * i)) for i in range(n_msgs))
            medium = "underwater acoustic" if v_up == 1500 else "surface radio"
            text = (f"# {task_id} — synthetic, not an RTX specification\n\nUSV link latency (USV, UAV, command ship, shore station).\n\n"
                    f"## Data path (sensor collection → final subscriber)\n\n"
                    f"| Hop | From | To | Medium | Distance | Propagation speed |\n|-----|------|----|--------|----------|-------------------|\n"
                    f"| uplink | USV sensor | shore station relay | {medium} | {d_up} km | {v_up} m/s |\n"
                    f"| downlink | shore station relay | MOC | fiber trunk | {d_down} km | 200000000 m/s |\n\n"
                    f"Processing delays (constant for every message, every hop):\n\n"
                    f"- Onboard processing on the sensor platform: {onboard} s\n"
                    f"- Relay processing at the shore station: {relay} s\n\n"
                    f"## Transmit windows at the relay\n\n"
                    f"A window opens every {period} s, the first at t = {first} s (unlimited schedule).\n\n"
                    f"## Message batch\n\n{n_msgs} messages, collected at t = {times} s (equal spacing).\n\n"
                    f"## Freshness deadline\n\n- Freshness (staleness) threshold: {threshold} s\n")
            params = parse_latency(text)
            cf = cf_latency(params)
            answers = {"mean_e2e_s": round(cf["mean_e2e_s"], 1), "max_e2e_s": round(cf["max_e2e_s"], 1),
                       "fresh_ratio": round(cf["fresh_ratio"], 4), "meets_staleness": cf["meets_staleness"]}
            if planted == "gold":
                answers["mean_e2e_s"] = round(answers["mean_e2e_s"] * 1.3, 1)
            write_task("sim_latency", task_id, text, answers, checks_of(answers, {}))

        latency_fixture("LAT-0001", 39, 300000000, 249, 244, 139, 540, 4, 240, 8, 780)
        latency_fixture("LAT-0002", 21, 1500, 174, 350, 98, 780, 584, 300, 6, 690, planted="gold")

        def storage_fixture(task_id, rate, cap, target, variant, planted=None):
            if variant == "compress":
                tail = (f"## Compression tiers\n\nThe mission plan fixes tier T4 (k = 4) for this recording, "
                        f"so the stored rate is r = {rate}/4 Mbit/s.\n")
            elif variant == "retention":
                tail = (f"The recorder keeps 1 frame in 4 of the raw stream, so the stored rate is "
                        f"r = {rate}/4 Mbit/s.\n")
            else:
                tiers = "\n".join(f"| T{k} | {k} | {rate/k} Mbit/s |" for k in (1, 2, 4, 8, 16))
                tail = (f"## Compression tiers\n\n| Tier | factor k | stored rate |\n|---|---|---|\n{tiers}\n\n"
                        f"Choose the storage plan: report the smallest tier factor k whose retention reaches the target.\n")
            text = (f"# {task_id} — synthetic, not an RTX specification\n\nUSV mission recorder (command ship, shore station).\n\n"
                    f"## Recorder\n\n- Raw stream rate R: {rate} Mbit/s (constant)\n"
                    f"- Recorder capacity S: {cap} GB (decimal units: 1 GB = 8000 Mbit)\n"
                    f"- Required retention T: {target} h\n\n{tail}")
            params = parse_storage(text)
            cf = cf_storage(params)
            if variant in {"retention", "compress"}:
                answers = {"retention_h": round(cf["retention_h"], 2), "meets_target": cf["meets_target"],
                           "headroom_gb": round(cf["headroom_gb"], 2)}
            else:
                answers = {"chosen_k": cf["chosen_k"], "retention_h": round(cf["retention_h"], 2),
                           "feasible": cf["feasible"]}
                if planted == "gold":
                    answers["chosen_k"] = 16 if cf["chosen_k"] is None else cf["chosen_k"] * 2
            write_task("sim_storage", task_id, text, answers, checks_of(answers, {}))

        storage_fixture("CMP-0001", 46, 212.5, 17.5, "retention")
        storage_fixture("CMP-0002", 46, 15.5, 23.5, "choice", planted="gold")
        storage_fixture("CMP-0003", 35, 427.5, 4.5, "compress")

        def uplink_fixture(task_id, scheme, cap, mission, init_usv, init_uav, starve, phases, planted=None, quota=None):
            phase_table = "\n".join(f"| {i+1} | {int(s)} | {int(e)} | {ru} | {ra} |"
                                    for i, (s, e, ru, ra) in enumerate(phases))
            if scheme == "fixed":
                alloc = (f"- Allocation scheme: fixed quotas\n- USV uplink quota: {quota[0]} Mbit/s\n"
                         f"- UAV uplink quota: {quota[1]} Mbit/s\n")
            else:
                alloc = (f"- Allocation scheme: priority preemption (UAV preempts)\n- Preempting platform: UAV\n")
            text = (f"# {task_id} — synthetic, not an RTX specification\n\nShared shore uplink for the USV and the "
                    f"fixed-wing UAV (command ship, shore station relay the streams).\n\n"
                    f"## Shared shore uplink\n\n- Total uplink capacity C: {cap} Mbit/s\n{alloc}"
                    f"- Mission window: 0 to {mission} min\n"
                    f"- Initial buffered data at t = 0: USV {init_usv} Mbit, UAV {init_uav} Mbit\n"
                    f"- Starvation threshold: a platform is starved iff it delivers less than {starve} % of its demand\n\n"
                    f"## Sensor generation schedule (rates constant within each phase)\n\n"
                    f"| Phase | Start (min) | End (min) | USV rate (Mbit/s) | UAV rate (Mbit/s) |\n"
                    f"|-------|-------------|-----------|-------------------|-------------------|\n{phase_table}\n")
            params = parse_uplink(text)
            cf = cf_uplink(params)
            answers = {"delivered_usv_gb": round(cf["delivered_usv_gb"], 2), "delivered_uav_gb": round(cf["delivered_uav_gb"], 2),
                       "starved_usv": cf["starved_usv"], "starved_uav": cf["starved_uav"],
                       "backlog_end_usv_gb": round(cf["backlog_end_usv_gb"], 2),
                       "backlog_end_uav_gb": round(cf["backlog_end_uav_gb"], 2),
                       "completion_time_min": (round(cf["completion_time_min"]) if cf["completion_time_min"] is not None else None)}
            if planted == "gold":
                answers["delivered_usv_gb"] = round(answers["delivered_usv_gb"] * 1.25, 2)
            tol = {"completion_time_min": "min", "delivered_usv_gb": "gb", "delivered_uav_gb": "gb",
                   "backlog_end_usv_gb": "gb", "backlog_end_uav_gb": "gb"}
            write_task("sim_uplink", task_id, text, answers, checks_of(answers, tol), platform="usv+uav")

        uplink_fixture("SHR-0001", "fixed", 54, 240, 30000, 60000, 70,
                       [(0, 45, 30, 25), (45, 120, 24, 25), (120, 240, 11, 25)], quota=(50, 4))
        uplink_fixture("SHR-0002", "preempt_uav", 43.1, 60, 2405, 23246, 90, [(0, 60, 40, 17)], planted="gold")
        uplink_fixture("SHR-0003", "preempt_uav", 43.2, 60.2, 2406, 23292, 90, [(0, 60.2, 40.2, 17.1)])

        for fam, prefix in (("sim_battery", "BAT"), ("sim_backlog", "BLG"), ("sim_thermal", "THM"),
                            ("sim_harvest", "HRV"), ("sim_latency", "LAT"), ("sim_storage", "CMP"),
                            ("sim_uplink", "SHR")):
            (bank / fam / "index.jsonl").write_text(
                "".join(json.dumps(e) + "\n" for e in entries if e["id"].startswith(prefix)), encoding="utf-8")
            (bank / fam / "manifest.json").write_text(
                json.dumps({"family": fam, "count": sum(1 for e in entries if e["id"].startswith(prefix))}) + "\n",
                encoding="utf-8")
        # plant a near-duplicate battery pair: BAT-0003/BAT-0004 rows differ by +1 W
        out = bank / "verification"
        tasks = discover(bank)
        reports = {
            "structure": audit_structure(bank, tasks, read_manifests(bank), out),
            "boundary": audit_boundary(tasks, out),
            "pilot": audit_pilot(tasks, out, stride=3, timeout=120),
            "modelica": audit_modelica(tasks, out, sample_pct=100, seed=1),
            "scenario": audit_scenario(tasks, read_manifests(bank), out),
        }
        write_summary(out, bank, tasks, reports,
                      argparse.Namespace(stride=3, pilot_timeout=120, sample_pct=100, seed=1))
        near = {(p["a"], p["b"]) for p in reports["boundary"]["near_duplicate_param_pairs"]}
        planted_dirty = {"BAT-0001", "THM-0002", "HRV-0002", "LAT-0002", "CMP-0002", "SHR-0002"}
        checks = [
            ("A: missing solution.md caught", any("missing gold/solution.md" in p for r in reports["structure"]["tasks"] for p in r["problems"])),
            ("A: index entry without platform caught", any(m.get("entries_missing_platform_count") for m in reports["structure"]["manifests"])),
            ("A: no other missing-file false positives", len(reports["structure"]["missing_files"]) == 1),
            ("A: manifests match disk", all(m["count_ok"] for m in reports["structure"]["manifests"])),
            ("B: battery near-duplicate pair found", any(set(pair) == {"BAT-0003", "BAT-0004"} for pair in near)),
            ("B: uplink near-duplicate pair found", any(set(pair) == {"SHR-0002", "SHR-0003"} for pair in near)),
            ("B: clean margins >= 3x tol", all(row["id"] in planted_dirty for row in reports["boundary"]["tight_below_3x_tol"])
             and not reports["boundary"]["outside_band"]),
            ("B: booleans on both sides", all(v["true"] and v["false"] for v in reports["boundary"]["boolean_distribution"].values()
                                              if sum(v.values()) >= 3)),
            ("B: boolean golds consistent with closed form",
             set(i["id"] for i in reports["boundary"]["boolean_gold_inconsistencies"]) <= planted_dirty),
            ("B: all 20 tasks parsed", reports["boundary"]["tasks_with_parameters"] == 20),
            ("C: pilot PASS on sampled models", reports["pilot"]["pass"] >= 1 and not reports["pilot"]["fail"]),
            ("D: planted wrong battery gold is RED", "BAT-0001" in reports["modelica"]["red_ids"]),
            ("D: planted wrong thermal gold is RED", "THM-0002" in reports["modelica"]["red_ids"]),
            ("D: planted wrong harvest gold is RED", "HRV-0002" in reports["modelica"]["red_ids"]),
            ("D: planted wrong latency gold is RED", "LAT-0002" in reports["modelica"]["red_ids"]),
            ("D: planted wrong storage choice is RED", "CMP-0002" in reports["modelica"]["red_ids"]),
            ("D: planted wrong uplink gold is RED", "SHR-0002" in reports["modelica"]["red_ids"]),
            ("D: clean tasks not RED", set(reports["modelica"]["red_ids"]) <= planted_dirty),
            ("D: backlog crosschecked via omc", any(r["family"] == "buffer" and r["status"] == "PASS" for r in reports["modelica"]["results"])),
            ("D: harvest crosschecked via generated omc model",
             any(r["family"] == "harvest" and r["status"] == "PASS"
                 and any(q["status"] == "OK" and q.get("omc") is not None for q in r["queries"])
                 for r in reports["modelica"]["results"])),
            ("D: uplink closed-form crosscheck PASS",
             any(r.get("id") == "SHR-0001" and r["status"] == "PASS" for r in reports["modelica"]["results"])),
            ("D: ge backlog verified by closed form only (WARN, no RED)",
             any(r.get("id") == "BLG-0002" and r["status"] == "WARN"
                 and all(q["status"] == "CF_ONLY" for q in r.get("queries", []))
                 for r in reports["modelica"]["results"])),
            ("E: missing RTX declaration flagged", reports["scenario"]["rtx_declaration"]["missing_count"] >= 1),
            ("E: missing vocabulary flagged", reports["scenario"]["maritime_vocabulary"]["missing_count"] == 1),
            ("E: platform distribution aggregated", reports["scenario"]["platform_distribution"].get("sim_battery", {}).get("usv", 0) >= 1),
            ("E: dual platform bucket counted", reports["scenario"]["platform_distribution"].get("sim_uplink", {}).get("usv+uav", 0) == 3),
        ]
        failed = [name for name, ok in checks if not ok]
        for name, ok in checks:
            print(f"[self-test] {'ok  ' if ok else 'FAIL'} {name}")
        print(f"[self-test] summary at {out / 'SUMMARY.md'}")
        return not failed
    finally:
        shutil.rmtree(temporary, ignore_errors=True)
        print(f"[self-test] temporary bank deleted: {temporary}")


# ---------------------------------------------------------------- main
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bank", type=Path, default=DEFAULT_BANK, help="staged bank root (default: %(default)s)")
    parser.add_argument("--families", default="",
                        help="comma list of family dirs to audit, e.g. sim_harvest,sim_uplink (default: all; "
                             "'_'-prefixed archive dirs are always skipped)")
    parser.add_argument("--out", type=Path, default=None,
                        help="verification output dir (default: <bank>/verification; use a fresh dir when "
                             "auditing a subset so an earlier full run is not overwritten)")
    parser.add_argument("--audits", default="A,B,C,D,E", help="subset to run, e.g. A,B,E (default: all)")
    parser.add_argument("--stride", type=int, default=20, help="pilot sample: validate every Nth task (default: %(default)s)")
    parser.add_argument("--pilot-timeout", type=int, default=120, help="per-task pilot timeout, seconds (default: %(default)s)")
    parser.add_argument("--sample-pct", type=float, default=5.0,
                        help="modelica crosscheck sample percent, stratified by family/variant (default: %(default)s)")
    parser.add_argument("--seed", type=int, default=20261010, help="seed for the stratified crosscheck sample")
    parser.add_argument("--self-test", action="store_true", help="audit 10 synthetic real-schema tasks in /tmp, then delete")
    args = parser.parse_args()

    if args.self_test:
        raise SystemExit(0 if run_selftest(args) else 1)

    bank = args.bank.resolve()
    out = (args.out.resolve() if args.out else bank / "verification")
    out.mkdir(parents=True, exist_ok=True)
    families = {f.strip() for f in args.families.split(",") if f.strip()} or None
    tasks = discover(bank, families)
    manifests = read_manifests(bank, families)
    selected = {letter.strip().upper() for letter in args.audits.split(",") if letter.strip()}
    reports: dict[str, dict] = {}
    if not tasks:
        print(f"bank {bank} contains no task directories (yet); writing an empty-run summary")
    if "A" in selected:
        reports["structure"] = audit_structure(bank, tasks, manifests, out)
        print(f"A structure: {reports['structure']['status']} over {len(tasks)} tasks")
    if "B" in selected and tasks:
        reports["boundary"] = audit_boundary(tasks, out)
        print(f"B boundary: {reports['boundary']['status']}")
    if "C" in selected and tasks:
        reports["pilot"] = audit_pilot(tasks, out, args.stride, args.pilot_timeout)
        print(f"C pilot: {reports['pilot']['status']} ({reports['pilot']['pass']}/{len(reports['pilot']['results'])} PASS)")
    if "D" in selected and tasks:
        reports["modelica"] = audit_modelica(tasks, out, args.sample_pct, args.seed)
        print(f"D modelica: {reports['modelica']['status']} (red: {reports['modelica'].get('red_ids')})")
    if "E" in selected and (tasks or manifests):
        reports["scenario"] = audit_scenario(tasks, manifests, out)
        print(f"E scenario: {reports['scenario']['status']}")
    # incremental: audits not selected this run keep their last on-disk result
    for name, filename in (("structure", "structure.json"), ("boundary", "boundary.json"),
                           ("pilot", "pilot-sample.json"), ("modelica", "modelica-crosscheck.json"),
                           ("scenario", "scenario-binding.json")):
        if name not in reports and (out / filename).is_file():
            try:
                reports[name] = json.loads((out / filename).read_text(encoding="utf-8"))
                reports[name]["from_cache"] = True
            except json.JSONDecodeError:
                pass
    write_summary(out, bank, tasks, reports, args)
    print(f"artifacts: {out}")
    red = [n for n, r in reports.items() if r.get("status") == "RED"]
    raise SystemExit(2 if red else 0)


if __name__ == "__main__":
    main()
