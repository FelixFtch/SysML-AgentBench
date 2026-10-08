#!/usr/bin/env python3
"""Download a checksum-verified, project-local Temurin 21 JDK; no global setup.

Linux x64 is the pinned platform of the frozen toolchain (java.lock.json, recorded in every validation result).
macOS (x64, Apple silicon) is supported for people who run the exam on their own computer: the same Adoptium API,
a lock of its own (java.lock.mac-<arch>.json, written on first use, not pinned by the project), and the alias
mvp/toolchain/java21 pointing at the JDK's Contents/Home. Windows is not supported natively because the frozen
validator (validate.py) uses a POSIX file lock; use WSL2, which is Linux.

Already have a JDK 21? Point the alias at it instead of downloading:  ln -s /path/to/jdk-21 mvp/toolchain/java21
(macOS: .../temurin-21.jdk/Contents/Home). validate.py only needs mvp/toolchain/java21/bin/java to exist.
"""
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import tarfile
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent


def _platform() -> tuple[str, str]:
    system, machine = platform.system(), platform.machine().lower()
    if system == "Linux" and machine in ("x86_64", "amd64"):
        return "linux", "x64"
    if system == "Darwin" and machine in ("x86_64", "amd64"):
        return "mac", "x64"
    if system == "Darwin" and machine in ("arm64", "aarch64"):
        return "mac", "aarch64"
    if system == "Windows":
        raise SystemExit("Windows is not supported natively (the frozen validator uses a POSIX file lock). Use WSL2 and run this inside it.")
    raise SystemExit(f"No pinned JDK for {system} {machine}. Install Temurin 21 yourself and symlink it to mvp/toolchain/java21.")


OS, ARCH = _platform()
LOCK = ROOT / ("java.lock.json" if (OS, ARCH) == ("linux", "x64") else f"java.lock.{OS}-{ARCH}.json")
API = f"https://api.adoptium.net/v3/assets/latest/21/hotspot?architecture={ARCH}&image_type=jdk&os={OS}&vendor=eclipse"


def request(url):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in {
        "api.adoptium.net", "github.com", "objects.githubusercontent.com",
        "release-assets.githubusercontent.com",
    }:
        raise ValueError(f"Unexpected download host: {parsed.hostname}")
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "SysML-MVP-toolchain-bootstrap"}), timeout=90)


def main():
    if LOCK.exists():
        lock = json.loads(LOCK.read_text())
    else:
        with request(API) as response:
            assets = json.load(response)
        asset = assets[0]
        package = asset["binary"]["package"]
        lock = {"vendor": "Eclipse Adoptium", "release": asset["release_name"],
                "metadata_url": API, "url": package["link"], "sha256": package["checksum"],
                "filename": package["name"], "major": 21, "os": OS, "arch": ARCH}
        LOCK.write_text(json.dumps(lock, indent=2) + "\n")
        if LOCK.name != "java.lock.json":
            print(f"Wrote {LOCK.name} for this computer. Validation results still record the project's pinned Linux lock "
                  "(java.lock.json, read by the frozen validate.py); the JDK actually used is the one this file names.")
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
        home = java_root / "Contents" / "Home" if OS == "mac" else java_root
        if not (home / "bin/java").exists():
            tar.extractall(runtime)
    alias = ROOT / "java21"
    if alias.is_symlink():
        alias.unlink()
    elif alias.exists():
        raise SystemExit(f"Refusing to replace non-symlink {alias}")
    alias.symlink_to(home.relative_to(ROOT), target_is_directory=True)
    subprocess.run([str(alias / "bin/java"), "-version"], check=True)
    print(f"Verified SHA-256: {lock['sha256']}")
    print(f"JAVA executable: {alias / 'bin/java'}")


if __name__ == "__main__":
    main()
