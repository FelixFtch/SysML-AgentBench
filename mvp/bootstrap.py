"""Recreate pinned full Git checkouts and the project-local official runtime."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all-references", action="store_true", help="Also clone the paper, API and memory reference repositories")
    args = parser.parse_args()
    projects = json.loads((ROOT / "reference-projects.json").read_text())["projects"]
    required = {"SysML-v2-Pilot-Implementation", "SysML-v2-Release"}
    for project in projects:
        if project["name"] not in required and not args.all_references:
            continue
        destination = WORKSPACE / "vendor" / project["name"]
        if not destination.exists():
            subprocess.run(["git", "clone", project["repository"], str(destination)], check=True)
        def git(*arguments):
            return subprocess.check_output(["git", "-C", str(destination), *arguments], text=True).strip()
        if git("status", "--porcelain"):
            raise RuntimeError("Refusing to change a modified reference checkout: " + str(destination))
        if git("rev-parse", "HEAD") != project["commit"]:
            subprocess.run(["git", "-C", str(destination), "checkout", "--detach", project["commit"]], check=True)
        if git("rev-parse", "--is-shallow-repository") != "false":
            raise RuntimeError("A full repository is required: " + project["name"])
    for script in ("bootstrap_java.py", "bootstrap_kernel.py"):
        subprocess.run([sys.executable, str(ROOT / "toolchain" / script)], check=True)
    print("Pinned official runtime is ready. Start: python3 -m mvp.app")


if __name__ == "__main__":
    main()
