"""Generate the deterministic SIM thermal steady-state task family (300 tasks).

Family t_sim_bank/sim_thermal. Every gold number is a closed-form evaluation of the
first-order thermal step response

    T(t) = Tamb + P*Rth*(1 - e^(-t/(Rth*Cth)))     # t in seconds, temperatures in degC
    t95  = 3*Rth*Cth                                # seconds; three time constants = 95 %

No model and no judge is called (decisions 019/025): the seed is fixed, the parameter
grid is fixed, and the same seed rebuilds the same bytes.

Two question variants:
  steady_state  continuous duty: steady-state temperature, limit check, t95 in minutes
  duty_cycle    N minutes powered then off: peak temperature at switch-off, limit check, t95

The narrative is bound to the synthetic maritime ISR scenario (four nodes: USV, fixed-wing
UAV, command ship, shore station). The heated object is the USV below-deck electronics
bay (sealed equipment enclosure) or the UAV avionics bay; the dissipation is the radio
transmit amplifier plus the mission computer. Platform split is 60/40 USV/UAV. Platforms
change the wording and the part name only, never the parameters or the gold.

Sampling rules (enforced per task):
  - parameters deduplicated on (P, Rth, Cth, Tamb, Tmax) across the whole bank
  - exceed/not-exceed split exactly 75/75 inside each variant (150/150 overall)
  - |gold_temperature - Tmax| >= 3 x (2 % tolerance band), so the boolean is never a
    rounding artefact
  - t95_min >= 6 min = 3 x the +/-2 min time tolerance

Output: bench/tasks_staging/t_sim_bank/sim_thermal/THM-0001..0300/ with
  case.yaml, input/model.sysml, input/requirements.md,
  gold/answer.json, gold/assertions.yaml, gold/solution.md
plus manifest.json (with a per-task platform field) at the family root. Nothing outside
that new directory is written.

Run:  python3 bench/build_sim_thermal.py          # (re)build
      python3 bench/build_sim_thermal.py --check  # independent recomputation self-check
"""
from __future__ import annotations

import json
import math
import random
import shutil
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import yaml

SEED = 20261010
COUNT = 300
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "bench" / "tasks_staging" / "t_sim_bank" / "sim_thermal"
FAMILY = "t_sim_bank/sim_thermal"
PACKAGE = "ThermalAccumulation"

# Parameter grids (exact decimals; ranges per the family spec).
P_GRID = [Decimal(v) / 10 for v in range(100, 805, 5)]        # 10.0 .. 80.0 W, step 0.5
RTH_GRID = [Decimal(v) / 100 for v in range(30, 205, 5)]      # 0.30 .. 2.00 K/W, step 0.05
CTH_GRID = [Decimal(v) for v in range(200, 2001, 50)]         # 200 .. 2000 J/K, step 50
TAMB_GRID = [Decimal(v) for v in range(15, 31)]               # 15 .. 30 degC, step 1
TMAX_GRID = [Decimal(v) for v in range(45, 71)]               # 45 .. 70 degC, step 1

TEMP_REL_TOL = Decimal("0.02")   # +/-2 % on temperatures
TIME_ABS_TOL = Decimal("2")      # +/-2 min on t95_min
KELVIN = Decimal("273.15")
E = 2.718281828459045
E3_9DP = Decimal("0.049787068")  # e^-3 to 9 decimals (solution cross-check)

# Maritime ISR platforms (synthetic four-node scenario: USV, fixed-wing UAV, command
# ship, shore station). 60/40 split; wording and the bay part name only, never the
# parameters and never the gold.
PLATFORM_SHARE = {"usv": 180, "uav": 120}
PLATFORMS = {
    "usv": {
        "bay_def": "BelowDeckBay",
        "header": "USV below-deck electronics bay in a sealed equipment enclosure (maritime ISR).",
        "story": ("An unmanned surface vessel (USV) carries a below-deck electronics bay "
                  "inside a sealed equipment enclosure. On a mission leg the radio transmit "
                  "amplifier that relays imagery toward the command ship and the mission "
                  "computer together dissipate"),
        "bay": "below-deck electronics bay",
    },
    "uav": {
        "bay_def": "AvionicsBay",
        "header": "UAV avionics bay in a sealed enclosure (maritime ISR).",
        "story": ("A fixed-wing unmanned aerial vehicle (UAV) carries an avionics bay in a "
                  "sealed enclosure. On a sortie the radio transmit amplifier that pushes "
                  "tracks to the command ship and the flight/mission computer together "
                  "dissipate"),
        "bay": "avionics bay",
    },
}


def q2(x) -> Decimal:
    """Round half up to two decimals (never banker's rounding)."""
    if not isinstance(x, Decimal):
        x = Decimal(repr(float(x)))
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def dstr(d: Decimal) -> str:
    """Plain decimal string without exponent or trailing-zero noise."""
    return format(d.normalize(), "f")


def steady_state(p: dict) -> Decimal:
    return p["tamb"] + p["power"] * p["rth"]


def tau_s(p: dict) -> Decimal:
    return p["rth"] * p["cth"]


def t95_min(p: dict) -> Decimal:
    return q2(Decimal(3) * tau_s(p) / Decimal(60))


def duty_peak(p: dict, n_min: int) -> tuple[Decimal, Decimal, Decimal]:
    """Peak temperature at switch-off, all arithmetic human-checkable.

    The exponential is evaluated once in float and frozen to 9 decimals; the rest is
    exact Decimal arithmetic, so gold/solution.md reproduces answer.json digit by digit.
    """
    tau = tau_s(p)
    x = Decimal(n_min * 60) / tau                      # exact ratio, 28-digit context
    e = math.exp(-float(x))
    e9 = Decimal(f"{e:.9f}")
    one_minus = Decimal(1) - e9
    peak = q2(p["tamb"] + p["power"] * p["rth"] * one_minus)
    return peak, x, e9


def margin_ok(gold: Decimal, tmax: Decimal) -> bool:
    return abs(gold - tmax) >= Decimal(3) * TEMP_REL_TOL * gold


# --------------------------------------------------------------------------- model

MODEL_HEAD = """package ThermalAccumulation {
    private import SI::*;
    private import ISQ::*;

    // PLATFORMHEADER
    calc def SteadyStateRise {
        in dissipation : PowerValue;
        in rTh : ThermalResistanceValue;
        return rise : ThermodynamicTemperatureValue = dissipation * rTh;
    }

    // Closed form of C*dT/dt = P - (T - Tamb)/R:  T(t) = Tamb + P*R*(1 - e^(-t/(R*C)))
    calc def TemperatureAt {
        in tAmb : ThermodynamicTemperatureValue;
        in dissipation : PowerValue;
        in rTh : ThermalResistanceValue;
        in cTh : HeatCapacityValue;
        in t : TimeValue;
        return temp : ThermodynamicTemperatureValue =
            tAmb + dissipation * rTh * (1.0 - 2.718281828459045 ** (-(t / (rTh * cTh))));
    }

    constraint def TempLimit {
        in temp : ThermodynamicTemperatureValue;
        in tMax : ThermodynamicTemperatureValue;
        temp <= tMax
    }

    part def BAYDEF {
"""

MODEL_TAIL = """    }

    requirement def ThermalRequirement {
        subject bay : BAYDEF;
        attribute temp : ThermodynamicTemperatureValue;
        attribute tMax : ThermodynamicTemperatureValue;
        require constraint { temp <= tMax }
    }

    analysis def ThermalAnalysis {
        subject bay : BAYDEF;
        requirement thermal : ThermalRequirement;
        return temp : ThermodynamicTemperatureValue;
        objective thermalObjective {
            require thermal {
                :>> temp = ThermalAnalysis::temp;
                :>> tMax = bay.tMax;
            }
        }
    }
}
"""


def model_sysml(p: dict, variant: str, n_min: int, t95_seconds: Decimal, platform: str) -> str:
    meta = PLATFORMS[platform]
    attrs = [
        f"        attribute dissipation : PowerValue = {dstr(p['power'])} [W];",
        f"        attribute rTh : ThermalResistanceValue = {dstr(p['rth'])} ['K/W'];",
        f"        attribute cTh : HeatCapacityValue = {dstr(p['cth'])} ['J/K'];",
        f"        attribute tAmb : ThermodynamicTemperatureValue = {dstr(p['tamb'] + KELVIN)} [K];",
        f"        attribute tMax : ThermodynamicTemperatureValue = {dstr(p['tmax'] + KELVIN)} [K];",
        "",
        "        attribute tempSS : ThermodynamicTemperatureValue =",
        "            tAmb + SteadyStateRise(dissipation, rTh);",
    ]
    if variant == "steady_state":
        attrs += [
            "        // t95 = 3*Rth*Cth: the temperature after three time constants",
            "        attribute tempAtT95 : ThermodynamicTemperatureValue =",
            f"            TemperatureAt(tAmb, dissipation, rTh, cTh, {float(t95_seconds):.1f} [s]);",
            "",
            "        assert constraint limit : TempLimit {",
            "            in temp = tempSS;",
            f"            in tMax = {meta['bay_def']}::tMax;",
            "        }",
        ]
    else:
        attrs += [
            f"        // transmit/compute for {n_min} min, then off: the peak is the temperature at switch-off",
            "        attribute tempAtShutdown : ThermodynamicTemperatureValue =",
            f"            TemperatureAt(tAmb, dissipation, rTh, cTh, {float(n_min * 60):.1f} [s]);",
            "",
            "        assert constraint limit : TempLimit {",
            "            in temp = tempAtShutdown;",
            f"            in tMax = {meta['bay_def']}::tMax;",
            "        }",
        ]
    text = MODEL_HEAD + "\n".join(attrs) + "\n" + MODEL_TAIL
    return text.replace("PLATFORMHEADER", meta["header"]).replace("BAYDEF", meta["bay_def"])


# -------------------------------------------------------------------- requirements

def requirements_md(task_id: str, p: dict, variant: str, n_min: int, platform: str) -> str:
    meta = PLATFORMS[platform]
    params = "\n".join([
        f"- dissipation P = {dstr(p['power'])} W (radio transmit amplifier + mission computer)",
        f"- thermal resistance Rth = {dstr(p['rth'])} K/W (bay to ambient)",
        f"- thermal capacity Cth = {dstr(p['cth'])} J/K",
        f"- ambient temperature Tamb = {dstr(p['tamb'])} degC (sea/air)",
        f"- temperature limit Tmax = {dstr(p['tmax'])} degC",
    ])
    common = """
Units rule: reply with temperatures in degrees Celsius and times in minutes. A temperature
rise is identical in K and degC; T[degC] = T[K] - 273.15; 1 min = 60 s. Round to two
decimals. The answer is closed-form: no simulation is needed.
"""
    if variant == "steady_state":
        ask = f"""The {meta['bay']} starts at ambient temperature and then runs continuously for the
rest of the mission leg. The calc `TemperatureAt` in the model is the closed form
T(t) = Tamb + P*Rth*(1 - e^(-t/(Rth*Cth))), with t in seconds and temperatures in degC.

Answer three questions:
1. `steady_state_c` - the steady-state bay temperature in degC (Tamb + P*Rth).
2. `exceeds_limit` - true if that temperature exceeds Tmax, else false.
3. `t95_min` - the time in minutes to arrive within 5 percent of the steady state,
   t95 = 3*Rth*Cth (three time constants).
{common}
Reply with JSON {{"steady_state_c": <number>, "exceeds_limit": <boolean>, "t95_min": <number>}}.
"""
    else:
        ask = f"""The {meta['bay']} starts at ambient temperature. The transmit amplifier and computer
run for {n_min} minutes and then power off when the link goes quiet. While powered the
temperature rises monotonically, so the peak is the temperature at switch-off,
t = {n_min} min. The calc `TemperatureAt` in the model is the closed form
T(t) = Tamb + P*Rth*(1 - e^(-t/(Rth*Cth))), with t in seconds and temperatures in degC.

Answer three questions:
1. `peak_temp_c` - the peak temperature reached before shutdown, T({n_min} min), in degC.
2. `exceeds_limit` - true if that peak exceeds Tmax, else false.
3. `t95_min` - the time in minutes to arrive within 5 percent of the steady-state rise,
   t95 = 3*Rth*Cth (three time constants).
{common}
Reply with JSON {{"peak_temp_c": <number>, "exceeds_limit": <boolean>, "t95_min": <number>}}.
"""
    return (
        f"# {task_id} — synthetic, not an RTX specification\n\n"
        f"{meta['story']} P = {dstr(p['power'])} W into the bay. Heat leaves through the "
        "enclosure wall to ambient; the model in this folder (package "
        f"{PACKAGE}, part definition {meta['bay_def']}) treats the bay as a first-order "
        "thermal system with the parameters below (repeated from the model; the model "
        "stores temperatures in K).\n\n"
        f"{params}\n{ask}"
    )


# ------------------------------------------------------------------------ solution

def solution_md(task_id: str, p: dict, variant: str, n_min: int, gold: dict) -> str:
    prod = p["power"] * p["rth"]
    tau = tau_s(p)
    t95 = t95_min(p)
    tkey = "steady_state_c" if variant == "steady_state" else "peak_temp_c"
    tval = Decimal(f"{gold[tkey]}")
    gap = abs(tval - p["tmax"])
    band = q2(Decimal(3) * TEMP_REL_TOL * tval)
    lines = [
        f"# {task_id} - closed-form solution (no simulation, no model called)",
        "",
        f"Parameters: P = {dstr(p['power'])} W, Rth = {dstr(p['rth'])} K/W, "
        f"Cth = {dstr(p['cth'])} J/K, Tamb = {dstr(p['tamb'])} degC, Tmax = {dstr(p['tmax'])} degC"
        + (f", N = {n_min} min." if variant == "duty_cycle" else "."),
        "",
        "A rise computed in W x K/W = K is the same number in degC, so the closed form can be",
        "evaluated directly in degC.",
        "",
        f"1. Full rise at steady state: P*Rth = {dstr(p['power'])} x {dstr(p['rth'])} = {dstr(prod)} degC.",
    ]
    if variant == "steady_state":
        ss = q2(p["tamb"] + prod)
        lines += [
            f"2. Steady state: Tamb + P*Rth = {dstr(p['tamb'])} + {dstr(prod)} = "
            f"{dstr(p['tamb'] + prod)} -> {dstr(ss)} degC (rounded half up).",
            "",
            f"3. Limit check: {dstr(ss)} - {dstr(p['tmax'])} = {dstr(ss - p['tmax'])} degC versus Tmax, "
            f"so exceeds_limit = {str(gold['exceeds_limit']).lower()}.",
            f"   Margin {dstr(gap)} degC >= 3 x tolerance band 3 x (2% x {dstr(ss)}) = {dstr(band)} degC: "
            "the boolean is not a rounding artefact.",
            "",
            f"4. Time constant: tau = Rth*Cth = {dstr(p['rth'])} x {dstr(p['cth'])} = {dstr(tau)} s.",
            f"   t95 = 3*tau = {dstr(Decimal(3) * tau)} s = {dstr(Decimal(3) * tau)}/60 = "
            f"{dstr(t95)} min.",
            "",
            "5. Exponential cross-check at t = t95 (the model's TemperatureAt):",
            "   -t/tau = -3 exactly, e^(-3) = 0.049787068,",
            f"   T(t95) = {dstr(p['tamb'])} + {dstr(prod)} x (1 - 0.049787068) "
            f"= {dstr(p['tamb'])} + {dstr(prod)} x {dstr(Decimal(1) - E3_9DP)} "
            f"= {dstr(p['tamb'])} + {dstr(prod * (Decimal(1) - E3_9DP))} "
            f"= {dstr(q2(p['tamb'] + prod * (Decimal(1) - E3_9DP)))} degC,",
            "   which is 95.0212932% of the full rise: consistent with 95% at three time constants.",
        ]
    else:
        peak, x, e9 = duty_peak(p, n_min)
        one_minus = Decimal(1) - e9
        lines += [
            f"2. Time constant: tau = Rth*Cth = {dstr(p['rth'])} x {dstr(p['cth'])} = {dstr(tau)} s.",
            f"3. Exponent at switch-off: -t/tau = -({n_min} x 60)/{dstr(tau)} = "
            f"-{n_min * 60}/{dstr(tau)} = -{float(x):.8f},",
            f"   e^(-t/tau) = {dstr(e9)}  (so 1 - e^(-t/tau) = {dstr(one_minus)}).",
            f"4. Peak at switch-off: T({n_min} min) = Tamb + P*Rth*(1 - e^(-t/tau)) "
            f"= {dstr(p['tamb'])} + {dstr(prod)} x {dstr(one_minus)} "
            f"= {dstr(p['tamb'])} + {dstr(prod * one_minus)} = {dstr(peak)} degC.",
            "   After switch-off the temperature decays back to ambient, so this is the peak.",
            "",
            f"5. Limit check: {dstr(peak)} - {dstr(p['tmax'])} = {dstr(peak - p['tmax'])} degC versus Tmax, "
            f"so exceeds_limit = {str(gold['exceeds_limit']).lower()}.",
            f"   Margin {dstr(gap)} degC >= 3 x tolerance band 3 x (2% x {dstr(peak)}) = {dstr(band)} degC: "
            "the boolean is not a rounding artefact.",
            "",
            f"6. t95 = 3*tau = {dstr(Decimal(3) * tau)} s = {dstr(Decimal(3) * tau)}/60 = "
            f"{dstr(t95)} min.",
        ]
    lines += [
        "",
        "Final answers (answer.json): "
        + json.dumps({k: gold[k] for k in (tkey, "exceeds_limit", "t95_min")}),
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------- case/gold

def case_yaml(task_id: str, variant: str, platform: str) -> dict:
    return {
        "id": task_id,
        "type": "SIM",
        "scenario_family": "t_sim_bank",
        "split": "staging",
        "package": PACKAGE,
        "synthetic": True,
        "platform": platform,
        "variant": variant,
        "difficulty": variant,
        "generator": "bench/build_sim_thermal.py",
        "seed": SEED,
        "status": "generated-closed-form",
        "second_reviewer": "pending",
    }


def assertions_dict(task_id: str, p: dict, variant: str, gold: dict, gap: Decimal,
                    platform: str) -> dict:
    tkey = "steady_state_c" if variant == "steady_state" else "peak_temp_c"
    tval = Decimal(f"{gold[tkey]}")
    tol = {
        tkey: {"type": "float", "rel": 0.02},
        "exceeds_limit": {"type": "bool", "exact": True},
        "t95_min": {"type": "float", "abs": 2.0, "unit": "min"},
    }
    return {
        "task_id": task_id,
        "family": FAMILY,
        "platform": platform,
        "variant": variant,
        "difficulty": variant,
        "answer_file": "gold/answer.json",
        "tolerance": tol,
        "margin_rule": {
            "temperature_limit_gap_c": float(gap),
            "required_gap_c": float(q2(Decimal(3) * TEMP_REL_TOL * tval)),
            "note": "|gold - Tmax| >= 3 x (2% band); t95_min >= 3 x 2 min = 6 min",
        },
        "formula": "T(t) = Tamb + P*Rth*(1 - exp(-t/(Rth*Cth))); t95 = 3*Rth*Cth/60 min",
    }


# ------------------------------------------------------------------------ sampling

def plan_slots(rng: random.Random) -> list[dict]:
    slots: list[dict] = []
    for variant in ("steady_state", "duty_cycle"):
        for exceeds in (True, False):
            # one dict per slot: a shared dict would let one platform label overwrite 75 tasks
            slots.extend({"variant": variant, "exceeds": exceeds} for _ in range(COUNT // 4))
    rng.shuffle(slots)
    platforms = ["usv"] * PLATFORM_SHARE["usv"] + ["uav"] * PLATFORM_SHARE["uav"]
    rng.shuffle(platforms)
    for slot, platform in zip(slots, platforms):
        slot["platform"] = platform
    return slots


def sample_task(rng: random.Random, slot: dict, used: set) -> dict:
    for _ in range(200000):
        p = {
            "power": rng.choice(P_GRID),
            "rth": rng.choice(RTH_GRID),
            "cth": rng.choice(CTH_GRID),
            "tamb": rng.choice(TAMB_GRID),
            "tmax": rng.choice(TMAX_GRID),
        }
        key = (p["power"], p["rth"], p["cth"], p["tamb"], p["tmax"])
        if key in used:
            continue
        if t95_min(p) < Decimal(3) * TIME_ABS_TOL:      # t95 >= 6 min
            continue
        n_min = 0
        if slot["variant"] == "duty_cycle":
            t95 = float(t95_min(p))
            lo = max(2, math.ceil(0.25 * t95))
            hi = max(lo, math.floor(1.5 * t95))
            n_min = rng.randint(lo, hi)
            temp, _, _ = duty_peak(p, n_min)
        else:
            temp = q2(steady_state(p))
        if not margin_ok(temp, p["tmax"]):
            continue
        if (temp > p["tmax"]) != slot["exceeds"]:
            continue
        used.add(key)
        return {"variant": slot["variant"], "params": p, "n_min": n_min, "temp": temp}
    raise SystemExit(f"sampling failed for slot {slot}")


# --------------------------------------------------------------------------- build

def build() -> None:
    if OUT.exists():
        # Only ever delete a directory this generator itself wrote.
        if not (OUT / "manifest.json").is_file() and any(OUT.iterdir()):
            raise SystemExit(f"refusing to remove unexpected directory {OUT}")
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    rng = random.Random(SEED)
    slots = plan_slots(rng)
    used: set = set()
    tasks: list[dict] = []

    for index, slot in enumerate(slots, start=1):
        task_id = f"THM-{index:04d}"
        spec = sample_task(rng, slot, used)
        p, variant, n_min = spec["params"], spec["variant"], spec["n_min"]
        platform = slot["platform"]
        t95 = t95_min(p)
        if variant == "steady_state":
            gold = {"steady_state_c": float(spec["temp"]),
                    "exceeds_limit": spec["temp"] > p["tmax"],
                    "t95_min": float(t95)}
        else:
            gold = {"peak_temp_c": float(spec["temp"]),
                    "exceeds_limit": spec["temp"] > p["tmax"],
                    "t95_min": float(t95)}
        gap = abs(spec["temp"] - p["tmax"])

        folder = OUT / task_id
        (folder / "input").mkdir(parents=True)
        (folder / "gold").mkdir()
        (folder / "case.yaml").write_text(
            yaml.safe_dump(case_yaml(task_id, variant, platform), sort_keys=False),
            encoding="utf-8")
        (folder / "input" / "model.sysml").write_text(
            model_sysml(p, variant, n_min, Decimal(3) * tau_s(p), platform), encoding="utf-8")
        (folder / "input" / "requirements.md").write_text(
            requirements_md(task_id, p, variant, n_min, platform), encoding="utf-8")
        (folder / "gold" / "answer.json").write_text(
            json.dumps(gold, indent=2) + "\n", encoding="utf-8")
        (folder / "gold" / "assertions.yaml").write_text(
            yaml.safe_dump(assertions_dict(task_id, p, variant, gold, gap, platform),
                           sort_keys=False),
            encoding="utf-8")
        (folder / "gold" / "solution.md").write_text(
            solution_md(task_id, p, variant, n_min, gold), encoding="utf-8")

        params_out = {
            "power_w": float(p["power"]),
            "rth_k_per_w": float(p["rth"]),
            "c_j_per_k": float(p["cth"]),
            "tamb_c": float(p["tamb"]),
            "tmax_c": float(p["tmax"]),
        }
        if variant == "duty_cycle":
            params_out["n_min"] = n_min
        tasks.append({
            "id": task_id, "variant": variant, "difficulty": variant, "platform": platform,
            "params": params_out, "gold": gold,
            "tau_s": float(tau_s(p)), "gap_c": float(gap),
        })

    cross: dict[str, int] = {}
    for t in tasks:
        k = f"{t['variant']}|exceeds={'true' if t['gold']['exceeds_limit'] else 'false'}"
        cross[k] = cross.get(k, 0) + 1
    manifest = {
        "family": FAMILY,
        "generator": "bench/build_sim_thermal.py",
        "seed": SEED,
        "count": len(tasks),
        "package": PACKAGE,
        "scenario": "synthetic maritime ISR (USV, fixed-wing UAV, command ship, shore station); "
                    "heated object = USV below-deck electronics bay or UAV avionics bay; "
                    "dissipation = radio transmit amplifier + mission computer",
        "closed_form": {
            "step_response": "T(t) = Tamb + P*Rth*(1 - exp(-t/(Rth*Cth)))",
            "steady_state": "Tamb + P*Rth",
            "t95": "3*Rth*Cth (s); /60 for minutes",
            "peak_after_n_min": "Tamb + P*Rth*(1 - exp(-60*N/(Rth*Cth)))",
        },
        "tolerances": {"temperature_rel": 0.02, "time_abs_min": 2.0, "boolean": "exact"},
        "parameter_space": {
            "power_w": [10.0, 80.0, 0.5],
            "rth_k_per_w": [0.30, 2.00, 0.05],
            "c_j_per_k": [200, 2000, 50],
            "tamb_c": [15, 30, 1],
            "tmax_c": [45, 70, 1],
            "n_min": "duty_cycle only: integer in [max(2, 0.25*t95), 1.5*t95]",
        },
        "constraints": [
            "parameters deduplicated on (P, Rth, Cth, Tamb, Tmax) across the bank",
            "exceeds split exactly 75/75 within each variant",
            "|gold_temp - Tmax| >= 3 x (2% x gold_temp)",
            "t95_min >= 3 x 2 min = 6 min",
        ],
        "stats": {
            "count": len(tasks),
            "by_variant": {v: sum(1 for t in tasks if t["variant"] == v)
                           for v in ("steady_state", "duty_cycle")},
            "by_platform": {pf: sum(1 for t in tasks if t["platform"] == pf)
                            for pf in ("usv", "uav")},
            "by_platform_variant": {
                f"{pf}|{v}": sum(1 for t in tasks
                                 if t["platform"] == pf and t["variant"] == v)
                for pf in ("usv", "uav") for v in ("steady_state", "duty_cycle")},
            "cross": dict(sorted(cross.items())),
            "t95_min_range": [min(t["gold"]["t95_min"] for t in tasks),
                              max(t["gold"]["t95_min"] for t in tasks)],
            "gap_c_range": [min(t["gap_c"] for t in tasks), max(t["gap_c"] for t in tasks)],
        },
        "tasks": tasks,
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(tasks)} tasks in {OUT}")
    print(json.dumps(manifest["stats"], indent=2))


# --------------------------------------------------------------------------- check

def check() -> None:
    """Re-derive every gold with an independent float implementation and audit files."""
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    tasks = manifest["tasks"]
    problems: list[str] = []
    if len(tasks) != COUNT:
        problems.append(f"expected {COUNT} tasks, manifest has {len(tasks)}")
    used: set = set()
    for index, t in enumerate(tasks, start=1):
        tid = t["id"]
        if tid != f"THM-{index:04d}":
            problems.append(f"{tid}: id out of order")
        folder = OUT / tid
        for rel in ("case.yaml", "input/model.sysml", "input/requirements.md",
                    "gold/answer.json", "gold/assertions.yaml", "gold/solution.md"):
            if not (folder / rel).is_file():
                problems.append(f"{tid}: missing {rel}")
        if problems and problems[-1].startswith(f"{tid}: missing"):
            continue
        p = t["params"]
        P, R = float(p["power_w"]), float(p["rth_k_per_w"])
        C, tamb, tmax = float(p["c_j_per_k"]), float(p["tamb_c"]), float(p["tmax_c"])
        tau = R * C
        t95 = 3.0 * tau / 60.0
        ans = json.loads((folder / "gold" / "answer.json").read_text(encoding="utf-8"))
        case = yaml.safe_load((folder / "case.yaml").read_text(encoding="utf-8"))
        asserts = yaml.safe_load((folder / "gold" / "assertions.yaml").read_text(encoding="utf-8"))
        if case["id"] != tid or case["variant"] != t["variant"]:
            problems.append(f"{tid}: case.yaml mismatch")
        if case.get("platform") != t.get("platform") or asserts.get("platform") != t.get("platform"):
            problems.append(f"{tid}: platform mismatch")
        model = (folder / "input" / "model.sysml").read_text(encoding="utf-8")
        if f"part def {PLATFORMS[t['platform']]['bay_def']} " not in model:
            problems.append(f"{tid}: model bay definition does not match platform")
        if PLATFORMS["usv" if t["platform"] == "uav" else "uav"]["bay_def"] in model:
            problems.append(f"{tid}: model mentions the other platform's bay")
        if abs(ans["t95_min"] - t95) > 0.011:
            problems.append(f"{tid}: t95 {ans['t95_min']} vs recomputed {t95:.4f}")
        if t["variant"] == "steady_state":
            ref, key = tamb + P * R, "steady_state_c"
            if "n_min" in p:
                problems.append(f"{tid}: steady_state task carries n_min")
        else:
            ref, key = tamb + P * R * (1.0 - math.exp(-60.0 * p["n_min"] / tau)), "peak_temp_c"
        if abs(ans[key] - ref) > 0.011:
            problems.append(f"{tid}: {key} {ans[key]} vs recomputed {ref:.4f}")
        if ans["exceeds_limit"] != (ref > tmax):
            problems.append(f"{tid}: exceeds_limit mismatch")
        if abs(ans[key] - tmax) < 0.06 * ans[key] - 1e-9:
            problems.append(f"{tid}: margin rule violated")
        if ans["t95_min"] < 6.0:
            problems.append(f"{tid}: t95 below 6 min")
        sol = (folder / "gold" / "solution.md").read_text(encoding="utf-8")
        for value in (ans[key], ans["t95_min"]):
            fixed = f"{value:.2f}"
            stripped = fixed.rstrip("0").rstrip(".")
            if fixed not in sol and stripped not in sol:
                problems.append(f"{tid}: solution.md does not carry the gold numbers")
                break
        five = (p["power_w"], p["rth_k_per_w"], p["c_j_per_k"], p["tamb_c"], p["tmax_c"])
        if five in used:
            problems.append(f"{tid}: duplicate parameter tuple")
        used.add(five)
    for pf, want in PLATFORM_SHARE.items():
        got = sum(1 for t in tasks if t.get("platform") == pf)
        if got != want:
            problems.append(f"platform {pf}: expected {want}, manifest has {got}")
    if problems:
        for line in problems[:20]:
            print("FAIL", line)
        raise SystemExit(1)
    print(f"check ok: {len(tasks)} tasks, {len(used)} distinct parameter tuples")
    print(json.dumps(manifest["stats"], indent=2))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        check()
    else:
        build()
