"""Render synthetic SysML v2 projects from the real legacy SQLite snapshot.

All engineering defaults are read from fixtures/legacy.sqlite. The fixture seed
is used only by fixtures/build_legacy_db.py to rebuild that snapshot. SysML
validation is the caller's responsibility; rendering never claims validation.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import sqlite3
from string import Template
from typing import Any

MODELS = Path(__file__).resolve().parent
FIXTURES = MODELS.parent / "fixtures"
DATABASE = FIXTURES / "legacy.sqlite"
ALIASES = {"unchanged": "upgraded_legacy", "legacy": "baseline", "A": "candidate_a", "B": "candidate_b", "a": "candidate_a", "b": "candidate_b"}
MODEL_FIELDS = {
    "dataRateMbps": ("data_rate_mbps", "Mbit/s", "R-CHANGE-001"),
    "retentionHours": ("retention_hours", "h", "R-STORE-001"),
    "storageGB": ("storage_gb", "GB decimal", "R-STORE-001"),
    "usableFraction": ("payload_fraction", "1", "R-STORE-002"),
    "linkMbps": ("link_mbps", "Mbit/s", "R-NET-002"),
    "networkFactor": ("network_overhead", "1", "R-NET-001"),
    "uploadRateMbps": ("upload_rate_mbps", "Mbit/s", "R-UPLOAD-001"),
    "previewMbps": ("preview_mbps", "Mbit/s", "R-UPLOAD-P2"),
    "totalPowerW": ("power_w", "W", "R-POWER-001"),
    "powerLimitW": ("power_limit_w", "W", "R-POWER-001"),
}


def _ensure_database() -> None:
    if DATABASE.exists():
        return
    spec = importlib.util.spec_from_file_location("marine_fixture_builder", FIXTURES / "build_legacy_db.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load the synthetic fixture database builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.build_database(DATABASE)


def _positive(value: float | str, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a positive finite number")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{name} must be a positive finite number")
    return number


def get_case_config(
    case_name: str,
    data_rate_mbps: float | None = None,
    link_mbps: float | None = None,
    *,
    preview_approved: bool = False,
) -> dict[str, Any]:
    """Read one SQLite row and apply only explicit caller overrides.

    preview_approved is a caller-provided decision, never silently inferred from
    the candidate name. The caller records approver/revision/decision evidence.
    """
    if not isinstance(preview_approved, bool):
        raise ValueError("preview_approved must be a boolean")
    canonical = ALIASES.get(case_name, case_name)
    _ensure_database()
    uri = DATABASE.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as database:
        database.row_factory = sqlite3.Row
        row = database.execute("SELECT rowid AS source_rowid, * FROM configs WHERE case_name = ?", (canonical,)).fetchone()
        if row is None:
            allowed = [r[0] for r in database.execute("SELECT case_name FROM configs ORDER BY rowid")]
            raise ValueError(f"Unknown case {case_name!r}; expected one of {allowed}")
        config: dict[str, Any] = dict(row)
    config["preview_requested"] = bool(config["preview_requested"])
    config["synthetic"] = True
    config["database_sha256"] = hashlib.sha256(DATABASE.read_bytes()).hexdigest()
    config["source_database"] = str(DATABASE)
    config["runtime_overrides"] = {}
    for name, value in (("data_rate_mbps", data_rate_mbps), ("link_mbps", link_mbps)):
        if value is not None:
            number = _positive(value, name)
            config["runtime_overrides"][name] = {"old_value": config[name], "new_value": number}
            config[name] = number
        else:
            config[name] = _positive(config[name], name)
    config["preview_approved"] = bool(preview_approved and config["preview_requested"])
    config["upload_rate_mbps"] = config["preview_mbps"] if config["preview_approved"] else config["data_rate_mbps"]
    config["upload_policy"] = "P2_APPROVED" if config["preview_approved"] else "FULL_REALTIME"
    config["approval_required"] = bool(config["preview_requested"])
    config["pending_approval"] = bool(config["preview_requested"] and not config["preview_approved"])
    config["upload_requirement_id"] = "R-UPLOAD-P2" if config["preview_approved"] else "R-UPLOAD-001"
    return config


def _render_config(config: dict[str, Any]) -> str:
    context: dict[str, Any] = dict(config)
    for key, value in list(context.items()):
        if isinstance(value, (float, int)) and not isinstance(value, bool):
            context[key] = format(value, ".15g")
    context["preview_approved_literal"] = "true" if config["preview_approved"] else "false"
    context["upload_requirement_type"] = "PreviewUploadRequirement" if config["preview_approved"] else "FullUploadRequirement"
    preview = config["preview_approved"]
    context["preview_action_definition"] = "action def GenerateP2Preview;" if preview else ""
    context["preview_part_definition"] = """part def PreviewProcessor {
        port fromProcessor : ~SharedDataPort;
        port toModem : SharedDataPort;
        perform action preview : GenerateP2Preview;
    }""" if preview else ""
    context["preview_part_usage"] = "part previewProcessor : PreviewProcessor;" if preview else ""
    context["upload_connections"] = """connection processingConnection connect processor.dataToModem to previewProcessor.fromProcessor;
        connection previewConnection connect previewProcessor.toModem to modem.fromProcessor;""" if preview else "connection processingConnection connect processor.dataToModem to modem.fromProcessor;"
    return Template((MODELS / "gateway.sysml.tmpl").read_text(encoding="utf-8")).substitute(context)


def render_model(
    case_name: str,
    data_rate_mbps: float | None = None,
    link_mbps: float | None = None,
    *,
    preview_approved: bool = False,
) -> str:
    """Return model text. The two supplier packages are separate dependencies."""
    return _render_config(get_case_config(case_name, data_rate_mbps, link_mbps, preview_approved=preview_approved))


def _source_mapping(config: dict[str, Any]) -> dict[str, Any]:
    with sqlite3.connect(DATABASE.resolve().as_uri() + "?mode=ro", uri=True) as database:
        database.row_factory = sqlite3.Row
        source_rows = [dict(row) for row in database.execute("SELECT rowid AS source_rowid, * FROM sources ORDER BY rowid")]
        component_rows = [dict(row) for row in database.execute(
            "SELECT rowid AS source_rowid, * FROM components WHERE configuration_id = ? ORDER BY rowid",
            (config["configuration_id"],),
        )]
        interface_rows = [dict(row) for row in database.execute("SELECT rowid AS source_rowid, * FROM interfaces ORDER BY rowid")]
    attributes = []
    for model_name, (field, unit, requirement) in MODEL_FIELDS.items():
        source_field = field
        origin = "legacy_database"
        if field in config["runtime_overrides"]:
            origin = "runtime_override"
        if field == "upload_rate_mbps":
            source_field = "preview_mbps" if config["preview_approved"] else "data_rate_mbps"
            origin = "approved_requirement_selection" if config["preview_approved"] else "original_upload_requirement"
            requirement = config["upload_requirement_id"]
        if field == "data_rate_mbps" and config["case_name"] == "baseline" and field not in config["runtime_overrides"]:
            requirement = "R-SOURCE-001"
        attributes.append({
            "model_element": f"MarineGateway::gateway::{model_name}",
            "value": config[field], "unit": unit, "origin": origin,
            "source_id": config["source_id"], "source_table": "configs",
            "source_rowid": config["source_rowid"], "source_key": {"case_name": config["case_name"]},
            "source_column": source_field, "requirement_id": requirement,
            "database_sha256": config["database_sha256"],
        })
    return {"synthetic": True, "source_database": "sources/legacy.sqlite", "source_database_sha256": config["database_sha256"],
            "attributes": attributes, "runtime_overrides": config["runtime_overrides"],
            "source_records": [{**row, "snapshot_path": "sources/original/" + row["source_path"]} for row in source_rows],
            "selected_component_records": component_rows,
            "legacy_interface_records": interface_rows,
            "interface_change": {
                "origin": "approved_requirement_selection" if config["preview_approved"] else "legacy_database",
                "source_interface_id": "IF-PROC-MODEM",
                "change": "insert previewProcessor between processor and modem" if config["preview_approved"] else "unchanged",
                "requirement_id": config["upload_requirement_id"],
                "requires_external_decision_record": config["preview_approved"],
            },
            "supplier_dependencies": [
                {"source_id": "SRC-PAYLOAD-ICD-R1", "file": "suppliers/PayloadSupplier.sysml", "package": "PayloadSupplier"},
                {"source_id": "SRC-LINK-ICD-R1", "file": "suppliers/SharingLinkSupplier.sysml", "package": "SharingLinkSupplier"},
            ]}


def write_model_package(
    output_dir: str | Path,
    case_name: str,
    data_rate_mbps: float | None = None,
    link_mbps: float | None = None,
    *,
    preview_approved: bool = False,
) -> dict[str, Any]:
    """Write a self-contained source/model package and return absolute paths.

    The caller must choose a new run directory; unrelated files are not removed.
    Preview approval records supplied by the application are attached separately.
    """
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    config = get_case_config(case_name, data_rate_mbps, link_mbps, preview_approved=preview_approved)
    model_path = output / "MarineGateway.sysml"
    model_path.write_text(_render_config(config), encoding="utf-8")
    supplier_dir = output / "suppliers"
    supplier_dir.mkdir(exist_ok=True)
    source_dir = output / "sources"
    source_dir.mkdir(exist_ok=True)
    shutil.copy2(DATABASE, source_dir / "legacy.sqlite")
    model_files = [model_path]
    for filename in ("PayloadSupplier.sysml", "SharingLinkSupplier.sysml", "payload_icd.json", "sharing_icd.json"):
        path = supplier_dir / filename
        shutil.copy2(FIXTURES / "suppliers" / filename, path)
        if path.suffix == ".sysml":
            model_files.append(path)
    requirements = json.loads((FIXTURES / "requirements.json").read_text(encoding="utf-8"))
    requirements["selected_configuration"] = config["configuration_id"]
    requirements["runtime_selection"] = {"preview_approved": config["preview_approved"], "active_upload_requirement": config["upload_requirement_id"], "requires_external_decision_record": config["preview_approved"]}
    for row in requirements["requirements"]:
        if row["id"] == "R-UPLOAD-001":
            row["status"] = "superseded_for_selected_configuration" if config["preview_approved"] else "active"
        if row["id"] == "R-UPLOAD-P2":
            row["status"] = "selected_by_explicit_caller_approval" if config["preview_approved"] else "proposed"
    requirements_path = output / "requirements.json"
    requirements_path.write_text(json.dumps(requirements, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    mapping = _source_mapping(config)
    for source in mapping["source_records"]:
        original = (FIXTURES / source["source_path"]).resolve()
        if not original.is_relative_to(FIXTURES.resolve()):
            raise ValueError("Database source path must stay inside the fixture directory")
        if hashlib.sha256(original.read_bytes()).hexdigest() != source["sha256"]:
            raise ValueError(f"Source {source['source_id']} differs from the SQLite snapshot; rebuild the fixture database")
        snapshot = output / source["snapshot_path"]
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, snapshot)
    mapping_path = output / "source_mapping.json"
    mapping_path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    shutil.copy2(FIXTURES / "reuse_packages.json", source_dir / "reuse_packages.json")
    manifest_path = output / "manifest.json"
    artifacts = []
    for path in sorted(output.rglob("*")):
        if path.is_file() and path != manifest_path:
            artifacts.append({"path": path.relative_to(output).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "size": path.stat().st_size})
    manifest = {"schema_version": 1, "synthetic": True, "notice": "Synthetic engineering example, not RTX source data or hardware test evidence.",
                "configuration": config, "model_entrypoint": "MarineGateway.sysml", "required_model_files": [p.relative_to(output).as_posix() for p in model_files],
                "validation_status": "NOT_RUN", "artifacts": artifacts}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"model_path": str(model_path), "model_files": [str(p) for p in model_files],
            "requirements_path": str(requirements_path), "mapping_path": str(mapping_path),
            "manifest_path": str(manifest_path), "config": config}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_name")
    parser.add_argument("--data-rate-mbps", type=float)
    parser.add_argument("--link-mbps", type=float)
    parser.add_argument("--preview-approved", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if args.output_dir:
        result = write_model_package(args.output_dir, args.case_name, args.data_rate_mbps, args.link_mbps, preview_approved=args.preview_approved)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render_model(args.case_name, args.data_rate_mbps, args.link_mbps, preview_approved=args.preview_approved), end="")
