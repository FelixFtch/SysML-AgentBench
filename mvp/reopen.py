"""Revalidate an existing extracted run with its recorded model bytes."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import uuid

from mvp.engine import ENGINE_SOURCE_SHA256, ModelView, dump, evaluate, exported_elements, sha
from mvp.toolchain.validate import validate_package


def reopen(run_folder: str | Path) -> dict:
    folder = Path(run_folder).resolve()
    original = json.loads((folder / "result.json").read_text(encoding="utf-8"))
    inventory = json.loads((folder / "evidence-manifest.json").read_text(encoding="utf-8"))
    for name, digest in inventory["files"].items():
        path = (folder / name).resolve()
        if not path.is_relative_to(folder) or sha(path) != digest:
            raise ValueError("Evidence inventory mismatch: " + name)
    original_root = Path(original["run_dir"])
    files = []
    expected = original["sysml"]["input_hashes"]
    for old_path in original["model_files"]:
        path = (folder / Path(old_path).relative_to(original_root)).resolve()
        if not path.is_relative_to(folder) or sha(path) != expected[old_path]:
            raise ValueError("Model bytes differ from the recorded run: " + old_path)
        files.append(str(path))
    for item in original.get("source_manifest", {}).get("files", []):
        path = (folder / item["path"]).resolve()
        if not path.is_relative_to(folder) or sha(path) != item["sha256"]:
            raise ValueError("Source snapshot differs from the recorded run: " + item["path"])
    if original.get("reference_name") is None:
        package_manifest = json.loads((folder / "model/manifest.json").read_text(encoding="utf-8"))
        for item in package_manifest["artifacts"]:
            path = (folder / "model" / item["path"]).resolve()
            if not path.is_relative_to(folder / "model") or sha(path) != item["sha256"]:
                raise ValueError("Model/source package artifact differs: " + item["path"])
        request = json.loads((folder / "request.json").read_text(encoding="utf-8"))
        decision = json.loads((folder / "decision.json").read_text(encoding="utf-8"))
        expected_approval = bool(request["preview_approved"] and original["config"]["preview_requested"])
        if (decision["preview_approved"] is not expected_approval
            or decision["requested_preview_approval"] is not request["preview_approved"]
            or decision["model_revision"] != original["model_revision"]
            or decision["source_snapshot"] != original["source_manifest"]["snapshot_sha256"]):
            raise ValueError("Requirements decision does not bind to this source/model/request")
    output = folder / "revalidation" / uuid.uuid4().hex[:8]
    validated = validate_package(files, original["sysml"]["package_name"], str(output))
    result = {"original_run_id": original["run_id"], "source_and_model_hashes": "PASS",
              "sysml": validated, "checks": []}
    pins = ("jar_sha256", "adapter_sha256", "library_commit", "library_content_sha256")
    result["toolchain_matches"] = all(validated["toolchain"][key] == original["sysml"]["toolchain"][key] for key in pins)
    result["analysis_code_matches"] = original.get("analysis_code_sha256") == ENGINE_SOURCE_SHA256
    if validated["status"] == "PASS" and original.get("reference_name") is None:
        view = ModelView(exported_elements(json.loads(Path(validated["model_json_path"]).read_text())),
                         json.loads(Path(validated["ast_json_path"]).read_text()))
        result["checks"] = evaluate(view)
        result["checks"].append({"id": "D-DECISION-BINDING", "status": "PASS" if view.literal("previewApproved") is expected_approval else "FAIL",
                                 "actual": view.literal("previewApproved"), "expected": expected_approval})
        old = {c["id"]: (c["status"], c.get("actual"), c.get("limit")) for c in original["checks"]}
        old.pop("D-WARNING-REVIEW", None)
        new = {c["id"]: (c["status"], c.get("actual"), c.get("limit")) for c in result["checks"]}
        result["same_check_results"] = old == new
        result["check_ids_match"] = set(old) == set(new)
    dump(output / "reopen-result.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_folder")
    args = parser.parse_args()
    result = reopen(args.run_folder)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["sysml"]["status"] == "PASS" and result.get("same_check_results", True)
                     and result["toolchain_matches"] and result["analysis_code_matches"] else 2)
