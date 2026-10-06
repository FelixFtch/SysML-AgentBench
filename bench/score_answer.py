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


NUMBER_WORDS = {"zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6",
                "seven": "7", "eight": "8", "nine": "9", "ten": "10", "eleven": "11", "twelve": "12",
                "twenty": "20", "thirty": "30", "forty": "40", "fifty": "50", "sixty": "60", "seventy": "70",
                "eighty": "80", "ninety": "90", "hundred": "100"}
# An imperative clarification request counts as asking (second review, 2026-10-06): the AMB statements say
# "ask", and "Please clarify whether the uplink value is 8 or 8 MHz." is asking without a question mark.
ASKING = re.compile(r"\b(please|kindly)\s+(clarify|specify|confirm|provide|state|indicate|tell|give)\b"
                    r"|\bclarify\s+(whether|which|what|if|the)\b"
                    r"|\b(could|can|would)\s+you\b"
                    r"|\b(need|needs|require|requires)\s+(you\s+)?to\s+(know|confirm|clarify|specify|provide)\b"
                    r"|\bmissing values?\b|\bplease (provide|supply) the (following|missing)\b", re.I)
UNIT_NUMBER = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*(w|watts?|mbps|mbit/s|mbit|kbps|gbps|mhz|khz|ghz|ms|milliseconds?|s|seconds?|gb|tb|mb|days?|hours?|h|km|m)\b", re.I)


def normalise(text: str) -> str:
    """Lower case, number words to digits, trailing .0 dropped, single spaces. Used for RT phrase matching so
    "2.0 seconds" and "two seconds" both match the key's "2 seconds" (second review, 2026-10-06)."""
    out = text.lower()
    out = re.sub(r"\b(" + "|".join(NUMBER_WORDS) + r")\b", lambda m: NUMBER_WORDS[m.group(1)], out)
    out = re.sub(r"(\d+)\.0\b", r"\1", out)
    out = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", out)  # sentence dots go, decimal points stay
    out = re.sub(r"[^a-z0-9%./-]+", " ", out)
    return " " + re.sub(r"\s+", " ", out).strip() + " "


def phrase_in(phrase: str, text: str) -> bool:
    wanted, body = normalise(phrase).strip(), normalise(text)
    if f" {wanted} " in body:
        return True
    # plural / singular tolerance on the last word
    singular = re.sub(r"s$", "", wanted)
    return f" {singular} " in body or f" {singular}s " in body


def invented_numbers(text: str, statement: str) -> list[str]:
    """Numbers with a unit in the answer that the statement does not contain. SysML blocks with a literal count too."""
    given = {f"{float(value):g}" for value, _unit in UNIT_NUMBER.findall(statement)}
    given |= set(re.findall(r"\d+(?:\.\d+)?", statement))
    found = []
    for value, unit in UNIT_NUMBER.findall(text):
        if f"{float(value):g}" not in given:
            found.append(f"{value} {unit}")
    if re.search(r"```sysml\b.*?=\s*\d", text, flags=re.S | re.I):
        found.append("a SysML block with a numeric assignment")
    return found


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
        statement = (task_dir / "input" / "requirements.md").read_text(encoding="utf-8")
        lowered = text.lower()
        missing = []
        for group in gold["should_ask"]:
            if not any(word.lower() in lowered for word in group):
                missing.append(group)
        found = invented_numbers(text, statement)
        # Revision 2 (decision 028): a new number counts as invented only when the answer also writes SysML. An
        # answer that asks and writes no model may show an example format or arithmetic from the statement.
        wrote_sysml = bool(re.search(r"```sysml\b", text, flags=re.I))
        invented = found if wrote_sysml else []
        asked_how = "question mark" if "?" in text else ("imperative request" if ASKING.search(text) else None)
        ok = asked_how is not None and not missing and not invented
        return {"status": "PASS" if ok else "FAIL", "missing_questions": missing,
                "invented_number": bool(invented), "invented": invented, "numbers_not_counted": [] if wrote_sysml else found,
                "asked": asked_how is not None, "asked_how": asked_how}
    if kind == "RT":
        gold = yaml.safe_load((task_dir / "gold" / "assertions.yaml").read_text(encoding="utf-8"))
        phrases = gold["must_mention"]
        hit = [phrase for phrase in phrases if phrase_in(phrase, text)]
        missing = [phrase for phrase in phrases if phrase not in hit]
        return {"status": "PASS" if not missing else "FAIL", "hit": len(hit),
                "expected": len(phrases), "missing": missing}
    raise ValueError(f"Not a text task: {kind}")
