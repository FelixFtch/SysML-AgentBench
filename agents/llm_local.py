"""The local Qwen (Ollama on this machine) as a model option of the Langflow flows, without touching the frozen agents/llm.py.

install() is called by bench/shell_service.py at start-up. It replaces the name `chat` in bench.discover and agents.solve
with a dispatcher: when the step's model (agents.llm.MODEL_OVERRIDE) names an Ollama model (local_tag), the request goes
to Ollama's OpenAI-compatible endpoint on 127.0.0.1:11434 with no key; every other model goes to agents.llm.chat
unchanged. The exam runners never import this module, so the frozen pipeline is unaffected.
agents/external/opencode_run.py uses the same rule to point OpenCode at Ollama when a run selects a local model.
A local model is named "<Ollama tag> (Ollama)" in the flows; the two names in LOCAL_MODELS are the ones our runs used.

The Ollama tag is the derived model made by scripts/qwen38.sh (tools/ollama/qwen3.8-27b-q3-64k.Modelfile): the same
3-bit weights as smtek/Qwen3.8-27B:Q3_K_XL with num_ctx 65536 instead of the published 224840, so the whole model sits
in the RTX 4090's memory. With the published value Ollama reserved the cache for 224k tokens, kept a third of the
weights on the CPU and ran at 8 tokens/s (run 20261007T014335).
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from agents import llm

OLLAMA_TAG = "qwen3.8-27b-q3:64k"
LOCAL_MODELS = {
    "qwen3.8-27b (Ollama)": OLLAMA_TAG,
    "qwen3.8-27b local": OLLAMA_TAG,
}
LOCAL_SUFFIX = " (Ollama)"
LOCAL_URL = os.environ.get("RTRC_LOCAL_LLM_URL", "http://127.0.0.1:11434/v1/chat/completions")
LOCAL_BASE = LOCAL_URL[: -len("/chat/completions")] if LOCAL_URL.endswith("/chat/completions") else LOCAL_URL


def local_tag(model: str | None) -> str | None:
    """The Ollama tag behind a model name, or None for a cloud model. The two names above are the ones our runs used;
    any other Ollama model is named "<tag> (Ollama)" in a flow, e.g. "llama3.3:70b (Ollama)" for the tag llama3.3:70b."""
    if not model:
        return None
    if model in LOCAL_MODELS:
        return LOCAL_MODELS[model]
    if model.endswith(LOCAL_SUFFIX) and model[: -len(LOCAL_SUFFIX)].strip():
        return model[: -len(LOCAL_SUFFIX)].strip()
    return None


def is_local(model: str | None) -> bool:
    return local_tag(model) is not None


def chat(messages: list[dict], *, max_tokens: int = 4000, temperature: float = 0.2) -> dict:
    model = llm.MODEL_OVERRIDE.get() or os.environ.get("MVP_LLM_MODEL", "")
    tag = local_tag(model)
    if tag is None:
        return llm.chat(messages, max_tokens=max_tokens, temperature=temperature)
    # Thinking off, as for the cloud models: the pipeline reads the answer text, and thinking would spend the token budget.
    # Ollama's OpenAI-compatible endpoint honours reasoning_effort "none" (not enable_thinking).
    body = json.dumps({"model": tag, "messages": messages, "temperature": temperature, "max_tokens": max_tokens,
                       "reasoning_effort": "none"}, ensure_ascii=False).encode()
    request = urllib.request.Request(LOCAL_URL, data=body, headers={"Content-Type": "application/json"}, method="POST")
    completion = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=900) as response:
                completion = json.loads(response.read(4_000_000))
            break
        except urllib.error.HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            if attempt == 2:
                raise RuntimeError("The local Qwen is not running. Start it with qwen38, then run the flow again.") from exc
            time.sleep(5 * (attempt + 1))
    message = completion["choices"][0]["message"]
    log = llm.USAGE_LOG.get()
    if log is not None:
        log.append({"model": completion.get("model", model), "usage": completion.get("usage")})
    return {"text": message.get("content") or "", "model": completion.get("model", model),
            "usage": completion.get("usage"), "finish_reason": completion["choices"][0].get("finish_reason")}


def install() -> None:
    import agents.solve
    import bench.discover
    bench.discover.chat = chat
    agents.solve.chat = chat
