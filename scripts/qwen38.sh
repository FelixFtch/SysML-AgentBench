#!/usr/bin/env bash
# The local Qwen3.8-27B (3-bit) on this machine's RTX 4090, served by Ollama on 127.0.0.1:11434.
#   scripts/qwen38.sh            start Ollama if needed, build the RTRC tag if missing, open a chat with it
#   scripts/qwen38.sh --serve    start Ollama and build the tag only (what the Langflow flows need)
#   scripts/qwen38.sh --status   what is loaded and how much of it is on the GPU
# The RTRC tag qwen3.8-27b-q3:64k is the published smtek/Qwen3.8-27B:Q3_K_XL with num_ctx 65536
# (tools/ollama/qwen3.8-27b-q3-64k.Modelfile), so the whole model sits in the GPU's memory.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TAG="qwen3.8-27b-q3:64k"
BASE="smtek/Qwen3.8-27B:Q3_K_XL"
export OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11434}"
export OLLAMA_FLASH_ATTENTION=1
export OLLAMA_KV_CACHE_TYPE=q8_0
export OLLAMA_MODELS="${OLLAMA_MODELS:-$HOME/.ollama/models}"
export PATH="$HOME/.local/ollama/bin:$PATH"

if ! curl -sf "http://$OLLAMA_HOST/api/tags" >/dev/null; then
  mkdir -p "$OLLAMA_MODELS" "$HOME/.ollama"
  nohup ollama serve >>"$HOME/.ollama/serve.log" 2>&1 &
  for _ in $(seq 1 20); do
    curl -sf "http://$OLLAMA_HOST/api/tags" >/dev/null && break
    sleep 0.5
  done
fi

if [ "${1:-}" = "--status" ]; then
  curl -s "http://$OLLAMA_HOST/api/ps" | python3 -c '
import json, sys
for m in json.load(sys.stdin).get("models", []):
    name, size, vram, ctx = m["name"], m["size"], m["size_vram"], m.get("context_length")
    print(name + ": %.1f GiB, %d%% on the GPU, context %s" % (size / 2**30, round(100 * vram / size), ctx))
' || true
  exit 0
fi

if ! ollama show "$TAG" >/dev/null 2>&1; then
  ollama show "$BASE" >/dev/null 2>&1 || ollama pull "$BASE"
  ollama create "$TAG" -f "$ROOT/tools/ollama/qwen3.8-27b-q3-64k.Modelfile"
fi

if [ "${1:-}" = "--serve" ]; then
  echo "Ollama on $OLLAMA_HOST; $TAG ready"
  exit 0
fi
exec ollama run "$TAG" "$@"
