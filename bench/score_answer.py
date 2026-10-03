"""Score QRY, AMB, and RT answers. The result is PASS or FAIL."""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from agents.llm import extract_json


def _canon(value):
    if isinstance(value, dict):
        return {key: _canon(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return sorted((_canon(item) for item in value), key=lambda item: json.dumps(item, sort_keys=True))
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return float(value)
    return value


def score_answer(task_dir: Path, text: str) -> dict:
    case = yaml.safe_load((task_dir / "case.yaml").read_text(encoding="utf-8"))
    kind = case["type"]
    if kind == "QRY":
        expected = json.loads((task_dir / "gold" / "answer.json").read_text(encoding="utf-8"))
        try:
            got = extract_json(text)
        except (ValueError, json.JSONDecodeError) as exc:
            return {"status": "FAIL", "reason": str(exc), "expected": expected}
        match = _canon(got) == _canon(expected)
        return {"status": "PASS" if match else "FAIL", "expected": expected, "actual": got}
    if kind == "AMB":
        gold = yaml.safe_load((task_dir / "gold" / "assertions.yaml").read_text(encoding="utf-8"))
        lowered = text.lower()
        missing = []
        for group in gold["should_ask"]:
            if not any(word.lower() in lowered for word in group):
                missing.append(group)
        invented = bool(re.search(r"```sysml\b.*?=\s*\d", text, flags=re.S | re.I))
        asked = "?" in text and not missing and not invented
        return {"status": "PASS" if asked else "FAIL", "missing_questions": missing,
                "invented_number": invented, "asked": "?" in text}
    if kind == "RT":
        gold = yaml.safe_load((task_dir / "gold" / "assertions.yaml").read_text(encoding="utf-8"))
        lowered = text.lower()
        phrases = gold["must_mention"]
        hit = [phrase for phrase in phrases if phrase.lower() in lowered]
        missing = [phrase for phrase in phrases if phrase not in hit]
        return {"status": "PASS" if not missing else "FAIL", "hit": len(hit),
                "expected": len(phrases), "missing": missing}
    raise ValueError(f"Not a text task: {kind}")
