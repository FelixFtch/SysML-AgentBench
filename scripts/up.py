#!/usr/bin/env python3
"""Start and stop the RTRC Langflow shell on Windows, macOS or Linux.

Ports, all on 127.0.0.1:

    7860  Langflow
    8781  shell service (the cards call this)
    8782  MCP server (OpenCode with memory)
    11434 Ollama, the local Qwen3.8-27B (this is the one that holds the GPU)
    8770  results page (no GPU; started on its own with python3 bench/exam_board.py)

    python scripts/up.py              start what is not running, then Langflow in the foreground (Ctrl-C stops Langflow only)
    python scripts/up.py --bg         start what is not running, including Langflow, and return
    python scripts/up.py --import     also import the flows once Langflow answers
    python scripts/up.py --down       stop Langflow, the shell, MCP, the results page, and Ollama (frees the GPU)
    python scripts/up.py --status     say what is up and exit

Needs the two environments of docs/langflow/01-install.md: .venv (requirements-bench.txt) and .venv-langflow
(requirements-langflow.txt). Secrets come from .langflow/secrets.env, created on first use by scripts/langflow_secrets.py
(login and tokens; never printed). Logs: .langflow/shell_service.log, .langflow/assistant_mcp.log, .langflow/langflow.log.
"""
from __future__ import annotations

import json
import os
import shutil
import signal
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
# name, url, port, cmdline fragment used to find leftover processes. The results page is not started here.
SERVICES = {"shell service": "http://127.0.0.1:8781/health", "MCP server": "http://127.0.0.1:8782/mcp",
            "Ollama": "http://127.0.0.1:11434/api/tags", "Langflow": f"http://127.0.0.1:{PORT}/health"}
STACK = [("Langflow", PORT, "langflow"), ("shell service", 8781, "shell_service.py"),
         ("MCP server", 8782, "assistant_mcp.py"), ("results page", 8770, "exam_board.py"),
         ("Ollama", 11434, "ollama")]


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


def _listeners(port: int) -> set[int]:
    """Process ids listening on a TCP port. Own processes only; other users' fds are skipped."""
    found: set[int] = set()
    if WINDOWS:
        try:
            out = subprocess.run(["netstat", "-ano", "-p", "tcp"], capture_output=True, text=True, check=False).stdout
        except OSError:
            return found
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[3] == "LISTENING" and parts[1].endswith(f":{port}"):
                found.add(int(parts[4]))
        return found
    if sys.platform == "darwin":
        try:
            out = subprocess.run(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"], capture_output=True, text=True, check=False).stdout
        except OSError:
            return found
        return {int(line) for line in out.split() if line.isdigit()}
    hexport = f"{port:04X}"
    inodes = set()
    for name in ("tcp", "tcp6"):
        path = Path(f"/proc/net/{name}")
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[1:]:
            parts = line.split()
            if len(parts) > 9 and parts[3] == "0A" and parts[1].rsplit(":", 1)[-1].upper() == hexport:
                inodes.add(parts[9])
    if not inodes:
        return found
    for fd_dir in Path("/proc").glob("[0-9]*/fd"):
        pid = int(fd_dir.parent.name)
        try:
            links = [os.readlink(fd) for fd in fd_dir.iterdir()]
        except OSError:
            continue
        if any(link.startswith("socket:[") and link[8:-1] in inodes for link in links):
            found.add(pid)
    return found


def _cmdline(pid: int) -> str:
    try:
        if WINDOWS:
            return ""
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
        return raw.replace(b"\0", b" ").decode(errors="replace")
    except OSError:
        return ""


def _descendants(pid: int) -> set[int]:
    kids: set[int] = set()
    if WINDOWS or not Path("/proc").is_dir():
        return kids
    for entry in Path("/proc").glob("[0-9]*"):
        try:
            text = (entry / "status").read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            if line.startswith("PPid:") and int(line.split()[1]) == pid:
                child = int(entry.name)
                kids.add(child)
                kids |= _descendants(child)
                break
    return kids


def _matching(fragment: str) -> set[int]:
    """Pids whose program is this service. A command line that only mentions the name does not count."""
    found = set()
    if WINDOWS or not Path("/proc").is_dir():
        return found
    for entry in Path("/proc").glob("[0-9]*"):
        command = _cmdline(int(entry.name))
        if not command:
            continue
        program = Path(command.split(" ", 1)[0]).name
        if fragment == "ollama" and program == "ollama":
            found.add(int(entry.name))
        elif fragment == "langflow" and (program == "langflow" or " langflow run " in f" {command} "):
            found.add(int(entry.name))
        elif fragment != "ollama" and fragment != "langflow" and command.split(" ")[-1].endswith(fragment):
            found.add(int(entry.name))
        elif fragment in ("shell_service.py", "assistant_mcp.py", "exam_board.py") and fragment in command.split(" "):
            found.add(int(entry.name))
    return found


def _stop(pids: set[int]) -> None:
    own = {os.getpid(), os.getppid()}
    pids = {pid for pid in pids if pid > 1 and pid not in own}
    for pid in sorted(pids):
        print(f"  stop pid {pid}  {_cmdline(pid)[:120]}", flush=True)
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    for _ in range(20):
        if not any(Path(f"/proc/{pid}").exists() for pid in pids):
            return
        time.sleep(0.25)
    for pid in pids:
        if Path(f"/proc/{pid}").exists():
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass


def down() -> None:
    """Stop the RTRC stack and unload Ollama so the GPU is free for other work."""
    ollama = shutil.which("ollama") or str(Path.home() / ".local" / "ollama" / "bin" / "ollama")
    if Path(ollama).is_file() and up(SERVICES["Ollama"], timeout=1):
        try:
            with urllib.request.urlopen("http://127.0.0.1:11434/api/ps", timeout=2) as response:
                loaded = json.load(response).get("models") or []
        except Exception:  # noqa: BLE001
            loaded = []
        for model in loaded:
            name = model.get("name") or model.get("model")
            if name:
                say([ollama, "stop", name])
                subprocess.run([ollama, "stop", name], check=False)
    for name, port, fragment in STACK:
        pids = _listeners(port) | _matching(fragment)
        if not pids:
            print(f"{name:14s} already down   127.0.0.1:{port}")
            continue
        print(f"{name:14s} stopping   127.0.0.1:{port}")
        extra: set[int] = set()
        for pid in pids:
            extra |= _descendants(pid)
        _stop(pids | extra)
    print("GPU: Ollama is stopped. Other projects can use the card.")


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
        for name, port, _fragment in STACK:
            url = SERVICES.get(name, f"http://127.0.0.1:{port}/")
            print(f"{name:14s} {'up' if up(url) else 'down':4s}   127.0.0.1:{port}")
        return
    if "--down" in args:
        down()
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
        ollama = shutil.which("ollama") or str(Path.home() / ".local" / "ollama" / "bin" / "ollama")
        if Path(ollama).is_file():
            print("Starting Ollama on 127.0.0.1:11434 (log: .langflow/ollama.log)")
            # The settings of scripts/qwen38.sh: without them the 64k-context 27B tag does not stay on a 24 GB GPU.
            spawn([ollama, "serve"], LOGS / "ollama.log", {**env, "OLLAMA_FLASH_ATTENTION": "1", "OLLAMA_KV_CACHE_TYPE": "q8_0"})
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
        if "--bg" not in args:
            threading.Thread(target=later, daemon=True).start()

    command = [str(LANGFLOW), "run", "--host", "127.0.0.1", "--port", str(PORT)]
    if "--bg" in args:
        if up(SERVICES["Langflow"]):
            print(f"Langflow already up at http://127.0.0.1:{PORT}")
        else:
            print(f"Starting Langflow on http://127.0.0.1:{PORT} (log: .langflow/langflow.log)")
            spawn(command, LOGS / "langflow.log", env)
            if not wait_for(SERVICES["Langflow"], 120):
                raise SystemExit("Langflow did not answer within two minutes. See .langflow/langflow.log")
        if "--import" in args:
            later()
        print(f"Ready. Langflow: http://127.0.0.1:{PORT}  (log in as {env.get('LANGFLOW_SUPERUSER', 'rtrc')}, password in .langflow/secrets.env)")
        print("Stop everything, including Ollama and the GPU:  python scripts/up.py --down")
        return

    print(f"Starting Langflow on http://127.0.0.1:{PORT} (log: .langflow/langflow.log). Log in as {env.get('LANGFLOW_SUPERUSER', 'rtrc')} "
          "with the password in .langflow/secrets.env. Ctrl-C stops Langflow; the services keep running. "
          "python scripts/up.py --down stops the whole stack and frees the GPU.")
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
