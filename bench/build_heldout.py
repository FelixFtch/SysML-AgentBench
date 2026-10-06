"""Write the 24 held-out maritime tasks and their answer keys.

Running this again replaces those task directories. It does not call a model.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
HELD = ROOT / "bench" / "tasks" / "t4_maritime_isr" / "heldout"
SCENARIO = ROOT / "scenario" / "maritime-isr" / "MaritimeISR.sysml"

USV_LINK = """\
package UsvLink {
    port def ImageryPort;
    port def LinkPort;
    part def Camera { port imagery : ImageryPort; }
    part def Processor {
        port imageryIn : ImageryPort;
        port uplink : LinkPort;
    }
    part def Radio {
        port fromProcessor : LinkPort;
        port toShore : LinkPort;
    }
    part def CommandShip { port fromUsv : LinkPort; }
    part usv {
        part camera : Camera;
        part processor : Processor;
        part radio : Radio;
    }
    part commandShip : CommandShip;
    connect usv.camera.imagery to usv.processor.imageryIn;
    connect usv.processor.uplink to usv.radio.fromProcessor;
    connect usv.radio.toShore to commandShip.fromUsv;
}
"""

UAV_SEARCH = """\
package UavSearch {
    port def TrackPort;
    port def ImageryPort;
    port def LinkPort;
    part def Radar { port tracks : TrackPort; }
    part def Camera { port imagery : ImageryPort; }
    part def Processor {
        port trackIn : TrackPort;
        port imageryIn : ImageryPort;
        port uplink : LinkPort;
    }
    part def Radio {
        port fromProcessor : LinkPort;
        port toShore : LinkPort;
    }
    part uav {
        part searchRadar : Radar;
        part eoCamera : Camera;
        part processor : Processor;
        part radio : Radio;
    }
    connect uav.searchRadar.tracks to uav.processor.trackIn;
    connect uav.eoCamera.imagery to uav.processor.imageryIn;
    connect uav.processor.uplink to uav.radio.fromProcessor;
}
"""

FUSION = """\
package FusionNode {
    private import ScalarValues::*;
    port def LinkPort;
    part def Processor { port trackIn : LinkPort; }
    part commandShip {
        port fromUsv : LinkPort;
        port fromUav : LinkPort;
        part fusion : Processor;
        attribute fusionLatencyS : Real = 2.0;
    }
}
"""

SHORE = """\
package ShoreArchive {
    private import ScalarValues::*;
    port def LinkPort;
    part def Processor;
    part shore {
        port fromCommand : LinkPort;
        part archive : Processor;
        attribute backhaulMbps : Real = 50.0;
        attribute archiveDays : Real = 30.0;
    }
    requirement def ShoreArchiveRetention {
        doc /* Shore archive keeps relayed tracks for 30 days. */
    }
}
"""

FOUR = """\
package FourNode {
    port def LinkPort;
    part def Radio { port toCommand : LinkPort; }
    part def ShoreStation { port fromCommand : LinkPort; }
    part usv { part radio : Radio; }
    part uav { part radio : Radio; }
    part commandShip {
        port fromUsv : LinkPort;
        port fromUav : LinkPort;
        port toShore : LinkPort;
    }
    part shore : ShoreStation;
    connect usv.radio.toCommand to commandShip.fromUsv;
    connect uav.radio.toCommand to commandShip.fromUav;
    connect commandShip.toShore to shore.fromCommand;
}
"""

MOD1_BASE = """\
package UsvPlain {
    private import ScalarValues::*;
    port def ImageryPort;
    port def TrackPort;
    port def LinkPort;
    part def Camera { port imagery : ImageryPort; }
    part def AisReceiver { port tracks : TrackPort; }
    part def Processor {
        port imageryIn : ImageryPort;
        port trackIn : TrackPort;
        port uplink : LinkPort;
    }
    part def Radio { port fromProcessor : LinkPort; port toShore : LinkPort; }
    part usv {
        part eoCamera : Camera;
        part ais : AisReceiver;
        part processor : Processor;
        part radio : Radio;
        attribute powerLimitW : Real = 60.0;
    }
    connect usv.eoCamera.imagery to usv.processor.imageryIn;
    connect usv.ais.tracks to usv.processor.trackIn;
    connect usv.processor.uplink to usv.radio.fromProcessor;
}
"""

MOD1_GOLD = MOD1_BASE.replace(
    "        part eoCamera : Camera;\n",
    "        part eoCamera : Camera;\n        part irCamera : Camera;\n",
).replace(
    "    connect usv.eoCamera.imagery to usv.processor.imageryIn;\n",
    "    connect usv.eoCamera.imagery to usv.processor.imageryIn;\n"
    "    connect usv.irCamera.imagery to usv.processor.imageryIn;\n",
)

MOD2_BASE = """\
package VesselAlign {
    port def ImageryPort;
    port def TrackPort;
    part def Camera { port imagery : ImageryPort; }
    part def AisReceiver { port tracks : TrackPort; }
    part def Processor {
        port imageryIn : ImageryPort;
        port trackIn : TrackPort;
    }
    part vessel {
        part camera : Camera;
        part processor : Processor;
    }
    connect vessel.camera.imagery to vessel.processor.imageryIn;
}
"""

MOD2_GOLD = MOD2_BASE.replace(
    "        part camera : Camera;\n        part processor : Processor;\n",
    "        part camera : Camera;\n        part ais : AisReceiver;\n        part processor : Processor;\n",
).replace(
    "    connect vessel.camera.imagery to vessel.processor.imageryIn;\n}\n",
    "    connect vessel.camera.imagery to vessel.processor.imageryIn;\n"
    "    connect vessel.ais.tracks to vessel.processor.trackIn;\n"
    "    requirement def TimeAlign {\n"
    "        doc /* Tracks and imagery share a timestamp. */\n"
    "    }\n}\n",
)

MOD3_BASE = """\
package ShoreHop {
    port def LinkPort;
    part def Radio { port fromProcessor : LinkPort; port toShore : LinkPort; }
    part def Processor { port uplink : LinkPort; }
    part def ShoreStation { port fromVessel : LinkPort; }
    part vessel {
        part processor : Processor;
        part radio : Radio;
    }
    part shore : ShoreStation;
    connect vessel.processor.uplink to vessel.radio.fromProcessor;
}
"""

MOD3_GOLD = MOD3_BASE.replace(
    "    connect vessel.processor.uplink to vessel.radio.fromProcessor;\n}\n",
    "    connect vessel.processor.uplink to vessel.radio.fromProcessor;\n"
    "    connect vessel.radio.toShore to shore.fromVessel;\n}\n",
)

MOD4_BASE = """\
package RadioHealth {
    private import ScalarValues::*;
    port def LinkPort;
    part usv {
        attribute uplinkMbps : Real = 8.0;
        part radio { port fromProcessor : LinkPort; }
    }
}
"""

MOD4_GOLD = MOD4_BASE.replace(
    "part radio { port fromProcessor : LinkPort; }",
    "part radio {\n            port fromProcessor : LinkPort;\n            port health : LinkPort;\n        }",
)

MOD5_BASE = """\
package PowerBudget {
    private import ScalarValues::*;
    part usv {
        attribute powerLimitW : Real = 60.0;
        part eoCamera { attribute drawW : Real = 41.0; }
        part computer { attribute drawW : Real = 25.0; }
    }
}
"""

MOD5_GOLD = MOD5_BASE.replace(
    "        part computer { attribute drawW : Real = 25.0; }\n",
    "        part computer { attribute drawW : Real = 25.0; }\n"
    "        part irCamera { attribute drawW : Real = 12.0; }\n",
)

RT_MODELS = {
    "RT-01": """\
package RoundTripShare {
    requirement def Share {
        doc /* The unmanned surface vessel sends camera imagery to the shore. */
    }
}
""",
    "RT-02": """\
package RoundTripPower {
    private import ScalarValues::*;
    part usv { attribute powerLimitW : Real = 60.0; }
    requirement def KeepPower {
        doc /* The unmanned surface vessel power limit is 60 W. */
    }
}
""",
    "RT-03": """\
package RoundTripRadar {
    requirement def RadarShare {
        doc /* The UAV radar shares tracks with the command ship. */
    }
}
""",
    "RT-04": """\
package RoundTripArchive {
    private import ScalarValues::*;
    part shore {
        attribute backhaulMbps : Real = 50.0;
        attribute archiveDays : Real = 30.0;
    }
    requirement def Archive {
        doc /* The shore archive keeps tracks for 30 days on a 50 Mbit/s backhaul. */
    }
}
""",
    "RT-05": """\
package RoundTripFusion {
    private import ScalarValues::*;
    part commandShip {
        port fromUsv;
        port fromUav;
        attribute fusionLatencyS : Real = 2.0;
    }
    requirement def Fusion {
        doc /* Fusion latency is 2 seconds and the command ship accepts two uplinks. */
    }
}
""",
}


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _case(task_id: str, kind: str, package: str | None) -> dict:
    return {"id": task_id, "type": kind, "scenario_family": "t4_maritime_isr", "split": "heldout",
            "package": package, "synthetic": True, "status": "single-author",
            "second_reviewer": "pending"}


def _model_task(spec: dict) -> None:
    folder = HELD / spec["id"]
    if folder.exists():
        shutil.rmtree(folder)
    _write(folder / "case.yaml", yaml.safe_dump(_case(spec["id"], spec["type"], spec["package"]), sort_keys=False))
    _write(folder / "input" / "requirements.md", spec["requirements"])
    if spec.get("baseline"):
        _write(folder / "input" / "baseline" / f"{spec['package']}.sysml", spec["baseline"])
    _write(folder / "gold" / "reference" / f"{spec['package']}.sysml", spec["sysml"])
    assertions = {"task_id": spec["id"], "package": spec["package"], "status": "single-author",
                  "must_exist": [{"qualified_name": name} for name in spec["must_exist"]],
                  "must_connect": spec.get("must_connect") or [],
                  "must_preserve": spec.get("must_preserve") or []}
    if spec.get("checks_expected"):
        assertions["checks_expected"] = spec["checks_expected"]
    _write(folder / "gold" / "assertions.yaml", yaml.safe_dump(assertions, sort_keys=False))


def main() -> None:
    HELD.mkdir(parents=True, exist_ok=True)
    models = [
        {"id": "GEN-01", "type": "GEN", "package": "UsvLink", "sysml": USV_LINK,
         "requirements": """# GEN-01 — synthetic, not an RTX specification

Package name: UsvLink

Write one SysML v2 package. Use these names and no others.

1. Port definitions ImageryPort and LinkPort.
2. Part definition Camera with port imagery of type ImageryPort.
3. Part definition Processor with port imageryIn of type ImageryPort and port uplink of type LinkPort.
4. Part definition Radio with port fromProcessor of type LinkPort and port toShore of type LinkPort.
5. Part definition CommandShip with port fromUsv of type LinkPort.
6. Part usage usv containing part usages camera, processor, and radio of those definitions.
7. Part usage commandShip of CommandShip.
8. Connections: usv.camera.imagery to usv.processor.imageryIn; usv.processor.uplink to usv.radio.fromProcessor; usv.radio.toShore to commandShip.fromUsv.
Do not invent numeric limits.
""",
         "must_exist": ["UsvLink::ImageryPort", "UsvLink::LinkPort", "UsvLink::Camera", "UsvLink::Processor",
                        "UsvLink::Radio", "UsvLink::CommandShip", "UsvLink::usv", "UsvLink::usv::camera",
                        "UsvLink::usv::processor", "UsvLink::usv::radio", "UsvLink::commandShip"],
         "must_connect": [["UsvLink::usv::camera::imagery", "UsvLink::usv::processor::imageryIn"],
                          ["UsvLink::usv::processor::uplink", "UsvLink::usv::radio::fromProcessor"],
                          ["UsvLink::usv::radio::toShore", "UsvLink::commandShip::fromUsv"]]},
        {"id": "GEN-02", "type": "GEN", "package": "UavSearch", "sysml": UAV_SEARCH,
         "requirements": """# GEN-02 — synthetic, not an RTX specification

Package name: UavSearch

1. Port definitions TrackPort, ImageryPort, and LinkPort.
2. Part definition Radar with port tracks of type TrackPort.
3. Part definition Camera with port imagery of type ImageryPort.
4. Part definition Processor with ports trackIn of type TrackPort, imageryIn of type ImageryPort, and uplink of type LinkPort.
5. Part definition Radio with ports fromProcessor and toShore, both of type LinkPort.
6. Part usage uav containing searchRadar, eoCamera, processor, and radio.
7. Connections: uav.searchRadar.tracks to uav.processor.trackIn; uav.eoCamera.imagery to uav.processor.imageryIn; uav.processor.uplink to uav.radio.fromProcessor.
Do not invent numeric limits.
""",
         "must_exist": ["UavSearch::Radar", "UavSearch::Camera", "UavSearch::Processor", "UavSearch::Radio",
                        "UavSearch::uav", "UavSearch::uav::searchRadar", "UavSearch::uav::eoCamera",
                        "UavSearch::uav::processor", "UavSearch::uav::radio"],
         "must_connect": [["UavSearch::uav::searchRadar::tracks", "UavSearch::uav::processor::trackIn"],
                          ["UavSearch::uav::eoCamera::imagery", "UavSearch::uav::processor::imageryIn"],
                          ["UavSearch::uav::processor::uplink", "UavSearch::uav::radio::fromProcessor"]]},
        {"id": "GEN-03", "type": "GEN", "package": "FusionNode", "sysml": FUSION,
         "requirements": """# GEN-03 — synthetic, not an RTX specification

Package name: FusionNode

1. Port definition LinkPort.
2. Part definition Processor with port trackIn of type LinkPort.
3. Part usage commandShip with ports fromUsv and fromUav of type LinkPort.
4. Nested part usage fusion of Processor.
5. Attribute fusionLatencyS on commandShip, type Real, value 2.0.
Do not add other numbers.
""",
         "must_exist": ["FusionNode::LinkPort", "FusionNode::Processor", "FusionNode::commandShip",
                        "FusionNode::commandShip::fromUsv", "FusionNode::commandShip::fromUav",
                        "FusionNode::commandShip::fusion", "FusionNode::commandShip::fusionLatencyS"],
         "must_preserve": [{"qualified_name": "FusionNode::commandShip::fusionLatencyS", "value": 2.0}]},
        {"id": "GEN-04", "type": "GEN", "package": "ShoreArchive", "sysml": SHORE,
         "requirements": """# GEN-04 — synthetic, not an RTX specification

Package name: ShoreArchive

1. Port definition LinkPort and part definition Processor.
2. Part usage shore with port fromCommand of type LinkPort and nested part archive of Processor.
3. Attribute backhaulMbps value 50.0 and attribute archiveDays value 30.0, both Real, both on shore.
4. Requirement definition ShoreArchiveRetention whose doc comment says the shore archive keeps relayed tracks for 30 days.
""",
         "must_exist": ["ShoreArchive::shore", "ShoreArchive::shore::fromCommand", "ShoreArchive::shore::archive",
                        "ShoreArchive::shore::backhaulMbps", "ShoreArchive::shore::archiveDays",
                        "ShoreArchive::ShoreArchiveRetention"],
         "must_preserve": [{"qualified_name": "ShoreArchive::shore::backhaulMbps", "value": 50.0},
                           {"qualified_name": "ShoreArchive::shore::archiveDays", "value": 30.0}]},
        {"id": "GEN-05", "type": "GEN", "package": "FourNode", "sysml": FOUR,
         "requirements": """# GEN-05 — synthetic, not an RTX specification

Package name: FourNode

1. Port definition LinkPort.
2. Part definition Radio with port toCommand of type LinkPort.
3. Part definition ShoreStation with port fromCommand of type LinkPort.
4. Part usages usv and uav, each containing part radio of Radio.
5. Part usage commandShip with ports fromUsv, fromUav, and toShore, each of type LinkPort.
6. Part usage shore of ShoreStation.
7. Connections: usv.radio.toCommand to commandShip.fromUsv; uav.radio.toCommand to commandShip.fromUav; commandShip.toShore to shore.fromCommand.
Do not invent numeric limits.
""",
         "must_exist": ["FourNode::usv", "FourNode::uav", "FourNode::commandShip", "FourNode::shore",
                        "FourNode::usv::radio", "FourNode::uav::radio"],
         "must_connect": [["FourNode::usv::radio::toCommand", "FourNode::commandShip::fromUsv"],
                          ["FourNode::uav::radio::toCommand", "FourNode::commandShip::fromUav"],
                          ["FourNode::commandShip::toShore", "FourNode::shore::fromCommand"]]},
        {"id": "MOD-01", "type": "MOD", "package": "UsvPlain", "baseline": MOD1_BASE, "sysml": MOD1_GOLD,
         "requirements": """# MOD-01 — synthetic, not an RTX specification

Package name stays UsvPlain. Edit the baseline.

Add part usage irCamera of Camera inside usv. Connect usv.irCamera.imagery to usv.processor.imageryIn.
Keep the existing camera, AIS, and radio connections. Keep powerLimitW equal to 60.0.
Do not add other numbers.
""",
         "must_exist": ["UsvPlain::usv::irCamera", "UsvPlain::usv::eoCamera", "UsvPlain::usv::ais",
                        "UsvPlain::usv::powerLimitW"],
         "must_connect": [["UsvPlain::usv::irCamera::imagery", "UsvPlain::usv::processor::imageryIn"],
                          ["UsvPlain::usv::eoCamera::imagery", "UsvPlain::usv::processor::imageryIn"],
                          ["UsvPlain::usv::ais::tracks", "UsvPlain::usv::processor::trackIn"]],
         "must_preserve": [{"qualified_name": "UsvPlain::usv::powerLimitW", "value": 60.0}]},
        {"id": "MOD-02", "type": "MOD", "package": "VesselAlign", "baseline": MOD2_BASE, "sysml": MOD2_GOLD,
         "requirements": """# MOD-02 — synthetic, not an RTX specification

Package name stays VesselAlign. Edit the baseline.

Add part usage ais of AisReceiver inside vessel. Connect vessel.ais.tracks to vessel.processor.trackIn.
Add requirement definition TimeAlign whose doc comment says tracks and imagery share a timestamp.
Keep the camera connection. Do not invent numeric limits.
""",
         "must_exist": ["VesselAlign::vessel::ais", "VesselAlign::vessel::camera", "VesselAlign::TimeAlign"],
         "must_connect": [["VesselAlign::vessel::camera::imagery", "VesselAlign::vessel::processor::imageryIn"],
                          ["VesselAlign::vessel::ais::tracks", "VesselAlign::vessel::processor::trackIn"]]},
        {"id": "MOD-03", "type": "MOD", "package": "ShoreHop", "baseline": MOD3_BASE, "sysml": MOD3_GOLD,
         "requirements": """# MOD-03 — synthetic, not an RTX specification

Package name stays ShoreHop. Edit the baseline.

Add a connection from vessel.radio.toShore to shore.fromVessel.
Keep the connection from vessel.processor.uplink to vessel.radio.fromProcessor.
Do not invent numeric limits.
""",
         "must_exist": ["ShoreHop::vessel::radio", "ShoreHop::shore"],
         "must_connect": [["ShoreHop::vessel::processor::uplink", "ShoreHop::vessel::radio::fromProcessor"],
                          ["ShoreHop::vessel::radio::toShore", "ShoreHop::shore::fromVessel"]]},
        {"id": "MOD-04", "type": "MOD", "package": "RadioHealth", "baseline": MOD4_BASE, "sysml": MOD4_GOLD,
         "requirements": """# MOD-04 — synthetic, not an RTX specification

Package name stays RadioHealth. Edit the baseline.

Add port health of type LinkPort on usv.radio.
Keep uplinkMbps equal to 8.0. Do not add other numbers.
""",
         "must_exist": ["RadioHealth::usv::radio::health", "RadioHealth::usv::uplinkMbps"],
         "must_preserve": [{"qualified_name": "RadioHealth::usv::uplinkMbps", "value": 8.0}]},
        {"id": "MOD-05", "type": "MOD", "package": "PowerBudget", "baseline": MOD5_BASE, "sysml": MOD5_GOLD,
         "requirements": """# MOD-05 — synthetic, not an RTX specification

Package name stays PowerBudget. Edit the baseline.

Add part irCamera inside usv with attribute drawW equal to 12.0.
Keep powerLimitW equal to 60.0, eoCamera.drawW equal to 41.0, and computer.drawW equal to 25.0.
Do not change 60 to make the power sum fit.
""",
         "must_exist": ["PowerBudget::usv::irCamera", "PowerBudget::usv::irCamera::drawW",
                        "PowerBudget::usv::eoCamera::drawW", "PowerBudget::usv::computer::drawW",
                        "PowerBudget::usv::powerLimitW"],
         "must_preserve": [{"qualified_name": "PowerBudget::usv::powerLimitW", "value": 60.0},
                           {"qualified_name": "PowerBudget::usv::eoCamera::drawW", "value": 41.0},
                           {"qualified_name": "PowerBudget::usv::computer::drawW", "value": 25.0},
                           {"qualified_name": "PowerBudget::usv::irCamera::drawW", "value": 12.0}],
         "checks_expected": [{"id": "R-POWER-001", "status": "FAIL", "total_w": 78.0, "limit_w": 60.0}]},
    ]
    for spec in models:
        _model_task(spec)

    queries = [
        ("QRY-01", "Which four platform part usages does the model contain? Reply with JSON "
         '{"platforms": ["qualified names"]}. The names are the part usages usv, uav, commandShip, and shore.',
         {"platforms": ["MaritimeISR::usv", "MaritimeISR::uav", "MaritimeISR::commandShip", "MaritimeISR::shore"]}),
        ("QRY-02", "What is the parsed value of UnmannedSurfaceVessel powerLimitW? Reply with JSON "
         '{"attribute": "qualified name", "value": number}.',
         {"attribute": "MaritimeISR::UnmannedSurfaceVessel::powerLimitW", "value": 60}),
        ("QRY-03", "How many connect statements have an endpoint on commandShip? Reply with JSON "
         '{"connections": number}.',
         {"connections": 3}),
        ("QRY-04", "Which part usages are nested in part definition FixedWingUav? Reply with JSON "
         '{"parts": ["qualified names"]}.',
         {"parts": ["MaritimeISR::FixedWingUav::eoCamera", "MaritimeISR::FixedWingUav::searchRadar",
                    "MaritimeISR::FixedWingUav::processor", "MaritimeISR::FixedWingUav::radio"]}),
        ("QRY-05", "Read the three numeric attributes of part definition UnmannedSurfaceVessel. Reply with JSON "
         '{"powerLimitW": number, "uplinkMbps": number, "storageGB": number}.',
         {"powerLimitW": 60, "uplinkMbps": 8, "storageGB": 128}),
    ]
    for task_id, question, answer in queries:
        folder = HELD / task_id
        if folder.exists():
            shutil.rmtree(folder)
        _write(folder / "case.yaml", yaml.safe_dump(_case(task_id, "QRY", "MaritimeISR"), sort_keys=False))
        _write(folder / "input" / "requirements.md", f"# {task_id} — synthetic, not an RTX specification\n\n{question}\n")
        shutil.copy2(SCENARIO, folder / "input" / "model.sysml")
        _write(folder / "gold" / "answer.json", json.dumps(answer, indent=2) + "\n")

    ambiguities = [
        ("AMB-01", "Tracks must be shared from the vessel to the shore in real time. No latency and no bandwidth are given.",
         [["latency", "delay"], ["bandwidth", "bit rate", "mbps", "mbit"]]),
        ("AMB-02", "The vessel power use must be as low as possible. No watt limit is given.",
         [["watt", "power limit", "how many watts"]]),
        ("AMB-03", "The shore keeps tracks for 30 days and has 128 GB of storage. No data rate is given, so the storage number cannot be checked.",
         [["data rate", "bit rate", "bandwidth", "mbps", "mbit"]]),
        ("AMB-04", "One sentence says the uplink is 8. Another sentence says the uplink is 8 MHz. The unit is not settled.",
         [["unit", "mbit", "mbps", "mhz"]]),
    ]
    for task_id, text, groups in ambiguities:
        folder = HELD / task_id
        if folder.exists():
            shutil.rmtree(folder)
        _write(folder / "case.yaml", yaml.safe_dump(_case(task_id, "AMB", None), sort_keys=False))
        _write(folder / "input" / "requirements.md",
               f"# {task_id} — synthetic, not an RTX specification\n\n{text}\n\n"
               "If a number or unit needed for a check is missing or in conflict, ask. Do not invent a value and do not write SysML.\n")
        _write(folder / "gold" / "assertions.yaml", yaml.safe_dump(
            {"task_id": task_id, "should_ask": groups, "must_not_invent_number": True}, sort_keys=False))

    phrases = {
        "RT-01": ["unmanned surface vessel", "camera", "shore"],
        "RT-02": ["power limit", "60"],
        "RT-03": ["radar", "command ship"],
        "RT-04": ["30 days", "50"],
        "RT-05": ["2 seconds", "two uplinks"],
    }
    for task_id, model in RT_MODELS.items():
        folder = HELD / task_id
        if folder.exists():
            shutil.rmtree(folder)
        package = model.split()[1]
        _write(folder / "case.yaml", yaml.safe_dump(_case(task_id, "RT", package), sort_keys=False))
        _write(folder / "input" / "requirements.md",
               f"# {task_id} — synthetic, not an RTX specification\n\n"
               "Read the given model and restate its requirements in sentences. "
               "Do not add facts that are not in the model.\n")
        _write(folder / "input" / "model.sysml", model)
        _write(folder / "gold" / "assertions.yaml", yaml.safe_dump(
            {"task_id": task_id, "must_mention": phrases[task_id]}, sort_keys=False))

    ids = sorted(path.name for path in HELD.iterdir() if (path / "case.yaml").is_file() and not path.name.startswith("ALN-"))
    if len(ids) != 24:
        raise SystemExit(f"Expected 24 tasks, found {len(ids)}: {ids}")
    index = HELD / "index.jsonl"
    lines = []
    for task_id in ["GEN-01", "GEN-02", "GEN-03", "GEN-04", "GEN-05",
                    "MOD-01", "MOD-02", "MOD-03", "MOD-04", "MOD-05",
                    "QRY-01", "QRY-02", "QRY-03", "QRY-04", "QRY-05",
                    "AMB-01", "AMB-02", "AMB-03", "AMB-04",
                    "RT-01", "RT-02", "RT-03", "RT-04", "RT-05"]:
        case = yaml.safe_load((HELD / task_id / "case.yaml").read_text(encoding="utf-8"))
        lines.append(json.dumps({"id": task_id, "type": case["type"], "path": f"bench/tasks/t4_maritime_isr/heldout/{task_id}"}))
    # The three alignment tasks are written by bench/build_aln_tasks.py and stay in the index.
    for path in sorted(HELD.glob("ALN-*")):
        if (path / "case.yaml").is_file():
            lines.append(json.dumps({"id": path.name, "type": "ALN", "path": f"bench/tasks/t4_maritime_isr/heldout/{path.name}"}))
    index.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {len(lines)} tasks")


if __name__ == "__main__":
    main()
