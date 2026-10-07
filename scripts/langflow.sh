#!/usr/bin/env bash
# Start the RTRC Langflow shell: the RTRC shell service (127.0.0.1:8781), Ollama for the local Qwen3.8-27B
# (127.0.0.1:11434) and Langflow 1.12.5 (127.0.0.1:7860).
#   scripts/langflow.sh            start them (Langflow in the foreground)
#   scripts/langflow.sh --import   also import langflow/flows/*.json into the project "RTRC SysML-AgentBench" and set up
#                                  the knowledge base rtrc_memory (Qwen embeddings; langflow/flows/setup_knowledge.py)
# Langflow runs local-only with login on, and executes only built-in components and ours (langflow/components);
# edited or pasted component code is refused. The RTRC nodes call the shell service, which reads .env itself; the only
# key Langflow holds is the Qwen key for the knowledge base's embeddings, stored as an encrypted credential.
# Login: user and password are in .langflow/secrets.env (never committed).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -x .venv-langflow/bin/langflow ]; then
  echo "Install first: python3.12 -m venv .venv-langflow && .venv-langflow/bin/pip install -r requirements-langflow.txt" >&2
  exit 1
fi
[ -f .langflow/secrets.env ] || python3 scripts/langflow_secrets.py
set -a
# shellcheck disable=SC1091
. .langflow/secrets.env
set +a

if ! curl -s -m 2 http://127.0.0.1:8781/health >/dev/null; then
  echo "Starting the RTRC shell service on 127.0.0.1:8781 (log: .langflow/shell_service.log)"
  nohup python3 -u bench/shell_service.py >> .langflow/shell_service.log 2>&1 &
  for _ in $(seq 1 30); do curl -s -m 1 http://127.0.0.1:8781/health >/dev/null && break; sleep 1; done
fi

if ! curl -s -m 2 http://127.0.0.1:11434/api/tags >/dev/null; then
  echo "Starting Ollama for the local Qwen3.8-27B (scripts/qwen38.sh --serve)"
  scripts/qwen38.sh --serve || echo "Ollama did not start; the local model flow will say so when run" >&2
fi

export LANGFLOW_HOST=127.0.0.1 LANGFLOW_PORT="${LANGFLOW_PORT:-7860}"
export LANGFLOW_AUTO_LOGIN=False LANGFLOW_NEW_USER_IS_ACTIVE=False
export LANGFLOW_ALLOW_CUSTOM_COMPONENTS=False LANGFLOW_CUSTOM_COMPONENT_ADMIN_ONLY=True
export LANGFLOW_CONFIG_DIR="$ROOT/.langflow/config" LANGFLOW_COMPONENTS_PATH="$ROOT/langflow/components"
export LANGFLOW_CORS_ORIGINS="http://127.0.0.1:$LANGFLOW_PORT,http://localhost:$LANGFLOW_PORT"
export LANGFLOW_DO_NOT_TRACK=true LANGFLOW_OPEN_BROWSER=false
export RTRC_SHELL_URL=http://127.0.0.1:8781
mkdir -p "$LANGFLOW_CONFIG_DIR"

if [ "${1:-}" = "--import" ]; then
  (for _ in $(seq 1 180); do
     curl -s -m 2 "http://127.0.0.1:$LANGFLOW_PORT/health" >/dev/null && break; sleep 2
   done
   .venv-langflow/bin/python langflow/flows/import_flows.py
   .venv-langflow/bin/python langflow/flows/setup_knowledge.py) &
fi
exec .venv-langflow/bin/langflow run --host "$LANGFLOW_HOST" --port "$LANGFLOW_PORT"
