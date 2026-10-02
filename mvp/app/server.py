"""Loopback-only workbench. Engineering verdicts come exclusively from engine.run_case."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib
import io
import json
import math
from pathlib import Path
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
import uuid
import zipfile


APP_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = APP_ROOT.parent
HISTORY_ROOT = APP_ROOT / "data" / "history"
CASES = ("baseline", "upgraded_legacy", "candidate_a", "candidate_b", "degraded_link")
REFERENCES = ("sysml-official-vehicle", "nasa-cfe")
RUN_LOCK = threading.Lock()
STATE_LOCK = threading.Lock()
ACTIVE_RUN: dict | None = None
MAX_BODY = 16_384
MAX_TEXT = 2_000_000
MAX_EXPORT = 128_000_000
RECORD_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,119}$")
TEXT_SUFFIXES = {".sysml", ".json", ".csv", ".md", ".txt", ".yaml", ".yml", ".toml", ".log", ".xml", ".out", ".err"}


class APIError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def safe_path(value: str, *, root: Path | None = None) -> Path:
    """Accept an engine absolute path or UI relative path only inside the project."""
    base = (root or PROJECT_ROOT).resolve()
    supplied = Path(value)
    resolved = (supplied if supplied.is_absolute() else base / supplied).resolve()
    try:
        relative = resolved.relative_to(base)
    except ValueError as exc:
        raise APIError(403, "File path is outside the authorized project directory") from exc
    if any(part.startswith(".") for part in relative.parts):
        raise APIError(403, "Hidden files and directories are not served")
    return resolved


def validate_request(payload: object) -> dict:
    if not isinstance(payload, dict):
        raise APIError(400, "Request must be a JSON object")
    if set(payload) - {"case_name", "data_rate_mbps", "link_mbps", "preview_approved"}:
        raise APIError(400, "Request contains unknown fields")
    case_name = payload.get("case_name")
    if case_name not in CASES:
        raise APIError(400, "Choose a supported case")
    preview = payload.get("preview_approved", False)
    if not isinstance(preview, bool):
        raise APIError(400, "preview_approved must be a boolean")
    result = {"case_name": case_name, "preview_approved": preview}
    for name in ("data_rate_mbps", "link_mbps"):
        value = payload.get(name)
        if value is None:
            result[name] = None
        elif isinstance(value, bool) or not isinstance(value, (int, float)):
            raise APIError(400, f"{name} must be a number or null")
        elif value <= 0 or value > 1e9 or not math.isfinite(value):
            raise APIError(400, f"{name} must be a finite positive number no greater than 1e9")
        else:
            result[name] = value
    return result


def json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2).encode("utf-8")


def record_path(record_id: str) -> Path:
    if not RECORD_ID.fullmatch(record_id):
        raise APIError(400, "Invalid run record ID")
    return safe_path(record_id + ".json", root=HISTORY_ROOT)


def read_record(record_id: str) -> dict:
    path = record_path(record_id)
    if not path.is_file():
        raise APIError(404, "Run record not found")
    return json.loads(path.read_text(encoding="utf-8"))


def save_record(record: dict) -> None:
    HISTORY_ROOT.mkdir(parents=True, exist_ok=True)
    target = record_path(record["record_id"])
    temp = target.with_suffix(".tmp")
    temp.write_bytes(json_bytes(record))
    temp.replace(target)


def list_history() -> list[dict]:
    if not HISTORY_ROOT.exists():
        return []
    records = []
    for path in sorted(HISTORY_ROOT.glob("*.json"), reverse=True):
        try:
            record = read_record(path.stem)
            result = record.get("result", {})
            records.append({"record_id": record["record_id"], "created_at": record["created_at"],
                            "request": record["request"], "status": record["status"],
                            "run_id": result.get("run_id"), "error": record.get("error")})
        except (APIError, ValueError, KeyError, OSError):
            continue
    return records[:500]


def source_files(record_id: str | None = None) -> list[dict]:
    files = []
    # Only engineering inputs/model assets, not arbitrary workspace or application data.
    roots = [PROJECT_ROOT / folder for folder in ("sources", "fixtures", "models", "cases", "projects", "data", "public-data")]
    if record_id:
        run_dir = read_record(record_id).get("result", {}).get("run_dir")
        if run_dir:
            roots = [safe_path(str(run_dir), root=PROJECT_ROOT / "runs"), PROJECT_ROOT / "public-data"]
    for base in roots:
        if not base.is_dir():
            continue
        for candidate in sorted(base.rglob("*")):
            if len(files) >= 2000:
                return files
            if not candidate.is_file() or candidate.suffix.lower() not in TEXT_SUFFIXES:
                continue
            try:
                path = safe_path(str(candidate))
                files.append({"path": str(path.relative_to(PROJECT_ROOT.resolve())),
                              "size": path.stat().st_size})
            except (APIError, OSError):
                continue
    return files


def read_source(value: str, record_id: str | None = None) -> dict:
    # Must be an enumerated input/model, not merely a path under mvp.
    allowed = {item["path"] for item in source_files(record_id)}
    if value not in allowed:
        raise APIError(403, "Only engineering text files listed in the source inventory may be read")
    path = safe_path(value)
    if path.stat().st_size > MAX_TEXT:
        raise APIError(413, "File exceeds the viewer limit; open it directly in the local project")
    return {"path": value, "text": path.read_text(encoding="utf-8", errors="replace")}


def execute(payload: object, *, reference: bool = False) -> tuple[int, dict]:
    global ACTIVE_RUN
    if reference:
        if not isinstance(payload, dict) or set(payload) != {"reference_name"} or payload["reference_name"] not in REFERENCES:
            raise APIError(400, "Choose a supported public reference project")
        request = {"reference_name": payload["reference_name"]}
    else:
        request = validate_request(payload)
    if not RUN_LOCK.acquire(blocking=False):
        raise APIError(409, "An engineering check is already running; wait for completion")
    now = datetime.now(timezone.utc)
    record = {"record_id": now.strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:10],
              "created_at": now.isoformat(), "request": request, "status": "RUNNING"}
    with STATE_LOCK:
        ACTIVE_RUN = {key: record[key] for key in ("record_id", "created_at", "request", "status")}
    response_code = 200
    try:
        try:
            engine = importlib.import_module("mvp.engine")
            runner = getattr(engine, "run_reference" if reference else "run_case")
        except (ImportError, AttributeError) as exc:
            raise APIError(503, "Real SysML engine is unavailable: " + str(exc)) from exc
        result = runner(**request)
        if not isinstance(result, dict):
            raise TypeError("The engine must return a dict")
        # Ensure a durable JSON contract; reject nonserializable engine results.
        json_bytes(result)
        record["result"] = result
        record["status"] = "COMPLETED"  # Execution complete, not an engineering PASS.
        model_path = result.get("model_path")
        if "model_text" not in result and isinstance(model_path, str):
            try:
                path = safe_path(model_path)
                if path.is_file() and path.stat().st_size <= MAX_TEXT:
                    result["model_text"] = path.read_text(encoding="utf-8", errors="replace")
            except (APIError, OSError):
                pass
    except Exception as exc:
        response_code = exc.status if isinstance(exc, APIError) else 500
        record["status"] = "ERROR"
        record["error"] = str(exc)
    finally:
        record["finished_at"] = datetime.now(timezone.utc).isoformat()
        try:
            save_record(record)
        finally:
            with STATE_LOCK:
                ACTIVE_RUN = None
            RUN_LOCK.release()
    return response_code, record


def export_run(record_id: str) -> bytes:
    record = read_record(record_id)
    result = record.get("result", {})
    output = io.BytesIO()
    total = 0
    count = 0
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("workbench-record.json", json_bytes(record))
        run_dir = result.get("run_dir")
        if run_dir:
            directory = safe_path(str(run_dir), root=PROJECT_ROOT / "runs")
            if directory == (PROJECT_ROOT / "runs").resolve() or not directory.is_dir():
                raise APIError(403, "Export must reference a single run directory inside this project")
            for candidate in sorted(directory.rglob("*")):
                if candidate.is_symlink():
                    raise APIError(403, "Run export does not include symbolic links")
                if not candidate.is_file():
                    continue
                path = safe_path(str(candidate))
                size = path.stat().st_size
                total += size
                count += 1
                if total > MAX_EXPORT or count > 2000:
                    raise APIError(413, "Run artifacts exceed export limits (128 MB / 2000 files)")
                archive.write(path, "run/" + str(path.relative_to(directory)))
        elif isinstance(result.get("model_text"), str):
            archive.writestr("model.sysml", result["model_text"])
    return output.getvalue()


class Handler(BaseHTTPRequestHandler):
    server_version = "RTXLocalWorkbench/0.1"

    def send_data(self, status: int, data: bytes, content_type: str, **headers: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        for key, value in headers.items():
            self.send_header(key.replace("_", "-"), value)
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, status: int, data: object) -> None:
        self.send_data(status, json_bytes(data), "application/json; charset=utf-8")

    def check_local(self) -> None:
        allowed_hosts = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        if self.headers.get("Host") not in allowed_hosts:
            raise APIError(403, "Only localhost access is allowed")
        origin = self.headers.get("Origin")
        if origin and origin not in {"http://" + host for host in allowed_hosts}:
            raise APIError(403, "Cross-site request rejected")

    def do_GET(self) -> None:
        try:
            self.check_local()
            url = urlsplit(self.path)
            path = url.path
            if path in ("/", "/index.html", "/app.js", "/style.css", "/harbor-replay.js"):
                filename = "index.html" if path in ("/", "/index.html") else path[1:]
                mime = {"index.html": "text/html", "app.js": "text/javascript", "harbor-replay.js": "text/javascript", "style.css": "text/css"}[filename]
                self.send_data(200, (APP_ROOT / filename).read_bytes(), mime + "; charset=utf-8")
            elif path == "/api/status":
                with STATE_LOCK:
                    active = ACTIVE_RUN.copy() if ACTIVE_RUN else None
                self.send_json(200, {"project_root": str(PROJECT_ROOT), "cases": CASES,
                                     "active_run": active, "engine_file_present": (PROJECT_ROOT / "engine.py").is_file()})
            elif path == "/api/sources":
                self.send_json(200, {"files": source_files(parse_qs(url.query).get("record_id", [None])[0])})
            elif path == "/api/source":
                query = parse_qs(url.query)
                self.send_json(200, read_source(query.get("path", [""])[0], query.get("record_id", [None])[0]))
            elif path == "/api/history":
                self.send_json(200, {"runs": list_history()})
            elif path.startswith("/api/runs/"):
                tail = path[len("/api/runs/"):]
                if tail.endswith("/export.zip"):
                    rid = tail[:-len("/export.zip")]
                    self.send_data(200, export_run(rid), "application/zip",
                                   Content_Disposition=f'attachment; filename="run-{rid}.zip"')
                else:
                    self.send_json(200, read_record(tail))
            else:
                raise APIError(404, "Resource not found")
        except APIError as exc:
            self.send_json(exc.status, {"status": "ERROR", "error": str(exc)})
        except Exception as exc:
            self.send_json(500, {"status": "ERROR", "error": str(exc)})

    def do_POST(self) -> None:
        try:
            self.check_local()
            if self.path not in ("/api/run", "/api/agent", "/api/reference"):
                raise APIError(404, "Endpoint not found")
            if self.headers.get_content_type() != "application/json":
                raise APIError(415, "Use application/json")
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError as exc:
                raise APIError(400, "Invalid Content-Length") from exc
            if not 0 < length <= MAX_BODY:
                raise APIError(413, "Request size must be 1–16384 bytes")
            try:
                payload = json.loads(self.rfile.read(length))
            except (ValueError, UnicodeError) as exc:
                raise APIError(400, "Invalid JSON") from exc
            if self.path == "/api/agent":
                if not isinstance(payload, dict) or set(payload) - {"message", "case_name", "preview_approved"}:
                    raise APIError(400, "Invalid agent request fields")
                message = payload.get("message")
                if not isinstance(message, str) or not 1 <= len(message.strip()) <= 4000:
                    raise APIError(400, "Enter an engineering request of 1–4000 characters")
                context = validate_request({"case_name": payload.get("case_name"), "preview_approved": payload.get("preview_approved", False)})
                try:
                    runner = getattr(importlib.import_module("mvp.engine"), "run_agent")
                except (ImportError, AttributeError) as exc:
                    raise APIError(503, "Agent not connected: a real LLM and agent runner are not configured. Engineering checks remain available.") from exc
                if not RUN_LOCK.acquire(blocking=False):
                    raise APIError(409, "A tool is already running; wait for completion")
                try:
                    result = runner(message=message.strip(), case_name=context["case_name"], preview_approved=context["preview_approved"])
                    if not isinstance(result, dict):
                        raise APIError(500, "run_agent must return a dict")
                    self.send_json(200, result)
                finally:
                    RUN_LOCK.release()
            else:
                status, record = execute(payload, reference=self.path == "/api/reference")
                self.send_json(status, record)
        except APIError as exc:
            self.send_json(exc.status, {"status": "ERROR", "error": str(exc)})
        except Exception as exc:
            self.send_json(500, {"status": "ERROR", "error": str(exc)})


def main() -> None:
    parser = argparse.ArgumentParser(description="Local workbench with a real SysML v2 engine")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Port must be 1–65535")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Engineering workbench: http://127.0.0.1:{args.port} (Ctrl+C to stop)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
