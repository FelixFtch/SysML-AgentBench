"""Give Langflow the Qwen embedding model and create the knowledge base that flow F0 fills with the memory cards.

    .venv-langflow/bin/python langflow/scripts/setup_knowledge.py

User decision of 2026-10-06: the memory is also kept as a Langflow knowledge base, embedded by Qwen
(qwen3.7-text-embedding) through Langflow's "OpenAI Compatible" provider. The endpoint and key come from .env
(MVP_LLM_URL, MVP_LLM_API_KEY); Langflow stores the key as an encrypted credential. No value is printed.
The agent flow's ① Search memory still uses our retrieval (MiniLM + FAISS), so its results match the results page.
Safe to repeat.
"""
from __future__ import annotations

import sys
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from import_flows import ROOT, _request, _secrets  # noqa: E402

PROVIDER = "OpenAI Compatible"
MODEL = "qwen3.7-text-embedding"
KNOWLEDGE_BASE = "rtrc_memory"


def _env() -> dict:
    values = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("'\"")
    return values


def _set_variable(token: str, name: str, value: str, kind: str) -> str:
    existing = {item["name"]: item for item in _request("GET", "/api/v1/variables/", token) or []}
    if name in existing:
        _request("PATCH", f"/api/v1/variables/{existing[name]['id']}", token, {"id": existing[name]["id"], "name": name, "value": value, "type": kind})
        return "updated"
    _request("POST", "/api/v1/variables/", token, {"name": name, "value": value, "type": kind, "default_fields": []})
    return "created"


def main() -> None:
    env = _env()
    secrets = _secrets()
    token = _request("POST", "/api/v1/login", form={"username": secrets["LANGFLOW_SUPERUSER"],
                                                    "password": secrets["LANGFLOW_SUPERUSER_PASSWORD"]})["access_token"]
    base = env["MVP_LLM_URL"].rsplit("/chat/completions", 1)[0]
    try:
        # The key is the provider's main variable; saving it checks the endpoint, so the base URL goes first.
        print("base URL variable:", _set_variable(token, "OPENAI_COMPATIBLE_BASE_URL", base, "Generic"))
        print("API key credential:", _set_variable(token, "OPENAI_COMPATIBLE_API_KEY", env["MVP_LLM_API_KEY"], "Credential"))
        _request("POST", "/api/v1/models/enabled_models", token,
                 [{"provider": PROVIDER, "model_id": MODEL, "enabled": True, "model_type": "embeddings"}])
        print(f"embedding model enabled: {PROVIDER} · {MODEL}")
        names = [item.get("name") for item in _request("GET", "/api/v1/knowledge_bases/", token) or []]
        if KNOWLEDGE_BASE in names:
            print(f"knowledge base {KNOWLEDGE_BASE}: exists")
        else:
            _request("POST", "/api/v1/knowledge_bases/", token, {"name": KNOWLEDGE_BASE, "embedding_provider": PROVIDER, "embedding_model": MODEL})
            print(f"knowledge base {KNOWLEDGE_BASE}: created; run flow F0 to fill it")
    except urllib.error.HTTPError as exc:
        print(f"Langflow refused a request: HTTP {exc.code} {exc.read()[:300]!r}")
        sys.exit(1)


if __name__ == "__main__":
    main()
