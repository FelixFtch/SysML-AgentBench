"""One chat completion against the configured Qwen endpoint."""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from contextvars import ContextVar

# Set inside one worker thread to pick the model or collect token usage for that run only.
MODEL_OVERRIDE: ContextVar[str | None] = ContextVar("MODEL_OVERRIDE", default=None)
USAGE_LOG: ContextVar[list | None] = ContextVar("USAGE_LOG", default=None)


def usage_summary(log: list[dict]) -> dict:
    by_model: dict[str, dict] = {}
    for item in log:
        usage = item.get("usage") or {}
        slot = by_model.setdefault(item.get("model") or "?", {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cached_tokens": 0})
        slot["calls"] += 1
        slot["prompt_tokens"] += usage.get("prompt_tokens") or 0
        slot["completion_tokens"] += usage.get("completion_tokens") or 0
        slot["cached_tokens"] += (usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0
    return {"calls": len(log), "by_model": by_model}


def chat(messages: list[dict], *, max_tokens: int = 4000, temperature: float = 0.2) -> dict:
    url = os.environ.get("MVP_LLM_URL", "")
    model = MODEL_OVERRIDE.get() or os.environ.get("MVP_LLM_MODEL", "")
    key = os.environ.get("MVP_LLM_API_KEY", "")
    if not url or not model:
        raise RuntimeError("Set MVP_LLM_URL and MVP_LLM_MODEL")
    body = json.dumps({"model": model, "messages": messages, "temperature": temperature,
                       "max_tokens": max_tokens, "enable_thinking": False}, ensure_ascii=False).encode()
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    completion = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                completion = json.loads(response.read(4_000_000))
            break
        except urllib.error.HTTPError as exc:
            # Rate limits and gateway errors are retried with a pause; anything else is raised as before.
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 3:
                raise
            time.sleep(5 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt == 3:
                raise
            time.sleep(5 * (attempt + 1))
    message = completion["choices"][0]["message"]
    log = USAGE_LOG.get()
    if log is not None:
        log.append({"model": completion.get("model", model), "usage": completion.get("usage")})
    return {"text": message.get("content") or "", "model": completion.get("model", model),
            "usage": completion.get("usage"), "finish_reason": completion["choices"][0].get("finish_reason")}


def extract_sysml(text: str) -> str:
    tagged = re.findall(r"```sysml\s*\n(.*?)```", text, flags=re.S | re.I)
    fenced = tagged or re.findall(r"```\s*\n(.*?)```", text, flags=re.S)
    body = fenced[-1] if fenced else text
    body = body.strip()
    if "package " not in body:
        raise ValueError("Model output contained no SysML package")
    return body + "\n"


def extract_json(text: str):
    fenced = re.findall(r"```(?:json)?\s*\n(.*?)```", text, flags=re.S)
    raw = fenced[-1] if fenced else text
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end < start:
        start, end = raw.find("["), raw.rfind("]")
    if start < 0 or end < start:
        raise ValueError("Output contained no JSON value")
    try:
        return json.loads(raw[start:end + 1])
    except json.JSONDecodeError:
        # Take the first complete JSON value when the model appended extra text or a second object.
        decoder = json.JSONDecoder()
        value, _ = decoder.raw_decode(raw[start:])
        return value
