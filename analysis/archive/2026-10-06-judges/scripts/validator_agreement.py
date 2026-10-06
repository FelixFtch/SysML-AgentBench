"""Second model versus the tool on replicate 1 of the GEN and MOD tasks.

The second model's verdict is not written back into the score.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.llm import chat, extract_json  # noqa: E402
from bench.experiment import load_env  # noqa: E402

SYSTEM = """You judge a SysML submission against the requirements.
Reply with one JSON object and no prose:
{"overall":"pass|fail","reason":"..."}
Use fail when the text is not legal SysML, omits a required element, or a stated numeric budget is exceeded.
"""


def main() -> None:
    load_env()
    rows = [json.loads(line) for line in (ROOT / "analysis" / "heldout-20261003T000045" / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    rows = [row for row in rows if row["type"] in {"GEN", "MOD"} and row["repeat"] == 1 and row.get("engine_run")]
    results = []
    for row in rows:
        run = ROOT / "mvp" / "runs" / row["engine_run"]
        model = next((run / "model").glob("*.sysml")).read_text(encoding="utf-8")
        requirements = (ROOT / "bench" / "tasks" / "t4_maritime_isr" / "heldout" / row["task_id"] / "input" / "requirements.md").read_text(encoding="utf-8")
        completed = chat([
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Requirements:\n{requirements}\n\nSysML:\n{model}"},
        ], max_tokens=400, temperature=0)
        try:
            parsed = extract_json(completed["text"])
            verdict = str(parsed.get("overall", "")).lower()
        except (ValueError, json.JSONDecodeError):
            verdict = ""
        tool_fail = row["status"] == "FAIL"
        validator_fail = verdict == "fail"
        results.append({"task_id": row["task_id"], "configuration": row["configuration"],
                        "tool_status": row["status"], "validator_overall": verdict or "unparsed",
                        "agree": (tool_fail == validator_fail) if verdict in {"pass", "fail"} else False,
                        "false_pass": bool(tool_fail and verdict == "pass")})
        print(row["task_id"], row["configuration"], row["status"], verdict, flush=True)
    agreed = sum(item["agree"] for item in results)
    false_pass = sum(item["false_pass"] for item in results)
    summary = {"cells": len(results), "agree": agreed,
               "agreement_rate": round(agreed / len(results), 3) if results else None,
               "false_pass": false_pass, "items": results}
    out = ROOT / "analysis" / "validator-agreement.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: summary[key] for key in ("cells", "agree", "agreement_rate", "false_pass")}))


if __name__ == "__main__":
    main()
