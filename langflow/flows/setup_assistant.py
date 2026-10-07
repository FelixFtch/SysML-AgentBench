"""Set up the Langflow-Agent comparison flow "RTRC design assistant (Langflow Agent, qwen3.8-max)": the Qwen provider
credentials, the chat model and the RTRC assistant MCP server registration (all per user in Langflow).

    .venv-langflow/bin/python langflow/flows/setup_assistant.py

Runs as the superuser (credentials from .langflow/secrets.env and .env, never printed). The MCP server itself is
tools/assistant_mcp.py on 127.0.0.1:8782, started outside Langflow (scripts/langflow.sh). Safe to repeat. If people
log in with another account, run move_to_user.py afterwards. The OpenCode assistant needs none of this: it reaches
the MCP server and Ollama directly.
"""
from __future__ import annotations

import sys
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from import_flows import _request, _secrets  # noqa: E402
from setup_knowledge import _env, _set_variable  # noqa: E402

SERVER = "rtrc-assistant"
URL = "http://127.0.0.1:8782/mcp"
PROVIDER = "OpenAI Compatible"
MODELS = [{"provider": PROVIDER, "model_id": "qwen3.8-max", "enabled": True, "model_type": "llm"},
          {"provider": PROVIDER, "model_id": "qwen3.7-text-embedding", "enabled": True, "model_type": "embeddings"}]


def main() -> None:
    secrets, env = _secrets(), _env()
    token = _request("POST", "/api/v1/login", form={"username": secrets["LANGFLOW_SUPERUSER"],
                                                    "password": secrets["LANGFLOW_SUPERUSER_PASSWORD"]})["access_token"]
    try:
        base = env["MVP_LLM_URL"].rsplit("/chat/completions", 1)[0]
        print("Qwen base URL:", _set_variable(token, "OPENAI_COMPATIBLE_BASE_URL", base, "Generic"))
        print("Qwen API key:", _set_variable(token, "OPENAI_COMPATIBLE_API_KEY", env["MVP_LLM_API_KEY"], "Credential"))
        names = [item.get("name") for item in _request("GET", "/api/v2/mcp/servers", token) or []]
        if SERVER in names:
            _request("PATCH", f"/api/v2/mcp/servers/{SERVER}", token, {"url": URL})
            print(f"mcp server {SERVER}: updated ({URL})")
        else:
            _request("POST", f"/api/v2/mcp/servers/{SERVER}", token, {"url": URL})
            print(f"mcp server {SERVER}: registered ({URL})")
        _request("POST", "/api/v1/models/enabled_models", token, MODELS)
        print("models enabled:", ", ".join(f"{m['provider']} · {m['model_id']}" for m in MODELS))
    except urllib.error.HTTPError as exc:
        print(f"Langflow refused a request: HTTP {exc.code} {exc.read()[:300]!r}")
        sys.exit(1)


if __name__ == "__main__":
    main()
