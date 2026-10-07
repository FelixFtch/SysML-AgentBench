"""The workspace of the RTRC design assistant: OpenCode as the conversational harness over the RTRC MCP tools.

    python3 tools/assistant/workspace.py                      # prepare it and print its path
    python3 tools/assistant/workspace.py --model qwen3.8-max   # the cloud model instead of the local one
    python3 tools/assistant/workspace.py --mode exam --model qwen3.8-flash   # the exam workspace (decision 035)

The assistant is OpenCode (the pinned binary of the exam) talking to the engineer, with the local Qwen3.8-27B served
by Ollama as its model and the RTRC MCP server (tools/assistant_mcp.py, 127.0.0.1:8782) as its only tools: memory
search, the verified design pipeline (which runs its own, sandboxed OpenCode to write the designs), the official Pilot,
the memory gate, decisions, Cameo export. The built-in file and shell tools are switched off, so the conversation layer
reads and writes nothing on this machine; the pipeline's sandbox rules (decision 026) are unchanged underneath.

The exam mode is the same harness sitting the 27-task exam: a second workspace (~/.rtrc-assistant-exam) whose prompt
is tools/assistant/rtrc-assistant-exam.md with the frozen exam rules of agents/solve.py appended, and whose MCP tools
are only search_memory and validate_sysml_text; no design run, no write to memory. The Langflow node runs a fresh
OpenCode session per task there, so nothing carries over between tasks.

The workspace is a directory outside the repository (RTRC_ASSISTANT_HOME, default ~/.rtrc-assistant) holding
opencode.json and the prompt; OpenCode keeps its sessions per directory, so a conversation can be continued.
scripts/assistant.sh opens it in the terminal; the Langflow node RtrcOpenCodeAssistant runs one turn per message.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.external.opencode_run import provider_config  # noqa: E402
from agents.llm_local import LOCAL_MODELS  # noqa: E402

HOME = Path(os.environ.get("RTRC_ASSISTANT_HOME", Path.home() / ".rtrc-assistant"))
EXAM_HOME = Path(os.environ.get("RTRC_ASSISTANT_EXAM_HOME", Path.home() / ".rtrc-assistant-exam"))
HERE = Path(__file__).resolve().parent
PROMPT = HERE / "rtrc-assistant.md"
EXAM_PROMPT = HERE / "rtrc-assistant-exam.md"
MCP_URL = os.environ.get("RTRC_ASSISTANT_MCP_URL", "http://127.0.0.1:8782/mcp")
DEFAULT_MODEL = "qwen3.8-27b (Ollama)"
EXAM_MODEL = "qwen3.8-flash"
CLOUD_MODELS = ("qwen3.8-max", "qwen3.8-flash")
MODES = ("chat", "exam")
TOOL_TIMEOUT_MS = 30 * 60 * 1000  # OpenCode's default MCP request timeout is far below one run_design
# OpenCode's own tools stay off: the assistant acts through the rtrc MCP tools only.
BUILTIN_TOOLS_OFF = {name: False for name in ("bash", "edit", "write", "patch", "read", "grep", "glob", "list", "webfetch", "todowrite", "todoread", "task")}
# The MCP tools (OpenCode names them rtrc_<tool>); the exam keeps two of them.
MCP_TOOLS = ("list_projects", "search_memory", "read_project", "run_design", "design_status", "validate_sysml_text",
             "write_to_memory", "record_decision", "export_cameo")
EXAM_TOOLS = ("search_memory", "validate_sysml_text")
# How the exam prompt names the two tools for this harness (the Langflow Agent names its Run Flow cards differently).
OPENCODE_EXAM_TOOLS = ("validate_sysml_text parses SysML v2 with the official SysML v2 Pilot, the same judge that scores the exam; "
                       "run it on every model you write and fix what it reports before you reply. search_memory finds elements of "
                       "the existing maritime model and of approved designs; use it for names when the task refers to the existing model.")


def exam_prompt(tools: str) -> str:
    """The exam prompt: the header file with the frozen rules of agents/solve.py filled in; `tools` names the two tools."""
    from agents.solve import ALIGN_RULES, SYSML_RULES
    text = EXAM_PROMPT.read_text(encoding="utf-8")
    return text.replace("{TOOLS}", tools).replace("{SYSML_RULES}", SYSML_RULES.strip()).replace("{ALIGN_RULES}", ALIGN_RULES.strip()) + "\n"


def prepare(model: str = DEFAULT_MODEL, mode: str = "chat") -> tuple[Path, str]:
    """Write opencode.json and the prompt into the workspace of `mode`; return (path, provider/model id)."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    if model not in LOCAL_MODELS:
        from bench.experiment import load_env
        load_env()  # the cloud provider block reads the Qwen endpoint from .env (the key stays an {env:...} reference)
    model_id, config = provider_config(model)
    home = HOME if mode == "chat" else EXAM_HOME
    tools = dict(BUILTIN_TOOLS_OFF)
    if mode == "exam":
        tools.update({f"rtrc_{name}": False for name in MCP_TOOLS if name not in EXAM_TOOLS})
    config.update({
        "$schema": "https://opencode.ai/config.json",
        "share": "disabled",
        # Session titles and other small tasks use the same model, so nothing goes to a third-party endpoint.
        "small_model": model_id,
        # The per-server timeout also bounds tool calls (OpenCode passes it to callTool); run_design takes minutes.
        "mcp": {"rtrc": {"type": "remote", "url": MCP_URL, "enabled": True, "timeout": TOOL_TIMEOUT_MS}},
        "experimental": {"mcp_timeout": TOOL_TIMEOUT_MS},
        # The default agent becomes the RTRC assistant: our prompt, no file or shell tools.
        "agent": {"build": {"description": "RTRC design assistant" if mode == "chat" else "RTRC exam candidate",
                            "prompt": "{file:./rtrc-assistant.md}", "tools": tools},
                  "plan": {"disable": True}},
    })
    home.mkdir(parents=True, exist_ok=True)
    (home / "opencode.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    if mode == "chat":
        shutil.copyfile(PROMPT, home / "rtrc-assistant.md")
    else:
        (home / "rtrc-assistant.md").write_text(exam_prompt(OPENCODE_EXAM_TOOLS), encoding="utf-8")
    return home, model_id


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--model", default=None, help=f"{DEFAULT_MODEL} (chat default), qwen3.8-max or qwen3.8-flash (exam default)")
    parser.add_argument("--mode", default="chat", choices=MODES, help="chat (the design assistant) or exam (one task per session, two tools)")
    args = parser.parse_args()
    model = args.model or (DEFAULT_MODEL if args.mode == "chat" else EXAM_MODEL)
    if model not in LOCAL_MODELS and model not in CLOUD_MODELS:
        sys.exit(f"Unknown model {model!r}")
    path, model_id = prepare(model, args.mode)
    print(path)
    print(model_id, file=sys.stderr)


if __name__ == "__main__":
    main()
