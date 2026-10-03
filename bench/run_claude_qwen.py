"""Run the 24 held-out tasks through the Qwen Claude Code profile.

Uses `ccr default-claude-code`, which points at 127.0.0.1:3456 and the qwen
provider. It does not use the GLM config directory.
"""
from __future__ import annotations

import json
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.llm import extract_sysml  # noqa: E402
from bench.experiment import grade  # noqa: E402
from mvp.engine import run_submitted_model  # noqa: E402

HELD = ROOT / "bench" / "tasks" / "t4_maritime_isr" / "heldout"
CCR = ["ccr", "default-claude-code", "--", "-p", "--model", "qwen3.8-max"]


def _prompt(task_dir: Path) -> str:
    case = yaml.safe_load((task_dir / "case.yaml").read_text(encoding="utf-8"))
    text = (task_dir / "input" / "requirements.md").read_text(encoding="utf-8")
    extra = []
    baseline = task_dir / "input" / "baseline"
    if baseline.is_dir():
        for path in sorted(baseline.glob("*.sysml")):
            extra.append(f"Baseline {path.name}:\n```sysml\n{path.read_text(encoding='utf-8')}```")
    given = task_dir / "input" / "model.sysml"
    if given.is_file() and case["type"] in {"QRY", "RT"}:
        extra.append(f"Given model:\n```sysml\n{given.read_text(encoding='utf-8')}```")
    body = text if not extra else text + "\n\n" + "\n\n".join(extra)
    if case["type"] in {"GEN", "MOD"}:
        body += "\n\nReply with one fenced sysml block and no other text."
    return body


def main() -> None:
    wanted = set(sys.argv[1:])
    tasks = [json.loads(line) for line in (HELD / "index.jsonl").read_text(encoding="utf-8").splitlines()]
    if wanted:
        tasks = [item for item in tasks if item["id"] in wanted]
        missing = wanted - {item["id"] for item in tasks}
        if missing:
            raise SystemExit(f"unknown task: {', '.join(sorted(missing))}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    out = ROOT / "analysis" / f"claude-qwen-{stamp}"
    out.mkdir(parents=True)
    for item in tasks:
        task_dir = ROOT / item["path"]
        record = {"task_id": item["id"], "type": item["type"], "configuration": "P-CODE-2",
                  "provider_model": "qwen3.8-max"}
        try:
            completed = subprocess.run(CCR + [_prompt(task_dir)], text=True, capture_output=True)
            text = completed.stdout
            (out / f"{item['id']}.txt").write_text(text, encoding="utf-8")
            solved = {"text": text, "run_dir": None, "sysml_status": None}
            case = yaml.safe_load((task_dir / "case.yaml").read_text(encoding="utf-8"))
            if case["type"] in {"GEN", "MOD"} and case.get("package"):
                source = extract_sysml(text)
                path = out / f"{item['id']}.sysml"
                path.write_text(source, encoding="utf-8")
                validated = run_submitted_model([path], case["package"], label=f"claude-{item['id']}")
                solved["run_dir"] = validated["run_dir"]
                solved["sysml_status"] = validated["sysml"]["status"]
            scored = grade(task_dir, solved)
            record.update({"status": scored["status"], "sysml_status": scored.get("sysml_status"),
                           "engineering_status": scored.get("engineering_status"),
                           "returncode": completed.returncode})
        except Exception as exc:
            record.update({"status": "FAIL", "error": f"{type(exc).__name__}: {exc}",
                           "trace": traceback.format_exc()[-1200:]})
        with (out / "results.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({k: v for k, v in record.items() if k != "trace"}, ensure_ascii=False) + "\n")
        print(item["id"], record["status"], flush=True)
    print(out)


if __name__ == "__main__":
    main()
