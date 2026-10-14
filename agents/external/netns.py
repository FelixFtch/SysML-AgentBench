"""The sandbox's own network (agents/external/jail.py): the internet and the local model are reachable from inside,
nothing else on this machine's loopback is.

`bwrap --unshare-net` gives the sandbox a network namespace that holds only its own loopback. slirp4netns connects it to
the internet through the launcher and refuses connections to the host's loopback (--disable-host-loopback), so the
results page (127.0.0.1:8770, which serves answer keys), the shell service, the MCP server and Langflow cannot be reached
from inside, while the model API is reached as before. The loopback services an agent does need are its model gateways:
the local model (Ollama) and claude-code-router's gateway for Claude Code. For each of those ports a relay listens on the
sandbox's own 127.0.0.1:<port> and passes each connection through a Unix socket in the run's home to the launcher, which
connects it to this machine's 127.0.0.1:<port>. The agent sees the same addresses as outside, so no provider
configuration changes.

    python3 netns.py launch --home <run home> --ports 11434,3456 -- bwrap ... -- python3 netns.py inside --sockets <dir> --ports 11434,3456 -- <agent argv>

Standard library only: the inside half runs in the sandbox, where the repository is hidden except this file.
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
from pathlib import Path

SOCKET_DIR = ".rtrc-net"
# slirp4netns's built-in DNS forwarder; the host's /etc/resolv.conf points at systemd-resolved on 127.0.0.53, which the
# sandbox cannot reach.
RESOLV = "nameserver 10.0.2.3\n"


def available() -> bool:
    return shutil.which("slirp4netns") is not None and shutil.which("bwrap") is not None


def _pump(source: socket.socket, target: socket.socket) -> None:
    try:
        while data := source.recv(65536):
            target.sendall(data)
    except OSError:
        pass
    try:
        target.shutdown(socket.SHUT_WR)
    except OSError:
        pass


def _bridge(client: socket.socket, connect) -> None:
    try:
        upstream = connect()
    except OSError:
        client.close()
        return
    back = threading.Thread(target=_pump, args=(upstream, client), daemon=True)
    back.start()
    _pump(client, upstream)
    back.join()
    client.close()
    upstream.close()


def _serve(listener: socket.socket, connect) -> None:
    while True:
        try:
            client, _ = listener.accept()
        except OSError:
            return
        threading.Thread(target=_bridge, args=(client, connect), daemon=True).start()


def _unix(path: str) -> socket.socket:
    sock = socket.socket(socket.AF_UNIX)
    sock.connect(path)
    return sock


def _forward_signals(child: subprocess.Popen) -> None:
    for number in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(number, lambda received, _frame: child.send_signal(received))


def _exit_code(code: int) -> int:
    return code if code >= 0 else 128 - code


def _child_pid(fd: int) -> int:
    decoder, text = json.JSONDecoder(), ""
    while chunk := os.read(fd, 4096):
        text += chunk.decode()
        try:
            info, _ = decoder.raw_decode(text.lstrip())
        except ValueError:
            continue
        return int(info["child-pid"])
    raise RuntimeError("bwrap ended before it reported the sandbox's process id")


def _to_host(port: int):
    return lambda: socket.create_connection(("127.0.0.1", port))


def _to_socket(path: str):
    return lambda: _unix(path)


def launch(home: Path, ports: list[int], bwrap: list[str]) -> int:
    """Outside: one Unix socket per forwarded port, bwrap held until slirp4netns has set up its network, then the run."""
    folder = home / SOCKET_DIR
    folder.mkdir(parents=True, exist_ok=True)
    for port in ports:
        name = f"{port}.sock"
        (folder / name).unlink(missing_ok=True)
        listener = socket.socket(socket.AF_UNIX)
        # A relative name: the run's home can be deeper than the 108 bytes a socket path may have.
        previous = os.getcwd()
        os.chdir(folder)
        try:
            listener.bind(name)
        finally:
            os.chdir(previous)
        listener.listen(64)
        threading.Thread(target=_serve, args=(listener, _to_host(port)), daemon=True).start()
    info_r, info_w = os.pipe()
    block_r, block_w = os.pipe()
    exit_r, exit_w = os.pipe()
    ready_r, ready_w = os.pipe()
    child = subprocess.Popen([bwrap[0], "--info-fd", str(info_w), "--block-fd", str(block_r), *bwrap[1:]], pass_fds=(info_w, block_r))
    os.close(info_w)
    os.close(block_r)
    _forward_signals(child)
    try:
        pid = _child_pid(info_r)
        slirp = subprocess.Popen(["slirp4netns", "--configure", "--mtu=65520", "--disable-host-loopback",
                                  f"--exit-fd={exit_r}", f"--ready-fd={ready_w}", str(pid), "tap0"],
                                 pass_fds=(exit_r, ready_w), stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.close(exit_r)
        os.close(ready_w)
        if os.read(ready_r, 1) != b"1":
            raise RuntimeError("slirp4netns could not set up the sandbox's network")
    except Exception as exc:  # noqa: BLE001
        child.kill()
        child.wait()
        print(f"sandbox network: {exc}", file=sys.stderr)
        return 1
    os.write(block_w, b"1")
    os.close(block_w)
    code = child.wait()
    os.close(exit_w)
    try:
        slirp.wait(timeout=10)
    except subprocess.TimeoutExpired:
        slirp.kill()
    return _exit_code(code)


def inside(sockets: Path, ports: list[int], argv: list[str]) -> int:
    """Inside: the forwarded ports on the sandbox's own loopback, then the agent; the agent's exit code is returned."""
    for port in ports:
        for family, host in ((socket.AF_INET, "127.0.0.1"), (socket.AF_INET6, "::1")):
            listener = socket.socket(family)
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                listener.bind((host, port))
            except OSError:
                if family == socket.AF_INET:
                    raise
                continue  # no IPv6 on the sandbox's loopback
            listener.listen(64)
            threading.Thread(target=_serve, args=(listener, _to_socket(str(sockets / f"{port}.sock"))), daemon=True).start()
    child = subprocess.Popen(argv)
    _forward_signals(child)
    return _exit_code(child.wait())


def main(args: list[str]) -> int:
    split = args.index("--")
    mode, options, command = args[0], args[1:split], args[split + 1:]
    values = dict(zip(options[::2], options[1::2]))
    ports = [int(port) for port in (values.get("--ports") or "").split(",") if port]
    if mode == "launch":
        return launch(Path(values["--home"]), ports, command)
    if mode == "inside":
        return inside(Path(values["--sockets"]), ports, command)
    raise SystemExit(f"unknown mode {mode!r}")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
