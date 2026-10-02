#!/usr/bin/env python3
"""Integration checks of the real official parser, including documented limitations."""
import json
from pathlib import Path
import tempfile

from validate import ROOT, validate_package


def literal_for(result, qualified_name):
    items = [change["payload"] for change in json.loads(Path(result["model_json_path"]).read_text())]
    elements = {item["@id"]: item for item in items}
    attribute = next(item for item in items if item.get("qualifiedName") == qualified_name)
    binding = next(item for item in items if item.get("@type") == "FeatureValue"
                   and item["featureWithValue"]["@id"] == attribute["@id"])
    return elements[binding["value"]["@id"]]["value"]


def main():
    root = ROOT / "smoke-results"
    root.mkdir(exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix="integration-", dir=root))
    models = ROOT / "smoke-models"
    checks = []

    def run(name, package, files):
        result = validate_package([str(file) for file in files], package, str(output / name))
        checks.append({"case": name, "status": result["status"], "diagnostics": result["diagnostics"],
                       "wall_seconds": result["wall_seconds"], "validation": str(output / name / "validation.json")})
        return result

    valid = run("multi-file-forward-reference", "Smoke", [models / "valid.sysml", models / "types.sysml"])
    assert valid["status"] == "PASS" and literal_for(valid, "Smoke::gateway::dataRateMbps") == 18.0
    changed_source = output / "changed.sysml"
    changed_source.write_text((models / "valid.sysml").read_text().replace("18.0", "30.0"))
    changed = run("actual-source-value-change", "Smoke", [changed_source, models / "types.sysml"])
    assert changed["status"] == "PASS" and literal_for(changed, "Smoke::gateway::dataRateMbps") == 30.0

    bad_reference = run("missing-type", "Broken", [models / "invalid-reference.sysml"])
    assert bad_reference["status"] == "FAIL" and bad_reference["model_json_path"] is None
    assert any(d["line"] == 2 and d["code"].endswith("Diagnostic.Linking") for d in bad_reference["diagnostics"])
    bad_syntax = run("bad-syntax", "BrokenSyntax", [models / "invalid-syntax.sysml"])
    assert bad_syntax["status"] == "FAIL" and any(d["syntax_error"] for d in bad_syntax["diagnostics"])

    warning = run("type-mismatch-is-upstream-warning", "WrongValue", [models / "invalid-value-type.sysml"])
    assert warning["status"] == "PASS" and warning["warning_count"] > 0
    unit_cases = [("units-valid", "UnitsGood", "SI::watt"), ("units-invalid", "UnitsBad", "SI::metre")]
    for name, package, expected_referent in unit_cases:
        result = run(name, package, [models / (name + ".sysml")])
        assert result["status"] == "PASS"  # Official static checker does not reject this dimension error.
        ast = json.loads(Path(result["ast_json_path"]).read_text())
        referents = [item["references"]["referent"]["qualified_name"]
                     for item in ast if item["type"] == "FeatureReferenceExpression"]
        assert expected_referent in referents
        checks[-1]["resolved_units"] = referents
        checks[-1]["engineering_unit_contract"] = "PASS" if expected_referent == "SI::watt" else "FAIL"
        checks[-1]["contract_basis"] = "Test fixture expects PowerValue in SI::watt; not a general unit solver"

    (output / "summary.json").write_text(json.dumps(checks, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"checks_passed": len(checks), "summary": str(output / "summary.json")}, indent=2))


if __name__ == "__main__":
    main()
