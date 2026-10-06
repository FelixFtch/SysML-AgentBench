"""One-hop retrieval over the official parse, then one answer from qwen3.8-max.

This follows the GRAG paper's steps on the parsed SysML export: MiniLM + FAISS seeds
(bench/vector_index.py), then each node plus its neighbors. It does not use their EV
model, and the retrieved text replaces the full model in the prompt.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.llm import chat  # noqa: E402
from bench.experiment import load_env  # noqa: E402
from bench.score_answer import score_answer  # noqa: E402
from mvp.engine import ModelView, exported_elements  # noqa: E402

PARSE = ROOT / "mvp" / "runs" / "20261002T231323-aea6edfc"
MARITIME_FILE = ROOT / "scenario" / "maritime-isr" / "MaritimeISR.sysml"
HELD = ROOT / "bench" / "tasks" / "t4_maritime_isr" / "heldout"


def official_parse(saved: Path, sources: list[Path], package: str) -> Path:
    """Folder holding the official parse of `sources`.

    mvp/runs/ is not in git, so on a fresh clone the saved folder is missing. Then an earlier
    re-parse of the same bytes is reused, or the official Pilot parses the committed files once.
    """
    if (saved / "sysml" / "model.json").is_file():
        return saved
    digest = hashlib.sha256(b"".join(path.read_bytes() for path in sources)).hexdigest()[:16]
    label = f"reparse-{package}-{digest}"
    for result in sorted((ROOT / "mvp" / "runs").glob("*/result.json"), reverse=True):
        try:
            data = json.loads(result.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if (data.get("case_name") == label and (data.get("sysml") or {}).get("status") == "PASS"
                and (result.parent / "sysml" / "model.json").is_file()):
            return result.parent
    from mvp.engine import run_submitted_model
    validated = run_submitted_model(sources, package, label=label)
    if validated["sysml"]["status"] != "PASS":
        raise RuntimeError(f"Official parse of {package} did not pass: {validated['run_dir']}")
    return Path(validated["run_dir"])


def maritime_parse() -> Path:
    return official_parse(PARSE, [MARITIME_FILE], "MaritimeISR")


def _graph():
    cards, neighbors, _kinds = build_graph(maritime_parse(), "MaritimeISR::")
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
    by_id = {element["@id"]: element for element in elements}
    for element in elements:
        name = element.get("qualifiedName")
        if element.get("@type") == "ConnectionUsage" and not name:
            # `connect a to b;` has no name of its own. Without a card the connection is invisible to
            # retrieval (the graph-retrieval QRY-03 run answered 0 connections for that reason), so it
            # gets a synthetic name under its owner: Owner::connect[a → b].
            owner = by_id.get((element.get("owner") or {}).get("@id") or "", {})
            owner_name = owner.get("qualifiedName") or ""
            ends = [view.reference_name(ref["@id"]) or "" for ref in element.get("relatedFeature") or []]
            if (owner_name.startswith(prefix) or owner_name == prefix.rstrip(":")) and len(ends) >= 2:
                name = f"{owner_name}::connect[{ends[0]} → {ends[1]}]"
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


def retrieve(question: str, cards: dict, neighbors: dict, limit: int = 8) -> tuple[list[str], dict]:
    """Paper 2's retrieval on our parse: MiniLM + FAISS seeds with the exact-name bonus, then one hop.
    Returns the card texts and the settings used. There is no other ranking: a missing embedding stack raises."""
    from bench.vector_index import retrieve as vector_retrieve
    found = vector_retrieve(question, cards, neighbors, name="memory", k_seeds=4, limit=limit)
    settings = {key: found[key] for key in ("method", "embedding_model", "threshold", "k_seeds", "name_bonus", "index_key", "library_size")}
    return [cards[item["id"]] for item in found["picked"]], settings


def main() -> None:
    load_env()
    cards, neighbors = _graph()
    rows = []
    for task_id in ("QRY-01", "QRY-02", "QRY-03", "QRY-04", "QRY-05"):
        task = HELD / task_id
        question = (task / "input" / "requirements.md").read_text(encoding="utf-8")
        texts, settings = retrieve(question, cards, neighbors)
        context = "\n".join(texts)
        completed = chat([
            {"role": "system", "content": "Answer from the retrieved model elements only. One JSON object, no prose."},
            {"role": "user", "content": question + "\n\nRetrieved elements:\n" + context},
        ], max_tokens=300, temperature=0)
        scored = score_answer(task, completed["text"])
        rows.append({"task_id": task_id, "model": completed["model"], "status": scored["status"], "retrieval": settings,
                     "retrieved": context, "answer": completed["text"], "usage": completed["usage"]})
        print(task_id, scored["status"], completed["model"], settings["method"], flush=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    out = ROOT / "analysis" / f"graph-query-{stamp}.json"
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
