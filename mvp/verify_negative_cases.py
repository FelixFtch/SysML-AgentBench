"""Adversarial integration checks against the real official SysML implementation."""
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid

from mvp.engine import ModelView, dump, evaluate, exported_elements, model_diff
from mvp.models.render_model import write_model_package
from mvp.toolchain.validate import validate_package


def main():
    root = Path(__file__).resolve().parent / "verification" / ("negative-" + uuid.uuid4().hex[:8])
    root.mkdir(parents=True)
    results = []
    baseline_elements = None
    for name in ("control", "missing-supplier", "deleted-recording-connection", "wrong-power-unit",
                 "wrong-power-factor", "unauthorized-upload-reduction", "miswired-recording-connection"):
        folder = root / name
        package = write_model_package(folder / "model", "baseline")
        files = package["model_files"]
        model = Path(package["model_path"])
        if name == "missing-supplier":
            files = [f for f in files if not f.endswith("PayloadSupplier.sysml")]
        elif name == "deleted-recording-connection":
            text = model.read_text()
            line = "        connection recordingConnection connect processor.rawToRecorder to recorder.rawInput;\n"
            assert line in text
            model.write_text(text.replace(line, ""))
        elif name == "wrong-power-unit":
            text = model.read_text()
            assert "totalPowerW * 1[W]" in text
            model.write_text(text.replace("totalPowerW * 1[W]", "totalPowerW * 1[m]"))
        elif name == "wrong-power-factor":
            text = model.read_text()
            model.write_text(text.replace("totalPowerW * 1[W]", "totalPowerW * 1000[W]"))
        elif name == "unauthorized-upload-reduction":
            text = model.read_text()
            assert "attribute :>> uploadRateMbps = 6;" in text
            model.write_text(text.replace("attribute :>> uploadRateMbps = 6;", "attribute :>> uploadRateMbps = 2;"))
        elif name == "miswired-recording-connection":
            text = model.read_text()
            model.write_text(text.replace("recordingConnection connect processor.rawToRecorder to recorder.rawInput;",
                                          "recordingConnection connect acquisition.toProcessor to processor.fromAcquisition;"))
        validation = validate_package(files, "MarineGateway", str(folder / "sysml"))
        row = {"case": name, "official_language_status": validation["status"],
               "diagnostics": validation["diagnostics"], "validation": str(folder / "sysml/validation.json")}
        if name == "missing-supplier":
            assert validation["status"] == "FAIL", row
            assert any("PayloadSupplier" in d["message"] or "ObservationPort" in d["message"] for d in validation["diagnostics"])
        else:
            assert validation["status"] == "PASS", row
            view = ModelView(exported_elements(json.loads(Path(validation["model_json_path"]).read_text())),
                             json.loads(Path(validation["ast_json_path"]).read_text()))
            checks = evaluate(view)
            row["checks"] = checks
            lookup = {c["id"]: c for c in checks}
            if name == "control":
                assert all(c["status"] == "PASS" for c in checks if c["id"] != "R-RUNTIME-001")
                baseline_elements = view.named_elements()
            elif name == "deleted-recording-connection":
                assert lookup["R-TOPOLOGY-001"]["status"] == "FAIL"
                delta = model_diff(view.named_elements(), baseline_elements)
                assert any(e["name"] == "recordingConnection" for e in delta["removed"])
                row["diff"] = delta
            elif name == "wrong-power-unit":
                assert lookup["D-UNIT-CONTRACT"]["status"] == "FAIL"
                assert lookup["D-UNIT-CONTRACT"]["actual"]["totalPower"] == ["SI::metre"]
            elif name == "wrong-power-factor":
                assert lookup["D-UNIT-CONTRACT"]["status"] == "FAIL"
            elif name == "unauthorized-upload-reduction":
                assert lookup["D-UPLOAD-POLICY"]["status"] == "FAIL"
            elif name == "miswired-recording-connection":
                assert lookup["R-TOPOLOGY-001"]["status"] == "FAIL"
        row["expected_behavior_verified"] = True
        results.append(row)
        dump(root / "summary.json", {"created_at": datetime.now(timezone.utc).isoformat(), "results": results})
        print(name, "verified", flush=True)
    print(root / "summary.json")


if __name__ == "__main__":
    main()
