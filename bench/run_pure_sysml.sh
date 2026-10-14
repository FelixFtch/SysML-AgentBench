#!/usr/bin/env bash
# PURE, protocol sysml-v2 (bench/build_pure_tasks.py): every passage of the six keyed documents through every
# answering line, three repeats, all lines in parallel. The direct lines are quick and run one after another in
# one chain; each agent and each Langflow flow is its own process. bench/run_side.py keeps one folder per line and
# resumes it, so running this script again fills in what is missing instead of starting over.
# Sandboxed OpenCode and Claude Code require the results page (8770) to be stopped; Langflow (7860) must be up.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
MODEL="${1:-qwen3.8-flash}"
LOGS="$ROOT/.langflow/parallel"
mkdir -p "$LOGS"

if curl -sf -m 2 http://127.0.0.1:8770/ >/dev/null; then
  echo "results page 8770 is up; sandboxed agents will be refused. Stop it first." >&2
  exit 1
fi
if ! curl -sf -m 3 http://127.0.0.1:7860/health >/dev/null; then
  echo "Langflow (7860) is not running; start it with python scripts/up.py --bg" >&2
  exit 1
fi
[ -f datasets/pure/tasks/BUILD.json ] || python3 bench/build_pure_tasks.py

run() { python3 bench/run_side.py --bench pure --pure all --model "$MODEL" --repeats 3 "$@"; }

(
  for c in direct direct-p0 direct-p1 direct-p2 direct-p3; do
    echo "$(date -u +%FT%TZ) START $c"; run --candidate "$c" --workers 4; echo "$(date -u +%FT%TZ) DONE $c"
  done
) > "$LOGS/pure2-direct.log" 2>&1 &
run --candidate opencode --workers 1 > "$LOGS/pure2-opencode.log" 2>&1 &
run --candidate claude --workers 2 > "$LOGS/pure2-claude.log" 2>&1 &
run --candidate langflow --flow "Langflow Agent, Pilot only chat" --workers 1 > "$LOGS/pure2-pilot.log" 2>&1 &
run --candidate langflow --flow "OpenCode with memory chat" --workers 1 > "$LOGS/pure2-ocmem.log" 2>&1 &
run --candidate langflow --flow "Langflow Agent with memory chat · qwen3.8-max" --workers 1 > "$LOGS/pure2-amem.log" 2>&1 &
echo "started; logs in $LOGS/pure2-*.log"
