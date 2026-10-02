#!/usr/bin/env python3
"""Fetch the official, pinned SysML Jupyter distribution without installing it globally."""
import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent
LOCK = {
    "repository": "https://github.com/Systems-Modeling/SysML-v2-Pilot-Implementation",
    "release": "2026-08", "kernel_version": "0.62.0",
    "url": "https://github.com/Systems-Modeling/SysML-v2-Pilot-Implementation/releases/download/2026-08/jupyter-sysml-kernel-0.62.0.zip",
    "sha256": "5a015ed3f2b3d2dae14e9c3fb9602d9e1fef5f9ce33cf396c422329405cc3cb2",
    "digest_source": "https://api.github.com/repos/Systems-Modeling/SysML-v2-Pilot-Implementation/releases/tags/2026-08",
    "compatibility_note": "This 2026-08 implementation includes 2.1 development content. Tested SysML v2 expressions are not a claim of complete SysML 2.0 conformance."
}


def main():
    downloads = ROOT / "downloads"
    downloads.mkdir(exist_ok=True)
    target = downloads / LOCK["url"].rsplit("/", 1)[-1]
    if not target.exists():
        temporary = target.with_suffix(".part")
        request = urllib.request.Request(LOCK["url"], headers={"User-Agent": "SysML-MVP-toolchain"})
        with urllib.request.urlopen(request, timeout=90) as response, temporary.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        temporary.replace(target)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    if digest != LOCK["sha256"]:
        raise SystemExit("Kernel archive SHA-256 mismatch")
    directory = ROOT / "kernel"
    directory.mkdir(exist_ok=True)
    with zipfile.ZipFile(target) as archive:
        for entry in archive.infolist():
            if not (directory / entry.filename).resolve().is_relative_to(directory.resolve()):
                raise ValueError("Archive path escapes kernel directory")
        archive.extractall(directory)
    (ROOT / "kernel.lock.json").write_text(json.dumps(LOCK, indent=2) + "\n")
    print(f"Verified kernel SHA-256: {digest}")
    for path in directory.rglob("*.jar"):
        print(path)


if __name__ == "__main__":
    main()
