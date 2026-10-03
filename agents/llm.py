"""One chat completion against the configured Qwen endpoint."""
from __future__ import annotations

import json
import os
import re
import urllib.request


def chat(messages: list[dict], *, max_tokens: int = 4000, temperature: float = 0.2) -> dict:
    url = os.environ.get("MVP_LLM_URL", "")
    model = os.environ.get("MVP_LLM_MODEL", "")
    key = os.environ.get("MVP_LLM_API_KEY", "")
    if not url or not model:
        raise RuntimeError("Set MVP_LLM_URL and MVP_LLM_MODEL")
    body = json.dumps({"model": model, "messages": messages, "temperature": temperature,
                       "max_tokens": max_tokens, "enable_thinking": False}, ensure_ascii=False).encode()
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=180) as response:
        completion = json.loads(response.read(4_000_000))
    message = completion["choices"][0]["message"]
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
    return json.loads(raw[start:end + 1])
