"""Write the three held-out alignment tasks (ALN-01..03) and their answer keys. Paper 1's task type.

Each task gives two independently written SysML v2 packages, an "OEM" specification and a
"supplier" solution, in input/baseline/. The candidate writes one alignment package that
imports both and declares the correspondences with `alias` (definition- and feature-level
names) and `allocation` (usage-level), plus a JSON report of mappings and unmatched elements.
The sources are never edited. The answer key lists the pairs that must be declared, the pairs
that look alike but must not be declared, and the elements that must be reported unmatched.

Running this again replaces the three task directories and re-appends them to index.jsonl.
No model is called. All content is synthetic and is not an RTX specification.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

HELD = ROOT / "bench" / "tasks" / "t4_maritime_isr" / "heldout"

CONTRACT = """\
Write one SysML v2 alignment package named {package}. It must:
1. Import both source packages; declare nothing new except aliases and allocations. Do not copy or edit the source models.
2. For each definition, port or attribute of the specification that corresponds to one supplier element, declare `alias <SpecificationShortName> for <Supplier::Qualified::Name>;` using the supplier element's fully qualified name.
3. For each part usage of the specification that corresponds to a supplier part usage, declare `allocation <name> allocate <Spec::path.with.dots> to <Supplier::path.with.dots>;` with fully qualified usage paths.
4. Leave elements without a counterpart unmapped; do not force a pair when the meaning differs.
Then, in one fenced json block, report {{"mappings": [{{"oem_element": "...", "supplier_element": "...", "mapping_type": "alias|allocation", "rationale": "..."}}], "unmatched": ["qualified names with no counterpart"]}}.
Reply with one fenced sysml block followed by one fenced json block, and no other text.
"""

TASKS = [
    {
        "id": "ALN-01", "package": "AlignCamera",
        "title": "camera payload: specification vs supplier kit",
        "spec_name": "UsvPayloadSpec", "supplier_name": "OptronicsKit",
        "spec": """\
package UsvPayloadSpec {
    private import ScalarValues::*;
    port def ImageryPort;
    part def Camera {
        port imagery : ImageryPort;
        attribute drawW : Real;
    }
    part def Processor {
        port imageryIn : ImageryPort;
    }
    part usv {
        part eoCamera : Camera;
        part processor : Processor;
        connect eoCamera.imagery to processor.imageryIn;
    }
}
""",
        "supplier": """\
package OptronicsKit {
    private import ScalarValues::*;
    port def VideoOut;
    part def EoCameraUnit {
        port videoOut : VideoOut;
        attribute powerDrawW : Real;
        attribute heaterW : Real;
    }
    part def VideoSink {
        port videoIn : VideoOut;
    }
    part kit {
        part cameraUnit : EoCameraUnit;
        part recorder : VideoSink;
        connect cameraUnit.videoOut to recorder.videoIn;
    }
}
""",
        "must_map": [
            {"kind": "alias", "name": "Camera", "target": "OptronicsKit::EoCameraUnit"},
            {"kind": "alias", "name": "ImageryPort", "target": "OptronicsKit::VideoOut"},
            {"kind": "alias", "name": "imagery", "target": "OptronicsKit::EoCameraUnit::videoOut"},
            {"kind": "alias", "name": "drawW", "target": "OptronicsKit::EoCameraUnit::powerDrawW"},
            {"kind": "allocation", "from": "UsvPayloadSpec::usv.eoCamera", "to": "OptronicsKit::kit.cameraUnit"},
        ],
        "must_not_map": [
            {"kind": "alias", "name": "drawW", "target": "OptronicsKit::EoCameraUnit::heaterW",
             "why": "heaterW is a second, separate power figure; powerDrawW is the counterpart of drawW"},
        ],
        "must_report_unmatched": ["OptronicsKit::EoCameraUnit::heaterW"],
        "reference": """\
package AlignCamera {
    public import UsvPayloadSpec::*;
    private import OptronicsKit::*;
    alias Camera for OptronicsKit::EoCameraUnit;
    alias ImageryPort for OptronicsKit::VideoOut;
    alias imagery for OptronicsKit::EoCameraUnit::videoOut;
    alias drawW for OptronicsKit::EoCameraUnit::powerDrawW;
    allocation eoCameraToUnit allocate UsvPayloadSpec::usv.eoCamera to OptronicsKit::kit.cameraUnit;
}
""",
        "reference_json": {"mappings": [
            {"oem_element": "UsvPayloadSpec::Camera", "supplier_element": "OptronicsKit::EoCameraUnit", "mapping_type": "alias", "rationale": "camera part definition"},
            {"oem_element": "UsvPayloadSpec::ImageryPort", "supplier_element": "OptronicsKit::VideoOut", "mapping_type": "alias", "rationale": "imagery port definition"},
            {"oem_element": "UsvPayloadSpec::Camera::imagery", "supplier_element": "OptronicsKit::EoCameraUnit::videoOut", "mapping_type": "alias", "rationale": "imagery output port"},
            {"oem_element": "UsvPayloadSpec::Camera::drawW", "supplier_element": "OptronicsKit::EoCameraUnit::powerDrawW", "mapping_type": "alias", "rationale": "electrical draw"},
            {"oem_element": "UsvPayloadSpec::usv.eoCamera", "supplier_element": "OptronicsKit::kit.cameraUnit", "mapping_type": "allocation", "rationale": "the camera instance"},
        ], "unmatched": ["OptronicsKit::EoCameraUnit::heaterW", "OptronicsKit::VideoSink", "UsvPayloadSpec::Processor"]},
    },
    {
        "id": "ALN-02", "package": "AlignLink",
        "title": "ship data link: interface control document vs vendor radio pack",
        "spec_name": "ShipLinkIcd", "supplier_name": "VendorRadioPack",
        "spec": """\
package ShipLinkIcd {
    private import ScalarValues::*;
    port def LinkPort;
    port def HealthPort;
    part def Radio {
        port toShore : LinkPort;
        port health : HealthPort;
        attribute uplinkMbps : Real;
    }
    part def CommandShip {
        port fromUsv : LinkPort;
        port fromUav : LinkPort;
    }
    part usv {
        part radio : Radio;
    }
    part commandShip : CommandShip;
    connect usv.radio.toShore to commandShip.fromUsv;
}
""",
        "supplier": """\
package VendorRadioPack {
    private import ScalarValues::*;
    port def DataLink;
    port def StatusOut;
    port def ControlIn;
    part def RadioUnit {
        port dataOut : DataLink;
        port status : StatusOut;
        port control : ControlIn;
        attribute linkRateMbps : Real;
        attribute txPowerW : Real;
    }
    part def ShipTerminal {
        port linkA : DataLink;
        port linkB : DataLink;
    }
    part vessel {
        part radioUnit : RadioUnit;
    }
    part terminal : ShipTerminal;
    connect vessel.radioUnit.dataOut to terminal.linkA;
}
""",
        "must_map": [
            {"kind": "alias", "name": "Radio", "target": "VendorRadioPack::RadioUnit"},
            {"kind": "alias", "name": "LinkPort", "target": "VendorRadioPack::DataLink"},
            {"kind": "alias", "name": "HealthPort", "target": "VendorRadioPack::StatusOut"},
            {"kind": "alias", "name": "toShore", "target": "VendorRadioPack::RadioUnit::dataOut"},
            {"kind": "alias", "name": "health", "target": "VendorRadioPack::RadioUnit::status"},
            {"kind": "alias", "name": "uplinkMbps", "target": "VendorRadioPack::RadioUnit::linkRateMbps"},
            {"kind": "alias", "name": "CommandShip", "target": "VendorRadioPack::ShipTerminal"},
            {"kind": "allocation", "from": "ShipLinkIcd::usv.radio", "to": "VendorRadioPack::vessel.radioUnit"},
            {"kind": "allocation", "from": "ShipLinkIcd::commandShip", "to": "VendorRadioPack::terminal"},
        ],
        "must_not_map": [
            {"kind": "alias", "name": "HealthPort", "target": "VendorRadioPack::ControlIn",
             "why": "health is reported out of the radio; ControlIn carries commands into it"},
            {"kind": "alias", "name": "uplinkMbps", "target": "VendorRadioPack::RadioUnit::txPowerW",
             "why": "a data rate is not a transmit power"},
        ],
        "must_report_unmatched": ["VendorRadioPack::ControlIn", "VendorRadioPack::RadioUnit::txPowerW"],
        "reference": """\
package AlignLink {
    public import ShipLinkIcd::*;
    private import VendorRadioPack::*;
    alias Radio for VendorRadioPack::RadioUnit;
    alias LinkPort for VendorRadioPack::DataLink;
    alias HealthPort for VendorRadioPack::StatusOut;
    alias toShore for VendorRadioPack::RadioUnit::dataOut;
    alias health for VendorRadioPack::RadioUnit::status;
    alias uplinkMbps for VendorRadioPack::RadioUnit::linkRateMbps;
    alias CommandShip for VendorRadioPack::ShipTerminal;
    allocation radioToUnit allocate ShipLinkIcd::usv.radio to VendorRadioPack::vessel.radioUnit;
    allocation shipToTerminal allocate ShipLinkIcd::commandShip to VendorRadioPack::terminal;
}
""",
        "reference_json": {"mappings": [
            {"oem_element": "ShipLinkIcd::Radio", "supplier_element": "VendorRadioPack::RadioUnit", "mapping_type": "alias", "rationale": "radio definition"},
            {"oem_element": "ShipLinkIcd::LinkPort", "supplier_element": "VendorRadioPack::DataLink", "mapping_type": "alias", "rationale": "data link port"},
            {"oem_element": "ShipLinkIcd::HealthPort", "supplier_element": "VendorRadioPack::StatusOut", "mapping_type": "alias", "rationale": "health status out"},
            {"oem_element": "ShipLinkIcd::Radio::toShore", "supplier_element": "VendorRadioPack::RadioUnit::dataOut", "mapping_type": "alias", "rationale": "the link port on the radio"},
            {"oem_element": "ShipLinkIcd::Radio::health", "supplier_element": "VendorRadioPack::RadioUnit::status", "mapping_type": "alias", "rationale": "the health port on the radio"},
            {"oem_element": "ShipLinkIcd::Radio::uplinkMbps", "supplier_element": "VendorRadioPack::RadioUnit::linkRateMbps", "mapping_type": "alias", "rationale": "link data rate"},
            {"oem_element": "ShipLinkIcd::CommandShip", "supplier_element": "VendorRadioPack::ShipTerminal", "mapping_type": "alias", "rationale": "the receiving terminal"},
            {"oem_element": "ShipLinkIcd::usv.radio", "supplier_element": "VendorRadioPack::vessel.radioUnit", "mapping_type": "allocation", "rationale": "the radio instance"},
            {"oem_element": "ShipLinkIcd::commandShip", "supplier_element": "VendorRadioPack::terminal", "mapping_type": "allocation", "rationale": "the ship terminal instance"},
        ], "unmatched": ["VendorRadioPack::ControlIn", "VendorRadioPack::RadioUnit::control", "VendorRadioPack::RadioUnit::txPowerW", "ShipLinkIcd::CommandShip::fromUav"]},
    },
    {
        "id": "ALN-03", "package": "AlignRadar",
        "title": "UAV sensors: definitions versus instances",
        "spec_name": "UavSensorSpec", "supplier_name": "RadarVendor",
        "spec": """\
package UavSensorSpec {
    private import ScalarValues::*;
    part def SearchRadar {
        attribute rangeKm : Real;
    }
    part def Camera;
    part uav {
        part searchRadar : SearchRadar;
        part eoCamera : Camera;
    }
}
""",
        "supplier": """\
package RadarVendor {
    private import ScalarValues::*;
    part def RadarModule_def {
        attribute maxRangeKm : Real;
        attribute massKg : Real;
    }
    part def GimbalCamera_def;
    part payload {
        part radar : RadarModule_def;
        part gimbal : GimbalCamera_def;
    }
}
""",
        "must_map": [
            {"kind": "alias", "name": "SearchRadar", "target": "RadarVendor::RadarModule_def"},
            {"kind": "alias", "name": "rangeKm", "target": "RadarVendor::RadarModule_def::maxRangeKm"},
            {"kind": "alias", "name": "Camera", "target": "RadarVendor::GimbalCamera_def"},
            {"kind": "allocation", "from": "UavSensorSpec::uav.searchRadar", "to": "RadarVendor::payload.radar"},
            {"kind": "allocation", "from": "UavSensorSpec::uav.eoCamera", "to": "RadarVendor::payload.gimbal"},
        ],
        "must_not_map": [
            {"kind": "alias", "name": "SearchRadar", "target": "RadarVendor::payload::radar",
             "why": "a definition must not be aliased to a usage; the usage pair is an allocation"},
            {"kind": "alias", "name": "searchRadar", "target": "RadarVendor::RadarModule_def",
             "why": "a usage must not be aliased to a definition"},
        ],
        "must_report_unmatched": ["RadarVendor::RadarModule_def::massKg"],
        "reference": """\
package AlignRadar {
    public import UavSensorSpec::*;
    private import RadarVendor::*;
    alias SearchRadar for RadarVendor::RadarModule_def;
    alias rangeKm for RadarVendor::RadarModule_def::maxRangeKm;
    alias Camera for RadarVendor::GimbalCamera_def;
    allocation radarToModule allocate UavSensorSpec::uav.searchRadar to RadarVendor::payload.radar;
    allocation cameraToGimbal allocate UavSensorSpec::uav.eoCamera to RadarVendor::payload.gimbal;
}
""",
        "reference_json": {"mappings": [
            {"oem_element": "UavSensorSpec::SearchRadar", "supplier_element": "RadarVendor::RadarModule_def", "mapping_type": "alias", "rationale": "radar definition"},
            {"oem_element": "UavSensorSpec::SearchRadar::rangeKm", "supplier_element": "RadarVendor::RadarModule_def::maxRangeKm", "mapping_type": "alias", "rationale": "range attribute"},
            {"oem_element": "UavSensorSpec::Camera", "supplier_element": "RadarVendor::GimbalCamera_def", "mapping_type": "alias", "rationale": "camera definition"},
            {"oem_element": "UavSensorSpec::uav.searchRadar", "supplier_element": "RadarVendor::payload.radar", "mapping_type": "allocation", "rationale": "radar instance"},
            {"oem_element": "UavSensorSpec::uav.eoCamera", "supplier_element": "RadarVendor::payload.gimbal", "mapping_type": "allocation", "rationale": "camera instance"},
        ], "unmatched": ["RadarVendor::RadarModule_def::massKg"]},
    },
]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    for spec in TASKS:
        folder = HELD / spec["id"]
        if folder.exists():
            shutil.rmtree(folder)
        case = {"id": spec["id"], "type": "ALN", "scenario_family": "t4_maritime_isr", "split": "heldout",
                "package": spec["package"], "sources": [f"{spec['spec_name']}.sysml", f"{spec['supplier_name']}.sysml"],
                "synthetic": True, "status": "single-author", "second_reviewer": "pending"}
        _write(folder / "case.yaml", yaml.safe_dump(case, sort_keys=False))
        _write(folder / "input" / "requirements.md",
               f"# {spec['id']} — synthetic, not an RTX specification\n\n"
               f"Align two independently written models of the {spec['title']}. The specification package is "
               f"`{spec['spec_name']}`; the supplier package is `{spec['supplier_name']}`. Both are given below as baseline files and must not be changed.\n\n"
               + CONTRACT.format(package=spec["package"]))
        _write(folder / "input" / "baseline" / f"{spec['spec_name']}.sysml", spec["spec"])
        _write(folder / "input" / "baseline" / f"{spec['supplier_name']}.sysml", spec["supplier"])
        _write(folder / "gold" / "reference" / f"{spec['package']}.sysml", spec["reference"])
        _write(folder / "gold" / "reference" / "report.json", json.dumps(spec["reference_json"], indent=2) + "\n")
        assertions = {"task_id": spec["id"], "package": spec["package"], "status": "single-author",
                      "sources": case["sources"], "must_map": spec["must_map"], "must_not_map": spec["must_not_map"],
                      "must_report_unmatched": spec["must_report_unmatched"]}
        _write(folder / "gold" / "assertions.yaml", yaml.safe_dump(assertions, sort_keys=False))
    index = HELD / "index.jsonl"
    lines = [line for line in index.read_text(encoding="utf-8").splitlines() if line.strip() and '"ALN-' not in line]
    for spec in TASKS:
        lines.append(json.dumps({"id": spec["id"], "type": "ALN", "path": f"bench/tasks/t4_maritime_isr/heldout/{spec['id']}"}))
    index.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {len(TASKS)} ALN tasks; index has {len(lines)} tasks")


if __name__ == "__main__":
    main()
