"""Run pinned OpenCode v1.18.27 on one task directory.

The workspace contains the task input only. Gold is not copied in.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BINARY = ROOT / "tools" / "opencode" / "opencode"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _base_url() -> str:
    url = os.environ["MVP_LLM_URL"]
    suffix = "/chat/completions"
    if url.endswith(suffix):
        url = url[: -len(suffix)]
    return url


def run_opencode(task_dir: Path) -> dict:
    if not BINARY.is_file():
        raise FileNotFoundError(f"Missing pinned binary {BINARY}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    case_id = task_dir.name
    work = ROOT / "mvp" / "agent-runs" / f"{stamp}-P-CODE-{case_id}"
    workspace = work / "workspace"
    shutil.copytree(task_dir / "input", workspace / "input")
    shutil.copy2(ROOT / "AGENTS.md", workspace / "AGENTS.md")
    model = os.environ.get("MVP_LLM_MODEL", "qwen3.8-flash")
    config = {
        "model": f"qwen/{model}",
        "provider": {"qwen": {
            "npm": "@ai-sdk/openai-compatible",
            "options": {"baseURL": _base_url(), "apiKey": "{env:MVP_LLM_API_KEY}"},
            "models": {model: {"name": model}},
        }},
    }
    (workspace / "opencode.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    prompt = (workspace / "input" / "requirements.md").read_text(encoding="utf-8")
    prompt += "\n\nWrite the answer into answer.md in this workspace. Follow AGENTS.md."
    completed = subprocess.run(
        [str(BINARY), "run", "--pure", "--auto", "--format", "json",
         "--dir", str(workspace), "--model", f"qwen/{model}", prompt],
        cwd=workspace, env=os.environ.copy(), text=True, capture_output=True, timeout=300,
    )
    (work / "stdout.jsonl").write_text(completed.stdout, encoding="utf-8")
    (work / "stderr.txt").write_text(completed.stderr, encoding="utf-8")
    answer = workspace / "answer.md"
    text = answer.read_text(encoding="utf-8") if answer.is_file() else completed.stdout
    return {"configuration": "P-CODE", "task_id": case_id, "returncode": completed.returncode,
            "text": text, "workspace": str(workspace), "sysml_status": None, "run_dir": None,
            "engine_run": None}
