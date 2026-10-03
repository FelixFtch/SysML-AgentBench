"""P0–P3 solvers. Gold files are never added to the prompt."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from agents.llm import chat, extract_sysml  # noqa: E402

CORPUS = ROOT / "bench" / "corpus"
SYSML_RULES = """You write SysML v2 textual notation.
Rules:
- Output one fenced code block tagged sysml, and no prose before or after it.
- The file contains exactly one package whose name is given in the task.
- Import ScalarValues only when you use Real.
- Use only names the task requires. Do not invent numeric limits.
- Do not change a number the task tells you to keep.
"""


def _task(task_dir: Path) -> tuple[dict, str]:
    case = yaml.safe_load((task_dir / "case.yaml").read_text(encoding="utf-8"))
    requirements = (task_dir / "input" / "requirements.md").read_text(encoding="utf-8")
    extra = []
    baseline = task_dir / "input" / "baseline"
    if baseline.is_dir():
        for path in sorted(baseline.glob("*.sysml")):
            extra.append(f"Baseline file {path.name}:\n```sysml\n{path.read_text(encoding='utf-8')}```")
    given = task_dir / "input" / "model.sysml"
    if given.is_file() and case["type"] in {"QRY", "RT"}:
        extra.append(f"Given model:\n```sysml\n{given.read_text(encoding='utf-8')}```")
    prompt = requirements if not extra else requirements + "\n\n" + "\n\n".join(extra)
    return case, prompt


def _retrieve(prompt: str, limit: int = 3) -> list[dict]:
    chunks = []
    for path in sorted(CORPUS.glob("*.md")):
        for block in path.read_text(encoding="utf-8").split("\n\n"):
            text = block.strip()
            if text:
                chunks.append({"source": path.name, "text": text})
    words = {word.lower() for word in prompt.split() if len(word) > 3}
    ranked = sorted(chunks, key=lambda item: sum(word in item["text"].lower() for word in words), reverse=True)
    return ranked[:limit]


def _folder(task_id: str, config: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    folder = ROOT / "mvp" / "agent-runs" / f"{stamp}-{config}-{task_id}"
    folder.mkdir(parents=True)
    return folder


def _generate(prompt: str, *, prefix: list[dict] | None = None) -> dict:
    messages = [{"role": "system", "content": SYSML_RULES}]
    messages.extend(prefix or [])
    messages.append({"role": "user", "content": prompt})
    return chat(messages)


def _answer(case: dict, prompt: str, *, prefix: list[dict] | None = None) -> dict:
    if case["type"] in {"GEN", "MOD"}:
        return _generate(prompt, prefix=prefix)
    kind = {"QRY": "Reply with one JSON object and no prose, using the field names required by the task.",
            "AMB": "If a required number or unit is missing, ask for it in one question. Do not invent a number and do not output SysML.",
            "RT": "Restate only the requirements that are written in the given model. Plain sentences. Do not add numbers that are not in the model."}
    messages = [{"role": "system", "content": kind[case["type"]]}]
    messages.extend(prefix or [])
    messages.append({"role": "user", "content": prompt})
    return chat(messages, max_tokens=1500)


def solve(task_dir: Path, config: str) -> dict:
    case, prompt = _task(task_dir)
    folder = _folder(case["id"], config)
    calls = []
    prefix: list[dict] = []
    if config in {"P2", "P3"}:
        notes = ""
        if config == "P3":
            found = _retrieve(prompt)
            notes = "\n\n".join(f"[{item['source']}]\n{item['text']}" for item in found)
            (folder / "retrieved.json").write_text(json.dumps(found, ensure_ascii=False, indent=2), encoding="utf-8")
        outline_prompt = prompt if not notes else prompt + "\n\nReference notes:\n" + notes
        outlined = chat([
            {"role": "system", "content": "List the parts, ports, connections, and attributes the task requires. Reply with one JSON object. Do not write SysML yet."},
            {"role": "user", "content": outline_prompt},
        ], max_tokens=1500)
        calls.append({"step": "outline", "usage": outlined["usage"]})
        (folder / "outline.txt").write_text(outlined["text"], encoding="utf-8")
        prefix = [{"role": "user", "content": "Outline:\n" + outlined["text"]},
                  {"role": "assistant", "content": "I will follow that outline."}]
    written = _answer(case, prompt, prefix=prefix)
    calls.append({"step": "write", "usage": written["usage"], "model": written["model"]})
    text = written["text"]
    rounds = 0
    engine_run = None
    run_dir = None
    sysml_status = None
    if case["type"] in {"GEN", "MOD"} and config == "P1":
        from mvp.engine import run_submitted_model
        source = None
        for attempt in range(4):
            try:
                source = extract_sysml(text)
            except ValueError as exc:
                diagnostic = str(exc)
                sysml_status = "FAIL"
                if attempt == 3:
                    break
            else:
                path = folder / f"{case['package']}.sysml"
                path.write_text(source, encoding="utf-8")
                validated = run_submitted_model([path], case["package"], label=f"{config}-{case['id']}")
                engine_run = validated["run_id"]
                run_dir = validated["run_dir"]
                sysml_status = validated["sysml"]["status"]
                diagnostic = "\n".join(item.get("message", "") for item in validated["sysml"].get("diagnostics", [])[:8])
                if sysml_status == "PASS" or attempt == 3:
                    break
            rounds += 1
            repaired = chat([
                {"role": "system", "content": SYSML_RULES},
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": text},
                {"role": "user", "content": "Official validation failed. Fix the model. Do not change numbers the task said to keep.\n" + diagnostic},
            ])
            calls.append({"step": f"repair-{rounds}", "usage": repaired["usage"]})
            text = repaired["text"]
    elif case["type"] in {"GEN", "MOD"}:
        from mvp.engine import run_submitted_model
        source = extract_sysml(text)
        path = folder / f"{case['package']}.sysml"
        path.write_text(source, encoding="utf-8")
        validated = run_submitted_model([path], case["package"], label=f"{config}-{case['id']}")
        engine_run = validated["run_id"]
        run_dir = validated["run_dir"]
        sysml_status = validated["sysml"]["status"]
    (folder / "response.txt").write_text(text, encoding="utf-8")
    record = {"configuration": config, "task_id": case["id"], "type": case["type"],
              "provider_model": calls[-1].get("model") or calls[0].get("model"),
              "calls": calls, "repair_rounds": rounds, "sysml_status": sysml_status,
              "engine_run": engine_run, "run_dir": run_dir, "response_path": str(folder / "response.txt")}
    (folder / "solve.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    record["text"] = text
    return record
