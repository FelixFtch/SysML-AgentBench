#!/usr/bin/env python3
"""Download a checksum-verified, project-local Temurin 21 JDK; no global setup."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import tarfile
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
LOCK = ROOT / "java.lock.json"
API = "https://api.adoptium.net/v3/assets/latest/21/hotspot?architecture=x64&image_type=jdk&os=linux&vendor=eclipse"


def request(url):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in {
        "api.adoptium.net", "github.com", "objects.githubusercontent.com",
        "release-assets.githubusercontent.com",
    }:
        raise ValueError(f"Unexpected download host: {parsed.hostname}")
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "SysML-MVP-toolchain-bootstrap"}), timeout=90)


def main():
    if platform.system() != "Linux" or platform.machine() not in ("x86_64", "AMD64"):
        raise SystemExit("This pinned bootstrap supports Linux x64 only.")
    if LOCK.exists():
        lock = json.loads(LOCK.read_text())
    else:
        with request(API) as response:
            assets = json.load(response)
        asset = assets[0]
        package = asset["binary"]["package"]
        lock = {"vendor": "Eclipse Adoptium", "release": asset["release_name"],
                "metadata_url": API, "url": package["link"], "sha256": package["checksum"],
                "filename": package["name"], "major": 21, "os": "linux", "arch": "x64"}
        LOCK.write_text(json.dumps(lock, indent=2) + "\n")
    downloads = ROOT / "downloads"
    downloads.mkdir(exist_ok=True)
    archive = downloads / lock["filename"]
    if not archive.exists():
        temporary = archive.with_suffix(archive.suffix + ".part")
        print(f"Downloading {lock['release']} from {lock['url']}", flush=True)
        with request(lock["url"]) as response, temporary.open("wb") as target:
            while chunk := response.read(1024 * 1024):
                target.write(chunk)
        temporary.replace(archive)
    digest = hashlib.sha256()
    with archive.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    if digest.hexdigest() != lock["sha256"]:
        raise SystemExit(f"Checksum mismatch: {archive}")
    runtime = ROOT / "runtime"
    runtime.mkdir(exist_ok=True)
    with tarfile.open(archive) as tar:
        for member in tar.getmembers():
            candidate = (runtime / member.name).resolve()
            if not candidate.is_relative_to(runtime.resolve()):
                raise ValueError("Archive path outside local runtime")
            if member.issym():
                link = (candidate.parent / member.linkname).resolve()
                if not link.is_relative_to(runtime.resolve()):
                    raise ValueError("Archive symlink outside local runtime")
            if member.islnk() or member.isdev() or member.isfifo():
                raise ValueError("Unsupported archive special entry")
        java_root = runtime / tar.getmembers()[0].name.split("/")[0]
        if not (java_root / "bin/java").exists():
            tar.extractall(runtime)
    alias = ROOT / "java21"
    if alias.is_symlink():
        alias.unlink()
    elif alias.exists():
        raise SystemExit(f"Refusing to replace non-symlink {alias}")
    alias.symlink_to(java_root.relative_to(ROOT), target_is_directory=True)
    subprocess.run([str(alias / "bin/java"), "-version"], check=True)
    print(f"Verified SHA-256: {lock['sha256']}")
    print(f"JAVA executable: {alias / 'bin/java'}")


if __name__ == "__main__":
    main()
