#!/usr/bin/env python3
"""Fetch small public engineering examples at fixed upstream commits, retaining licenses."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
SOURCES = [
    {"id": "nasa-cfe", "repository": "nasa/cFE",
     "commit": "7d283938c9af5bd6e439f3fc307e61b0c7799640", "license": "Apache-2.0",
     "type": "public software engineering requirements; not paired with gold SysML models",
     "files": ["LICENSE", "README.md", "docs/cFE_FunctionalRequirements.csv", "docs/cfe requirements.docx"]},
    {"id": "sysml-official-vehicle", "repository": "Systems-Modeling/SysML-v2-Release",
     "commit": "fb97b754f29588b8e9c7a35f370880cd15eb29e7", "license": "EPL-2.0",
     "type": "official illustrative SysML v2 engineering model; not measured vehicle or requirements-to-model gold",
     "files": ["LICENSE", "README.md", "sysml/src/examples/Vehicle Example/VehicleDefinitions.sysml",
               "sysml/src/examples/Vehicle Example/VehicleUsages.sysml"]},
]


def main():
    manifests = []
    for source in SOURCES:
        source_root = ROOT / source["id"]
        prior_path = source_root / "manifest.json"
        prior = json.loads(prior_path.read_text()) if prior_path.exists() else None
        expected_hashes = {item["upstream_path"]: item["sha256"] for item in prior["files"]} if prior else {}
        manifest = {**source, "retrieved_at": prior["retrieved_at"] if prior else datetime.now(timezone.utc).isoformat(),
                    "source_url": "https://github.com/" + source["repository"],
                    "license_scope": "Upstream repository declaration; original licenses and notices retained; no relicensing of third-party material",
                    "rtx_relation": "Public independent source, not RTX requirements, models, parameters or endorsement",
                    "provenance": "Downloaded byte-for-byte over HTTPS from commit-pinned upstream raw URLs",
                    "files": []}
        for relative in source["files"]:
            url = f"https://raw.githubusercontent.com/{source['repository']}/{source['commit']}/" + urllib.parse.quote(relative)
            target = source_root / "upstream" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                request = urllib.request.Request(url, headers={"User-Agent": "SysML-MVP-public-data"})
                with urllib.request.urlopen(request, timeout=60) as response:
                    payload = response.read()
                target.write_bytes(payload)
            payload = target.read_bytes()
            digest = hashlib.sha256(payload).hexdigest()
            if relative in expected_hashes and digest != expected_hashes[relative]:
                raise ValueError(f"Preserved original has changed: {target}; refusing to bless it with a new manifest")
            manifest["files"].append({"upstream_path": relative, "local_path": str(target.relative_to(ROOT)),
                                      "source_url": url, "size_bytes": len(payload),
                                      "sha256": digest, "modified": False})
        (source_root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        manifests.append({"id": source["id"], "manifest": f"{source['id']}/manifest.json"})
        print(source["id"], len(manifest["files"]), "files", sum(x["size_bytes"] for x in manifest["files"]), "bytes", flush=True)
    (ROOT / "catalog.json").write_text(json.dumps({"sources": manifests}, indent=2) + "\n")


if __name__ == "__main__":
    main()
