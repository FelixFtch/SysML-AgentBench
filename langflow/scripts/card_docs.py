"""Write docs/langflow/05-cards.md from the RTRC cards themselves (langflow/components/rtrc/*.py): for every card its name,
what it does, every input with its tooltip, every output, which shell-service routes it calls, and the module's own notes.

    .venv-langflow/bin/python langflow/scripts/card_docs.py

Needs the Langflow environment (the cards import lfx). The page is generated; edit the card and regenerate.
"""
from __future__ import annotations

import importlib
import inspect
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPONENTS = ROOT / "langflow" / "components"
sys.path.insert(0, str(COMPONENTS))
DOC = ROOT / "docs" / "langflow" / "05-cards.md"

HEAD = """# 5 · The cards (RTRC custom components)

**You get:** every RTRC card in the Langflow sidebar: what it does, its inputs and outputs, what it calls.
**You need:** nothing; find the card you dragged onto the canvas.

Each card is one Python class in [`langflow/components/rtrc/`](../../langflow/components/rtrc/). Langflow loads the folder at
start (`LANGFLOW_COMPONENTS_PATH`). The cards do little themselves: most call the RTRC shell service
(`bench/shell_service.py`, 127.0.0.1:8781) over HTTP, which runs the same functions the results page runs. Change a
card, restart Langflow. How to write one: [06-make-your-own.md](06-make-your-own.md), section B.

This page is generated from the card files by `langflow/scripts/card_docs.py`; do not edit it by hand.
"""


def _routes(source: str) -> list[str]:
    return sorted(set(re.findall(r'"(/(?:tool|run|exam|chat|cameo|gate|mod|memory|facts)[^"\s]*)"', source)))


def main() -> None:
    from lfx.custom.custom_component.component import Component
    sections = []
    for path in sorted((COMPONENTS / "rtrc").glob("rtrc_*.py")):
        module = importlib.import_module(f"rtrc.{path.stem}")
        source = path.read_text(encoding="utf-8")
        doc = (inspect.getdoc(module) or "").strip()
        classes = [obj for _, obj in inspect.getmembers(module, inspect.isclass)
                   if issubclass(obj, Component) and obj is not Component and obj.__module__ == module.__name__]
        for cls in classes:
            lines = [f"\n## {cls.display_name}\n",
                     f"`{cls.__name__}` · file [`rtrc/{path.name}`](../../langflow/components/rtrc/{path.name})\n",
                     f"{cls.description}\n"]
            inputs = getattr(cls, "inputs", []) or []
            if inputs:
                lines.append("| Input | Type | What it is |\n|---|---|---|")
                for item in inputs:
                    kind = type(item).__name__.replace("Input", "")
                    extra = ""
                    options = getattr(item, "options", None)
                    if options and not callable(options):
                        extra = f" Options: {', '.join(str(o) for o in options[:8])}{'…' if len(options) > 8 else ''}."
                        if getattr(item, "combobox", False):
                            extra += " Any value may be typed."
                    info = re.sub(r"\s+", " ", (getattr(item, "info", "") or "")).strip()
                    advanced = " (advanced)" if getattr(item, "advanced", False) else ""
                    lines.append(f"| **{item.display_name or item.name}**{advanced} | {kind} | {info}{extra} |")
            outputs = getattr(cls, "outputs", []) or []
            if outputs:
                lines.append("\n| Output | Method |\n|---|---|")
                for out in outputs:
                    lines.append(f"| **{out.display_name or out.name}** | `{out.method}` |")
            routes = _routes(source)
            if routes:
                lines.append(f"\nCalls the shell service at: {', '.join(f'`{r}`' for r in routes)}.")
            if doc:
                lines.append(f"\n**From the file:** {doc}")
            sections.append("\n".join(lines))
    DOC.write_text(HEAD + "\n".join(sections) + "\n", encoding="utf-8")
    print(f"wrote {DOC.relative_to(ROOT)} ({len(sections)} cards)")


if __name__ == "__main__":
    main()
