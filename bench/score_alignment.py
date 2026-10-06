"""Score one alignment package (task type ALN, paper 1) against gold/assertions.yaml.

Only the official Pilot's export is read for the package: aliases are `Membership` elements owned
by the package (member name → the element they refer to), allocations are `AllocationUsage`
elements whose ends resolve to usage paths. The JSON report in the answer text is read only for
the unmatched list.

Task verdict PASS when, together:
- the official parse of sources + package passes (names resolve);
- every `must_map` pair is declared with the right construct (alias or allocation);
- no `must_not_map` pair is declared;
- the package declares nothing but imports, aliases and allocations (sources are not rewritten);
- every `must_report_unmatched` element appears in the report's unmatched list.
Precision and recall over the declared pairs are reported alongside.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mvp.engine import ModelView, exported_elements  # noqa: E402

DECLARATION_TYPES = {"PartDefinition", "PortDefinition", "AttributeDefinition", "InterfaceDefinition", "ItemDefinition",
                     "ActionDefinition", "RequirementDefinition", "ConnectionDefinition", "PartUsage", "PortUsage",
                     "AttributeUsage", "InterfaceUsage", "ConnectionUsage", "RequirementUsage", "ItemUsage", "ActionUsage",
                     "Package"}


def declared(run_dir: Path, package: str) -> dict:
    """Aliases, allocations and stray declarations owned by `package` in one official parse."""
    sysml = run_dir / "sysml"
    elements = exported_elements(json.loads((sysml / "model.json").read_text(encoding="utf-8")))
    ast = json.loads((sysml / "ast-elements.json").read_text(encoding="utf-8"))
    view = ModelView(elements, ast)
    by_id = {element["@id"]: element for element in elements}

    def name_of(ref) -> str | None:
        return by_id.get((ref or {}).get("@id") or "", {}).get("qualifiedName")

    aliases: list[dict] = []
    allocations: list[dict] = []
    stray: list[str] = []
    for element in elements:
        kind = element.get("@type")
        if kind == "Membership" and element.get("memberName") and name_of(element.get("membershipOwningNamespace")) == package:
            aliases.append({"name": element["memberName"], "target": name_of(element.get("memberElement"))})
        elif kind == "AllocationUsage" and name_of(element.get("owner")) == package:
            ends = [view.reference_name(ref["@id"]) or "" for ref in element.get("relatedFeature") or []]
            if len(ends) >= 2:
                allocations.append({"name": element.get("declaredName"), "from": ends[0], "to": ends[1]})
        elif kind in DECLARATION_TYPES and name_of(element.get("owner")) == package:
            stray.append(f"{kind} {element.get('qualifiedName') or element.get('declaredName') or '?'}")
    return {"aliases": aliases, "allocations": allocations, "stray": stray}


def report_from(text: str) -> dict:
    """The JSON object in the answer's json block (or, failing that, the last balanced object), or {}."""
    candidates = re.findall(r"```json\s*\n(.*?)```", text or "", flags=re.S)
    candidates += re.findall(r"```\s*\n(\{.*?)```", text or "", flags=re.S)
    for block in candidates:
        try:
            data = json.loads(block.strip())
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    # Fallback: the last brace-balanced object anywhere in the text.
    body = text or ""
    for start in [match.start() for match in re.finditer(r"\{", body)][::-1]:
        depth = 0
        for index in range(start, len(body)):
            if body[index] == "{":
                depth += 1
            elif body[index] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        data = json.loads(body[start:index + 1])
                    except json.JSONDecodeError:
                        break
                    if isinstance(data, dict) and ("mappings" in data or "unmatched" in data):
                        return data
                    break
    return {}


def _pair_key(item: dict) -> tuple:
    if item.get("kind", "alias") == "alias":
        return ("alias", item["name"], item["target"])
    return ("allocation", frozenset((item["from"], item["to"])))


def score_alignment(run_dir: Path | None, assertions_path: Path, answer_text: str, *, sysml_status: str | None) -> dict:
    gold = yaml.safe_load(assertions_path.read_text(encoding="utf-8"))
    package = gold["package"]
    result: dict = {"status": "FAIL", "sysml_status": sysml_status, "engineering_status": "NOT_APPLICABLE", "package": package}
    if sysml_status != "PASS" or not run_dir:
        result["reason"] = "The official parse of the sources plus the alignment package did not pass."
        result.update({"must_map": {"hit": 0, "expected": len(gold.get("must_map") or []), "missing": gold.get("must_map") or []},
                       "must_not_map": {"violations": []}, "stray_declarations": [], "unmatched": {"hit": 0, "expected": len(gold.get("must_report_unmatched") or []), "missing": gold.get("must_report_unmatched") or []},
                       "declared": {"aliases": [], "allocations": []}, "precision": None, "recall": None})
        return result
    found = declared(Path(run_dir), package)
    declared_keys = {("alias", a["name"], a["target"]) for a in found["aliases"]} | {("allocation", frozenset((a["from"], a["to"]))) for a in found["allocations"]}
    wanted = gold.get("must_map") or []
    wanted_keys = {_pair_key(item) for item in wanted}
    missing = [item for item in wanted if _pair_key(item) not in declared_keys]
    violations = [item for item in (gold.get("must_not_map") or []) if _pair_key(item) in declared_keys]
    report = report_from(answer_text)
    unmatched_reported = [str(item) for item in (report.get("unmatched") or []) if isinstance(item, (str, int, float))]

    def reported(name: str) -> bool:
        short = name.split("::")[-1]
        return any(entry == name or entry.endswith("::" + short) or entry.endswith("." + short) or entry == short for entry in unmatched_reported)

    unmatched_wanted = gold.get("must_report_unmatched") or []
    unmatched_missing = [name for name in unmatched_wanted if not reported(name)]
    hits = len(wanted) - len(missing)
    precision = round(hits / len(declared_keys), 3) if declared_keys else None
    recall = round(hits / len(wanted), 3) if wanted else None
    reasons = []
    if missing:
        reasons.append(f"{len(missing)} required mapping(s) not declared")
    if violations:
        reasons.append(f"{len(violations)} forbidden mapping(s) declared")
    if found["stray"]:
        reasons.append("the package declares elements of its own")
    if unmatched_missing:
        reasons.append(f"{len(unmatched_missing)} unmatched element(s) not reported")
    result.update({
        "status": "PASS" if not reasons else "FAIL",
        "reason": "; ".join(reasons) if reasons else "Every required pair is declared, no forbidden pair, sources untouched, unmatched elements reported.",
        "must_map": {"hit": hits, "expected": len(wanted), "missing": missing},
        "must_not_map": {"violations": violations},
        "stray_declarations": found["stray"],
        "unmatched": {"hit": len(unmatched_wanted) - len(unmatched_missing), "expected": len(unmatched_wanted), "missing": unmatched_missing,
                      "reported": unmatched_reported},
        "declared": {"aliases": found["aliases"], "allocations": found["allocations"]},
        "report_mappings": len(report.get("mappings") or []) if isinstance(report, dict) else 0,
        "precision": precision, "recall": recall,
    })
    return result
