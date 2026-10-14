"""Time-domain check of a Part 2 run: its requirements and each of its designs, simulated over the mission.

Activity (9) of the sponsor brief: "running simulations to evaluate requirement consistency, completeness, and
design-model alignment". What is evaluated here is what the design flow produced (analysis/discover-<run>.json):
the numbered requirements written from the brief and the official Pilot's parse of each design. No model is asked
anything; every number comes from those two records. The exam's budget checks (bench/discover.py simulate()) are
static sums at one instant; this module runs the same quantities over the mission timeline and reports when a
requirement is first violated.

Three results per run:
- Consistency. The requirements alone, simulated: can any design satisfy all of them at once? (power draws that
  the requirements fix against the power limit they fix; recording rate x retention against storage; upload
  against uplink.)
- Completeness. What the mission simulation needed and no requirement states (gaps), and which requirement values
  no design element carries.
- Alignment. Each design, with the values of its own official parse, against each requirement over the mission:
  PASS, FAIL with the first violation time, or UNKNOWN when the design does not state the quantity.

Cross-check: the same balance equations as a Modelica model, simulated with OpenModelica (tools/om/bin/omc); the
final values must agree with the Python integration. When omc is missing the report says so and the Python result
stands.

Mission profile: duration = retentionHours (the brief's recording window), constant rates, link up. The brief and
the requirements state no outage, no queue policy and no energy store, so none is assumed; the exploratory outage
sweep is labelled as such and is not a requirement. All values are synthetic and not an RTX specification.

    python3 bench/simulate_design.py                 # every analysis/discover-*.json
    python3 bench/simulate_design.py --run latest    # one run
Output: analysis/simulation/<run id>/{result.json, report.md, mission.mo, mission.mos} and analysis/simulation/SUMMARY.md
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis" / "simulation"
OMC = ROOT / "tools" / "om" / "bin" / "omc"
STEP_S = 60  # one minute
QUANTITIES = ("powerLimitW", "drawW", "dataRateMbps", "storageGB", "retentionHours", "uploadMbps", "uplinkMbps")


def _tail(numbers: dict, suffix: str) -> dict:
    return {name: value for name, value in numbers.items() if name.endswith("::" + suffix)}


def requirement_values(requirements: list[dict]) -> dict:
    """The quantities the requirements fix: one value per quantity, draws as a list (one per device)."""
    values: dict = {"drawW": []}
    for item in requirements:
        quantity = item.get("quantity") or {}
        name, value = quantity.get("name"), quantity.get("value")
        if name not in QUANTITIES or value is None:
            continue
        if name == "drawW":
            values["drawW"].append((item.get("id"), float(value)))
        else:
            values.setdefault(name, (item.get("id"), float(value)))
    return values


def design_values(numbers: dict) -> dict:
    values: dict = {"drawW": sorted(_tail(numbers, "drawW").items())}
    for name in QUANTITIES:
        if name == "drawW":
            continue
        found = _tail(numbers, name)
        if found:
            qualified, value = sorted(found.items())[0]
            values[name] = (qualified, float(value))
    return values


def integrate(values: dict) -> dict:
    """Minute-by-minute balance over the mission. Returns trajectories and verdicts; UNKNOWN where a quantity is absent."""
    hours = values.get("retentionHours", (None, None))[1]
    rate = values.get("dataRateMbps", (None, None))[1]
    storage = values.get("storageGB", (None, None))[1]
    upload = values.get("uploadMbps", (None, None))[1]
    uplink = values.get("uplinkMbps", (None, None))[1]
    limit = values.get("powerLimitW", (None, None))[1]
    draws = [value for _name, value in values.get("drawW", [])]
    total_draw = sum(draws) if draws else None
    result = {"mission_hours": hours, "steps": None, "series": {}, "checks": []}
    if hours is None:
        result["checks"].append({"id": "MISSION", "status": "UNKNOWN", "detail": "No retentionHours: no mission duration to simulate."})
        return result
    steps = int(round(hours * 3600 / STEP_S))
    result["steps"] = steps
    recorded = backlog = energy = 0.0
    overflow_at = None
    rec_series, back_series = [], []
    for step in range(1, steps + 1):
        if rate is not None:
            recorded += rate * STEP_S / 8000.0            # Mb/s x s -> Mb -> GB (1 GB = 8000 Mb, the exam's convention)
        if upload is not None and uplink is not None:
            backlog += max(0.0, upload - uplink) * STEP_S / 8000.0
        if total_draw is not None:
            energy += total_draw * STEP_S / 3600.0        # Wh
        if storage is not None and rate is not None and overflow_at is None and recorded > storage:
            overflow_at = step * STEP_S / 3600.0
        if step % 60 == 0 or step == steps:
            rec_series.append(round(recorded, 3))
            back_series.append(round(backlog, 3))
    result["series"] = {"hour": [round(step * STEP_S / 3600.0, 2) for step in range(60, steps + 1, 60)] + ([round(hours, 2)] if steps % 60 else []),
                        "recorded_gb": rec_series, "backlog_gb": back_series}
    result["final"] = {"recorded_gb": round(recorded, 3), "backlog_gb": round(backlog, 3), "energy_wh": round(energy, 1),
                       "total_draw_w": total_draw}
    # power over the mission: constant draws, so one verdict holds for every minute
    if limit is not None and total_draw is not None:
        result["checks"].append({"id": "POWER", "status": "PASS" if total_draw <= limit else "FAIL", "actual": total_draw, "limit": limit, "unit": "W",
                                 "first_violation_h": None if total_draw <= limit else 0.0,
                                 "detail": f"sum of draws {total_draw:g} W against the limit {limit:g} W, every minute of the mission"})
    else:
        result["checks"].append({"id": "POWER", "status": "UNKNOWN", "detail": "powerLimitW or the device draws are not stated."})
    if storage is not None and rate is not None:
        result["checks"].append({"id": "STORE", "status": "FAIL" if overflow_at is not None else "PASS", "actual": round(recorded, 2), "limit": storage, "unit": "GB",
                                 "first_violation_h": overflow_at,
                                 "detail": (f"recording fills {recorded:.1f} GB of {storage:g} GB by hour {hours:g}" if overflow_at is None
                                            else f"storage full at hour {overflow_at:.2f}; the retention requirement of {hours:g} h is not met")})
    else:
        result["checks"].append({"id": "STORE", "status": "UNKNOWN", "detail": "dataRateMbps or storageGB is not stated."})
    if upload is not None and uplink is not None:
        result["checks"].append({"id": "LINK", "status": "PASS" if upload <= uplink else "FAIL", "actual": upload, "limit": uplink, "unit": "Mbps",
                                 "first_violation_h": None if upload <= uplink else 0.0,
                                 "detail": (f"upload {upload:g} Mbps within the {uplink:g} Mbps link; nothing is left undelivered" if upload <= uplink
                                            else f"upload exceeds the link from the first minute; {backlog:.1f} GB undelivered by hour {hours:g}")})
    else:
        result["checks"].append({"id": "LINK", "status": "UNKNOWN", "detail": "uploadMbps or uplinkMbps is not stated."})
    return result


def outage_sweep(values: dict) -> list[dict]:
    """Exploratory, not a requirement: if the link were down for the first N hours and the upload stream had to wait on
    the vessel, how much would be undelivered at the end of the mission and would the recording plus that queue fit the
    storage? No requirement states an outage; this shows the exposure. Skipped when the quantities are absent."""
    hours = values.get("retentionHours", (None, None))[1]
    upload = values.get("uploadMbps", (None, None))[1]
    uplink = values.get("uplinkMbps", (None, None))[1]
    storage = values.get("storageGB", (None, None))[1]
    rate = values.get("dataRateMbps", (None, None))[1]
    if None in (hours, upload, uplink, storage, rate):
        return []
    rows = []
    for outage_h in [h for h in (0, 1, 2, 4) if h <= hours]:
        queued = upload * outage_h * 3600 / 8000.0                    # GB waiting when the link returns
        spare = max(0.0, uplink - upload)                              # Mbps available to drain it
        remaining_h = hours - outage_h
        drained = spare * remaining_h * 3600 / 8000.0
        undelivered = max(0.0, queued - drained) + max(0.0, upload - uplink) * remaining_h * 3600 / 8000.0
        peak_local = rate * hours * 3600 / 8000.0 + queued
        rows.append({"outage_h": outage_h, "undelivered_gb": round(undelivered, 2), "recording_plus_queue_gb": round(peak_local, 2),
                     "fits_storage": peak_local <= storage})
    return rows


def consistency(req_values: dict) -> dict:
    """The requirements against each other, simulated with their own values."""
    sim = integrate(req_values)
    conflicts = [check for check in sim["checks"] if check["status"] == "FAIL"]
    return {"checks": sim["checks"], "final": sim.get("final"), "status": "FAIL" if conflicts else ("PASS" if sim["checks"] and all(c["status"] == "PASS" for c in sim["checks"]) else "PARTIAL"),
            "conflicts": [c["id"] for c in conflicts]}


def completeness(req_values: dict, designs: list[dict]) -> dict:
    gaps = []
    if "retentionHours" not in req_values:
        gaps.append("mission duration: no requirement states how long the vessel operates (retentionHours is used as the window when present)")
    if "uploadMbps" not in req_values and "dataRateMbps" in req_values:
        gaps.append("upload rate: no requirement says what rate is sent to shore; the recording rate stands in")
    gaps.append("link availability: no requirement states an outage duration or what happens to the upload stream while the link is down")
    gaps.append("energy: the requirements fix a power limit but no energy store or endurance, so energy over the mission is reported and not judged")
    gaps.append("queue storage: no requirement says whether undelivered upload data occupies the recording storage")
    missing_in_designs = {}
    for design in designs:
        values = design["values"]
        absent = [name for name in QUANTITIES if name != "drawW" and name in req_values and name not in values]
        if req_values.get("drawW") and not values.get("drawW"):
            absent.append("drawW")
        missing_in_designs[design["key"]] = absent
    return {"gaps": gaps, "requirement_quantities_absent_in_design": missing_in_designs}


def alignment(req_values: dict, design: dict) -> dict:
    """Each requirement against the design over the mission: the design's own numbers drive the simulation."""
    values = design["values"]
    sim = integrate(values)
    rows = []
    for name in QUANTITIES:
        if name not in req_values or name == "drawW":
            continue
        rid, wanted = req_values[name]
        have = values.get(name)
        rows.append({"requirement": rid, "quantity": name, "required": wanted, "in_design": None if have is None else have[1],
                     "value_match": None if have is None else abs(have[1] - wanted) < 1e-9})
    if req_values.get("drawW"):
        wanted = sorted(value for _rid, value in req_values["drawW"])
        have = sorted(value for _name, value in values.get("drawW", []))
        rows.append({"requirement": ",".join(rid for rid, _v in req_values["drawW"]), "quantity": "drawW", "required": wanted, "in_design": have or None,
                     "value_match": (have == wanted) if have else None})
    verdicts = {check["id"]: check for check in sim["checks"]}
    statuses = [check["status"] for check in sim["checks"]]
    overall = "FAIL" if "FAIL" in statuses else ("UNKNOWN" if "UNKNOWN" in statuses or any(r["value_match"] is None for r in rows) else ("PASS" if all(r["value_match"] for r in rows) else "FAIL"))
    return {"key": design["key"], "pilot": design.get("pilot"), "values": rows, "mission": verdicts, "final": sim.get("final"), "series": sim.get("series"),
            "status": overall, "outage_sweep_exploratory": outage_sweep(values)}


def modelica_crosscheck(values: dict, folder: Path) -> dict:
    """The same balance in Modelica, run with OpenModelica; final values compared with the Python integration."""
    hours = values.get("retentionHours", (None, None))[1]
    rate = values.get("dataRateMbps", (None, 0.0))[1] or 0.0
    upload = values.get("uploadMbps", (None, None))[1]
    uplink = values.get("uplinkMbps", (None, None))[1]
    draws = sum(value for _n, value in values.get("drawW", [])) or 0.0
    if hours is None:
        return {"status": "SKIPPED", "detail": "no mission duration"}
    if not OMC.is_file():
        return {"status": "UNAVAILABLE", "detail": f"{OMC} not found"}
    excess = max(0.0, (upload or 0.0) - (uplink if uplink is not None else (upload or 0.0)))
    model = f"""model Mission "Recording, undelivered upload and energy over the mission; synthetic values"
  parameter Real dataRateMbps = {rate:g};
  parameter Real excessUploadMbps = {excess:g} "upload rate above the link rate";
  parameter Real totalDrawW = {draws:g};
  Real recordedGB(start = 0, fixed = true);
  Real backlogGB(start = 0, fixed = true);
  Real energyWh(start = 0, fixed = true);
equation
  der(recordedGB) = dataRateMbps / 8000;
  der(backlogGB) = excessUploadMbps / 8000;
  der(energyWh) = totalDrawW / 3600;
end Mission;
"""
    stop = hours * 3600
    script = (f'loadFile("mission.mo"); getErrorString();\n'
              f'simulate(Mission, stopTime={stop:g}, numberOfIntervals=200, outputFormat="csv"); getErrorString();\n')
    (folder / "mission.mo").write_text(model, encoding="utf-8")
    (folder / "mission.mos").write_text(script, encoding="utf-8")
    env = dict(os.environ, OPENMODELICAHOME=str(ROOT / "tools" / "om"), PATH=f"{ROOT / 'tools' / 'om' / 'bin'}:{os.environ.get('PATH', '')}")
    try:
        run = subprocess.run([str(OMC), "mission.mos"], cwd=folder, env=env, text=True, capture_output=True, timeout=300)
    except (subprocess.TimeoutExpired, OSError) as exc:
        return {"status": "ERROR", "detail": str(exc)[:300]}
    csv_path = folder / "Mission_res.csv"
    if not csv_path.is_file():
        return {"status": "ERROR", "detail": (run.stdout + run.stderr)[-600:]}
    with csv_path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    last = rows[-1]
    om = {"recorded_gb": float(last["recordedGB"]), "backlog_gb": float(last["backlogGB"]), "energy_wh": float(last["energyWh"])}
    py = integrate(values)["final"]
    deltas = {key: abs(om[key] - py[key]) for key in om}
    agree = all(delta <= max(1e-3, 1e-3 * abs(py[key])) for key, delta in deltas.items())
    for extra in folder.glob("Mission*"):
        if extra.suffix not in {".csv"}:
            extra.unlink()
    return {"status": "AGREE" if agree else "DISAGREE", "openmodelica": om, "python": {k: py[k] for k in om}, "max_delta": max(deltas.values()),
            "omc": str(OMC.relative_to(ROOT)), "stop_time_s": stop}


def evaluate(record: dict, folder: Path) -> dict:
    requirements = (record.get("requirements") or {}).get("requirements") or []
    req_values = requirement_values(requirements)
    designs = []
    for design in record.get("designs") or []:
        designs.append({"key": design["key"], "pilot": design.get("sysml_status"), "values": design_values(design.get("numbers") or {}),
                        "numbers": design.get("numbers") or {}})
    result = {"run_id": record.get("id"), "brief": record.get("brief"), "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "mission_hours": req_values.get("retentionHours", (None, None))[1],
              "requirement_values": {k: v for k, v in req_values.items()},
              "consistency": consistency(req_values),
              "completeness": completeness(req_values, designs),
              "alignment": [alignment(req_values, design) for design in designs]}
    folder.mkdir(parents=True, exist_ok=True)
    cross = modelica_crosscheck(req_values, folder)
    result["modelica_crosscheck"] = cross
    (folder / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    (folder / "report.md").write_text(report(result), encoding="utf-8")
    return result


def report(result: dict) -> str:
    lines = [f"# Simulation check · run {result['run_id']}", "",
             "Requirements and designs produced by the design flow, simulated over the mission (minute steps, constant rates, link up). "
             "Synthetic values, not an RTX specification.", "", f"Brief: {result['brief']}", "",
             f"## Consistency of the requirements: {result['consistency']['status']}", ""]
    for check in result["consistency"]["checks"]:
        lines.append(f"- {check['id']}: {check['status']} — {check.get('detail', '')}")
    lines += ["", "## Completeness", "", "Gaps the simulation met (no requirement states them):"]
    lines += [f"- {gap}" for gap in result["completeness"]["gaps"]]
    for key, absent in result["completeness"]["requirement_quantities_absent_in_design"].items():
        lines.append(f"- design {key}: requirement quantities absent from the model: {', '.join(absent) if absent else 'none'}")
    lines += ["", "## Alignment of each design with the requirements", ""]
    for design in result["alignment"]:
        lines.append(f"### Design {design['key']} · official parse {design.get('pilot')} · {design['status']}")
        lines.append("")
        lines.append("| requirement | quantity | required | in the design | match |")
        lines.append("|---|---|---|---|---|")
        for row in design["values"]:
            lines.append(f"| {row['requirement']} | {row['quantity']} | {row['required']} | {row['in_design']} | {row['value_match']} |")
        lines.append("")
        for cid, check in design["mission"].items():
            when = check.get("first_violation_h")
            lines.append(f"- {cid}: {check['status']}" + (f" (first violation at hour {when:g})" if when is not None else "") + f" — {check.get('detail', '')}")
        if design.get("final"):
            final = design["final"]
            lines.append(f"- end of mission: {final['recorded_gb']} GB recorded, {final['backlog_gb']} GB undelivered, {final['energy_wh']} Wh consumed")
        sweep = design.get("outage_sweep_exploratory") or []
        if sweep:
            lines.append("- exploratory outage sweep (no requirement states an outage): " + "; ".join(
                f"{row['outage_h']} h down → {row['undelivered_gb']} GB undelivered, recording+queue {row['recording_plus_queue_gb']} GB {'fits' if row['fits_storage'] else 'exceeds'} storage"
                for row in sweep))
        lines.append("")
    cross = result["modelica_crosscheck"]
    lines += ["## OpenModelica cross-check", "", f"{cross['status']}: " + (json.dumps({k: cross[k] for k in ('openmodelica', 'python') if k in cross}) if "openmodelica" in cross else cross.get("detail", ""))]
    return "\n".join(lines) + "\n"


def summary(results: list[dict]) -> str:
    lines = ["# Simulation checks over the Part 2 runs", "",
             "One row per run of the design flow (analysis/discover-*.json). Consistency: the requirements against each other. "
             "Alignment: each design's own numbers over the mission. Cross-check: OpenModelica against the Python integration. "
             "Synthetic values, not an RTX specification.", "",
             "| run | mission h | consistency | design A | design B | cross-check |", "|---|---|---|---|---|---|"]
    for result in results:
        by_key = {d["key"]: d for d in result["alignment"]}
        cell = lambda k: (f"{by_key[k]['status']}" + (" · " + ", ".join(f"{cid} {c['status']}" for cid, c in by_key[k]["mission"].items()) if by_key.get(k) else "")) if k in by_key else "—"
        lines.append(f"| {result['run_id']} | {result['mission_hours']} | {result['consistency']['status']}"
                     f"{(' (' + ', '.join(result['consistency']['conflicts']) + ')') if result['consistency']['conflicts'] else ''} | {cell('A')} | {cell('B')} | {result['modelica_crosscheck']['status']} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--run", default="all", help="a run id, 'latest', or 'all' (default)")
    args = parser.parse_args()
    records = sorted(ROOT.glob("analysis/discover-*.json"))
    if args.run == "latest":
        records = [ROOT / "analysis" / "discover-latest.json"]
    elif args.run != "all":
        records = [ROOT / "analysis" / f"discover-{args.run}.json"]
    else:
        records = [path for path in records if path.name != "discover-latest.json"]
    results = []
    for path in records:
        record = json.loads(path.read_text(encoding="utf-8"))
        run_id = record.get("id") or path.stem.replace("discover-", "")
        result = evaluate(record, OUT / run_id)
        results.append(result)
        cells = " ".join(f"{d['key']}:{d['status']}" for d in result["alignment"])
        print(f"{run_id}  consistency {result['consistency']['status']:7}  {cells:28}  omc {result['modelica_crosscheck']['status']}")
    if args.run == "all":
        (OUT / "SUMMARY.md").write_text(summary(results), encoding="utf-8")
        print(OUT / "SUMMARY.md")


if __name__ == "__main__":
    main()
