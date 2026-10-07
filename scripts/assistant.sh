#!/usr/bin/env bash
# The RTRC design assistant in the terminal: OpenCode on the local Qwen3.8-27B with the RTRC tools (decision 032).
#   scripts/assistant.sh                 open the assistant (OpenCode's interface; sessions can be resumed there)
#   scripts/assistant.sh "a message"     one turn, continuing the last session
#   scripts/assistant.sh --cloud ...     the same on qwen3.8-max (reads the Qwen key from .env in this shell)
# Starts what it needs: Ollama with the local model, the RTRC shell service (8781) and the MCP server (8782).
# The design pipeline's sandboxed agent needs the results page (8770) stopped; the assistant will say so if not.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
MODEL="qwen3.8-27b (Ollama)"
if [ "${1:-}" = "--cloud" ]; then
  MODEL="qwen3.8-max"; shift
  set -a; . ./.env; set +a
fi
[ -f .langflow/secrets.env ] || python3 scripts/langflow_secrets.py
set -a
# shellcheck disable=SC1091
. .langflow/secrets.env
set +a

scripts/qwen38.sh --serve >/dev/null
if ! curl -s -m 2 http://127.0.0.1:8781/health >/dev/null; then
  echo "Starting the RTRC shell service on 127.0.0.1:8781 (log: .langflow/shell_service.log)"
  nohup python3 -u bench/shell_service.py >> .langflow/shell_service.log 2>&1 &
  for _ in $(seq 1 30); do curl -s -m 1 http://127.0.0.1:8781/health >/dev/null && break; sleep 1; done
fi
if ! curl -s -m 2 -o /dev/null http://127.0.0.1:8782/mcp; then
  echo "Starting the RTRC assistant MCP server on 127.0.0.1:8782 (log: .langflow/assistant_mcp.log)"
  nohup python3 -u tools/assistant_mcp.py >> .langflow/assistant_mcp.log 2>&1 &
  for _ in $(seq 1 20); do curl -s -m 1 -o /dev/null http://127.0.0.1:8782/mcp && break; sleep 1; done
fi

WS="$(python3 tools/assistant/workspace.py --model "$MODEL" 2>/dev/null)"
if [ $# -eq 0 ]; then
  exec tools/opencode/opencode "$WS"
fi
exec tools/opencode/opencode run --dir "$WS" --auto --continue "$@"
