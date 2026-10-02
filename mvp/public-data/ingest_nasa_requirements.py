#!/usr/bin/env python3
"""Create traceable candidate requirement records from the preserved NASA cFE CSV.

Blank-ID CSV records are continuations of the preceding identified requirement.
All original row fields and physical line ranges are retained for human review.
No engineering numbers, satisfaction relationships or gold SysML models are inferred.
"""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = ROOT / "nasa-cfe"
SOURCE = SOURCE_ROOT / "upstream/docs/cFE_FunctionalRequirements.csv"
SELECTED = ["cSB4301", "cSB4303", "cSB4305", "cSB4305.3", "cSB4305.6", "cSB4307", "cSB4332", "cSB4328"]


def main():
    manifest = json.loads((SOURCE_ROOT / "manifest.json").read_text())
    digest = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    expected = next(f["sha256"] for f in manifest["files"] if f["upstream_path"].endswith(".csv"))
    if digest != expected:
        raise ValueError("Original CSV differs from the pinned acquisition manifest")
    requirements = []
    total_records = 0
    continuation_count = 0
    with SOURCE.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        reader.fieldnames  # Read the header so line positions start after it.
        previous_line = reader.line_num
        for ordinal, row in enumerate(reader, start=2):
            total_records += 1
            original = {"csv_record": ordinal, "line_start": previous_line + 1,
                        "line_end": reader.line_num, "fields": row}
            previous_line = reader.line_num
            identifier = row["Requirement ID"].strip()
            if identifier:
                requirements.append({"requirement_id": identifier, "summary": row["Summary"],
                                     "description": row["Description"], "rationale": row["Requirement Rationale"],
                                     "source_records": [original], "state": "imported_candidate",
                                     "source_sha256": digest, "source_commit": manifest["commit"],
                                     "source_file": "upstream/docs/cFE_FunctionalRequirements.csv",
                                     "source_owner": "NASA cFE public repository",
                                     "license": manifest["license"], "is_rtx_requirement": False})
            else:
                if not requirements:
                    raise ValueError("Continuation without an identified predecessor")
                continuation_count += 1
                requirements[-1]["source_records"].append(original)
                for output_field, source_field in [("description", "Description"), ("rationale", "Requirement Rationale")]:
                    if row[source_field]:
                        requirements[-1][output_field] += "\n" + row[source_field]
                if row["Summary"]:
                    requirements[-1].setdefault("continuation_summaries", []).append(row["Summary"])
    ids = [item["requirement_id"] for item in requirements]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate nonempty requirement IDs need manual reconciliation")
    for item in requirements:
        item["configuration_placeholders"] = [name for name in ("MISSION_DEFINED", "PLATFORM_DEFINED")
                                                if name in item["description"]]
        item["scope_note"] = "Source-system cFE requirement; applicability to a new design must be reviewed."
    output = SOURCE_ROOT / "derived"
    output.mkdir(exist_ok=True)
    with (output / "requirements.jsonl").open("w") as stream:
        for item in requirements:
            stream.write(json.dumps(item, ensure_ascii=False) + "\n")
    selected = [next(item for item in requirements if item["requirement_id"] == identifier) for identifier in SELECTED]
    (output / "demo-bus-requirements.json").write_text(json.dumps(selected, indent=2, ensure_ascii=False) + "\n")
    document = ["# Public NASA cFE software-bus requirement sample", "",
                "Source: NASA cFE, commit `" + manifest["commit"] + "`, Apache-2.0.", "",
                "These are public source-system requirements, not RTX requirements or an approved gateway specification.",
                "Mission/platform placeholders remain unresolved. Review applicability before reuse.", ""]
    for item in selected:
        document.extend(["## " + item["requirement_id"] + " — " + item["summary"], "", item["description"], "",
                         "Rationale: " + item["rationale"], "",
                         "Source CSV records: " + ", ".join(str(r["csv_record"]) for r in item["source_records"]), ""])
    (output / "demo-requirements.md").write_text("\n".join(document))
    # Preserve natural-language requirements as requirements, without inventing
    # quantified acceptance predicates, system design, satisfy links or verification results.
    model = ["package NASA_CFE_Imported {", "    private import ScalarValues::*;",
             "    doc /* Public NASA cFE requirement text import. Not RTX requirements.",
             "        No design satisfaction or executable verification is asserted.",
             "        Semantic mapping and new-project applicability remain pending. */", "",
             "    requirement def ImportedCFERequirement {",
             "        attribute sourceRequirementId : String;",
             "        attribute sourceCommit : String;",
             "        attribute sourceArtifactHash : String;",
             "        attribute sourceLocation : String;",
             "        attribute interpretationStatus : String;", "    }", ""]
    for item in selected:
        identifier = item["requirement_id"].replace(".", "_")
        model.extend([f"    requirement {identifier} : ImportedCFERequirement {{",
                      "        doc /* " + item["summary"].replace("*/", "* /")])
        for line in (item["description"] + "\n\nRationale: " + item["rationale"]).splitlines():
            model.append("            " + line.replace("*/", "* /"))
        model.append("        */")
        location = "CSV records " + ", ".join(str(r["csv_record"]) for r in item["source_records"])
        for field, value in [("sourceRequirementId", item["requirement_id"]),
                             ("sourceCommit", manifest["commit"]), ("sourceArtifactHash", digest),
                             ("sourceLocation", location), ("interpretationStatus", "TEXT_IMPORTED_SEMANTIC_MAPPING_PENDING")]:
            model.append(f"        attribute :>> {field} = {json.dumps(value)};")
        model.extend(["    }", ""])
    model.append("}")
    (output / "NASA_CFE_Imported.sysml").write_text("\n".join(model) + "\n")
    (SOURCE_ROOT / "reference.json").write_text(json.dumps({
        "package_name": "NASA_CFE_Imported", "model_files": ["derived/NASA_CFE_Imported.sysml"],
        "label": "NASA cFE software-bus requirements — source-backed text import",
        "source_kind": "public_nasa_requirements_text_import",
        "license": "Apache-2.0", "source_commit": manifest["commit"],
        "manifest": "manifest.json", "gold_semantic_model": False,
        "scope": "Requirement definitions/usages and source metadata; no formal constraints or satisfy links"
    }, indent=2) + "\n")
    report = {"source_sha256": digest, "csv_data_records": total_records,
              "identified_requirements": len(requirements), "continuation_records": continuation_count,
              "software_bus_requirements": sum(identifier.startswith("cSB") for identifier in ids),
              "demo_requirement_ids": SELECTED,
              "continuation_policy": "Append blank-ID records to the immediately preceding identified record; retain original fields and line positions for review",
              "gold_model_available": False, "new_project_applicability_reviewed": False,
              "sysml_import": "Eight requirement usages and one definition; original text and provenance only; semantic mapping pending",
              "derived_files": [{"path": str(p.relative_to(SOURCE_ROOT)), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                                for p in sorted(output.iterdir()) if p.is_file() and p.name != "ingestion-report.json"]}
    (output / "ingestion-report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
