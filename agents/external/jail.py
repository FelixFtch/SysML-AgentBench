"""Run an off-the-shelf agent in a bubblewrap sandbox that cannot see answer keys, past answers or transcripts.

Why: on 2026-10-06 OpenCode, run in a workspace inside the repository with `--auto`, read the answer key of the
task it was solving in several runs (`heldout/GEN-01/gold/assertions.yaml`, the GEN-02 reference model, the GEN-05
key it then scored itself). Inside the sandbox:

- the repository is an empty tmpfs except the official validator (`mvp/toolchain`, read-only, without its old
  `runs/`), the pinned OpenCode binary and the SysML standard library it loads;
- the home directory is a fresh per-run directory holding only what the agents need to start: node and the
  Claude Code binary (read-only), OpenCode's provider packages (read-only, its user config replaced by one without
  the MCP server), a copy of the CCR client config; no earlier sessions, transcripts or tool outputs;
- /tmp is empty and /proc shows only the sandbox's own processes, so /proc/<pid>/root cannot reach the host tree;
- the agent's workspace is bound read-write at its usual path and holds the task input, AGENTS.md (and CLAUDE.md,
  the same text) and `./validate`, a wrapper around the official Pilot that passes the files in the scorer's order
  (the file that declares the package last; the Pilot's verdict can depend on the order, see decision 026).

The network is shared because the agents call the model API; the results page server is stopped while agents run.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOME = Path(os.environ.get("HOME", "/home/felix"))
TOOLCHAIN = ROOT / "mvp" / "toolchain"
OPENCODE_BIN = ROOT / "tools" / "opencode"
JAIL_HOMES = Path(os.environ.get("BENCH_JAIL_HOMES", "/tmp/rtrc-jail-homes"))

VALIDATE = r'''#!/usr/bin/env python3
"""Official SysML v2 Pilot 0.62 validator (the same one that scores the answer).
Usage: ./validate <PackageName> <file.sysml> [more .sysml files that it imports]
Prints the official status (PASS / FAIL) and every diagnostic as JSON.
Files are passed in the scorer's order: the file that declares <PackageName> last."""
import os
import re
import sys
import time
from pathlib import Path

if len(sys.argv) < 3:
    sys.exit("usage: ./validate <PackageName> <file.sysml> [more files]")
package, files = sys.argv[1], sys.argv[2:]
declares = re.compile(r"\bpackage\s+" + re.escape(package) + r"\b")
files.sort(key=lambda name: Path(name).is_file() and bool(declares.search(Path(name).read_text(encoding="utf-8", errors="replace"))))
out = Path.cwd() / "validation" / (time.strftime("%Y%m%dT%H%M%S") + f"{time.time_ns() % 10**9:09d}")
os.execvp("python3", ["python3", "@VALIDATOR@", "--package", package, "--output", str(out), *files])
'''

PROMPT_SUFFIX = ("\n\nWrite the answer into answer.md in this workspace. Follow AGENTS.md. "
                 "The official SysML v2 validator is available as `./validate <PackageName> <file.sysml> [more files]`; "
                 "it prints the official status and every diagnostic.")


def prepare_workspace(task_dir: Path, workspace: Path) -> None:
    """Task input, the rules file under both names the agents look for, and the validator wrapper."""
    shutil.copytree(task_dir / "input", workspace / "input")
    rules = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    (workspace / "AGENTS.md").write_text(rules, encoding="utf-8")
    (workspace / "CLAUDE.md").write_text(rules, encoding="utf-8")
    script = workspace / "validate"
    script.write_text(VALIDATE.replace("@VALIDATOR@", str(TOOLCHAIN / "validate.py")), encoding="utf-8")
    script.chmod(0o755)


def fake_home(run_name: str) -> Path:
    """A fresh home for one run: a copy of the CCR client config and an OpenCode user config without MCP."""
    home = JAIL_HOMES / run_name
    if home.exists():
        shutil.rmtree(home)
    (home / ".claude-code-router").mkdir(parents=True)
    source = HOME / ".claude-code-router" / "config.sqlite"
    if source.is_file():
        shutil.copy2(source, home / ".claude-code-router" / "config.sqlite")
    (home / "opencode-user-config.jsonc").write_text('{"$schema": "https://opencode.ai/config.json"}\n', encoding="utf-8")
    # The validator takes a lock in its compile directory; each run gets a private copy, so nothing an agent
    # does in the sandbox can touch the copy that scores the answer afterwards.
    shutil.copytree(TOOLCHAIN / "build", home / "toolchain-build")
    return home


def wrap(argv: list[str], workspace: Path, home: Path) -> list[str]:
    """bwrap argv that runs `argv` with the view described in the module docstring."""
    vendor = (ROOT / "vendor").resolve()
    library = vendor / "SysML-v2-Release"
    args = ["bwrap", "--die-with-parent", "--unshare-pid",
            "--dev-bind", "/", "/",
            "--proc", "/proc",
            "--tmpfs", "/tmp",
            "--tmpfs", "/root"]
    if Path("/run/user").is_dir():
        args += ["--tmpfs", "/run/user"]
    args += ["--tmpfs", str(ROOT),
             "--ro-bind", str(TOOLCHAIN), str(TOOLCHAIN),
             "--tmpfs", str(TOOLCHAIN / "runs"),
             "--bind", str(home / "toolchain-build"), str(TOOLCHAIN / "build"),
             "--ro-bind", str(OPENCODE_BIN), str(OPENCODE_BIN),
             "--symlink", str(vendor), str(ROOT / "vendor"),
             "--bind", str(home), str(HOME)]
    for relative in (".nvm", ".local/bin", ".local/share/claude", ".config/opencode"):
        path = HOME / relative
        if path.exists():
            args += ["--ro-bind", str(path), str(HOME / relative)]
    if (HOME / ".config" / "opencode" / "opencode.jsonc").is_file():
        args += ["--ro-bind", str(home / "opencode-user-config.jsonc"), str(HOME / ".config" / "opencode" / "opencode.jsonc")]
    if (HOME / ".cache" / "opencode").exists():
        args += ["--bind", str(HOME / ".cache" / "opencode"), str(HOME / ".cache" / "opencode")]
    # The standard library the validator loads; bound after the fake home because it lives under the real one.
    args += ["--ro-bind", str(library), str(library)]
    args += ["--bind", str(workspace), str(workspace), "--chdir", str(workspace), "--"]
    return args + argv
