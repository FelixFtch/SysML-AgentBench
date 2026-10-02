"""Explicit, real-engine HTTP acceptance. Run manually after starting mvp.app.

This module has no unittest test cases, so normal unit discovery stays fast.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
from urllib.request import Request, urlopen
import zipfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8765")
    parser.add_argument("--review-smoke", action="store_true", help="Rerun approved/unapproved candidate A without replacing the six-case evidence")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    summary = {"timestamp": datetime.now(timezone.utc).isoformat(), "server": args.url,
               "mode": "real HTTP + official SysML engine; no mock", "cases": []}

    def read(path):
        with urlopen(args.url + path, timeout=240) as response:
            return json.loads(response.read())

    cases = [
        ({"case_name": "baseline"}, {"R-STORE-001": "PASS", "R-UPLOAD-001": "PASS", "R-POWER-001": "PASS"}),
        ({"case_name": "candidate_a", "preview_approved": True}, {"R-STORE-001": "PASS", "R-UPLOAD-P2": "PASS", "R-POWER-001": "PASS"}),
        ({"case_name": "candidate_b", "preview_approved": True}, {"R-POWER-001": "FAIL"}),
        ({"case_name": "candidate_a", "preview_approved": True, "data_rate_mbps": 30}, {"R-STORE-001": "FAIL"}),
        ({"case_name": "candidate_a", "preview_approved": False}, {"R-UPLOAD-001": "FAIL"}),
        ({"case_name": "degraded_link", "preview_approved": True}, {"R-UPLOAD-P2": "FAIL"}),
    ]
    if args.review_smoke:
        cases = [cases[1], cases[4]]
    output_name = "reviewed-verification-results.json" if args.review_smoke else "verification-results.json"
    for payload, expected in cases:
        print("RUN", json.dumps(payload), flush=True)
        req = Request(args.url + "/api/run", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=240) as response:
            record = json.loads(response.read())
        result = record.get("result", {})
        assert result.get("sysml", {}).get("status") == "PASS", result.get("sysml") or record
        assert result.get("execution_mode") == "real-official-sysml-toolchain", result
        checks = {item["id"]: item for item in result["checks"]}
        for ident, status in expected.items():
            assert checks[ident]["status"] == status, checks[ident]
        assert checks["R-RUNTIME-001"]["status"] == "UNKNOWN"
        assert result["status"] in {"FAIL", "UNKNOWN"}  # Never imply full product verification.
        assert result["model_elements"] and result["model_text"]
        assert any(element["type"] == "ConnectionUsage" and (element.get("relatedFeature") or element.get("connectorEnd")) for element in result["model_elements"])
        reopened = read("/api/runs/" + record["record_id"])
        assert reopened == record, "Reopened record differs"
        with urlopen(args.url + "/api/runs/" + record["record_id"] + "/export.zip", timeout=240) as response:
            archive_bytes = response.read()
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            names = archive.namelist()
            assert "workbench-record.json" in names
            for required in ("result.json", "request.json", "source-manifest.json", "model-manifest.json", "checks.json", "decision.json", "diff.json", "model/MarineGateway.sysml", "sysml/validation.json"):
                assert "run/" + required in names, required
            assert json.loads(archive.read("workbench-record.json")) == record
            for source in result["source_manifest"]["files"]:
                snapshot = archive.read("run/" + source["path"])
                assert hashlib.sha256(snapshot).hexdigest() == source["sha256"]
            local_files = {"run/" + str(path.relative_to(result["run_dir"])) for path in Path(result["run_dir"]).rglob("*") if path.is_file()}
            assert set(names) - {"workbench-record.json"} == local_files, "ZIP is missing run artifacts"
        summary["cases"].append({"request": payload, "record_id": record["record_id"], "run_id": result["run_id"],
                                 "run_dir": result["run_dir"], "sysml_status": result["sysml"]["status"],
                                 "status": result["status"], "checks": [{key: item.get(key) for key in ("id", "status", "actual", "limit", "unit")} for item in result["checks"]],
                                 "named_element_count": len(result["model_elements"]), "zip_files": len(names), "zip_bytes": len(archive_bytes),
                                 "reopen_equal": True, "source_hashes_verified": True})
        (root / "app" / output_name).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print("OK", result["run_id"], result["status"], len(result["model_elements"]), "elements", len(names), "zip files", flush=True)
    history_ids = {record["record_id"] for record in read("/api/history")["runs"]}
    assert all(case["record_id"] in history_ids for case in summary["cases"])
    sources = read("/api/sources")["files"]
    assert sources
    source = read("/api/source?path=" + sources[0]["path"])
    assert isinstance(source["text"], str)
    print("ALL ACCEPTED", len(summary["cases"]), "real engine runs; history, source reads and complete ZIP verified", flush=True)


if __name__ == "__main__":
    main()
