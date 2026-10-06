"""Build the exam's retrieval library: official SysML-v2-Release examples, parsed by the Pilot, plus the notes corpus.

Why a separate library: the held-out QRY tasks read MaritimeISR itself and several GEN keys repeat
MaritimeISR values (GEN-03's fusionLatencyS = 2.0 is in it), so MaritimeISR cards may not be shown
to an exam candidate. The official examples (EPL-2.0, vendor/SysML-v2-Release/sysml/src/examples)
contain none of the held-out answers and are exactly the "examples" slot of paper 3's
rules + template + examples prompt.

Each example folder is validated as one submission with the official Pilot; folders that pass give one
card per named element plus the one-hop graph (bench.graph_query.build_graph). Notes from bench/corpus
become cards without neighbours. Output: analysis/vector-index/examples/{cards.json,neighbors.json,manifest.json}.
The FAISS index is built lazily by bench.vector_index and is not committed.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bench.graph_query import build_graph  # noqa: E402
from mvp.engine import run_submitted_model  # noqa: E402

EXAMPLES = ROOT / "vendor" / "SysML-v2-Release" / "sysml" / "src" / "examples"
CORPUS = ROOT / "bench" / "corpus"
OUT = ROOT / "analysis" / "vector-index" / "examples"
PACKAGE = re.compile(r"^\s*(?:private |public )?package\s+('[^']+'|[A-Za-z_][A-Za-z0-9_]*)", re.M)
FORBIDDEN = ("MaritimeISR", "FusionNode", "FourNode", "ShoreArchive", "RadioHealth", "PowerBudget", "UsvPlain",
             "RoundTrip", "fusionLatencyS", "UnmannedSurfaceVessel", "FixedWingUav")


def first_package(files: list[Path]) -> str | None:
    for path in files:
        match = PACKAGE.search(path.read_text(encoding="utf-8", errors="replace"))
        if match:
            return match.group(1).strip("'")
    return None


def note_chunks(path: Path) -> list[str]:
    """Blank-line blocks, with a heading line (ending in ':') kept together with the block it introduces."""
    chunks: list[str] = []
    for block in path.read_text(encoding="utf-8").split("\n\n"):
        text = block.strip()
        if not text:
            continue
        if chunks and chunks[-1].endswith(":"):
            chunks[-1] = chunks[-1] + "\n\n" + text
        else:
            chunks.append(text)
    return chunks


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cards: dict[str, str] = {}
    sources: dict[str, str] = {}
    neighbors: dict[str, list[str]] = {}
    folders = []
    notes_only = "--notes-only" in sys.argv and (OUT / "cards.json").is_file()
    if notes_only:
        # Keep the parsed example cards; only the notes are rebuilt.
        for row in json.loads((OUT / "cards.json").read_text(encoding="utf-8")):
            if not row["id"].startswith("notes:"):
                cards[row["id"]], sources[row["id"]] = row["text"], row["source"]
        neighbors = {key: value for key, value in json.loads((OUT / "neighbors.json").read_text(encoding="utf-8")).items()
                     if not key.startswith("notes:")}
        folders = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))["folders"]
    for folder in [] if notes_only else sorted(path for path in EXAMPLES.iterdir() if path.is_dir()):
        files = sorted(folder.glob("*.sysml"))
        if not files:
            continue
        package = first_package(files)
        entry = {"folder": folder.name, "files": [path.name for path in files], "package": package}
        if not package:
            entry["status"] = "SKIP"
            entry["reason"] = "no package statement found"
            folders.append(entry)
            continue
        result = run_submitted_model(files, package, label=f"examples-{folder.name}")
        entry["status"] = result["sysml"]["status"]
        entry["run_id"] = result["run_id"]
        if entry["status"] == "PASS":
            folder_cards, folder_neighbors, _kinds = build_graph(Path(result["run_dir"]), "")
            kept = {ident: text for ident, text in folder_cards.items()
                    if not text.split(" ")[1].startswith(("ScalarValues", "ISQ", "SI", "KerML", "Base", "Occurrences", "Items", "Parts", "Ports"))}
            entry["cards"] = len(kept)
            for ident, text in kept.items():
                key = f"{folder.name}:{ident}"
                cards[key] = text
                sources[key] = f"official example · {folder.name}"
                neighbors[key] = [f"{folder.name}:{other}" for other in folder_neighbors.get(ident, ()) if other in kept]
        else:
            entry["diagnostics"] = [item.get("message") for item in result["sysml"].get("diagnostics", [])[:5]]
        folders.append(entry)
        print(f"{entry['status']:5} {folder.name} ({entry.get('cards', 0)} cards)", flush=True)
    note_count = 0
    for path in sorted(CORPUS.glob("*.md")):
        for number, text in enumerate(note_chunks(path)):
            key = f"notes:{path.name}:{number}"
            cards[key] = text
            sources[key] = f"notes · {path.name}"
            neighbors[key] = []
            note_count += 1
    leaks = sorted(key for key, text in cards.items() if any(token in text for token in FORBIDDEN) and not key.startswith("notes:"))
    manifest = {"built_at": datetime.now(timezone.utc).isoformat(), "examples_root": str(EXAMPLES.relative_to(ROOT)),
                "license": "EPL-2.0 (SysML-v2-Release)", "folders": folders, "cards": len(cards), "notes": note_count,
                "leak_check": {"forbidden_tokens": FORBIDDEN, "example_cards_with_forbidden_token": leaks}}
    (OUT / "cards.json").write_text(json.dumps([{"id": key, "text": cards[key], "source": sources[key]} for key in sorted(cards)],
                                               ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "neighbors.json").write_text(json.dumps(neighbors, ensure_ascii=False), encoding="utf-8")
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    passed = sum(1 for item in folders if item["status"] == "PASS")
    print(f"{passed}/{len(folders)} folders parsed, {len(cards)} cards ({note_count} notes), leaks: {len(leaks)} -> {OUT}")


if __name__ == "__main__":
    main()
