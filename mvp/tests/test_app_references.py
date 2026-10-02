"""Manual real-engine public-reference HTTP acceptance, not part of fast unit tests."""
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
from urllib.request import Request, urlopen
import zipfile


def main():
    base = "http://127.0.0.1:8765"
    root = Path(__file__).resolve().parents[1]
    summary = {"timestamp": datetime.now(timezone.utc).isoformat(), "mode": "real HTTP + official SysML reference imports", "references": []}
    for name in ("sysml-official-vehicle", "nasa-cfe"):
        print("RUN REFERENCE", name, flush=True)
        req = Request(base + "/api/reference", data=json.dumps({"reference_name": name}).encode(), headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=240) as response:
            record = json.loads(response.read())
        result = record.get("result", {})
        assert result.get("sysml", {}).get("status") == "PASS", result
        assert result.get("budget_status") == "NOT_APPLICABLE", result
        assert result.get("status") == "UNKNOWN", result
        assert result["model_elements"] and result["model_text"]
        assert result["source_manifest"]["files"]
        assert all(check["status"] == "UNKNOWN" for check in result["checks"])
        with urlopen(base + "/api/runs/" + record["record_id"]) as response:
            assert json.loads(response.read()) == record
        with urlopen(base + "/api/runs/" + record["record_id"] + "/export.zip", timeout=240) as response:
            archive_bytes = response.read()
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            for source in result["source_manifest"]["files"]:
                assert hashlib.sha256(archive.read("run/" + source["path"])).hexdigest() == source["sha256"]
            local_files = {"run/" + str(path.relative_to(result["run_dir"])) for path in Path(result["run_dir"]).rglob("*") if path.is_file()}
            assert set(archive.namelist()) == local_files | {"workbench-record.json"}
            file_count = len(archive.namelist())
        with urlopen(base + "/api/sources?record_id=" + record["record_id"]) as response:
            files = json.loads(response.read())["files"]
        assert any(item["path"].startswith("public-data/") for item in files)
        summary["references"].append({"reference_name": name, "record_id": record["record_id"], "run_id": result["run_id"],
                                      "sysml_status": result["sysml"]["status"], "status": result["status"], "budget_status": result["budget_status"],
                                      "model_elements": len(result["model_elements"]), "parsed_element_count": result.get("parsed_element_count"),
                                      "checks": result["checks"], "zip_files": file_count, "zip_bytes": len(archive_bytes),
                                      "source_hashes_verified": True, "reopen_equal": True})
        (root / "app/reference-verification-results.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print("OK", name, result["run_id"], len(result["model_elements"]), "named elements", file_count, "ZIP files", flush=True)
    print("ALL REFERENCES ACCEPTED; semantic acceptance remains UNKNOWN", flush=True)


if __name__ == "__main__":
    main()
