"""One-hop retrieval over the official parse, then one answer from qwen3.8-max.

This follows the GRAG paper's step "node plus its neighbors," using the parsed
SysML export. It does not use their MiniLM/FAISS index or their EV model, and
the retrieved text replaces the full model in the prompt.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.llm import chat  # noqa: E402
from bench.experiment import load_env  # noqa: E402
from bench.score_answer import score_answer  # noqa: E402
from mvp.engine import ModelView, exported_elements  # noqa: E402

PARSE = ROOT / "mvp" / "runs" / "20261002T231323-aea6edfc"
HELD = ROOT / "bench" / "tasks" / "t4_maritime_isr" / "heldout"


def _graph():
    cards, neighbors, _kinds = build_graph(PARSE, "MaritimeISR::")
    return cards, neighbors


def build_graph(parse_dir: Path, prefix: str):
    """Element cards and one-hop links from one official parse.

    Returns cards (id -> text), neighbors (id -> ids) and kinds ((a, b) -> "owner" | "connect").
    """
    elements = exported_elements(json.loads((parse_dir / "sysml" / "model.json").read_text(encoding="utf-8")))
    ast = json.loads((parse_dir / "sysml" / "ast-elements.json").read_text(encoding="utf-8"))
    view = ModelView(elements, ast)
    neighbors = {element["@id"]: set() for element in elements}
    kinds = {}
    for element in elements:
        owner = (element.get("owner") or {}).get("@id")
        if owner in neighbors:
            neighbors[element["@id"]].add(owner)
            neighbors[owner].add(element["@id"])
            kinds[(element["@id"], owner)] = kinds[(owner, element["@id"])] = "owner"
        for ref in element.get("relatedFeature") or []:
            other = ref.get("@id")
            if other in neighbors:
                neighbors[element["@id"]].add(other)
                neighbors[other].add(element["@id"])
                kinds[(element["@id"], other)] = kinds[(other, element["@id"])] = "connect"
    cards = {}
    for element in elements:
        name = element.get("qualifiedName")
        if not name or not name.startswith(prefix):
            continue
        bits = [element.get("@type", ""), name]
        if element.get("@type") == "AttributeUsage":
            try:
                bits.append(str(view.literal_at(name)))
            except ValueError:
                pass
        if element.get("@type") == "ConnectionUsage":
            ends = [view.reference_name(ref["@id"]) or "" for ref in element.get("relatedFeature") or []]
            bits.append(" ".join(ends))
        cards[element["@id"]] = " ".join(bits)
    return cards, neighbors, kinds


def retrieve(question: str, cards: dict, neighbors: dict, limit: int = 8) -> list[str]:
    words = {word.lower() for word in re.findall(r"[A-Za-z0-9]+", question) if len(word) > 2}
    ranked = sorted(cards, key=lambda ident: sum(word in cards[ident].lower() for word in words), reverse=True)
    chosen = []
    for ident in ranked[:4]:
        if ident not in chosen:
            chosen.append(ident)
        for hop in neighbors.get(ident, ()):
            if hop in cards and hop not in chosen:
                chosen.append(hop)
            if len(chosen) >= limit:
                break
        if len(chosen) >= limit:
            break
    return [cards[ident] for ident in chosen[:limit]]


def main() -> None:
    load_env()
    cards, neighbors = _graph()
    rows = []
    for task_id in ("QRY-01", "QRY-02", "QRY-03", "QRY-04", "QRY-05"):
        task = HELD / task_id
        question = (task / "input" / "requirements.md").read_text(encoding="utf-8")
        context = "\n".join(retrieve(question, cards, neighbors))
        completed = chat([
            {"role": "system", "content": "Answer from the retrieved model elements only. One JSON object, no prose."},
            {"role": "user", "content": question + "\n\nRetrieved elements:\n" + context},
        ], max_tokens=300, temperature=0)
        scored = score_answer(task, completed["text"])
        rows.append({"task_id": task_id, "model": completed["model"], "status": scored["status"],
                     "retrieved": context, "answer": completed["text"], "usage": completed["usage"]})
        print(task_id, scored["status"], completed["model"], flush=True)
    out = ROOT / "analysis" / "graph-query-max.json"
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
