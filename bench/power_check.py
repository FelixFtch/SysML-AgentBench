"""Read power numbers from the official parse and compare their sum with the limit.

If the official validation did not pass, or the limit and both draws are absent,
the budget status is UNKNOWN. When those numbers are present, the comparison is
PASS or FAIL.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mvp.engine import ModelView, exported_elements  # noqa: E402


def budget(run_dir: Path) -> dict:
    sysml = run_dir / "sysml"
    validation = json.loads((sysml / "validation.json").read_text(encoding="utf-8"))
    if validation.get("status") != "PASS":
        return {"sysml_status": validation.get("status"), "budget_status": "UNKNOWN",
                "reason": "Official validation did not pass, so the numbers were not read."}
    elements = exported_elements(json.loads((sysml / "model.json").read_text(encoding="utf-8")))
    view = ModelView(elements, json.loads((sysml / "ast-elements.json").read_text(encoding="utf-8")))
    found = {}
    for element in elements:
        name = element.get("qualifiedName") or ""
        if element.get("@type") != "AttributeUsage":
            continue
        link = view.value_links.get(element["@id"])
        if not link:
            continue
        value = view.by_id.get((link.get("value") or {}).get("@id"), {})
        if value.get("@type") not in {"LiteralInteger", "LiteralRational"}:
            continue
        found[name] = float(value["value"])
    limits = {key: val for key, val in found.items() if key.endswith("::powerLimitW")}
    draws = {key: val for key, val in found.items() if key.endswith("::drawW")}
    if len(limits) != 1 or len(draws) < 2:
        return {"sysml_status": "PASS", "budget_status": "UNKNOWN",
                "reason": "The parsed model does not contain the limit and both draw attributes.",
                "found": found}
    limit = next(iter(limits.values()))
    total = sum(draws.values())
    status = "PASS" if total <= limit else "FAIL"
    return {"sysml_status": "PASS", "budget_status": status, "total_w": total, "limit_w": limit,
            "draws_w": draws, "numbers": found,
            "reason": "The summed draw exceeds the limit in the parsed model." if status == "FAIL"
            else "The summed draw is within the limit written in the model."}


if __name__ == "__main__":
    print(json.dumps(budget(Path(sys.argv[1])), ensure_ascii=False, indent=2))
