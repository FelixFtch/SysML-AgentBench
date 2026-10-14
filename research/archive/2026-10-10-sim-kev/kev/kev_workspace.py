"""The Kev workspaces of the OpenCode-with-memory assistant (project 7, langflow/flows/7-kev-tools/): the same two
workspaces tools/assistant/workspace.py prepares — chat and exam — with one difference: the `kev` MCP server
(tools/kev_mcp.py, 127.0.0.1:8793) is mounted next to `rtrc`, so the assistant also has the Kev requirement
classifier. The homes are separate (~/.rtrc-assistant-kev, ~/.rtrc-assistant-kev-exam), so nothing changes for the
two flows of project 3, which keep their own homes.

    python3 tools/assistant/kev_workspace.py --mode chat --model "qwen3.8-27b (Ollama)"
    python3 tools/assistant/kev_workspace.py --mode exam --model qwen3.8-flash

The Langflow card RtrcOpenCodeKevAssistant (langflow/components/rtrc/rtrc_opencode_kev.py) runs this script before
each turn, exactly the way RtrcOpenCodeAssistant runs workspace.py.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
# workspace.py reads these at import time; the Kev variants get their own homes, apart from project 3's.
os.environ["RTRC_ASSISTANT_HOME"] = os.environ.get("KEV_ASSISTANT_HOME", str(Path.home() / ".rtrc-assistant-kev"))
os.environ["RTRC_ASSISTANT_EXAM_HOME"] = os.environ.get("KEV_ASSISTANT_EXAM_HOME", str(Path.home() / ".rtrc-assistant-kev-exam"))

from tools.assistant import workspace  # noqa: E402

KEV_MCP_URL = os.environ.get("KEV_MCP_URL", "http://127.0.0.1:8793/mcp")
KEV_CHAT_SECTION = """

Tool of the `kev` server: kev_classify_requirement judges whether sentences are software requirement statements. Pass the sentences in its `sentences` argument, one per line. It returns one verdict per sentence — requirement yes or no with a probability — in milliseconds; it is a small decision model (Kev), not a chat model, and it writes nothing. Use it whenever the engineer asks whether a sentence or a line is a requirement."""
KEV_EXAM_SECTION = """

One more tool: kev_classify_requirement judges whether sentences are software requirement statements. Pass the sentences in its `sentences` argument, one per line; it returns yes or no with a probability per sentence, in milliseconds. Use it when the task asks which sentences are requirements."""


def prepare(model: str = workspace.DEFAULT_MODEL, mode: str = "chat") -> tuple[Path, str]:
    """The workspace of `mode` with the kev MCP server mounted and its tool named in the prompt."""
    home, model_id = workspace.prepare(model, mode)  # opencode.json (rtrc server, tool rules) and the prompt
    config = json.loads((home / "opencode.json").read_text(encoding="utf-8"))
    config["mcp"]["kev"] = {"type": "remote", "url": KEV_MCP_URL, "enabled": True, "timeout": workspace.TOOL_TIMEOUT_MS}
    (home / "opencode.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    prompt = home / "rtrc-assistant.md"
    prompt.write_text(prompt.read_text(encoding="utf-8") + (KEV_CHAT_SECTION if mode == "chat" else KEV_EXAM_SECTION),
                      encoding="utf-8")
    return home, model_id


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--model", default=None, help=f"{workspace.DEFAULT_MODEL} (chat default) or qwen3.8-flash (exam default)")
    parser.add_argument("--mode", default="chat", choices=("chat", "exam"), help="chat or exam (a fresh session per task)")
    args = parser.parse_args()
    model = args.model or (workspace.DEFAULT_MODEL if args.mode == "chat" else workspace.EXAM_MODEL)
    path, model_id = prepare(model, args.mode)
    print(path)
    print(model_id, file=sys.stderr)


if __name__ == "__main__":
    main()
