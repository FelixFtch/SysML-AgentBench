"""SQLite -> SysML v2 -> official validator/export -> independent checks.

Budget values are read ONLY from the official model export. No regex parser or
configuration fallback is used to grant an engineering PASS.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import difflib
import hashlib
import json
import math
from pathlib import Path
import shutil
import uuid

ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "runs"
ENGINE_SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exported_elements(payload: object) -> list[dict]:
    """Handle official flat-element or commit-delta JSON without inferring syntax."""
    found: dict[str, dict] = {}
    def walk(value):
        if isinstance(value, dict):
            if "@id" in value and "@type" in value:
                found[value["@id"]] = value
            for child in value.values():
                if isinstance(child, (dict, list)):
                    walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    walk(payload)
    return list(found.values())


class ModelView:
    def __init__(self, elements: list[dict], ast: list[dict] | None = None):
        self.elements = elements
        self.by_id = {e["@id"]: e for e in elements}
        self.by_name = {e["qualifiedName"]: e for e in elements if e.get("qualifiedName")}
        self.value_links = {e["featureWithValue"]["@id"]: e for e in elements
                            if e.get("@type") == "FeatureValue" and e.get("featureWithValue")}
        self.ast = {e["element_id"]: e for e in (ast or [])}

    def literal(self, name: str):
        return self.literal_at("MarineGateway::gateway::" + name)

    def literal_at(self, name: str):
        element = self.by_name.get(name)
        if not element:
            raise ValueError(f"Official model export is missing attribute {name}")
        link = self.value_links.get(element["@id"])
        if not link:
            raise ValueError(f"Attribute {name} has no FeatureValue")
        value = self.by_id.get((link.get("value") or {}).get("@id"), {})
        if value.get("@type") not in {"LiteralInteger", "LiteralRational", "LiteralBoolean", "LiteralString"}:
            raise ValueError(f"{name} is not a supported parsed literal; expression values are not guessed")
        return value["value"]

    def number(self, name: str) -> float:
        value = self.literal(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"{name} must be a finite number")
        return float(value)

    def reference_name(self, ident: str) -> str | None:
        element = self.by_id.get(ident, {})
        if element.get("qualifiedName"):
            return element["qualifiedName"]
        chain = element.get("chainingFeature", [])
        if chain:
            parts = [self.by_id.get(ref["@id"], {}) for ref in chain]
            if parts and parts[0].get("qualifiedName") and all(p.get("name") for p in parts[1:]):
                return parts[0]["qualifiedName"] + "." + ".".join(p["name"] for p in parts[1:])
        return self.ast.get(ident, {}).get("qualified_name")

    def units_in_expression(self, qualified_name: str) -> set[str]:
        element = self.by_name.get(qualified_name, {})
        link = self.value_links.get(element.get("@id"), {})
        start = (link.get("value") or {}).get("@id")
        if not start:
            raise ValueError(f"No parsed value expression for {qualified_name}")
        units: set[str] = set()
        visited: set[str] = set()
        def visit(ident):
            if ident in visited:
                return
            visited.add(ident)
            expr = self.by_id.get(ident, {})
            if expr.get("@type") == "FeatureReferenceExpression":
                resolved = self.ast.get(ident, {}).get("references", {}).get("referent", {})
                refs = resolved if isinstance(resolved, list) else [resolved]
                for ref in refs:
                    name = ref.get("qualified_name", "") or ""
                    if name.startswith("SI::"):
                        units.add(name)
            for ref in expr.get("argument", []):
                visit(ref["@id"])
        visit(start)
        return units

    def expression_tree(self, qualified_name: str) -> dict:
        element = self.by_name.get(qualified_name, {})
        link = self.value_links.get(element.get("@id"), {})
        def visit(ident, depth=0):
            if depth > 12:
                raise ValueError("Expression exceeds this checker's bounded contract")
            expr = self.by_id.get(ident, {})
            kind = expr.get("@type")
            if kind in {"LiteralInteger", "LiteralRational"}:
                return {"literal": expr["value"]}
            if kind == "FeatureReferenceExpression":
                ref = self.ast.get(ident, {}).get("references", {}).get("referent", {})
                if not isinstance(ref, dict) or ref.get("is_proxy") or not ref.get("qualified_name"):
                    raise ValueError("Expression contains an unresolved reference")
                return {"ref": ref["qualified_name"]}
            if kind == "OperatorExpression":
                return {"op": expr.get("operator"), "args": [visit(r["@id"], depth + 1) for r in expr.get("argument", [])]}
            return {"unsupported_expression_type": kind}
        return visit((link.get("value") or {}).get("@id"))

    def unit_contract(self) -> dict:
        expected = {"totalPower": {"SI::watt"}, "powerLimit": {"SI::watt"}, "retentionTime": {"SI::second"}}
        actual = {name: self.units_in_expression("MarineGateway::Gateway::" + name) for name in expected}
        scalar_units = {"dataRateUnit": "Mbit/s (decimal)", "capacityUnit": "GB (decimal)"}
        labels = {name: self.literal_at("MarineGateway::Gateway::" + name) for name in scalar_units}
        contracts = {"totalPower": ("totalPowerW", 1, "SI::watt"), "powerLimit": ("powerLimitW", 1, "SI::watt"),
                     "retentionTime": ("retentionHours", 3600, "SI::second")}
        expected_expressions = {key: {"op": "*", "args": [{"ref": "MarineGateway::Gateway::" + scalar},
                                  {"op": "[", "args": [{"literal": factor}, {"ref": unit}]}]}
                                for key, (scalar, factor, unit) in contracts.items()}
        expressions = {key: self.expression_tree("MarineGateway::Gateway::" + key) for key in contracts}
        ok = actual == expected and labels == scalar_units and expressions == expected_expressions
        return {"id": "D-UNIT-CONTRACT", "label": "Pinned unit contract for budget attributes",
                "status": "PASS" if ok else "FAIL", "actual": {k: sorted(v) for k, v in actual.items()} | labels,
                "expected": {k: sorted(v) for k, v in expected.items()} | scalar_units,
                "expression_contracts": expressions, "expected_expressions": expected_expressions,
                "detail": "Checks scalar references, operators, conversion factors, resolved SI units and unit labels. This accepts only the declared expression forms, not arbitrary dimensional reasoning.",
                "tool": "official-EMF-references-plus-domain-contract-v1"}

    def named_elements(self, package_name: str = "MarineGateway") -> list[dict]:
        result = []
        for element in self.elements:
            name = element.get("qualifiedName", "")
            if not name.startswith(package_name + "::") or not element.get("declaredName"):
                continue
            entry = {"id": element["@id"], "name": element["declaredName"], "qualifiedName": name,
                     "type": element["@type"]}
            owner = self.by_id.get((element.get("owner") or {}).get("@id"), {})
            entry["owner"] = owner.get("qualifiedName")
            if name.startswith("MarineGateway::gateway::"):
                try:
                    entry["value"] = self.literal(element["declaredName"])
                except (ValueError, KeyError):
                    pass
            for key in ("relatedFeature", "connectorEnd", "type", "definition"):
                refs = element.get(key, [])
                if isinstance(refs, dict):
                    refs = [refs]
                names = [self.reference_name(ref.get("@id"))
                         for ref in refs if isinstance(ref, dict)]
                if any(names):
                    entry[key if key != "type" else "typedBy"] = [n for n in names if n]
            result.append(entry)
        return sorted(result, key=lambda e: (e["qualifiedName"], e["type"]))


def evaluate(view: ModelView) -> list[dict]:
    values = {key: view.number(key) for key in (
        "dataRateMbps", "retentionHours", "storageGB", "usableFraction", "linkMbps",
        "networkFactor", "uploadRateMbps", "totalPowerW", "powerLimitW")}
    if any(values[key] <= 0 for key in values) or values["usableFraction"] > 1:
        raise ValueError("Model values violate the checker contract: positive values and usable fraction <= 1")
    def check(ident, label, actual, limit, unit, detail):
        return {"id": ident, "label": label, "status": "PASS" if actual <= limit else "FAIL",
                "actual": round(actual, 9), "limit": round(limit, 9), "unit": unit,
                "margin": round(limit - actual, 9), "detail": detail,
                "tool": "independent-python-budget-checker-v1",
                "input": "official SysML v2 export / MarineGateway::gateway"}
    storage = values["dataRateMbps"] * values["retentionHours"] * 3600 / 8000
    preview = view.literal("previewApproved")
    if not isinstance(preview, bool):
        raise ValueError("previewApproved must be a parsed Boolean literal")
    expected_rate = view.number("previewMbps") if preview else values["dataRateMbps"]
    expected_policy = "P2_APPROVED" if preview else "FULL_REALTIME"
    policy_ok = view.literal("uploadPolicy") == expected_policy and math.isclose(values["uploadRateMbps"], expected_rate, rel_tol=1e-12)
    results = [
        check("R-STORE-001", "Complete raw-data retention", storage,
              values["storageGB"] * values["usableFraction"], "GB",
              "Decimal GB; the 80% allocation is net of logs and indexing. Capacity analysis is not an endurance test."),
        check("R-UPLOAD-P2" if view.literal("previewApproved") else "R-UPLOAD-001", "Approved uplink profile bandwidth", values["uploadRateMbps"] * values["networkFactor"],
              values["linkMbps"], "Mbit/s", "Includes overhead for one uplink; the shore relay distributes to both subscribers."),
        check("R-POWER-001", "Total node input power budget", values["totalPowerW"], values["powerLimitW"], "W",
              "Synthetic budget at the declared condition; not a hardware measurement or coverage of other conditions."),
    ]
    results.append({"id": "D-UPLOAD-POLICY", "label": "Upload rate preserves the active requirement",
                    "status": "PASS" if policy_ok else "FAIL", "actual": values["uploadRateMbps"], "limit": expected_rate,
                    "unit": "Mbit/s", "policy": view.literal("uploadPolicy"), "expected_policy": expected_policy,
                    "detail": "Full upload must equal raw input rate. Approved P2 must equal the declared P2 profile; bandwidth alone is insufficient."})
    required_connections = {
        "payloadAConnection": ("payloadAlpha.observationOut", "acquisition.fromAlpha"),
        "payloadBConnection": ("payloadBeta.observationOut", "acquisition.fromBeta"),
        "acquisitionConnection": ("acquisition.toProcessor", "processor.fromAcquisition"),
        "recordingConnection": ("processor.rawToRecorder", "recorder.rawInput"),
        "processingConnection": ("processor.dataToModem", "previewProcessor.fromProcessor" if preview else "modem.fromProcessor"),
        "uplinkConnection": ("modem.toShore", "shoreRelay.fromPlatform"),
        "shoreConnection": ("shoreRelay.toShoreSubscriber", "shoreSubscriber.receive"),
        "peerConnection": ("shoreRelay.toPeerSubscriber", "peerSubscriber.receive"),
    }
    if preview:
        required_connections["previewConnection"] = ("previewProcessor.toModem", "modem.fromProcessor")
    missing, incorrect = [], []
    prefix = "MarineGateway::Gateway::"
    for name, endpoints in required_connections.items():
        connection = view.by_name.get(prefix + name)
        if not connection or connection.get("@type") != "ConnectionUsage":
            missing.append(name)
        else:
            actual = [view.reference_name(ref["@id"]) for ref in connection.get("relatedFeature", [])]
            wanted = [prefix + endpoint for endpoint in endpoints]
            if actual != wanted:
                incorrect.append({"connection": name, "actual": actual, "expected": wanted})
    results.append({"id": "R-TOPOLOGY-001", "label": "Required acquisition, recording and sharing connections",
                    "status": "FAIL" if missing or incorrect else "PASS", "actual": len(required_connections) - len(missing) - len(incorrect),
                    "limit": len(required_connections), "unit": "connections", "missing": missing, "incorrect_endpoints": incorrect,
                    "detail": "Checks scoped connection identities and ordered endpoints against the declared topology contract; interface behavior requires separate verification.",
                    "tool": "model-topology-endpoints-v2"})
    results.append(view.unit_contract())
    results.append({"id": "R-RUNTIME-001", "label": "Preview quality, latency and hardware conditions",
                    "status": "UNKNOWN", "detail": "Real payload, hardware and mission-quality tests have not run. Budget feasibility is not product acceptance."})
    return results


def snapshot_sources(run_dir: Path) -> dict:
    files = []
    source_root = ROOT / "fixtures"
    for source in sorted(source_root.rglob("*")):
        if source.is_file() and source.suffix in {".json", ".sqlite", ".sysml", ".md"}:
            relative = source.relative_to(source_root)
            dest = run_dir / "sources" / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
            files.append({"path": str(dest.relative_to(run_dir)), "original_path": str(source),
                          "sha256": sha(dest), "bytes": dest.stat().st_size})
    fingerprint = hashlib.sha256(json.dumps([(f["path"], f["sha256"]) for f in files], sort_keys=True).encode()).hexdigest()
    result = {"synthetic": True, "snapshot_sha256": fingerprint, "files": files}
    dump(run_dir / "source-manifest.json", result)
    return result


def model_diff(current: list[dict], previous: list[dict]) -> dict:
    def canonical(elements):
        return {e["qualifiedName"]: {k: v for k, v in e.items() if k != "id"} for e in elements}
    new, old = canonical(current), canonical(previous)
    return {"added": [new[k] for k in sorted(new.keys() - old.keys())],
            "removed": [old[k] for k in sorted(old.keys() - new.keys())],
            "changed": [{"element": k, "before": old[k], "after": new[k]} for k in sorted(new.keys() & old.keys()) if new[k] != old[k]],
            "scope": "declared named model elements and supported semantic fields; full text diff also retained"}


def run_case(case_name, data_rate_mbps=None, link_mbps=None, *, preview_approved=False):
    from mvp.models.render_model import write_model_package
    from mvp.toolchain.validate import validate_package

    if not isinstance(preview_approved, bool):
        raise ValueError("preview_approved must be an explicit boolean decision")
    RUNS.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
    run_dir = RUNS / run_id
    run_dir.mkdir()
    request = {"case_name": case_name, "data_rate_mbps": data_rate_mbps, "link_mbps": link_mbps,
               "preview_approved": preview_approved}
    dump(run_dir / "request.json", request)
    result = {"run_id": run_id, "run_dir": str(run_dir), "case_name": case_name,
              "synthetic": True, "execution_mode": "real-official-sysml-toolchain",
              "analysis_code_sha256": ENGINE_SOURCE_SHA256,
              "created_at": datetime.now(timezone.utc).isoformat(), "checks": [], "model_elements": []}
    try:
        package = write_model_package(run_dir / "model", **request)
        result["source_manifest"] = snapshot_sources(run_dir)
        result["model_path"] = str(package["model_path"])
        result["model_text"] = Path(package["model_path"]).read_text(encoding="utf-8")
        result["model_files"] = [str(p) for p in package["model_files"]]
        model_hashes = {str(Path(p).relative_to(run_dir)): sha(Path(p)) for p in package["model_files"]}
        result["model_revision"] = hashlib.sha256(json.dumps(model_hashes, sort_keys=True).encode()).hexdigest()
        dump(run_dir / "model-manifest.json", {"sha256": result["model_revision"], "files": model_hashes})
        result["config"] = package["config"]
        result["sysml"] = validate_package(result["model_files"], "MarineGateway", str(run_dir / "sysml"))
        generated_manifest_path = Path(package["manifest_path"])
        generated_manifest = json.loads(generated_manifest_path.read_text(encoding="utf-8"))
        generated_manifest.update({"validation_status": result["sysml"]["status"],
                                   "validation_evidence": "../sysml/validation.json", "run_id": run_id})
        dump(generated_manifest_path, generated_manifest)
        if result["sysml"]["status"] == "PASS":
            exported = json.loads(Path(result["sysml"]["model_json_path"]).read_text(encoding="utf-8"))
            elements = exported_elements(exported)
            if not elements:
                raise ValueError("The official parser returned no readable semantic model elements")
            ast = json.loads(Path(result["sysml"]["ast_json_path"]).read_text(encoding="utf-8"))
            view = ModelView(elements, ast)
            result["model_elements"] = view.named_elements()
            result["parsed_element_count"] = len(elements)
            result["checks"] = evaluate(view)
            expected_approval = bool(preview_approved and package["config"]["preview_requested"])
            result["checks"].append({"id": "D-DECISION-BINDING", "label": "Model requirement decision matches the explicit request",
                                     "status": "PASS" if view.literal("previewApproved") is expected_approval else "FAIL",
                                     "actual": view.literal("previewApproved"), "expected": expected_approval})
            warnings = [d for d in result["sysml"].get("diagnostics", []) if d.get("severity") == "WARNING"]
            result["checks"].append({"id": "D-WARNING-REVIEW", "label": "Official static-warning review",
                                      "status": "UNKNOWN" if warnings else "PASS",
                                      "detail": "Static warnings require review; official severities are preserved." if warnings else "No static warnings from the official validator.",
                                      "warnings": warnings})
            result["budget_status"] = "FAIL" if any(c["status"] == "FAIL" for c in result["checks"]) else "PASS"
            result["status"] = "FAIL" if result["budget_status"] == "FAIL" else "UNKNOWN"
            for check in result["checks"]:
                check["model_revision"] = result["model_revision"]
        else:
            result["status"] = result["sysml"]["status"]
            result["checks"] = [{"id": "BLOCKED-BY-SYSML", "status": "UNKNOWN", "label": "Engineering checks not executed",
                                 "detail": "The model did not pass official validation. Input configuration is not used to bypass the model."}]
        baseline = None
        for path in sorted(RUNS.glob("*/result.json"), reverse=True):
            prior = json.loads(path.read_text(encoding="utf-8"))
            if prior.get("case_name") == "baseline" and prior.get("sysml", {}).get("status") == "PASS":
                baseline = prior
                break
        result["diff"] = model_diff(result["model_elements"], (baseline or {}).get("model_elements", []))
        result["diff"]["base_run_id"] = (baseline or {}).get("run_id")
        result["diff"]["text"] = "".join(difflib.unified_diff((baseline or {}).get("model_text", "").splitlines(True),
                                result["model_text"].splitlines(True), fromfile="baseline.sysml", tofile="candidate.sysml"))
        dump(run_dir / "diff.json", result["diff"])
        dump(run_dir / "checks.json", result["checks"])
        dump(run_dir / "decision.json", {"preview_approved": package["config"]["preview_approved"], "requested_preview_approval": preview_approved,
             "decision_type": "explicit synthetic requirement replacement", "model_revision": result["model_revision"],
             "source_snapshot": result["source_manifest"]["snapshot_sha256"],
             "notice": "Local demonstration decision, not enterprise authentication or engineering release approval"})
    except Exception as exc:
        result["status"] = "ERROR"
        result["error"] = f"{type(exc).__name__}: {exc}"
        result.setdefault("sysml", {"status": "ERROR", "diagnostics": []})
    dump(run_dir / "result.json", result)
    seal_evidence(run_dir)
    return result


def seal_evidence(run_dir: Path) -> None:
    files = {str(path.relative_to(run_dir)): sha(path) for path in sorted(run_dir.rglob("*"))
             if path.is_file() and path.name != "evidence-manifest.json" and "revalidation" not in path.relative_to(run_dir).parts}
    dump(run_dir / "evidence-manifest.json", {"scope": "integrity inventory, not a digital signature", "files": files})


def run_agent(message, case_name="candidate_a", preview_approved=False):
    from mvp.agent import run_agent as execute
    return execute(message, case_name, preview_approved)


def run_reference(reference_name: str) -> dict:
    """Import and validate a pinned public engineering source, without fake budgets."""
    from mvp.toolchain.validate import validate_package
    if reference_name not in {"sysml-official-vehicle", "nasa-cfe"}:
        raise ValueError("Unknown public reference project")
    source = ROOT / "public-data" / reference_name
    reference = json.loads((source / "reference.json").read_text(encoding="utf-8"))
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
    run_dir = RUNS / run_id
    run_dir.mkdir(parents=True)
    result = {"run_id": run_id, "run_dir": str(run_dir), "case_name": reference_name,
              "reference_name": reference_name, "source_kind": reference.get("source_kind"),
              "analysis_code_sha256": ENGINE_SOURCE_SHA256,
              "created_at": datetime.now(timezone.utc).isoformat(), "execution_mode": "real-official-sysml-toolchain",
              "checks": [], "model_elements": [], "config": {}, "budget_status": "NOT_APPLICABLE"}
    try:
        files = []
        for path in sorted(source.rglob("*")):
            relative = path.relative_to(source)
            if path.is_symlink() or any(part.startswith("validation") or part in {"__pycache__", ".git"} for part in relative.parts):
                continue
            if not path.is_file():
                continue
            dest = run_dir / "model" / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
            files.append({"path": str(dest.relative_to(run_dir)), "sha256": sha(dest), "bytes": dest.stat().st_size})
        model_files = []
        for name in reference["model_files"]:
            path = (run_dir / "model" / name).resolve()
            if not path.is_relative_to((run_dir / "model").resolve()) or not path.is_file():
                raise ValueError("Reference manifest contains a missing or out-of-scope model")
            model_files.append(str(path))
        result["model_files"] = model_files
        result["model_path"] = model_files[0]
        result["model_text"] = Path(model_files[0]).read_text(encoding="utf-8")
        snapshot = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
        result["source_manifest"] = {"reference": reference_name, "source_kind": reference.get("source_kind"),
                                     "snapshot_sha256": snapshot, "files": files}
        result["model_revision"] = hashlib.sha256("".join(sha(Path(f)) for f in model_files).encode()).hexdigest()
        dump(run_dir / "source-manifest.json", result["source_manifest"])
        result["sysml"] = validate_package(model_files, reference["package_name"], str(run_dir / "sysml"))
        if result["sysml"]["status"] == "PASS":
            elements = exported_elements(json.loads(Path(result["sysml"]["model_json_path"]).read_text(encoding="utf-8")))
            ast = json.loads(Path(result["sysml"]["ast_json_path"]).read_text(encoding="utf-8"))
            result["model_elements"] = ModelView(elements, ast).named_elements(reference["package_name"])
            result["parsed_element_count"] = len(elements)
            result["status"] = "UNKNOWN"
            result["checks"] = [{"id": "PUBLIC-SEMANTIC-REVIEW", "label": "Engineering meaning and acceptance",
                                 "status": "UNKNOWN", "detail": "Public source imported and statically validated. No unstated requirements, satisfaction or physical verification are inferred."}]
        else:
            result["status"] = result["sysml"]["status"]
        result["diff"] = {"added": result["model_elements"], "removed": [], "changed": [],
                          "scope": "Public reference import; no comparison against the marine gateway baseline."}
        dump(run_dir / "checks.json", result["checks"])
    except Exception as exc:
        result["status"] = "ERROR"
        result["error"] = f"{type(exc).__name__}: {exc}"
        result.setdefault("sysml", {"status": "ERROR", "diagnostics": []})
    dump(run_dir / "result.json", result)
    seal_evidence(run_dir)
    return result


def run_submitted_model(model_files, package_name: str, *, label: str = "submitted") -> dict:
    """Validate agent- or human-written .sysml files with the official toolchain.

    Unlike run_case, nothing is rendered from a fixture template and no marine budget
    contract is applied. A language PASS therefore stays engineering UNKNOWN: there is
    no domain contract to satisfy. Files are copied into the run directory so the
    evidence pack does not depend on the caller's temporary paths.
    """
    from mvp.toolchain.validate import validate_package

    if not isinstance(package_name, str) or not package_name.strip():
        raise ValueError("package_name is required")
    sources = [Path(path).resolve() for path in model_files]
    if not sources:
        raise ValueError("At least one .sysml file is required")
    RUNS.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
    run_dir = RUNS / run_id
    model_dir = run_dir / "model"
    model_dir.mkdir(parents=True)
    copied = []
    seen = set()
    for source in sources:
        if not source.is_file() or source.suffix not in {".sysml", ".kerml"}:
            raise ValueError(f"Missing or unsupported model input: {source}")
        name = source.name
        if name in seen:
            raise ValueError(f"Duplicate file name in one submission: {name}")
        seen.add(name)
        dest = model_dir / name
        shutil.copy2(source, dest)
        copied.append(dest)
    result = {"run_id": run_id, "run_dir": str(run_dir), "case_name": label,
              "source_kind": "submitted-model", "synthetic": True,
              "execution_mode": "real-official-sysml-toolchain",
              "analysis_code_sha256": ENGINE_SOURCE_SHA256,
              "created_at": datetime.now(timezone.utc).isoformat(),
              "package_name": package_name, "checks": [], "model_elements": [],
              "budget_status": "NOT_APPLICABLE", "config": {}}
    try:
        files = [{"path": str(path.relative_to(run_dir)), "original_path": str(src),
                  "sha256": sha(path), "bytes": path.stat().st_size}
                 for src, path in zip(sources, copied)]
        result["source_manifest"] = {"kind": "submitted-model", "files": files,
                                      "snapshot_sha256": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()}
        dump(run_dir / "source-manifest.json", result["source_manifest"])
        result["model_files"] = [str(path) for path in copied]
        result["model_path"] = str(copied[0])
        result["model_text"] = copied[0].read_text(encoding="utf-8")
        result["model_revision"] = hashlib.sha256("".join(item["sha256"] for item in files).encode()).hexdigest()
        dump(run_dir / "model-manifest.json", {"sha256": result["model_revision"], "files": files})
        result["sysml"] = validate_package(result["model_files"], package_name, str(run_dir / "sysml"))
        if result["sysml"]["status"] == "PASS":
            elements = exported_elements(json.loads(Path(result["sysml"]["model_json_path"]).read_text(encoding="utf-8")))
            ast = json.loads(Path(result["sysml"]["ast_json_path"]).read_text(encoding="utf-8"))
            result["model_elements"] = ModelView(elements, ast).named_elements(package_name)
            result["parsed_element_count"] = len(elements)
            # No domain contract was supplied, so language success cannot become engineering acceptance.
            result["status"] = "UNKNOWN"
            result["checks"] = [{"id": "NO-DOMAIN-CONTRACT", "label": "Engineering checks",
                                 "status": "NOT_APPLICABLE",
                                 "detail": "Submitted model passed official language checks. No budget, topology or requirement contract was supplied, so engineering acceptance is not inferred."}]
        else:
            result["status"] = result["sysml"]["status"]
            result["checks"] = [{"id": "BLOCKED-BY-SYSML", "status": "UNKNOWN",
                                 "label": "Engineering checks not executed",
                                 "detail": "The submitted model did not pass official validation."}]
        dump(run_dir / "checks.json", result["checks"])
    except Exception as exc:
        result["status"] = "ERROR"
        result["error"] = f"{type(exc).__name__}: {exc}"
        result.setdefault("sysml", {"status": "ERROR", "diagnostics": []})
    dump(run_dir / "result.json", result)
    seal_evidence(run_dir)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_name", nargs="?", choices=["baseline", "upgraded_legacy", "candidate_a", "candidate_b", "degraded_link"])
    parser.add_argument("--files", nargs="+", help="Validate these .sysml files instead of rendering a fixture case")
    parser.add_argument("--package", help="Root package name, required with --files")
    parser.add_argument("--data-rate", type=float)
    parser.add_argument("--link", type=float)
    parser.add_argument("--approve-preview", action="store_true")
    args = parser.parse_args()
    if args.files:
        if not args.package:
            parser.error("--package is required with --files")
        output = run_submitted_model(args.files, args.package)
    elif args.case_name:
        output = run_case(args.case_name, args.data_rate, args.link, preview_approved=args.approve_preview)
    else:
        parser.error("provide a fixture case name or --files")
    summary = {k: output.get(k) for k in ["run_id", "run_dir", "status", "budget_status", "error", "checks"]}
    summary["sysml_status"] = (output.get("sysml") or {}).get("status")
    summary["diagnostics"] = [d.get("message") for d in (output.get("sysml") or {}).get("diagnostics", [])][:8]
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    raise SystemExit(2 if output["status"] == "ERROR" else 0)
