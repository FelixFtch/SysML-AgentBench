"""Register the RTRC assistant MCP server in Langflow and enable qwen3.8-max as the Agent's chat model.

    .venv-langflow/bin/python langflow/flows/setup_assistant.py

Runs as the superuser (credentials from .langflow/secrets.env, never printed). The MCP server itself is
tools/assistant_mcp.py on 127.0.0.1:8782, started by scripts/langflow.sh. Safe to repeat. If people log in with
another account, run move_to_user.py afterwards.
"""
from __future__ import annotations

import sys
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from import_flows import _request, _secrets  # noqa: E402

SERVER = "rtrc-assistant"
URL = "http://127.0.0.1:8782/mcp"
PROVIDER = "OpenAI Compatible"
MODEL = "qwen3.8-max"


def main() -> None:
    secrets = _secrets()
    token = _request("POST", "/api/v1/login", form={"username": secrets["LANGFLOW_SUPERUSER"],
                                                    "password": secrets["LANGFLOW_SUPERUSER_PASSWORD"]})["access_token"]
    try:
        names = [item.get("name") for item in _request("GET", "/api/v2/mcp/servers", token) or []]
        if SERVER in names:
            _request("PATCH", f"/api/v2/mcp/servers/{SERVER}", token, {"url": URL})
            print(f"mcp server {SERVER}: updated ({URL})")
        else:
            _request("POST", f"/api/v2/mcp/servers/{SERVER}", token, {"url": URL})
            print(f"mcp server {SERVER}: registered ({URL})")
        _request("POST", "/api/v1/models/enabled_models", token,
                 [{"provider": PROVIDER, "model_id": MODEL, "enabled": True, "model_type": "llm"}])
        print(f"chat model enabled: {PROVIDER} · {MODEL}")
    except urllib.error.HTTPError as exc:
        print(f"Langflow refused a request: HTTP {exc.code} {exc.read()[:300]!r}")
        sys.exit(1)


if __name__ == "__main__":
    main()
