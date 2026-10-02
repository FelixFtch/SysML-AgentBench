"""Run real SysML v2 parsing, linking, Xtext validation and official model export.

Public interface: validate_package(model_files, package_name, output_dir) -> dict.
PASS means only that supported language/static checks passed, not engineering feasibility.
No Jupyter server or Python dependency is required for this direct JVM path.
"""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Sequence

ROOT = Path(__file__).resolve().parent
JDK = ROOT / "java21"
JAR = ROOT / "kernel/sysml/jupyter-sysml-kernel-0.62.0-all.jar"
LIBRARY = ROOT.parent.parent / "vendor/SysML-v2-Release/sysml.library"
SOURCE = ROOT / "SysMLHeadless.java"
BUILD = ROOT / "build"


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _compile() -> None:
    BUILD.mkdir(exist_ok=True)
    digest = _sha(SOURCE) + ":" + _sha(JAR)
    with (BUILD / "compile.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        stamp = BUILD / "compile.sha256"
        if not (BUILD / "SysMLHeadless.class").exists() or not stamp.exists() or stamp.read_text() != digest:
            compiled = subprocess.run(
                [str(JDK / "bin/javac"), "-encoding", "UTF-8", "-cp", str(JAR), "-d", str(BUILD), str(SOURCE)],
                text=True, capture_output=True, timeout=90,
            )
            (BUILD / "javac.stdout.log").write_text(compiled.stdout)
            (BUILD / "javac.stderr.log").write_text(compiled.stderr)
            if compiled.returncode:
                raise RuntimeError(f"Java adapter compilation failed: {compiled.stderr}")
            stamp.write_text(digest)


def _library_manifest() -> dict:
    """Pin the exact standard-library contents actually read, not just its directory."""
    files = {str(file.relative_to(LIBRARY)): _sha(file)
             for file in sorted(LIBRARY.rglob("*"))
             if file.is_file() and file.suffix in {".sysml", ".kerml"}}
    content_hash = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    commit = subprocess.run(["git", "-C", str(LIBRARY.parent), "rev-parse", "HEAD"], text=True,
                            capture_output=True, check=True).stdout.strip()
    expected_commit = "fb97b754f29588b8e9c7a35f370880cd15eb29e7"
    if commit != expected_commit:
        raise RuntimeError(f"Standard library checkout differs from pinned 2026-08 release: {commit}")
    return {"source": "https://github.com/Systems-Modeling/SysML-v2-Release", "commit": commit,
            "path": str(LIBRARY), "content_sha256": content_hash, "file_count": len(files), "files": files}


def validate_package(model_files: Sequence[str], package_name: str, output_dir: str,
                     timeout: int = 180) -> dict:
    """Validate all supplied files together in a fresh official JVM resource set.

    Returns PASS/FAIL/ERROR, structured Xtext diagnostics, official JSON export path,
    actual stdout/stderr paths, source hashes, timing, and pinned toolchain identifiers.
    Every invocation uses a distinct output directory to preserve prior evidence.
    """
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError(f"Validation output directory must be empty: {output}")
    files = [Path(file).resolve() for file in model_files]
    if not files or len(files) != len(set(files)):
        raise ValueError("Provide at least one input file, without duplicates")
    for file in files:
        if not file.is_file() or file.suffix not in {".sysml", ".kerml"}:
            raise ValueError(f"Missing or unsupported model input: {file}")
    input_hashes = {str(file): _sha(file) for file in files}
    if not JAR.is_file() or not (JDK / "bin/java").is_file() or not LIBRARY.is_dir():
        raise RuntimeError("Local Java/kernel missing: run bootstrap_java.py and bootstrap_kernel.py")
    _compile()
    library_manifest = _library_manifest()
    (output / "library-manifest.json").write_text(json.dumps(library_manifest, indent=2) + "\n")
    request = {"model_files": [str(file) for file in files], "package_name": package_name,
               "output_dir": str(output), "library_path": str(LIBRARY)}
    request_path = output / "request.json"
    request_path.write_text(json.dumps(request, indent=2) + "\n")
    command = [str(JDK / "bin/java"), "-Xmx1536m", "-Dfile.encoding=UTF-8", "-cp",
               str(BUILD) + os.pathsep + str(JAR), "SysMLHeadless", str(request_path)]
    started = time.monotonic()
    stdout_path, stderr_path = output / "stdout.log", output / "stderr.log"
    with stdout_path.open("w") as stdout, stderr_path.open("w") as stderr:
        try:
            completed = subprocess.run(command, cwd=str(ROOT), stdout=stdout, stderr=stderr, timeout=timeout)
            return_code = completed.returncode
            raw_result = output / "result.json"
            if raw_result.exists():
                result = json.loads(raw_result.read_text())
            else:
                result = {"status": "ERROR", "model_json_path": None,
                          "diagnostics": [{"severity": "ERROR", "code": "JVM_NO_RESULT",
                                           "message": f"Official JVM exited {return_code} without a result file"}]}
        except subprocess.TimeoutExpired:
            return_code = None
            result = {"status": "ERROR", "model_json_path": None,
                      "diagnostics": [{"severity": "ERROR", "code": "TOOL_TIMEOUT",
                                       "message": f"Official parser exceeded {timeout} seconds"}]}
    if result.get("status") == "PASS" and return_code != 0:
        result["status"] = "ERROR"
        result["model_json_path"] = None
        result["diagnostics"].append({"severity": "ERROR", "code": "JVM_EXIT_MISMATCH", "message": str(return_code)})
    current_hashes = {str(file): _sha(file) for file in files}
    if current_hashes != input_hashes:
        result["status"] = "ERROR"
        result["model_json_path"] = None
        result["diagnostics"].append({"severity": "ERROR", "code": "INPUT_CHANGED_DURING_VALIDATION",
                                      "message": "Source changed while the JVM was validating; result is not an accepted snapshot"})
    result.update({"return_code": return_code, "wall_seconds": round(time.monotonic() - started, 3),
                   "stdout_path": str(stdout_path), "stderr_path": str(stderr_path),
                   "input_hashes": input_hashes,
                   "warning_count": sum(d.get("severity") == "WARNING" for d in result["diagnostics"]),
                   "validation_scope": "Official parser/linker and implemented Xtext static checks; excludes engineering budgets and complete unit/dimension verification",
                   "toolchain": {"java": json.loads((ROOT / "java.lock.json").read_text()),
                                 "kernel": json.loads((ROOT / "kernel.lock.json").read_text()),
                                 "jar_sha256": _sha(JAR), "adapter_sha256": _sha(SOURCE),
                                 "library_commit": library_manifest["commit"],
                                 "library_content_sha256": library_manifest["content_sha256"]},
                   "command": command})
    (output / "validation.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True, dest="package_name")
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("files", nargs="+")
    args = parser.parse_args()
    response = validate_package(args.files, args.package_name, args.output, args.timeout)
    print(json.dumps(response, indent=2, ensure_ascii=False))
    raise SystemExit({"PASS": 0, "FAIL": 2, "ERROR": 3}[response["status"]])
