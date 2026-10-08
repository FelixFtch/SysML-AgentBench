"""Write docs/langflow/04-flows.md and one SVG diagram per flow from the flow files, so the documentation shows what the
files hold and cannot drift from them.

    python3 langflow/scripts/flow_docs.py            # the page and the diagrams (dot from tools/graphviz or PATH)
    python3 langflow/scripts/flow_docs.py --no-svg   # the page only

For every flow: its name, file, the cards on its canvas in left-to-right order (display name, component), the note
card's text (what the flow does and what to click, as written on the canvas), and a diagram of the wiring drawn with
Graphviz from the nodes and edges. The diagrams land next to the flow files (langflow/flows/<project>/<slug>.svg).
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "langflow" / "flows"))
from catalog import FLOWS_DIR, FOLDERS, PROJECTS, flow_file  # noqa: E402

DOC = ROOT / "docs" / "langflow" / "04-flows.md"
DOT = ROOT / "tools" / "graphviz" / "bin" / "dot"

HEAD = """# 4 · The flows, one by one

**You get:** for every flow, what is on its canvas, what it does, what to click and what to change.
**You need:** nothing; read the section you are about to open.

This page is generated from the flow files by `langflow/scripts/flow_docs.py`: the card list and the wiring diagram come
from the JSON, the explanation is the note card written on the canvas itself. Edit the flows (or
`langflow/scripts/build_flows.py`) and regenerate; do not edit this page by hand.

**Exam** flows take one sealed task in and are scored outside Langflow by the frozen scorer; **chat** flows are a
conversation and score nothing. Every model card accepts any model name ([02-keys-and-models.md](02-keys-and-models.md)).
"""


def _nodes(flow: dict) -> tuple[list[dict], list[str]]:
    cards, notes = [], []
    for node in flow["data"]["nodes"]:
        data = node.get("data", {})
        info = data.get("node", {})
        if node.get("type") == "noteNode":
            text = (info.get("description") or "").strip()
            if text:
                notes.append(text)
            continue
        cards.append({"id": node["id"], "kind": data.get("type") or "?", "title": info.get("display_name") or data.get("type") or node["id"],
                      "info": (info.get("description") or "").strip(), "x": node.get("position", {}).get("x", 0), "y": node.get("position", {}).get("y", 0)})
    cards.sort(key=lambda c: (round(c["x"] / 200), c["y"]))
    return cards, notes


def _dot(flow: dict, cards: list[dict]) -> str:
    def q(text: str) -> str:
        return text.replace("\\", "\\\\").replace('"', '\\"')
    lines = ["digraph flow {", "  rankdir=LR; nodesep=0.35; ranksep=0.6; bgcolor=\"transparent\";",
             "  node [shape=box, style=\"rounded,filled\", fontname=\"Helvetica\", fontsize=11, color=\"#9aa4ad\", fillcolor=\"#f6f8fa\"];",
             "  edge [color=\"#6b7680\", arrowsize=0.7];"]
    colour = {"ChatInput": "#dff1ff", "ChatOutput": "#dff1ff", "Agent": "#fff1cc", "RunFlow": "#e6f4e6", "MCPTools": "#e6f4e6", "Knowledge": "#e6f4e6",
              "ConditionalRouter": "#f3e8ff", "HumanInput": "#ffe4e4"}
    for card in cards:
        fill = colour.get(card["kind"]) or ("#e9f7ef" if card["kind"].startswith("Rtrc") else "#f6f8fa")
        title = re.sub(r"\s+", " ", card["title"])[:48]
        lines.append(f'  "{q(card["id"])}" [label="{q(title)}\\n{q(card["kind"])}", fillcolor="{fill}"];')
    ids = {c["id"] for c in cards}
    for edge in flow["data"]["edges"]:
        if edge["source"] in ids and edge["target"] in ids:
            lines.append(f'  "{q(edge["source"])}" -> "{q(edge["target"])}";')
    lines.append("}")
    return "\n".join(lines)


def _svg(dot_src: str, target: Path, dot_bin: str) -> bool:
    try:
        completed = subprocess.run([dot_bin, "-Tsvg"], input=dot_src, text=True, capture_output=True, check=True, timeout=60)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False
    target.write_text(completed.stdout, encoding="utf-8")
    return True


def _kind(slug: str) -> str:
    if "exam" in slug:
        return "exam"
    if "chat" in slug or slug == "rtrc-assistant-langchain":
        return "chat"
    if slug.startswith("tool-"):
        return "tool flow (run by projects 3 and 4)"
    return "other"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--no-svg", action="store_true")
    args = parser.parse_args()
    dot_bin = str(DOT) if DOT.is_file() else shutil.which("dot")
    if not args.no_svg and not dot_bin:
        print("Graphviz 'dot' not found (tools/graphviz/bin/dot or PATH); writing the page without new diagrams", file=sys.stderr)
    out = [HEAD]
    drawn = 0
    for project, description, flows in PROJECTS:
        folder = FOLDERS[project]
        out.append(f"\n## {project}\n\n{description}\n\nFolder: [`langflow/flows/{folder}/`](../../langflow/flows/{folder}/)\n")
        for slug, name in flows:
            path = flow_file(slug)
            flow = json.loads(path.read_text(encoding="utf-8"))
            cards, notes = _nodes(flow)
            svg = path.with_suffix(".svg")
            if not args.no_svg and dot_bin and _svg(_dot(flow, cards), svg, dot_bin):
                drawn += 1
            rel_json = f"../../langflow/flows/{folder}/{path.name}"
            out.append(f"\n### {name}\n")
            out.append(f"`{_kind(slug)}` · file [`{folder}/{path.name}`]({rel_json}) · {len(cards)} cards · {flow.get('description') or ''}\n")
            if svg.is_file():
                out.append(f"![{name}]({rel_json[:-5]}.svg)\n")
            out.append("| Card | Component | What it does |\n|---|---|---|")
            for card in cards:
                info = re.sub(r"\s+", " ", card["info"])
                out.append(f"| {card['title']} | `{card['kind']}` | {info[:220]}{'…' if len(info) > 220 else ''} |")
            if notes:
                note = notes[0]
                # the note starts with a heading that repeats the flow name; keep the body
                body = re.sub(r"^#\s+.*\n+", "", note, count=1).strip()
                out.append(f"\n**On the canvas:** {body}\n")
    DOC.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"wrote {DOC.relative_to(ROOT)}" + (f", {drawn} diagram(s)" if drawn else ""))


if __name__ == "__main__":
    main()
