#!/usr/bin/env bash
# Start the Kev services of the Kev tools (project 7, langflow/flows/7-kev-tools/):
#   1. the Kev decision service on 127.0.0.1:8009 (the laptop-scale Jev clone of tools/jev-arena/kev;
#      the Classify requirements flow and kev_classify_requirement call its /v1/systemone), and
#   2. the kev MCP server on 127.0.0.1:8793 (tools/kev_mcp.py), which mounts the classifier as a tool for the
#      OpenCode-with-memory Kev flows.
#   scripts/kev_up.sh              start both (no-op for whichever is already up)
#   KEV_MODEL=jaredpalmer/kev-4b scripts/kev_up.sh    another checkpoint (default: kev-0.8b, the laptop-scale one)
#   scripts/kev_down.sh           stop both
# Safe to repeat. Logs: tools/jev-arena/kev/serve.log and .langflow/kev_mcp.log.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
KEV_PORT="${KEV_PORT:-8009}"
KEV_MCP_PORT="${KEV_MCP_PORT:-8793}"
KEV_MODEL="${KEV_MODEL:-jaredpalmer/kev-0.8b}"
KEV_REPO="$ROOT/tools/jev-arena/kev/repo"

if curl -s -m 3 "http://127.0.0.1:$KEV_PORT/v1/models" >/dev/null; then
  echo "Kev service already up on 127.0.0.1:$KEV_PORT"
else
  [ -d "$KEV_REPO" ] || { echo "Missing $KEV_REPO; fetch it first (see tools/jev-arena/)" >&2; exit 1; }
  echo "Starting the Kev service on 127.0.0.1:$KEV_PORT ($KEV_MODEL; log: tools/jev-arena/kev/serve.log)"
  (cd "$KEV_REPO" && nohup uv run --extra serve python -m kev.serve --run "$KEV_MODEL" --port "$KEV_PORT" \
     >> "$ROOT/tools/jev-arena/kev/serve.log" 2>&1 &)
  for _ in $(seq 1 120); do
    curl -s -m 3 "http://127.0.0.1:$KEV_PORT/v1/models" >/dev/null && break
    sleep 2
  done
  curl -s -m 3 "http://127.0.0.1:$KEV_PORT/v1/models" >/dev/null || { echo "The Kev service did not come up; see tools/jev-arena/kev/serve.log" >&2; exit 1; }
  echo "Kev service up on 127.0.0.1:$KEV_PORT"
fi

if curl -s -m 3 -o /dev/null "http://127.0.0.1:$KEV_MCP_PORT/mcp"; then
  echo "kev MCP server already up on 127.0.0.1:$KEV_MCP_PORT"
else
  echo "Starting the kev MCP server on 127.0.0.1:$KEV_MCP_PORT (log: .langflow/kev_mcp.log)"
  mkdir -p "$ROOT/.langflow"
  (cd "$ROOT" && KEV_URL="http://127.0.0.1:$KEV_PORT" KEV_MCP_PORT="$KEV_MCP_PORT" \
     nohup python3 -u tools/kev_mcp.py >> .langflow/kev_mcp.log 2>&1 &)
  for _ in $(seq 1 15); do
    curl -s -m 3 -o /dev/null "http://127.0.0.1:$KEV_MCP_PORT/mcp" && break
    sleep 1
  done
  curl -s -m 3 -o /dev/null "http://127.0.0.1:$KEV_MCP_PORT/mcp" || { echo "The kev MCP server did not come up; see .langflow/kev_mcp.log" >&2; exit 1; }
  echo "kev MCP server up on 127.0.0.1:$KEV_MCP_PORT"
fi
