#!/usr/bin/env bash
# Stop the Kev services started by scripts/kev_up.sh: the Kev decision service (127.0.0.1:8009) and the kev MCP
# server (127.0.0.1:8793). Safe to repeat; says what it stopped.
set -uo pipefail
KEV_PORT="${KEV_PORT:-8009}"
KEV_MCP_PORT="${KEV_MCP_PORT:-8793}"

pids() { pgrep -f "$1" || true; }

stopped=0
for pattern in "kev.serve.*--port $KEV_PORT" "python3 -u tools/kev_mcp.py" "tools/kev_mcp.py"; do
  for pid in $(pids "$pattern"); do
    kill "$pid" 2>/dev/null || true
    echo "stopped $pattern (pid $pid)"
    stopped=1
  done
done
[ "$stopped" = 1 ] || echo "nothing to stop (Kev $KEV_PORT / kev MCP $KEV_MCP_PORT not running)"
for port in "$KEV_PORT" "$KEV_MCP_PORT"; do
  for _ in $(seq 1 10); do
    curl -s -m 2 -o /dev/null "http://127.0.0.1:$port/v1/models" 2>/dev/null || break
    sleep 1
  done
done
exit 0
