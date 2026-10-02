"""Rebuild the synthetic legacy SQLite fixture using only the Python standard library."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3

FIXTURES = Path(__file__).resolve().parent


def build_database(output: str | Path | None = None) -> Path:
    destination = Path(output) if output else FIXTURES / "legacy.sqlite"
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".building")
    temporary.unlink(missing_ok=True)
    payload = json.loads((FIXTURES / "configs.json").read_text(encoding="utf-8"))
    db = sqlite3.connect(temporary)
    try:
        db.executescript("""
        PRAGMA foreign_keys=ON;
        CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE sources (source_id TEXT PRIMARY KEY, source_path TEXT NOT NULL,
            source_revision TEXT NOT NULL, sha256 TEXT NOT NULL, synthetic INTEGER NOT NULL CHECK(synthetic=1));
        CREATE TABLE configs (case_name TEXT PRIMARY KEY, configuration_id TEXT UNIQUE NOT NULL,
            label TEXT NOT NULL, data_rate_mbps REAL NOT NULL, retention_hours REAL NOT NULL,
            storage_gb REAL NOT NULL, payload_fraction REAL NOT NULL, link_mbps REAL NOT NULL,
            network_overhead REAL NOT NULL, power_w REAL NOT NULL, power_limit_w REAL NOT NULL,
            preview_mbps REAL NOT NULL, preview_requested INTEGER NOT NULL, preview_approved INTEGER NOT NULL,
            source_id TEXT NOT NULL REFERENCES sources(source_id), reuse_id TEXT,
            power_condition TEXT NOT NULL, synthetic INTEGER NOT NULL CHECK(synthetic=1));
        CREATE TABLE components (configuration_id TEXT NOT NULL REFERENCES configs(configuration_id),
            component_id TEXT NOT NULL, component_type TEXT NOT NULL, part_number TEXT NOT NULL,
            nominal_capacity_gb REAL, allocated_power_w REAL NOT NULL, source_id TEXT NOT NULL REFERENCES sources(source_id),
            source_locator TEXT NOT NULL, PRIMARY KEY(configuration_id, component_id));
        CREATE TABLE interfaces (interface_id TEXT PRIMARY KEY, from_component TEXT NOT NULL,
            to_component TEXT NOT NULL, port_type TEXT NOT NULL, timestamp_field TEXT NOT NULL,
            timestamp_unit TEXT NOT NULL, icd_revision TEXT NOT NULL, source_id TEXT NOT NULL REFERENCES sources(source_id));
        """)
        db.executemany("INSERT INTO metadata VALUES (?,?)", [
            ("synthetic", "true"), ("notice", payload["notice"]),
            ("schema_version", "1"), ("snapshot_id", "SYNTHETIC-MARINE-01-R1"),
            ("power_measurement", "budget only; no hardware measurement"),
        ])
        sources = {
            "SRC-LEGACY-DB-R1": ("configs.json", "1"),
            "SRC-REQ-R1": ("requirements.json", "MARINE-01-REQ-R1"),
            "SRC-CHANGE-001": ("requirements.json", "CHANGE-001"),
            "SRC-CHANGE-002": ("configs.json", "CHANGE-002"),
            "SRC-REUSE-LOW-R1": ("reuse_packages.json", "1"),
            "SRC-REUSE-HIGH-R1": ("reuse_packages.json", "1"),
            "SRC-PAYLOAD-ICD-R1": ("suppliers/payload_icd.json", "PAYLOAD-ICD-R1"),
            "SRC-LINK-ICD-R1": ("suppliers/sharing_icd.json", "SHARING-ICD-R1"),
        }
        for source_id, (relative, revision) in sources.items():
            digest = hashlib.sha256((FIXTURES / relative).read_bytes()).hexdigest()
            db.execute("INSERT INTO sources VALUES (?,?,?,?,1)", (source_id, relative, revision, digest))
        for case_name, row in payload["cases"].items():
            c = {**payload["common"], **row}
            db.execute("INSERT INTO configs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)", (
                case_name, c["configuration_id"], c["label"], c["data_rate_mbps"], c["retention_hours"],
                c["storage_gb"], c["payload_fraction"], c["link_mbps"], c["network_overhead"],
                c["power_w"], c["power_limit_w"], c["preview_mbps"], int(c["preview_requested"]), 0,
                c["source_id"], c["reuse_id"], c["power_condition"],
            ))
            recorder_power = 4.0 if c["storage_gb"] == 64 else 6.0
            processor_power = c["power_w"] - (4 + 4 + 4 + recorder_power + 10 + 6)
            parts = [
                ("payload_alpha", "ObservationPayload", "SYNTH-PAYLOAD-A", None, 4.0),
                ("payload_beta", "ObservationPayload", "SYNTH-PAYLOAD-B", None, 4.0),
                ("acquisition", "AcquisitionNode", "SYNTH-ACQ", None, 4.0),
                ("processor", "ProcessingNode", "SYNTH-HIGH" if case_name == "candidate_b" else "SYNTH-LOW", None, processor_power),
                ("recorder", "Recorder", f"SYNTH-REC-{int(c['storage_gb'])}", c["storage_gb"], recorder_power),
                ("modem", "UplinkModem", "SYNTH-LINK", None, 10.0),
                ("power_conversion", "ConversionLossBudget", "SYNTH-LOSS", None, 6.0),
            ]
            for component_id, kind, pn, storage, power in parts:
                db.execute("INSERT INTO components VALUES (?,?,?,?,?,?,?,?)", (
                    c["configuration_id"], component_id, kind, pn, storage, power, c["source_id"],
                    f"configs.json#/cases/{case_name}",
                ))
        interfaces = [
            ("IF-PAYLOAD-A", "payload_alpha", "acquisition", "ObservationPort", "SRC-PAYLOAD-ICD-R1", "PAYLOAD-ICD-R1"),
            ("IF-PAYLOAD-B", "payload_beta", "acquisition", "ObservationPort", "SRC-PAYLOAD-ICD-R1", "PAYLOAD-ICD-R1"),
            ("IF-ACQ-PROC", "acquisition", "processor", "ObservationPort", "SRC-PAYLOAD-ICD-R1", "PAYLOAD-ICD-R1"),
            ("IF-RAW-STORE", "processor", "recorder", "ObservationPort", "SRC-PAYLOAD-ICD-R1", "PAYLOAD-ICD-R1"),
            ("IF-PROC-MODEM", "processor", "modem", "SharedDataPort", "SRC-LINK-ICD-R1", "SHARING-ICD-R1"),
            ("IF-UPLINK", "modem", "shore_relay", "SharedDataPort", "SRC-LINK-ICD-R1", "SHARING-ICD-R1"),
            ("IF-SHORE", "shore_relay", "shore_subscriber", "SharedDataPort", "SRC-LINK-ICD-R1", "SHARING-ICD-R1"),
            ("IF-PEER", "shore_relay", "peer_subscriber", "SharedDataPort", "SRC-LINK-ICD-R1", "SHARING-ICD-R1"),
        ]
        for ident, source, target, port, source_id, revision in interfaces:
            db.execute("INSERT INTO interfaces VALUES (?,?,?,?,?,?,?,?)", (
                ident, source, target, port, "timestamp_ms", "ms", revision, source_id,
            ))
        db.commit()
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not db.execute("PRAGMA foreign_key_check").fetchall()
    finally:
        db.close()
    temporary.replace(destination)
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    print(build_database(args.output))
