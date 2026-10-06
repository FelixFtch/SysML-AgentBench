"""P0–P3 solvers. Gold files are never added to the prompt.

The approaches are cumulative. P0 writes once and is validated once. P1 adds the
repair loop: when the official Pilot rejects the model, the complete error list
goes back to the model in the same conversation, so every earlier version and
every earlier error list stays visible, until the parse passes or the round cap
is reached. P2 adds an outline before writing. P3 adds retrieved notes before
the outline. The round cap is BENCH_REPAIR_ROUNDS (default 20).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from agents.llm import chat, extract_sysml  # noqa: E402

DEFAULT_ROUNDS = int(os.environ.get("BENCH_REPAIR_ROUNDS", "20"))
# Stop early after this many consecutive byte-identical resubmissions; 0 disables the guard.
IDENTICAL_STOP = int(os.environ.get("BENCH_REPAIR_IDENTICAL_STOP", "3"))
REPAIR_NOTE = ("Official validation failed: attempt {attempt}, repair {repair} of at most {cap}. "
               "The complete error list from the official SysML v2 Pilot follows. Fix the model and "
               "resubmit the whole file in one fenced sysml block. Do not change numbers the task said to keep.")
IDENTICAL_NOTE = ("Your last submission was byte-identical to the one before it and produced the same errors. "
                  "Resubmitting the same text will fail again; change the file.")
ALIGN_RULES = """You align two independently written SysML v2 packages without editing either of them.
Rules:
- Output one fenced code block tagged sysml containing exactly one package with the name given in the task, then one fenced code block tagged json, and no prose.
- The package may contain only import statements, `alias <Name> for <Qualified::Name>;` declarations and `allocation <name> allocate <a.b.c> to <x.y.z>;` declarations. Do not declare parts, ports, attributes or definitions of your own.
- In this toolchain an import inside a package needs a visibility keyword: write `private import Pkg::*;` or `public import Pkg::*;`, never a bare `import`.
- Alias names are the specification's short names; alias targets are fully qualified with `::` at every level (`Pkg::Def::feature`). Allocation ends are usage paths: the package name, `::`, then the nested usages joined with dots (`Pkg::usv.radio`), never a dot after the package name.
- Alias a definition only to a definition and a feature only to a feature; map usages to usages with allocations.
- Do not map elements whose meaning differs; list them under "unmatched" in the json report instead.
"""
SYSML_RULES = """You write SysML v2 textual notation.
Rules:
- Output one fenced code block tagged sysml, and no prose before or after it.
- The file contains exactly one package whose name is given in the task.
- When you use Real, write `private import ScalarValues::*;` as the first line inside the package. In this toolchain an import inside a package needs the visibility keyword; a bare `import` is rejected. Do not import anything else.
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


EXAMPLES_LIBRARY = ROOT / "analysis" / "vector-index" / "examples"


def _retrieve(prompt: str, limit: int = 6) -> list[dict]:
    """P3's retrieval (paper 2): MiniLM + FAISS over the examples library, then one-hop neighbours.

    The library is official SysML-v2-Release example elements plus the notes corpus
    (bench/build_examples_library.py). MaritimeISR is not in it: the held-out keys repeat its values.
    There is no other ranking: a missing library or embedding stack raises."""
    from bench.vector_index import retrieve as vector_retrieve
    cards_file = EXAMPLES_LIBRARY / "cards.json"
    if not cards_file.is_file():
        raise FileNotFoundError(f"{cards_file} is missing; build it with python3 bench/build_examples_library.py")
    rows = json.loads(cards_file.read_text(encoding="utf-8"))
    cards = {row["id"]: row["text"] for row in rows}
    sources = {row["id"]: row["source"] for row in rows}
    neighbors = {key: set(value) for key, value in json.loads((EXAMPLES_LIBRARY / "neighbors.json").read_text(encoding="utf-8")).items()}
    found = vector_retrieve(prompt, cards, neighbors, name="examples", k_seeds=3, limit=limit)
    return [{"source": sources[item["id"]], "text": cards[item["id"]], "method": found["method"], "role": item["role"],
             "score": item["score"], "threshold": found["threshold"], "embedding_model": found["embedding_model"]}
            for item in found["picked"]]


def _folder(task_id: str, config: str) -> Path:
    # Two batches may run at once (flash and max); a short random suffix keeps their folders apart.
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    folder = ROOT / "mvp" / "agent-runs" / f"{stamp}-{config}-{task_id}"
    if folder.exists():
        folder = ROOT / "mvp" / "agent-runs" / f"{stamp}-{uuid.uuid4().hex[:4]}-{config}-{task_id}"
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
    if case["type"] == "ALN":
        messages = [{"role": "system", "content": ALIGN_RULES}]
        messages.extend(prefix or [])
        messages.append({"role": "user", "content": prompt})
        return chat(messages)
    kind = {"QRY": "Reply with one JSON object and no prose, using the field names required by the task.",
            "AMB": "If a required number or unit is missing, ask for it in one question. Do not invent a number and do not output SysML.",
            "RT": "Restate only the requirements that are written in the given model. Plain sentences. Do not add numbers that are not in the model."}
    messages = [{"role": "system", "content": kind[case["type"]]}]
    messages.extend(prefix or [])
    messages.append({"role": "user", "content": prompt})
    return chat(messages, max_tokens=1500)


def rounds_for(config: str, max_rounds: int | None = None) -> int:
    """P0 never repairs. P1, P2 and P3 repair up to the cap."""
    if config == "P0":
        return 0
    return DEFAULT_ROUNDS if max_rounds is None else max_rounds


def format_diagnostics(diagnostics: list[dict]) -> str:
    """Every diagnostic, with its position, in the order the Pilot reported it."""
    if not diagnostics:
        return "The official tool returned no diagnostic text; the run did not reach PASS."
    lines = []
    for item in diagnostics:
        where = "no position"
        if item.get("line") is not None:
            where = f"line {item['line']}"
            if item.get("column") is not None:
                where += f", column {item['column']}"
        lines.append(f"[{item.get('severity') or 'ERROR'}] {where}: {item.get('message') or ''}")
    return "\n".join(lines)


def companions_of(case: dict, task_dir: Path | None) -> list[Path]:
    """Source files that are validated together with the answer but are not part of it (ALN tasks)."""
    if case.get("type") != "ALN" or not task_dir:
        return []
    return [task_dir / "input" / "baseline" / name for name in case.get("sources") or []]


def validate_with_repair(case: dict, prompt: str, text: str, folder: Path, *, prefix: list[dict] | None,
                         label: str, max_rounds: int, calls: list[dict],
                         on_attempt: Callable[[dict, str, str], None] | None = None,
                         companions: list[Path] | None = None) -> dict:
    """Validate one submission with the official Pilot; on failure, repair in one cumulative conversation.

    Attempt 1 is the text already written. Each failed attempt appends the model's text and the full
    error list to the same message list, so later repairs see every earlier version and every earlier
    error. Each version and its diagnostics are saved under folder/attempts/. Stops at PASS or when
    max_rounds repairs have been made. `companions` are read-only source files parsed together with
    the answer (the two models an alignment package imports).
    """
    from mvp.engine import run_submitted_model

    messages = [{"role": "system", "content": ALIGN_RULES if case.get("type") == "ALN" else SYSML_RULES}]
    messages.extend(prefix or [])
    messages.append({"role": "user", "content": prompt})
    attempts_dir = folder / "attempts"
    attempts_dir.mkdir(exist_ok=True)
    attempts: list[dict] = []
    engine_run = run_dir = None
    status = None
    previous_sha = None
    identical_streak = 0
    stop_reason = None
    attempt = 0
    while True:
        attempt += 1
        messages.append({"role": "assistant", "content": text})
        run_id = None
        try:
            source = extract_sysml(text)
        except ValueError as exc:
            source = ""
            status = "FAIL"
            diagnostics = [{"severity": "ERROR", "line": None, "column": None, "message": str(exc)}]
        else:
            path = folder / f"{case['package']}.sysml"
            path.write_text(source, encoding="utf-8")
            validated = run_submitted_model(list(companions or []) + [path], case["package"], label=label)
            engine_run = run_id = validated["run_id"]
            run_dir = validated["run_dir"]
            status = validated["sysml"]["status"]
            diagnostics = [{key: item.get(key) for key in ("severity", "line", "column", "message")}
                           for item in validated["sysml"].get("diagnostics", [])]
        sha = hashlib.sha256((source or text).encode("utf-8")).hexdigest()[:12]
        entry = {"attempt": attempt, "status": status, "run_id": run_id, "sha": sha,
                 "same_as_previous": previous_sha == sha, "diagnostics": diagnostics}
        attempts.append(entry)
        (attempts_dir / f"attempt-{attempt:02d}.sysml").write_text(source or text, encoding="utf-8")
        (attempts_dir / f"attempt-{attempt:02d}.diagnostics.json").write_text(
            json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8")
        feedback = format_diagnostics(diagnostics)
        identical_streak = identical_streak + 1 if entry["same_as_previous"] else 0
        if on_attempt:
            on_attempt(entry, text, feedback)
        previous_sha = sha
        if status == "PASS":
            stop_reason = "pass"
            break
        if attempt > max_rounds:
            stop_reason = "cap"
            break
        if IDENTICAL_STOP and identical_streak >= IDENTICAL_STOP:
            stop_reason = f"identical x{identical_streak}"
            break
        note = REPAIR_NOTE.format(attempt=attempt, repair=attempt, cap=max_rounds)
        if case.get("type") == "ALN":
            note += " Also repeat the fenced json report (mappings and unmatched) after the sysml block."
        if entry["same_as_previous"]:
            note += " " + IDENTICAL_NOTE
            entry["nudged"] = True
        messages.append({"role": "user", "content": note + "\n" + feedback})
        repaired = chat(messages)
        calls.append({"step": f"repair-{attempt}", "usage": repaired["usage"], "model": repaired.get("model")})
        text = repaired["text"]
    (folder / "conversation.json").write_text(json.dumps(messages, ensure_ascii=False, indent=2), encoding="utf-8")
    first_pass = next((item["attempt"] for item in attempts if item["status"] == "PASS"), None)
    carried = False
    if case.get("type") == "ALN" and "```json" not in text:
        # Repairs resubmit the package; the JSON report from the latest reply that had one still stands.
        for earlier in reversed([m["content"] for m in messages if m["role"] == "assistant"]):
            block = re.search(r"```json\s*\n.*?```", earlier, flags=re.S)
            if block:
                text = text.rstrip() + "\n\n" + block.group(0)
                carried = True
                break
    return {"text": text, "sysml_status": status, "engine_run": engine_run, "run_dir": run_dir,
            "attempts": attempts, "repair_rounds": len(attempts) - 1, "max_rounds": max_rounds,
            "first_pass_attempt": first_pass, "stop_reason": stop_reason, "report_carried_forward": carried,
            "resubmitted_unchanged": sum(1 for item in attempts if item["same_as_previous"])}


def solve(task_dir: Path, config: str, *, max_rounds: int | None = None) -> dict:
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
    loop = {"sysml_status": None, "engine_run": None, "run_dir": None, "attempts": [], "repair_rounds": 0,
            "max_rounds": 0, "first_pass_attempt": None, "resubmitted_unchanged": 0, "stop_reason": None}
    if case["type"] in {"GEN", "MOD", "ALN"}:
        loop = validate_with_repair(case, prompt, text, folder, prefix=prefix, label=f"{config}-{case['id']}",
                                    max_rounds=rounds_for(config, max_rounds), calls=calls,
                                    companions=companions_of(case, task_dir))
        text = loop["text"]
    (folder / "response.txt").write_text(text, encoding="utf-8")
    record = {"configuration": config, "task_id": case["id"], "type": case["type"],
              "provider_model": calls[-1].get("model") or calls[0].get("model"),
              "calls": calls, "repair_rounds": loop["repair_rounds"], "max_rounds": loop["max_rounds"],
              "first_pass_attempt": loop["first_pass_attempt"], "resubmitted_unchanged": loop["resubmitted_unchanged"],
              "stop_reason": loop.get("stop_reason"),
              "attempts": loop["attempts"], "sysml_status": loop["sysml_status"],
              "engine_run": loop["engine_run"], "run_dir": loop["run_dir"], "response_path": str(folder / "response.txt")}
    (folder / "solve.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    record["text"] = text
    return record
