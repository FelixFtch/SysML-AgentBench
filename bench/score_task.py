"""Score one submitted SysML run against a task's gold/assertions.yaml.

The checklist is the ground truth. The official parser export is the only model
read. When the checklist names an engineering check, that check's PASS or FAIL
is the engineering result.

`status` is the task verdict: every required name and connection is present, no
number was invented, every value the task said to keep is unchanged, and every
engineering check came out the way the checklist expects. `engineering_status`
is the design verdict on its own.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mvp.engine import ModelView, exported_elements  # noqa: E402


def _path(name: str) -> str:
    body = name.split("::", 1)[-1]
    return body.replace("::", ".")


def _load_assertions(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
        return yaml.safe_load(text)
    except Exception:
        # The committed checklist is a small fixed shape. A dependency-free
        # fallback keeps scoring runnable with the standard library.
        return _tiny_yaml(text)


def _tiny_yaml(text: str) -> dict:
    data = {"must_exist": [], "must_connect": [], "must_not_add": []}
    section = None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not line.startswith(" ") and line.endswith(":"):
            section = line[:-1].strip()
            if section not in data:
                data[section] = []
            continue
        stripped = line.strip()
        if section == "must_exist" and stripped.startswith("- "):
            item = {}
            body = stripped[2:].strip("{} ")
            for part in body.split(","):
                if ":" not in part:
                    continue
                key, value = part.split(":", 1)
                item[key.strip()] = value.strip()
            if item:
                data["must_exist"].append(item)
        elif section == "must_connect" and stripped.startswith("- ["):
            pair = [piece.strip() for piece in stripped[2:].strip("[]").split(",")]
            data["must_connect"].append(pair)
        elif section == "must_not_add" and stripped.startswith("- "):
            data["must_not_add"].append(stripped[2:].strip())
    return data


def score_run(run_dir: Path, assertions_path: Path) -> dict:
    assertions = _load_assertions(assertions_path)
    sysml = run_dir / "sysml"
    validation = json.loads((sysml / "validation.json").read_text(encoding="utf-8"))
    if validation.get("status") != "PASS" or not (sysml / "model.json").is_file():
        return {"run_dir": str(run_dir), "sysml_status": validation.get("status"),
                "engineering_status": "FAIL", "status": "FAIL",
                "reason": "Official validation did not pass, so the checklist was not applied.",
                "structure_pass": False, "checks_match": False, "pass": False}
    elements = exported_elements(json.loads((sysml / "model.json").read_text(encoding="utf-8")))
    ast = json.loads((sysml / "ast-elements.json").read_text(encoding="utf-8"))
    view = ModelView(elements, ast)
    names = {element.get("qualifiedName") for element in elements if element.get("qualifiedName")}
    present = []
    missing = []
    for item in assertions.get("must_exist") or []:
        wanted = item["qualified_name"]
        (present if wanted in names else missing).append(wanted)
    ends = set()
    for element in elements:
        if element.get("@type") != "ConnectionUsage":
            continue
        pair = tuple(sorted(_path(view.reference_name(ref["@id"]) or "") for ref in element.get("relatedFeature") or []))
        if all(pair):
            ends.add(pair)
    connected = []
    disconnected = []
    for left, right in assertions.get("must_connect") or []:
        pair = tuple(sorted((_path(left), _path(right))))
        (connected if pair in ends else disconnected).append(list(pair))
    numeric = []
    for element in elements:
        if element.get("@type") != "AttributeUsage":
            continue
        link = view.value_links.get(element["@id"])
        if not link:
            continue
        value = view.by_id.get((link.get("value") or {}).get("@id"), {})
        if value.get("@type") in {"LiteralInteger", "LiteralRational"}:
            numeric.append({"name": element.get("qualifiedName"), "value": value.get("value")})
    invented = numeric if assertions.get("must_not_add") else []
    structure_pass = not missing and not disconnected and not invented
    preserved = []
    preserve_misses = []
    by_name = {item["name"]: float(item["value"]) for item in numeric}
    for item in assertions.get("must_preserve") or []:
        wanted = item["qualified_name"]
        actual = by_name.get(wanted)
        ok = actual is not None and actual == float(item["value"])
        (preserved if ok else preserve_misses).append({"qualified_name": wanted, "expected": item["value"], "actual": actual})
    checks = []
    engineering = "UNKNOWN"
    if assertions.get("checks_expected"):
        from bench.power_check import budget
        measured = budget(run_dir)
        engineering = measured["budget_status"]
        for expected in assertions["checks_expected"]:
            checks.append({
                "id": expected["id"],
                "expected": expected["status"],
                "actual": measured["budget_status"],
                "match": measured["budget_status"] == expected["status"],
                "total_w": measured.get("total_w"),
                "limit_w": measured.get("limit_w"),
                "draws_w": measured.get("draws_w"),
            })
    checks_match = all(item["match"] for item in checks) if checks else None
    if checks and engineering == "UNKNOWN":
        status = "UNKNOWN"
    else:
        status = "PASS" if structure_pass and not preserve_misses and checks_match is not False else "FAIL"
    result = {
        "run_dir": str(run_dir),
        "sysml_status": json.loads((sysml / "validation.json").read_text(encoding="utf-8")).get("status"),
        "engineering_status": engineering if checks else "UNKNOWN",
        "status": status,
        "must_exist": {"hit": len(present), "expected": len(present) + len(missing), "missing": missing},
        "must_connect": {"hit": len(connected), "expected": len(connected) + len(disconnected), "missing": disconnected},
        "must_preserve": {"hit": len(preserved), "expected": len(preserved) + len(preserve_misses), "missing": preserve_misses},
        "checks": checks,
        "checks_match": checks_match,
        "invented_numbers": invented,
        "structure_pass": structure_pass and not preserve_misses,
        "pass": status == "PASS",
    }
    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("assertions", type=Path)
    args = parser.parse_args()
    print(json.dumps(score_run(args.run_dir, args.assertions), ensure_ascii=False, indent=2))
