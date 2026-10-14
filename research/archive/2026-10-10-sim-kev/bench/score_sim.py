"""Score one SIM answer against gold/assertions.yaml, for the seven families of the SIM bank
(sim_battery, sim_backlog, sim_thermal, sim_harvest, sim_latency, sim_storage, sim_uplink).

Pure code rules only, no model judges (decision 025). `status` is the task verdict and
`design_status` the design verdict, kept separate as in decision 019: an answer that
reports the numbers correctly passes the task even when the design itself misses its
requirement (battery below reserve, buffer overflow, temperature over the limit, harvest
reserve breached, stale chain, infeasible storage choice, a starved platform).

The task verdict is PASS when the answer is one JSON object whose top-level fields are
exactly the fields the assertions check, and every checked value sits inside the band the
assertions define:

- boolean fields are exact (a JSON true/false, not 1/0);
- a null gold is exact (overflow_at_min when the buffer never overflows, chosen_k when no
  storage ladder step fits, completion_time_min when no platform clears its buffer);
- numbers pass inside max(rel band, absolute band) of the yaml: the relative band is
  ±rel_tol/rel (2 %) of |gold|, the absolute bands are abs_tol_min/abs (±2 min on times),
  abs_tol_gb / abs_floor (the 0.05 GB floors of sim_backlog and sim_storage) and abs_tol
  (sim_latency's fresh_ratio ±0.02);
- sim_latency fresh_ratio is a ratio by definition: besides the band it must lie in [0, 1]
  (VALUE_RANGES), so a value like 1.01 is out even when the band would admit it;
- sim_storage is scored by variant: the retention variant checks retention_h, meets_target
  and headroom_gb; the choice variant checks chosen_k (an exact ladder step, or exactly
  null when infeasible), retention_h and feasible, with no headroom field — the expected
  schema follows each task's own assertions, so a headroom_gb in a choice answer is an
  extra field and a missing one in a retention answer is a missing field;
- sim_battery / sim_harvest key_points: exactly key_point_count entries, each t_min within
  ±2 min and each soc_pct within the relative band of the gold entry at the same point in
  time order (both sides are sorted by t_min before pairing); the entry field `mode` is
  part of the reply schema and of the gold answer but is not a checked value, so it is not
  scored.

A top-level `task_id` whose value equals the task's id is accepted as an identification
echo (gold/answer.json carries it; the reply schema does not ask for it). Any other
missing or extra field fails the whole task, and any value out of band fails the whole
task with the expected band echoed per field.

Two assertion layouts are in the bank and both are read, never re-written:
- `checks:` with per-field `{gold, rel_tol}` / `{gold, exact}` / `{gold, abs_tol_min}` /
  `{gold, rel_tol, abs_tol_gb}` (sim_battery, sim_backlog, sim_harvest, sim_latency,
  sim_storage, sim_uplink; sim_storage adds margin_rule/formula, which are not scored);
- `tolerance:` mapping each field to `{type: float, rel}` / `{type: float, abs, unit}` /
  `{type: bool, exact}` (sim_thermal); the gold values come from gold/answer.json.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.llm import extract_json  # noqa: E402

# family -> (design criterion field, the gold value that means the design meets its requirement).
# sim_storage picks its field by the assertions' variant (retention / choice); sim_uplink fails its
# design requirement when any listed starved flag is true.
DESIGN_CRITERIA = {
    "sim_battery": ("meets_reserve", True),
    "sim_backlog": ("overflows", False),
    "sim_thermal": ("exceeds_limit", False),
    "sim_harvest": ("breached", False),
    "sim_latency": ("meets_staleness", True),
    "sim_storage": {"retention": ("meets_target", True), "choice": ("feasible", True)},
    "sim_uplink": (("starved_usv", "starved_uav"), False),
}
# Fields that are a ratio by definition: inside the tolerance band is not enough, the value itself
# must stay a ratio (fresh_ratio is a fraction of messages; the yaml band alone would admit 1.02).
VALUE_RANGES = {"sim_latency:fresh_ratio": (0.0, 1.0)}
EPS = 1e-9


def _load(task_dir: Path) -> tuple[dict, dict, dict]:
    assertions = yaml.safe_load((task_dir / "gold" / "assertions.yaml").read_text(encoding="utf-8"))
    gold = json.loads((task_dir / "gold" / "answer.json").read_text(encoding="utf-8"))
    case = yaml.safe_load((task_dir / "case.yaml").read_text(encoding="utf-8"))
    return case, assertions, gold


def _family(assertions: dict, task_dir: Path) -> str:
    name = str(assertions.get("family") or "")
    return name.split("/")[-1] or task_dir.parent.name


def _number(value) -> float | None:
    """A JSON number (bool is not a number here); None for anything else, strings included."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _row(field: str, gold, got, band: str, ok: bool, note: str = "") -> dict:
    row = {"field": field, "gold": gold, "got": got, "band": band, "ok": ok}
    if note:
        row["note"] = note
    return row


def _scalar_field_row(name: str, spec: dict, gold, got, defaults: dict, value_range=None) -> dict:
    """One non-list field against its assertion spec. `gold` comes from the spec or from gold/answer.json."""
    if spec.get("type") == "bool" or isinstance(gold, bool) or spec.get("exact") is True:
        if gold is None:
            return _row(name, None, got, "exactly null", got is None,
                        "" if got is None else "expected null")
        if isinstance(gold, bool):
            return _row(name, gold, got, f"exactly {str(gold).lower()}",
                        isinstance(got, bool) and got == gold,
                        "a JSON boolean" if isinstance(got, bool) else "expected a JSON boolean, not 1/0 or a string")
        return _row(name, gold, got, f"exactly {gold!r}", got == gold)
    if gold is None:
        return _row(name, None, got, "exactly null", got is None, "expected null")
    number = _number(got)
    limits, parts = [], []
    rel = spec.get("rel_tol", spec.get("rel"))
    abs_time = spec.get("abs_tol_min", spec.get("abs"))
    floor = spec.get("abs_tol_gb")
    abs_plain = spec.get("abs_tol", spec.get("abs_floor"))  # LAT fresh_ratio ±0.02; CMP headroom ±0.05 GB floor
    if rel is None and abs_time is None and floor is None and abs_plain is None:
        # a bare spec (no band of its own): the family defaults are the fallback
        rel, abs_time, floor = defaults.get("rel"), defaults.get("abs_min"), defaults.get("abs_floor_gb")
    if rel is not None:
        limits.append(abs(rel) * abs(gold))
        parts.append(f"±{rel:.0%} of {gold:g}")
    if abs_time is not None:
        limits.append(abs(abs_time))
        unit = spec.get("unit") or ("min" if spec.get("abs_tol_min") is not None else "")
        parts.append(f"±{abs_time:g}{(' ' + unit) if unit else ''}")
    if floor is not None:
        limits.append(abs(floor))
        parts.append(f"±{floor:g} GB")
    if abs_plain is not None:
        limits.append(abs(abs_plain))
        parts.append(f"±{abs_plain:g}" + (" GB" if spec.get("abs_floor") is not None else ""))
    if not limits:
        return _row(name, gold, got, f"exactly {gold!r}", got == gold)
    tol = max(limits)
    band = f"{gold - tol:g} … {gold + tol:g} ({' or '.join(parts)})"
    if value_range is not None:
        band += f", and within [{value_range[0]:g}, {value_range[1]:g}]"
    if number is None:
        return _row(name, gold, got, band, False, "expected a number")
    ok = abs(number - gold) <= tol + EPS * max(1.0, abs(gold))
    if ok and value_range is not None:
        ok = value_range[0] <= number <= value_range[1]
    return _row(name, gold, got, band, ok)


def _key_point_rows(name: str, spec: list[dict], gold_answer: dict, got, defaults: dict) -> list[dict]:
    """sim_battery key_points: count exact, then t_min/soc_pct per entry paired in time order."""
    rows = []
    gold_list = gold_answer.get(name) or []
    wanted = len(gold_list)
    if not isinstance(got, list):
        return [_row(f"{name}", wanted, type(got).__name__, f"exactly {wanted} entries", False, "expected a JSON list")]
    rows.append(_row(f"{name}.count", wanted, len(got), f"exactly {wanted} entries", len(got) == wanted))
    rel_default = defaults.get("rel")
    time_default = defaults.get("abs_min")

    def sort_key(pair):
        index, entry = pair
        value = _number(entry.get("t_min")) if isinstance(entry, dict) else None
        return (value is None, value if value is not None else float(index), index)

    gold_sorted = [entry for _, entry in sorted(enumerate(gold_list), key=sort_key)]
    got_sorted = [entry for _, entry in sorted(enumerate(got), key=sort_key)]
    for index, (gold_entry, gold_spec) in enumerate(zip(gold_sorted, spec)):
        if index >= len(got_sorted):
            break
        got_entry = got_sorted[index]
        label = f"{name}[{index}]"
        if not isinstance(got_entry, dict):
            tol = gold_spec["t_min"].get("abs_tol_min", time_default) or 0
            rows.append(_row(f"{label}.t_min", gold_entry.get("t_min"), got_entry,
                             f"{gold_entry.get('t_min') - tol:g} … {gold_entry.get('t_min') + tol:g} (±{tol:g} min)",
                             False, "expected a JSON object"))
            continue
        for key, default_abs, default_rel in (("t_min", time_default, None), ("soc_pct", None, rel_default)):
            inner = gold_spec.get(key) or {}
            gold_value = inner.get("gold", gold_entry.get(key))
            row = _scalar_field_row(f"{label}.{key}", {**inner, "abs_tol_min": inner.get("abs_tol_min", default_abs),
                                                       "rel_tol": inner.get("rel_tol", default_rel)},
                                    gold_value, got_entry.get(key),
                                    {"rel": default_rel, "abs_min": default_abs, "abs_floor_gb": None})
            rows.append(row)
    return rows


def score_sim(task_dir: Path, answer) -> dict:
    """Score one SIM answer. `answer` is the parsed JSON object, or the model's text (extract_json is used)."""
    case, assertions, gold_answer = _load(task_dir)
    family = _family(assertions, Path(task_dir))
    task_id = case.get("id") or assertions.get("task_id") or Path(task_dir).name
    result = {"task_id": task_id, "family": family, "type": "SIM",
              "expected": gold_answer, "design": design_verdict(family, assertions, gold_answer)}
    result["design_status"] = "FAIL" if result["design"] and not result["design"]["meets_requirement"] else (
        "PASS" if result["design"] else "UNKNOWN")

    if isinstance(answer, str):
        try:
            got = extract_json(answer)
        except (ValueError, json.JSONDecodeError) as exc:
            result.update({"status": "FAIL", "reason": str(exc), "checks": [], "failed": [],
                           "missing_fields": [], "extra_fields": []})
            return result
    else:
        got = answer

    tols = assertions.get("tolerances") or assertions.get("tolerance") or {}
    defaults = {"rel": tols.get("soc_rel", tols.get("numeric_rel")),
                "abs_min": tols.get("time_abs_min"), "abs_floor_gb": tols.get("abs_floor_gb")}
    fields, list_check = _expected_fields(assertions)
    expected = set(fields) | ({list_check[0]} if list_check else set())
    if not isinstance(got, dict):
        result.update({"status": "FAIL", "reason": "the answer is not a JSON object",
                       "checks": [], "failed": [], "missing_fields": sorted(expected), "extra_fields": [],
                       "actual": got})
        return result
    allowed = set(expected)
    if got.get("task_id") == task_id:  # identification echo, present in gold/answer.json
        allowed.add("task_id")
    missing = sorted(expected - set(got))
    extra = sorted(set(got) - allowed)

    rows = []
    for name in sorted(fields):
        spec = fields[name]
        gold = spec.get("gold", gold_answer.get(name))
        rows.append(_scalar_field_row(name, spec, gold, got.get(name), defaults,
                                      VALUE_RANGES.get(f"{family}:{name}")))
    if list_check:
        rows.extend(_key_point_rows(list_check[0], list_check[1], gold_answer, got.get(list_check[0]), defaults))

    failed = [row["field"] for row in rows if not row["ok"]]
    problems = []
    if missing:
        problems.append("missing fields: " + ", ".join(missing))
    if extra:
        problems.append("extra fields: " + ", ".join(extra))
    for row in rows:
        if not row["ok"]:
            problems.append(f"{row['field']}: got {row['got']!r}, band {row['band']}")
    result.update({"status": "PASS" if not failed and not missing and not extra else "FAIL",
                   "checks": rows, "failed": failed,
                   "missing_fields": missing, "extra_fields": extra,
                   "actual": got, "reason": "; ".join(problems) if problems else "all checked values in band"})
    return result


def design_verdict(family: str, assertions: dict, gold_answer: dict) -> dict | None:
    """The design verdict of the gold itself (decision 019): does the design meet its requirement.

    sim_storage reads its criterion from the assertions' variant; sim_uplink reports any starved
    platform as one criterion. The value always comes from the gold (the checks spec first, then
    gold/answer.json), never from the answer: a correct answer to a starving schedule passes the
    task and fails the design.
    """
    criterion = DESIGN_CRITERIA.get(family)
    if not criterion:
        return None
    if isinstance(criterion, dict):  # variant-aware
        criterion = criterion.get(assertions.get("variant"))
        if not criterion:
            return None
    fields, meets_when = criterion
    labels = [fields] if isinstance(fields, str) else list(fields)
    checks = assertions.get("checks") or {}

    def gold_of(field):
        value = (checks.get(field) or {}).get("gold") if isinstance(checks.get(field), dict) else None
        return value if value is not None else gold_answer.get(field)

    values = [value for value in (gold_of(field) for field in labels) if isinstance(value, bool)]
    if not values:
        return None
    if len(labels) == 1:
        value, label = values[0], labels[0]
    else:
        value, label = any(values), "|".join(labels)
    return {"criterion": label, "gold": value, "meets_requirement": value == meets_when,
            "meets_when": meets_when}


def _expected_fields(assertions: dict) -> tuple[dict, tuple | None]:
    """Scalar checked fields and the (name, spec) of the key_points-style list check, if any."""
    if "checks" in assertions:
        fields, list_check = {}, None
        for name, spec in assertions["checks"].items():
            if isinstance(spec, list):
                list_check = (name, spec)
            elif name != "key_point_count":  # a derived count, checked with the list itself
                fields[name] = spec
        return fields, list_check
    return dict(assertions.get("tolerance") or {}), None


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task_dir", type=Path, help="a SIM task directory under bench/tasks_staging/t_sim_bank")
    parser.add_argument("answer", type=str, help="path to a JSON answer file, the literal text, or - for stdin")
    args = parser.parse_args()
    text = sys.stdin.read() if args.answer == "-" else (
        Path(args.answer).read_text(encoding="utf-8") if Path(args.answer).is_file() else args.answer)
    print(json.dumps(score_sim(args.task_dir, text), ensure_ascii=False, indent=2))
