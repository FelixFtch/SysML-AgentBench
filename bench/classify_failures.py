"""Label every failing cell of the four scored batches from the saved runs. No model is called.

Batches are the ones in bench/batches.py (direct flash, direct max, OpenCode and Claude Code in the sandbox).
Each FAIL gets one class and the evidence that decided it: the official diagnostic for a parse failure, the
missing name or pair for a checklist failure, the answer and the key for a text task.
Output: analysis/failure-classes-20261006.jsonl. The 2026-10-03 classification is kept in analysis/archive/.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bench.batches import COHORTS, rows  # noqa: E402

HELD = ROOT / "bench" / "tasks" / "t4_maritime_isr" / "heldout"
OUT = ROOT / "analysis" / "failure-classes-20261006.jsonl"
CLASS_TEXT = {
    "syntax-import": "Official parse fails on an import or an unresolved Real (a bare `import`, or `Real` used without importing ScalarValues).",
    "syntax-connection": "Official parse fails on a connection that does not name two legal ends.",
    "syntax-reference": "Official parse fails on a name that does not resolve.",
    "syntax-nesting": "Official parse fails on a nested usage written with `::` where the Pilot wants a dot (`Pkg::part.sub`).",
    "syntax-other": "Official parse fails for another reason.",
    "no-sysml": "The answer contains no SysML package to parse.",
    "checklist-missing": "Parses, but a required part, port or connection is missing.",
    "kept-value-changed": "Parses, but a value the task said to keep is changed or no longer readable.",
    "aln-missing-pair": "Alignment parses, but a required pair is not declared.",
    "aln-forbidden-pair": "Alignment declares a look-alike pair the key forbids.",
    "aln-stray": "The alignment package declares elements of its own.",
    "aln-unmatched": "Alignment pairs are right, but an element with no counterpart is not reported.",
    "query-renamed": "Query answer has the right members or values but writes a qualified name differently.",
    "query-wrong-value": "Query answer has a wrong number or member.",
    "query-no-json": "Query answer has no JSON to compare.",
    "missed-topic": "Asks, but not about the missing quantity.",
    "no-question": "Does not ask; describes what is missing or proceeds.",
    "invented-number": "Puts a number with a unit that the task does not contain.",
    "missing-phrase": "Round trip leaves out a required phrase.",
    "agent-error": "The agent run ended with an error.",
    "agent-timeout": "The agent hit the 900 s limit before writing answer.md.",
}


def _last_validate(workspace: Path) -> str:
    results = sorted((workspace / "validation").glob("*/result.json"))
    if not results:
        return "it never ran ./validate"
    status = json.loads(results[-1].read_text(encoding="utf-8")).get("status")
    return f"its last of {len(results)} ./validate runs was {status}"


def _diagnostics(run_id: str | None) -> list[str]:
    path = ROOT / "mvp" / "runs" / (run_id or "-") / "sysml" / "validation.json"
    if not path.is_file():
        return []
    return [item.get("message", "") for item in json.loads(path.read_text(encoding="utf-8")).get("diagnostics") or []]


def _last_run(row: dict) -> str | None:
    ids = [item.get("run_id") for item in row.get("attempts") or [] if item.get("run_id")]
    return ids[-1] if ids else row.get("engine_run")


def _syntax_class(messages: list[str]) -> str:
    text = " ".join(messages)
    if "use dot notation for nesting" in text:
        return "syntax-nesting"
    if "input 'import'" in text or "to Type 'Real'" in text or "attribute must be typed" in text:
        return "syntax-import"
    if "related elements" in text or "input '.'" in text or "connect" in text.lower():
        return "syntax-connection"
    if "Couldn't resolve reference" in text:
        return "syntax-reference"
    return "syntax-other"


def _answer(row: dict) -> str:
    folder = row.get("_folder")
    if folder and (Path(folder) / "response.txt").is_file():
        return (Path(folder) / "response.txt").read_text(encoding="utf-8", errors="replace")
    workspace = row.get("workspace")
    if workspace and (Path(workspace) / "answer.md").is_file():
        return (Path(workspace) / "answer.md").read_text(encoding="utf-8", errors="replace")
    return ""


def classify(row: dict) -> tuple[str, str]:
    from bench.score_alignment import score_alignment
    from bench.score_answer import score_answer
    from bench.score_task import score_run
    kind = row["type"]
    task = HELD / row["task_id"]
    if row.get("error"):
        return "agent-error", row["error"][:200]
    workspace = Path(row["workspace"]) if row.get("workspace") else None
    if workspace and str(row.get("returncode")) == "timeout" and not (workspace / "answer.md").is_file():
        return "agent-timeout", f"No answer.md when the limit was hit; {_last_validate(workspace)}."
    if kind in {"GEN", "MOD", "ALN"}:
        run = _last_run(row)
        if row.get("sysml_status") != "PASS":
            if not run:
                return "no-sysml", row.get("reason") or "No SysML package in the answer."
            messages = _diagnostics(run)
            stop = (f" (repair loop stopped: {row['stop_reason']})"
                    if row.get("configuration") in {"P1", "P2", "P3"} and row.get("stop_reason") not in {None, "pass"} else "")
            return _syntax_class(messages), (messages[0] if messages else "Official validation failed.") + stop
        if kind == "ALN":
            scored = score_alignment(ROOT / "mvp" / "runs" / run, task / "gold" / "assertions.yaml", _answer(row), sysml_status="PASS")
            if (scored.get("must_not_map") or {}).get("violations"):
                item = scored["must_not_map"]["violations"][0]
                return "aln-forbidden-pair", f"alias {item['name']} for {item['target']}"
            if scored.get("stray_declarations"):
                return "aln-stray", "; ".join(scored["stray_declarations"][:2])
            if (scored.get("must_map") or {}).get("missing"):
                item = scored["must_map"]["missing"][0]
                return "aln-missing-pair", (f"alias {item['name']} for {item['target']}" if item.get("kind", "alias") == "alias"
                                            else f"allocation {item['from']} to {item['to']}")
            return "aln-unmatched", ", ".join((scored.get("unmatched") or {}).get("missing") or [])
        scored = score_run(ROOT / "mvp" / "runs" / run, task / "gold" / "assertions.yaml")
        preserve = (scored.get("must_preserve") or {}).get("missing") or []
        if preserve:
            item = preserve[0]
            return "kept-value-changed", f"{item['qualified_name']} should be {item['expected']}, is {item['actual']}"
        missing = [*((scored.get("must_exist") or {}).get("missing") or []), *((scored.get("must_connect") or {}).get("missing") or [])]
        return "checklist-missing", json.dumps(missing[:2], ensure_ascii=False)[:200]
    scored = score_answer(task, _answer(row))
    if kind == "QRY":
        expected, actual = scored.get("expected"), scored.get("actual")
        if not isinstance(actual, dict):
            return "query-no-json", scored.get("reason") or ""
        tail = lambda value: str(value).replace(".", "::").split("::")[-1]  # noqa: E731
        renamed = all((tail(actual.get(key)) == tail(value)) if isinstance(value, str) else
                      (sorted(map(tail, actual.get(key) or [])) == sorted(map(tail, value))) if isinstance(value, list) else
                      (isinstance(actual.get(key), (int, float)) and float(actual.get(key)) == float(value))
                      for key, value in expected.items())
        return ("query-renamed" if renamed else "query-wrong-value"), json.dumps({"expected": expected, "actual": actual}, ensure_ascii=False)[:240]
    if kind == "AMB":
        if scored.get("invented_number"):
            return "invented-number", ", ".join(scored.get("invented") or [])
        if not scored.get("asked"):
            return "no-question", _answer(row).strip().replace("\n", " ")[:160]
        return "missed-topic", json.dumps(scored.get("missing_questions"), ensure_ascii=False)
    return "missing-phrase", json.dumps(scored.get("missing"), ensure_ascii=False)


def main() -> None:
    labeled = []
    for cohort in COHORTS:
        for row in rows(cohort):
            if row["status"] == "PASS":
                continue
            label, detail = classify(row)
            labeled.append({"cohort": cohort, "task_id": row["task_id"], "type": row["type"], "configuration": row.get("configuration"),
                            "repeat": row.get("repeat"), "class": label, "detail": detail})
    OUT.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in labeled), encoding="utf-8")
    summary = {cohort: dict(Counter(item["class"] for item in labeled if item["cohort"] == cohort)) for cohort in COHORTS}
    print(json.dumps({"failures": {cohort: sum(counts.values()) for cohort, counts in summary.items()}, "classes": summary}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
