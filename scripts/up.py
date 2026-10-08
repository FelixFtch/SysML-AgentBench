#!/usr/bin/env python3
"""Start the RTRC Langflow shell on Windows, macOS or Linux: the shell service (127.0.0.1:8781), the RTRC MCP server
(8782), Ollama if it is installed, and Langflow 1.12.5 (7860). The same steps as scripts/langflow.sh, in Python so that
Windows has them too, and every command is printed before it runs. Nothing is hidden.

    python scripts/up.py              start what is not running, then Langflow in the foreground (Ctrl-C stops Langflow only)
    python scripts/up.py --import     also import the flow files into the six projects and run the set-up scripts once Langflow answers
    python scripts/up.py --status     say what is up and exit

Needs the two environments of docs/langflow/01-install.md: .venv (requirements-bench.txt) and .venv-langflow
(requirements-langflow.txt). Secrets come from .langflow/secrets.env, created on first use by scripts/langflow_secrets.py
(login and tokens; never printed). Logs: .langflow/shell_service.log, .langflow/assistant_mcp.log, .langflow/langflow.log.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WINDOWS = os.name == "nt"
# The benchmark side runs in .venv when it exists, else in the Python that runs this script (a machine where the
# packages of requirements-bench.txt were installed for the system Python).
BENCH_PY = ROOT / ".venv" / ("Scripts/python.exe" if WINDOWS else "bin/python")
if not BENCH_PY.exists():
    BENCH_PY = Path(sys.executable)
LF_DIR = ROOT / ".venv-langflow" / ("Scripts" if WINDOWS else "bin")
LF_PY = LF_DIR / ("python.exe" if WINDOWS else "python")
LANGFLOW = LF_DIR / ("langflow.exe" if WINDOWS else "langflow")
SECRETS = ROOT / ".langflow" / "secrets.env"
LOGS = ROOT / ".langflow"
PORT = int(os.environ.get("LANGFLOW_PORT", "7860"))
SERVICES = {"shell service": "http://127.0.0.1:8781/health", "MCP server": "http://127.0.0.1:8782/mcp",
            "Ollama": "http://127.0.0.1:11434/api/tags", "Langflow": f"http://127.0.0.1:{PORT}/health"}


def up(url: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout):
            return True
    except urllib.error.HTTPError as exc:  # the MCP route answers 4xx to a plain GET: it is up
        return exc.code < 500
    except Exception:  # noqa: BLE001
        return False


def say(command: list[str]) -> None:
    print("  $ " + " ".join(str(part) for part in command), flush=True)


def spawn(command: list[str], log: Path, env: dict) -> None:
    say(command)
    handle = log.open("a", encoding="utf-8")
    kwargs = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if WINDOWS else {"start_new_session": True}
    subprocess.Popen(command, cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env, **kwargs)


def wait_for(url: str, seconds: int) -> bool:
    for _ in range(seconds):
        if up(url):
            return True
        time.sleep(1)
    return False


def secrets() -> dict[str, str]:
    if not SECRETS.is_file():
        say([sys.executable, "scripts/langflow_secrets.py"])
        subprocess.run([sys.executable, str(ROOT / "scripts" / "langflow_secrets.py")], cwd=ROOT, check=True)
    values = {}
    for line in SECRETS.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def main() -> None:
    args = set(sys.argv[1:])
    if "--status" in args:
        for name, url in SERVICES.items():
            print(f"{name:14s} {'up' if up(url) else 'down'}   {url}")
        return
    if not LANGFLOW.exists():
        raise SystemExit(f"Missing {LANGFLOW.relative_to(ROOT)}. Install first:  python3.12 -m venv .venv-langflow && "
                         ".venv-langflow/bin/pip install -r requirements-langflow.txt")
    env = {**os.environ, **secrets()}
    env.update({
        "LANGFLOW_HOST": "127.0.0.1", "LANGFLOW_PORT": str(PORT),
        "LANGFLOW_AUTO_LOGIN": "False", "LANGFLOW_NEW_USER_IS_ACTIVE": "False",
        "LANGFLOW_ALLOW_CUSTOM_COMPONENTS": "False", "LANGFLOW_CUSTOM_COMPONENT_ADMIN_ONLY": "True",
        "LANGFLOW_CONFIG_DIR": str(ROOT / ".langflow" / "config"), "LANGFLOW_COMPONENTS_PATH": str(ROOT / "langflow" / "components"),
        "LANGFLOW_CORS_ORIGINS": f"http://127.0.0.1:{PORT},http://localhost:{PORT}",
        "LANGFLOW_DO_NOT_TRACK": "true", "LANGFLOW_OPEN_BROWSER": "false",
        "RTRC_SHELL_URL": "http://127.0.0.1:8781", "RTRC_ROOT": str(ROOT),
    })
    (ROOT / ".langflow" / "config").mkdir(parents=True, exist_ok=True)

    if not up(SERVICES["shell service"]):
        print("Starting the RTRC shell service on 127.0.0.1:8781 (log: .langflow/shell_service.log)")
        spawn([str(BENCH_PY), "-u", "bench/shell_service.py"], LOGS / "shell_service.log", env)
        wait_for(SERVICES["shell service"], 30)
    if not up(SERVICES["MCP server"]):
        print("Starting the RTRC MCP server on 127.0.0.1:8782 (log: .langflow/assistant_mcp.log)")
        spawn([str(BENCH_PY), "-u", "tools/assistant_mcp.py"], LOGS / "assistant_mcp.log", env)
    if not up(SERVICES["Ollama"]):
        ollama = shutil.which("ollama")
        if ollama:
            print("Starting Ollama on 127.0.0.1:11434 (log: .langflow/ollama.log)")
            spawn([ollama, "serve"], LOGS / "ollama.log", env)
            wait_for(SERVICES["Ollama"], 10)
        else:
            print("Ollama is not installed; the local-model flows will say so when run (https://ollama.com/download)")

    if "--import" in args:
        def later() -> None:
            if not wait_for(SERVICES["Langflow"], 360):
                print("Langflow did not answer within six minutes; run the import by hand: python langflow/scripts/import_flows.py", flush=True)
                return
            for script in ("import_flows.py", "setup_knowledge.py", "setup_assistant.py"):
                command = [str(LF_PY), f"langflow/scripts/{script}"]
                say(command)
                subprocess.run(command, cwd=ROOT, env=env, check=False)
        threading.Thread(target=later, daemon=True).start()

    print(f"Starting Langflow on http://127.0.0.1:{PORT} (log: .langflow/langflow.log). Log in as {env.get('LANGFLOW_SUPERUSER', 'rtrc')} "
          "with the password in .langflow/secrets.env. Ctrl-C stops Langflow; the services keep running.")
    command = [str(LANGFLOW), "run", "--host", "127.0.0.1", "--port", str(PORT)]
    say(command)
    with (LOGS / "langflow.log").open("a", encoding="utf-8") as log:
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            process.wait()
        except KeyboardInterrupt:
            process.terminate()
            process.wait(timeout=30)


if __name__ == "__main__":
    main()
