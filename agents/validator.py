"""Second model. It judges the submission and is not the scorer.

Its labels are compared with the tool check afterwards. They never change
the engineering PASS or FAIL.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request

SYSTEM = """You are a second reviewer, not the scorer.
Read the requirements and the SysML text.
Reply with one JSON object and no prose:
{"requirements":[{"id":"power limit","verdict":"satisfied|partial|missing","reason":"..."},
{"id":"camera draw","verdict":"satisfied|partial|missing","reason":"..."},
{"id":"computer draw","verdict":"satisfied|partial|missing","reason":"..."},
{"id":"budget 60 W","verdict":"satisfied|partial|missing","reason":"..."}]}
Use satisfied only when the text itself meets that item.
The budget item is satisfied only when the stated draws fit under the stated limit.
"""


def _complete(requirements: str, model_text: str) -> dict:
    url = os.environ.get("MVP_LLM_URL", "")
    model = os.environ.get("MVP_LLM_MODEL", "")
    key = os.environ.get("MVP_LLM_API_KEY", "")
    if not url or not model:
        raise RuntimeError("Set MVP_LLM_URL and MVP_LLM_MODEL")
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"Requirements:\n{requirements}\n\nSysML:\n{model_text}"},
    ]
    body = json.dumps({"model": model, "messages": messages, "temperature": 0,
                       "max_tokens": 1500, "enable_thinking": False}, ensure_ascii=False).encode()
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=360) as response:
        completion = json.loads(response.read(2_000_000))
    message = completion["choices"][0]["message"]
    return {"text": message.get("content") or "", "model": completion.get("model", model),
            "usage": completion.get("usage")}


def _parse(text: str) -> dict:
    fenced = re.findall(r"```(?:json)?\s*\n(.*?)```", text, flags=re.S)
    raw = fenced[-1] if fenced else text
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Validator output contained no JSON object")
    return json.loads(raw[start:end + 1])


def review(requirements: str, model_text: str, *, tool_status: str) -> dict:
    completed = _complete(requirements, model_text)
    parsed = _parse(completed["text"])
    items = parsed.get("requirements") or []
    budget = next((item for item in items if item.get("id") == "budget 60 W"), None)
    verdict = (budget or {}).get("verdict")
    tool_fail = tool_status == "FAIL"
    validator_says_fail = verdict in {"missing", "partial"}
    return {"provider_model": completed["model"], "usage": completed["usage"],
            "requirements": items,
            "budget_verdict": verdict,
            "agrees_with_tool": tool_fail == validator_says_fail if verdict else None,
            "false_pass": bool(tool_fail and verdict == "satisfied"),
            "counts_toward_score": False}
