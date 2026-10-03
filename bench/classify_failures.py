"""Label every held-out FAIL from the saved runs. No model is called."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
RUNS = [
    ROOT / "analysis" / "heldout-20261003T000045" / "results.jsonl",
    ROOT / "analysis" / "heldout-20261003T001321" / "results.jsonl",
]
OUT = ROOT / "analysis" / "failure-classes.jsonl"


def _diagnostics(run_id: str) -> list[str]:
    path = ROOT / "mvp" / "runs" / run_id / "sysml" / "validation.json"
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [item.get("message", "") for item in data.get("diagnostics") or []]


def _syntax_class(messages: list[str]) -> str:
    text = " ".join(messages)
    if "Real" in text or "attribute must be typed" in text:
        return "syntax-real-or-import"
    if "related elements" in text or "input '.'" in text or "connection" in text.lower():
        return "syntax-connection"
    return "syntax-other"


def _text_answer(task_id: str, configuration: str, repeat: int) -> str | None:
    # Replicates share the agent-run clock. The Nth saved answer for this pair is repeat N.
    folders = sorted((ROOT / "mvp" / "agent-runs").glob(f"20261003T00*-{configuration}-{task_id}"))
    chosen = [folder for folder in folders if (folder / "response.txt").is_file()]
    index = repeat - 1
    if index < 0 or index >= len(chosen):
        return None
    return (chosen[index] / "response.txt").read_text(encoding="utf-8")


def main() -> None:
    from bench.rescore import apply, load
    from bench.score_answer import score_answer
    table = load()
    rows = []
    for path in RUNS:
        rows.extend(apply("flash", json.loads(line), table) for line in path.read_text(encoding="utf-8").splitlines())
    labeled = []
    for row in rows:
        if row["status"] != "FAIL":
            continue
        kind = row["type"]
        label = "unclassified"
        detail = ""
        if kind in {"GEN", "MOD"} and row.get("sysml_status") == "FAIL":
            messages = _diagnostics(row.get("engine_run") or "")
            label = _syntax_class(messages)
            detail = messages[0] if messages else "Official validation failed."
        elif kind in {"QRY", "AMB", "RT"}:
            text = _text_answer(row["task_id"], row["configuration"], row["repeat"])
            task = ROOT / "bench" / "tasks" / "t4_maritime_isr" / "heldout" / row["task_id"]
            scored = score_answer(task, text or "")
            if kind == "QRY":
                actual = scored.get("actual")
                expected = scored.get("expected")
                label = "query-renamed"
                if isinstance(expected, dict) and isinstance(actual, dict):
                    for key, value in expected.items():
                        if isinstance(value, (int, float)) and not isinstance(value, bool):
                            got = actual.get(key)
                            if not isinstance(got, (int, float)) or float(got) != float(value):
                                label = "query-wrong-number"
                detail = json.dumps({"expected": expected, "actual": actual}, ensure_ascii=False)[:240]
            elif kind == "AMB":
                if scored.get("invented_number"):
                    label = "invented-number"
                elif not scored.get("asked"):
                    label = "no-question"
                else:
                    label = "missed-topic"
                detail = json.dumps(scored.get("missing_questions"), ensure_ascii=False)
            else:
                label = "missing-phrase"
                detail = json.dumps(scored.get("missing"), ensure_ascii=False)
        labeled.append({"task_id": row["task_id"], "type": kind, "configuration": row["configuration"],
                        "repeat": row["repeat"], "class": label, "detail": detail})
    OUT.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in labeled), encoding="utf-8")
    counts = Counter(item["class"] for item in labeled)
    print(json.dumps({"failures": len(labeled), "classes": dict(counts)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
