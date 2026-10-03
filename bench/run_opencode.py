"""Score pinned OpenCode once on every held-out task. Configuration name: P-CODE."""
from __future__ import annotations

import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.external.opencode_run import run_opencode  # noqa: E402
from agents.llm import extract_sysml  # noqa: E402
from bench.experiment import grade, load_env  # noqa: E402
from mvp.engine import run_submitted_model  # noqa: E402

HELD = ROOT / "bench" / "tasks" / "t4_maritime_isr" / "heldout"


def main() -> None:
    load_env()
    tasks = [json.loads(line) for line in (HELD / "index.jsonl").read_text(encoding="utf-8").splitlines()]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    out = ROOT / "analysis" / f"opencode-{stamp}"
    out.mkdir(parents=True)
    for item in tasks:
        task_dir = ROOT / item["path"]
        record = {"task_id": item["id"], "type": item["type"], "configuration": "P-CODE"}
        try:
            solved = run_opencode(task_dir)
            case = yaml.safe_load((task_dir / "case.yaml").read_text(encoding="utf-8"))
            if case["type"] in {"GEN", "MOD"} and case.get("package"):
                source = extract_sysml(solved["text"])
                path = Path(solved["workspace"]) / f"{case['package']}.sysml"
                path.write_text(source, encoding="utf-8")
                validated = run_submitted_model([path], case["package"], label=f"P-CODE-{item['id']}")
                solved["run_dir"] = validated["run_dir"]
                solved["engine_run"] = validated["run_id"]
                solved["sysml_status"] = validated["sysml"]["status"]
            scored = grade(task_dir, solved)
            record.update({"status": scored["status"], "sysml_status": scored.get("sysml_status"),
                           "engineering_status": scored.get("engineering_status"),
                           "returncode": solved["returncode"], "workspace": solved["workspace"]})
        except Exception as exc:
            record.update({"status": "FAIL", "error": f"{type(exc).__name__}: {exc}",
                           "trace": traceback.format_exc()[-1500:]})
        with (out / "results.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({key: value for key, value in record.items() if key != "trace"},
                                    ensure_ascii=False) + "\n")
        print(item["id"], record["status"], flush=True)
    print(out)


if __name__ == "__main__":
    main()
