#!/usr/bin/env bash
# Flash side benchmarks for every flow that can answer a text prompt.
# SysEngBench: every question in test.csv (not the 100-question draw). PURE: the two keyed excerpts.
# Tool flows and the design pipeline are not candidates: they do not answer a question.
# Sandboxed OpenCode and Claude Code require the results page (8770) to be stopped.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
MODEL="${1:-qwen3.8-flash}"
LOG="$ROOT/.langflow/side-flash.log"
mkdir -p "$ROOT/.langflow"

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*" | tee -a "$LOG"; }

run() {
  log "START $*"
  python3 bench/run_side.py "$@" || log "FAIL exit $? :: $*"
  log "DONE $*"
}

if curl -sf -m 2 http://127.0.0.1:8770/ >/dev/null; then
  log "results page 8770 is up; sandboxed agents will be refused. Stop it first."
  exit 1
fi

log "matrix model=$MODEL"
for bench in pure sysengbench; do
  extra=()
  workers=1
  if [ "$bench" = "sysengbench" ]; then
    extra=(--subset all)
    workers=4
  fi
  run --bench "$bench" --candidate direct --model "$MODEL" --repeats 3 --workers "$workers" "${extra[@]}"
  for approach in direct-p0 direct-p1 direct-p2 direct-p3; do
    run --bench "$bench" --candidate "$approach" --model "$MODEL" --repeats 3 --workers "$workers" "${extra[@]}"
  done
  run --bench "$bench" --candidate opencode --model "$MODEL" --repeats 3 --workers 1 "${extra[@]}"
  run --bench "$bench" --candidate claude --model "$MODEL" --repeats 3 --workers 1 "${extra[@]}"
  for flow in \
    "Langflow Agent, Pilot only chat" \
    "OpenCode with memory chat" \
    "Langflow Agent with memory chat · qwen3.8-max"
  do
    run --bench "$bench" --candidate langflow --flow "$flow" --model "$MODEL" --repeats 3 --workers 1 "${extra[@]}"
  done
done
log "matrix finished"
