"""Second review of the 27 held-out answer keys: mechanical checks, one line per task.

What is checked, without calling a model:
- GEN / MOD / ALN: the reference passes the official Pilot and its own key (bench/validate_gold.py does this;
  here it is rerun), and every short name the key requires is written in the task statement or the baseline,
  so the key never asks for something the candidate was not told.
- MOD: every value the key says to keep is literally in the baseline file.
- QRY: the gold answer is recomputed from the official parse of the given model and compared with gold/answer.json.
- AMB: every should-ask group has at least one word that is not already answered in the statement.
- RT: every must-mention phrase is in the requirement text of the given model (normalised as the scorer normalises).
The reading of each statement against its key is recorded separately in bench/tasks/t4_maritime_isr/heldout/REVIEW.md.
Output: analysis/gold-review-<stamp>.json. Exit code 1 if any mechanical check fails.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bench.graph_query import maritime_parse  # noqa: E402
from bench.score_alignment import score_alignment  # noqa: E402
from bench.score_answer import normalise  # noqa: E402
from bench.score_task import score_run  # noqa: E402
from mvp.engine import ModelView, exported_elements, run_submitted_model  # noqa: E402

HELD = ROOT / "bench" / "tasks" / "t4_maritime_isr" / "heldout"


def text_of(task: Path) -> str:
    parts = [(task / "input" / "requirements.md").read_text(encoding="utf-8")]
    for path in sorted((task / "input").rglob("*.sysml")):
        parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def check_model_task(task: Path, case: dict) -> dict:
    gold = yaml.safe_load((task / "gold" / "assertions.yaml").read_text(encoding="utf-8"))
    reference = next((task / "gold" / "reference").glob("*.sysml"))
    validated = run_submitted_model([reference], case["package"], label=f"review-{case['id']}")
    scored = score_run(Path(validated["run_dir"]), task / "gold" / "assertions.yaml")
    shown = text_of(task)
    unstated = [item["qualified_name"] for item in gold.get("must_exist") or []
                if item["qualified_name"].split("::")[-1] not in shown]
    for pair in gold.get("must_connect") or []:
        for end in pair:
            if end.split("::")[-1] not in shown:
                unstated.append(end)
    # A kept value must be given to the candidate: in the baseline (MOD) or in the statement (GEN, and MOD-05's added camera).
    kept_missing = [item for item in gold.get("must_preserve") or []
                    if "value" in item and f"{float(item['value']):g}" not in shown and str(item["value"]) not in shown]
    ok = validated["sysml"]["status"] == "PASS" and scored["status"] == "PASS" and not unstated and not kept_missing
    if case["id"] == "MOD-05":
        ok = ok and scored.get("checks_match") and scored.get("engineering_status") == "FAIL"
    return {"ok": ok, "reference_pilot": validated["sysml"]["status"], "reference_task_verdict": scored["status"],
            "names_not_in_statement": unstated, "kept_values_not_in_baseline": kept_missing,
            "engineering": scored.get("engineering_status")}


def check_alignment_task(task: Path, case: dict) -> dict:
    sources = [task / "input" / "baseline" / name for name in case["sources"]]
    reference = task / "gold" / "reference" / f"{case['package']}.sysml"
    validated = run_submitted_model(sources + [reference], case["package"], label=f"review-{case['id']}")
    report = (task / "gold" / "reference" / "report.json").read_text(encoding="utf-8")
    scored = score_alignment(Path(validated["run_dir"]), task / "gold" / "assertions.yaml", "```json\n" + report + "\n```",
                             sysml_status=validated["sysml"]["status"])
    gold = yaml.safe_load((task / "gold" / "assertions.yaml").read_text(encoding="utf-8"))
    shown = "\n".join(path.read_text(encoding="utf-8") for path in sources)
    unstated = []
    for item in gold.get("must_map") or []:
        for name in (item.get("name"), item.get("target"), item.get("from"), item.get("to")):
            if name and re.split(r"::|\.", name)[-1] not in shown:
                unstated.append(name)
    return {"ok": validated["sysml"]["status"] == "PASS" and scored["status"] == "PASS" and not unstated,
            "reference_pilot": validated["sysml"]["status"], "reference_task_verdict": scored["status"],
            "names_not_in_sources": unstated, "must_map": scored["must_map"]["expected"]}


def check_query_task(task: Path, case: dict) -> dict:
    gold = json.loads((task / "gold" / "answer.json").read_text(encoding="utf-8"))
    parse = maritime_parse()
    elements = exported_elements(json.loads((parse / "sysml" / "model.json").read_text(encoding="utf-8")))
    ast = json.loads((parse / "sysml" / "ast-elements.json").read_text(encoding="utf-8"))
    view = ModelView(elements, ast)
    by_id = {e["@id"]: e for e in elements}

    def owner_name(e):
        return by_id.get((e.get("owner") or {}).get("@id") or "", {}).get("qualifiedName")

    computed = None
    if case["id"] == "QRY-01":
        computed = {"platforms": sorted(e["qualifiedName"] for e in elements if e.get("@type") == "PartUsage" and owner_name(e) == "MaritimeISR")}
    elif case["id"] == "QRY-02":
        computed = {"attribute": "MaritimeISR::UnmannedSurfaceVessel::powerLimitW", "value": view.literal_at("MaritimeISR::UnmannedSurfaceVessel::powerLimitW")}
    elif case["id"] == "QRY-03":
        count = 0
        for e in elements:
            if e.get("@type") == "ConnectionUsage":
                ends = [view.reference_name(ref["@id"]) or "" for ref in e.get("relatedFeature") or []]
                if any(end.startswith("MaritimeISR::commandShip") for end in ends):
                    count += 1
        computed = {"connections": count}
    elif case["id"] == "QRY-04":
        computed = {"parts": sorted(e["qualifiedName"] for e in elements if e.get("@type") == "PartUsage" and owner_name(e) == "MaritimeISR::FixedWingUav")}
    elif case["id"] == "QRY-05":
        computed = {key: view.literal_at(f"MaritimeISR::UnmannedSurfaceVessel::{key}") for key in ("powerLimitW", "uplinkMbps", "storageGB")}

    def canon(value):
        if isinstance(value, dict):
            return {k: canon(value[k]) for k in sorted(value)}
        if isinstance(value, list):
            return sorted(canon(v) for v in value)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        return value
    return {"ok": canon(computed) == canon(gold), "computed": computed, "gold": gold}


def check_ambiguity_task(task: Path, case: dict) -> dict:
    gold = yaml.safe_load((task / "gold" / "assertions.yaml").read_text(encoding="utf-8"))
    statement = (task / "input" / "requirements.md").read_text(encoding="utf-8").lower()
    groups = gold.get("should_ask") or []
    # A group is already answered if the statement quantifies every one of its words (then there is nothing to ask).
    # AMB-04 quantifies "MHz" on purpose: the unit is in conflict, and "unit" itself is not quantified.
    answered = []
    for group in groups:
        quantified = [word for word in group if re.search(r"\d+(\.\d+)?\s*" + re.escape(word.lower()), statement)]
        if quantified and len(quantified) == len(group):
            answered.extend(quantified)
    return {"ok": bool(groups) and not answered, "groups": len(groups), "words_already_quantified_in_statement": answered,
            "must_not_invent_number": bool(gold.get("must_not_invent_number"))}


def check_roundtrip_task(task: Path, case: dict) -> dict:
    gold = yaml.safe_load((task / "gold" / "assertions.yaml").read_text(encoding="utf-8"))
    model = (task / "input" / "model.sysml").read_text(encoding="utf-8") if (task / "input" / "model.sysml").is_file() else text_of(task)
    docs = " ".join(re.findall(r"doc\s*/\*(.*?)\*/", model, flags=re.S))
    missing = [phrase for phrase in gold["must_mention"] if normalise(phrase) not in normalise(docs)]
    return {"ok": not missing, "phrases": gold["must_mention"], "phrases_not_in_requirement_text": missing}


def main() -> None:
    rows = []
    for line in (HELD / "index.jsonl").read_text(encoding="utf-8").splitlines():
        item = json.loads(line)
        task = HELD / item["id"]
        case = yaml.safe_load((task / "case.yaml").read_text(encoding="utf-8"))
        kind = case["type"]
        check = {"GEN": check_model_task, "MOD": check_model_task, "ALN": check_alignment_task, "QRY": check_query_task,
                 "AMB": check_ambiguity_task, "RT": check_roundtrip_task}[kind](task, case)
        rows.append({"id": item["id"], "type": kind, **check})
        detail = {k: v for k, v in check.items() if k != "ok" and v not in ([], None, "", False)}
        print(f"{item['id']:7} {kind:3} {'ok' if check['ok'] else 'CHECK'}  {json.dumps(detail, ensure_ascii=False)[:150]}", flush=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    out = ROOT / "analysis" / f"gold-review-{stamp}.json"
    out.write_text(json.dumps({"id": stamp, "tasks": rows, "all_ok": all(r["ok"] for r in rows)}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{sum(r['ok'] for r in rows)}/{len(rows)} tasks pass the mechanical checks -> {out}")
    if not all(r["ok"] for r in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
