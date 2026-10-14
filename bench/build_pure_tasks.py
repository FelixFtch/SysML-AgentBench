"""Turn the PURE XML subset into requirements-to-SysML v2 tasks: a passage of a real requirements document in, one
SysML v2 package out, scored by the official Pilot and the document's own requirement marks.

The sponsor brief asks to validate the selected approaches on natural-language requirements datasets such as PURE
(nlreqdataset.isti.cnr.it). The Zenodo record 7118517 is CC BY 4.0. It ships 79 public requirement documents as
PDFs and a subset as XML. Only the XML marks requirements: every <req> element is one requirement as the document
itself presents it (EIRENE and ERTMS number every clause, including the ones they label informative, optional or
deleted; the SRS documents prefix theirs with REQ-n). PURE has no SysML model and no translation key for any
document, so those marks, the official Pilot and the numbers in the text are the whole key. A document with no <req>
is kept in the zip and is not scored, because this script does not invent a key.

Protocol "sysml-v2" (2026-10-10). The first protocol asked the model to copy the requirement sentences and scored
the copied text; 88% of its failures were the right text cut at a different boundary, because a <req> is often two
or three sentences, and no approach of ours was involved. Here the passage is pre-segmented by code into the
document's own units, in document order and numbered: section headings (<title>), explanatory text (<text_body>
outside a requirement) and requirement statements (<req>). The candidate writes one SysML v2 package in which every
requirement is one `requirement def` carrying the requirement's text in its doc comment. bench/run_side.py scores
it: the official Pilot parses the package; every marked requirement must be inside a requirement def (its words, in
order; numbering and punctuation aside); no explanatory paragraph may be inside one; no requirement def beyond the
marked ones; no number with a unit that the passage does not contain. Every unit of the six keyed documents is in
exactly one passage; a passage may hold no requirement at all (the right answer is then the empty package).

Output (gitignored with the zip): datasets/pure/tasks/PURE-<doc>-<nn>/
  input/excerpt.md   the prompt: numbered items and the task
  input/items.json   item number -> verbatim text
  gold/answer.json   {"requirements": [item numbers]}   (opened only when scoring)
  gold/units.json    item number -> title | text | req          (opened only when scoring)
  case.yaml          type GEN, package name, protocol sysml-v2
"""
from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
ZIP = ROOT / "datasets" / "pure" / "requirements-xml.zip"
OUT = ROOT / "datasets" / "pure" / "tasks"
PROTOCOL = "sysml-v2"
WINDOW = 12  # units per passage

QUESTION = (
    "Task: write one SysML v2 package named `{package}` that models the requirements in this passage. The passage is "
    "split into numbered items in the document's own order; some items are requirements of the specified system, the "
    "others are section headings, purpose, scope, background, definitions or explanations. Make every requirement one "
    "`requirement def` (give it a short name) whose doc comment holds that item's text as written above: "
    "`requirement def R1 {{ doc /* ...the item's text... */ }}`. Count a clause the document itself states as a "
    "requirement even when it is marked informative (I), optional (O) or Deleted. Headings and explanatory text are not "
    "requirements and must not become requirement defs. Do not invent values: every number in the package must appear in "
    "the passage. If no item is a requirement, return the empty package. Reply with the complete package in one fenced "
    "code block tagged sysml.\n"
)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _text(node: ET.Element) -> str:
    return re.sub(r"\s+", " ", "".join(node.itertext())).strip()


def _req_text(node: ET.Element) -> str:
    """The requirement as the document shows it: its text_body children. The PURE <modifier> (M/O/I of ERTMS) is an
    annotation on requirements only, so it is left out; it would give the answer away."""
    bodies = [child for child in node if _local(child.tag) == "text_body"]
    if bodies:
        return re.sub(r"\s+", " ", " ".join(_text(child) for child in bodies)).strip()
    return re.sub(r"\s+", " ", " ".join(_text(child) for child in node if _local(child.tag) != "modifier")).strip()


def units(path: Path) -> list[tuple[str, str]]:
    """Document order: ('title', heading), ('text', paragraph) or ('req', requirement). Nothing is emitted twice."""
    root = ET.parse(path).getroot()
    out: list[tuple[str, str]] = []

    def walk(node: ET.Element) -> None:
        kind = _local(node.tag)
        if kind == "req":
            text = _req_text(node)
            if text:
                out.append(("req", text))
            return
        if kind == "title":
            text = _text(node)
            if text:
                out.append(("title", text))
            return
        if kind == "text_body":
            text = _text(node)
            if text:
                out.append(("text", text))
            return
        for child in list(node):
            walk(child)

    walk(root)
    return out


def _slug(name: str) -> str:
    stem = Path(name).stem.lower()
    stem = re.sub(r"^\d+\s*-\s*", "", stem)
    stem = re.sub(r"[^a-z0-9]+", "-", stem).strip("-")
    return stem[:40] or "doc"


def _clear() -> None:
    if not OUT.exists():
        return
    for old in OUT.iterdir():
        if old.is_dir() and old.name.startswith("PURE-"):
            for child in old.rglob("*"):
                if child.is_file():
                    child.unlink()
            for child in sorted(old.rglob("*"), reverse=True):
                if child.is_dir():
                    child.rmdir()
            old.rmdir()


def build() -> dict:
    _clear()
    OUT.mkdir(parents=True, exist_ok=True)
    stats = {"protocol": PROTOCOL, "window": WINDOW, "documents": {}, "passages": 0, "units": 0, "requirements": 0,
             "passages_without_requirement": 0}
    with zipfile.ZipFile(ZIP) as archive:
        names = sorted(n for n in archive.namelist() if n.startswith("XMLZIPFile/") and n.endswith(".xml") and not n.split("/")[-1].startswith("."))
        for name in names:
            target = Path("/tmp") / "pure-one.xml"
            target.write_bytes(archive.read(name))
            items = units(target)
            if not any(kind == "req" for kind, _ in items):
                continue
            slug = _slug(name)
            doc_stats = {"units": len(items), "requirements": sum(1 for kind, _ in items if kind == "req"), "passages": 0}
            for part, start in enumerate(range(0, len(items), WINDOW), 1):
                chunk = items[start:start + WINDOW]
                task_id = f"PURE-{slug}-{part:02d}"
                package = "PURE_" + re.sub(r"[^A-Za-z0-9]+", "_", f"{slug}_{part:02d}").strip("_")
                folder = OUT / task_id
                (folder / "input").mkdir(parents=True)
                (folder / "gold").mkdir()
                numbered = "\n\n".join(f"[{i}] {text}" for i, (_kind, text) in enumerate(chunk, 1))
                gold = [i for i, (kind, _text_) in enumerate(chunk, 1) if kind == "req"]
                excerpt = (
                    f"# {task_id}\n\n"
                    "Source: Ferrari, Spagnolo, and Gnesi, PURE dataset, Zenodo 10.5281/zenodo.7118517, CC BY 4.0.\n"
                    f"Document in that collection: `{Path(name).name}`.\n\n"
                    f"Passage, {len(chunk)} items:\n\n"
                    f"{numbered}\n\n"
                    f"{QUESTION.format(package=package)}"
                )
                (folder / "input" / "excerpt.md").write_text(excerpt, encoding="utf-8")
                (folder / "input" / "items.json").write_text(
                    json.dumps({str(i): text for i, (_kind, text) in enumerate(chunk, 1)}, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
                (folder / "gold" / "answer.json").write_text(
                    json.dumps({"requirements": gold}, indent=2) + "\n", encoding="utf-8")
                (folder / "gold" / "units.json").write_text(
                    json.dumps({str(i): kind for i, (kind, _text_) in enumerate(chunk, 1)}, indent=2) + "\n", encoding="utf-8")
                (folder / "case.yaml").write_text(yaml.safe_dump({
                    "id": task_id, "type": "GEN", "package": package, "scenario_family": "t5_requirements", "split": "side",
                    "synthetic": False, "source": Path(name).name, "protocol": PROTOCOL, "items": len(chunk),
                }), encoding="utf-8")
                doc_stats["passages"] += 1
                stats["passages"] += 1
                stats["units"] += len(chunk)
                stats["requirements"] += len(gold)
                if not gold:
                    stats["passages_without_requirement"] += 1
            stats["documents"][Path(name).name] = doc_stats
    digest = hashlib.sha256()
    for folder in sorted(OUT.iterdir()):
        if folder.is_dir():
            digest.update((folder / "input" / "excerpt.md").read_bytes())
            digest.update((folder / "gold" / "answer.json").read_bytes())
    stats["tasks_sha256"] = digest.hexdigest()
    (OUT / "BUILD.json").write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    print(f"{stats['passages']} passages, {stats['units']} units, {stats['requirements']} requirements, "
          f"{stats['passages_without_requirement']} passages without a requirement, in {OUT}")
    return stats


if __name__ == "__main__":
    build()
