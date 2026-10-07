"""The workspace of the RTRC design assistant: OpenCode as the conversational harness over the RTRC MCP tools.

    python3 tools/assistant/workspace.py                      # prepare it and print its path
    python3 tools/assistant/workspace.py --model qwen3.8-max   # the cloud model instead of the local one

The assistant is OpenCode (the pinned binary of the exam) talking to the engineer, with the local Qwen3.8-27B served
by Ollama as its model and the RTRC MCP server (tools/assistant_mcp.py, 127.0.0.1:8782) as its only tools: memory
search, the verified design pipeline (which runs its own, sandboxed OpenCode to write the designs), the official Pilot,
the memory gate, decisions, Cameo export. The built-in file and shell tools are switched off, so the conversation layer
reads and writes nothing on this machine; the pipeline's sandbox rules (decision 026) are unchanged underneath.

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
PROMPT = Path(__file__).resolve().parent / "rtrc-assistant.md"
MCP_URL = os.environ.get("RTRC_ASSISTANT_MCP_URL", "http://127.0.0.1:8782/mcp")
DEFAULT_MODEL = "qwen3.8-27b (Ollama)"
TOOL_TIMEOUT_MS = 30 * 60 * 1000  # OpenCode's default MCP request timeout is far below one run_design
# OpenCode's own tools stay off: the assistant acts through the rtrc MCP tools only.
BUILTIN_TOOLS_OFF = {name: False for name in ("bash", "edit", "write", "patch", "read", "grep", "glob", "list", "webfetch", "todowrite", "todoread", "task")}


def prepare(model: str = DEFAULT_MODEL) -> tuple[Path, str]:
    """Write opencode.json and the prompt into the workspace; return (path, provider/model id)."""
    model_id, config = provider_config(model)
    config.update({
        "$schema": "https://opencode.ai/config.json",
        "share": "disabled",
        # Session titles and other small tasks use the same model, so nothing goes to a third-party endpoint.
        "small_model": model_id,
        # The per-server timeout also bounds tool calls (OpenCode passes it to callTool); run_design takes minutes.
        "mcp": {"rtrc": {"type": "remote", "url": MCP_URL, "enabled": True, "timeout": TOOL_TIMEOUT_MS}},
        "experimental": {"mcp_timeout": TOOL_TIMEOUT_MS},
        # The default agent becomes the RTRC assistant: our prompt, no file or shell tools.
        "agent": {"build": {"description": "RTRC design assistant", "prompt": "{file:./rtrc-assistant.md}", "tools": dict(BUILTIN_TOOLS_OFF)},
                  "plan": {"disable": True}},
    })
    HOME.mkdir(parents=True, exist_ok=True)
    (HOME / "opencode.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    shutil.copyfile(PROMPT, HOME / "rtrc-assistant.md")
    return HOME, model_id


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"{DEFAULT_MODEL} (default), qwen3.8-max or qwen3.8-flash")
    args = parser.parse_args()
    if args.model not in LOCAL_MODELS and args.model not in ("qwen3.8-max", "qwen3.8-flash"):
        sys.exit(f"Unknown model {args.model!r}")
    path, model_id = prepare(args.model)
    print(path)
    print(model_id, file=sys.stderr)


if __name__ == "__main__":
    main()
