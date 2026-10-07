"""Run pinned OpenCode v1.18.27 on one task directory, inside the sandbox of agents/external/jail.py.

The workspace holds the task input, the rules file and ./validate (the official Pilot). Gold, past runs and earlier
sessions are not visible (decision 026). The prompt suffix is the same one Claude Code gets.

The model comes from MVP_LLM_MODEL. The cloud Qwen models go to the Qwen endpoint of .env; the local model names of
agents/llm_local.py go to Ollama on this machine (127.0.0.1:11434, no key, thinking off) through the same
OpenAI-compatible provider package (decision 032). The sandbox shares the network, so Ollama is reachable from it.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BINARY = ROOT / "tools" / "opencode" / "opencode"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.external.jail import PROMPT_SUFFIX, fake_home, prepare_workspace, wrap  # noqa: E402


def _base_url() -> str:
    url = os.environ["MVP_LLM_URL"]
    suffix = "/chat/completions"
    if url.endswith(suffix):
        url = url[: -len(suffix)]
    return url


def provider_config(model: str) -> tuple[str, dict]:
    """OpenCode's provider block for one model name: (provider/model id, opencode.json contents)."""
    from agents.llm_local import LOCAL_BASE, LOCAL_MODELS
    if model in LOCAL_MODELS:
        tag = LOCAL_MODELS[model]
        # reasoningEffort is passed through as reasoning_effort; Ollama's OpenAI-compatible endpoint reads "none" as
        # thinking off (the same switch agents/llm_local.py uses), so the token budget goes to the answer and the tools.
        config = {
            "model": f"ollama/{tag}",
            "provider": {"ollama": {
                "npm": "@ai-sdk/openai-compatible",
                "name": "Ollama (local)",
                "options": {"baseURL": LOCAL_BASE, "apiKey": "ollama"},
                "models": {tag: {"name": tag, "options": {"reasoningEffort": "none"}}},
            }},
        }
        return f"ollama/{tag}", config
    config = {
        "model": f"qwen/{model}",
        "provider": {"qwen": {
            "npm": "@ai-sdk/openai-compatible",
            "options": {"baseURL": _base_url(), "apiKey": "{env:MVP_LLM_API_KEY}"},
            "models": {model: {"name": model}},
        }},
    }
    return f"qwen/{model}", config


def run_opencode(task_dir: Path, *, jailed: bool = True) -> dict:
    if not BINARY.is_file():
        raise FileNotFoundError(f"Missing pinned binary {BINARY}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    case_id = task_dir.name
    work = ROOT / "mvp" / "agent-runs" / f"{stamp}-{uuid.uuid4().hex[:4]}-P-CODE-{case_id}"
    workspace = work / "workspace"
    workspace.mkdir(parents=True)
    prepare_workspace(task_dir, workspace)
    model = os.environ.get("MVP_LLM_MODEL", "qwen3.8-flash")
    model_id, config = provider_config(model)
    (workspace / "opencode.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    prompt = (workspace / "input" / "requirements.md").read_text(encoding="utf-8") + PROMPT_SUFFIX
    argv = [str(BINARY), "run", "--pure", "--auto", "--format", "json", "--dir", str(workspace), "--model", model_id, prompt]
    home = None
    if jailed:
        home = fake_home(work.name)
        argv = wrap(argv, workspace, home)
    try:
        completed = subprocess.run(argv, cwd=workspace, env=os.environ.copy(), text=True, capture_output=True,
                                   timeout=int(os.environ.get("BENCH_AGENT_TIMEOUT", "900")))
        stdout, stderr, returncode = completed.stdout, completed.stderr, completed.returncode
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr, returncode = f"timeout after {exc.timeout}s", "timeout"
    finally:
        if home:
            shutil.rmtree(home, ignore_errors=True)
    (work / "stdout.jsonl").write_text(stdout, encoding="utf-8")
    (work / "stderr.txt").write_text(stderr, encoding="utf-8")
    answer = workspace / "answer.md"
    text = answer.read_text(encoding="utf-8") if answer.is_file() else stdout
    return {"configuration": "P-CODE", "task_id": case_id, "returncode": returncode, "jailed": jailed,
            "text": text, "workspace": str(workspace), "sysml_status": None, "run_dir": None, "engine_run": None}
