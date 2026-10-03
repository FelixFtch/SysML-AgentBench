"""Blank-task flow: brief -> retrieval -> requirements -> two designs -> official parse -> alignment
-> deterministic checks -> trade-offs -> read-back -> a person decides.

The model writes requirements, SysML and mapping proposals. The official Pilot parses every design and
the alignment package. The "checks" step is arithmetic on parsed literals (power sum, link rate, storage)
plus a trace count. It is not a physics simulation. A number in the requirements that is not written in
the brief blocks approval. Only a design whose four checks all pass can be approved into memory, and an
approved design becomes searchable by the next run's retrieval.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.llm import chat, extract_json, extract_sysml  # noqa: E402
from agents.solve import SYSML_RULES  # noqa: E402
from bench.experiment import load_env  # noqa: E402

NUMBER = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)(?!\w|\.\d)")
MARITIME_FILE = ROOT / "scenario" / "maritime-isr" / "MaritimeISR.sysml"
MEMORY = ROOT / "analysis" / "memory" / "approved.jsonl"
GATED_CHECKS = ("POWER", "LINK", "STORE", "TRACE")
STOPWORDS = {"and", "the", "for", "with", "over", "one", "from", "that", "this", "are", "per", "its", "into",
             "not", "all", "any", "add", "via", "has", "have", "each", "both", "only", "than", "then"}

# Synthetic device catalogue for the design space and the trade-off step. Not a bill of materials, not RTX data.
CATALOG = {
    "slots": {
        "visible_camera": {"label": "Visible camera", "options": {
            "eo_std": {"label": "standard", "drawW": 41},
            "eo_lite": {"label": "low power", "drawW": 28}}},
        "ir_camera": {"label": "Infrared camera", "options": {
            "ir_std": {"label": "standard", "drawW": 12},
            "ir_lite": {"label": "low power", "drawW": 7},
            "ir_none": {"label": "none for now", "drawW": 0}}},
        "computer": {"label": "Edge computer", "options": {
            "edge_std": {"label": "standard", "drawW": 25},
            "edge_low": {"label": "low power", "drawW": 14}}},
        "uplink": {"label": "Uplink", "options": {
            "cell_8": {"label": "cellular", "uplinkMbps": 8},
            "cell_20": {"label": "cellular plus", "uplinkMbps": 20}}},
        "storage": {"label": "Local storage", "options": {
            "ssd_128": {"label": "128 GB", "storageGB": 128},
            "ssd_256": {"label": "256 GB", "storageGB": 256}}},
    },
    "params": {
        "powerLimitW": {"label": "Power limit", "unit": "W", "choices": [60], "fixed": True},
        "dataRateMbps": {"label": "Recording rate", "unit": "Mbps", "choices": [6, 12, 18]},
        "retentionHours": {"label": "Keep originals", "unit": "h", "choices": [4, 8]},
        "uploadMbps": {"label": "Upload rate", "unit": "Mbps", "choices": [2, 6, 12, 18],
                        "note": "below the recording rate means only a preview is uploaded"},
    },
    "default": {"visible_camera": "eo_std", "ir_camera": "ir_std", "computer": "edge_std", "uplink": "cell_8",
                "storage": "ssd_128", "dataRateMbps": 18, "retentionHours": 8, "uploadMbps": 18},
}


def _option(choice: dict, slot: str) -> dict:
    return CATALOG["slots"][slot]["options"][choice.get(slot) or CATALOG["default"][slot]]


def budgets(choice: dict) -> dict:
    """Arithmetic on a catalogue choice. Same formulas as simulate() applies to a parsed model."""
    draw = _option(choice, "visible_camera")["drawW"] + _option(choice, "ir_camera")["drawW"] + _option(choice, "computer")["drawW"]
    limit = 60
    rate = float(choice.get("dataRateMbps") or CATALOG["default"]["dataRateMbps"])
    hours = float(choice.get("retentionHours") or CATALOG["default"]["retentionHours"])
    upload = float(choice.get("uploadMbps") or CATALOG["default"]["uploadMbps"])
    uplink = _option(choice, "uplink")["uplinkMbps"]
    storage = _option(choice, "storage")["storageGB"]
    need_gb = rate * hours * 3600 / 8000
    return {
        "power": {"actual": draw, "limit": limit, "unit": "W", "status": "PASS" if draw <= limit else "FAIL"},
        "link": {"actual": upload, "limit": uplink, "unit": "Mbps", "status": "PASS" if upload <= uplink else "FAIL"},
        "store": {"actual": round(need_gb, 1), "limit": storage, "unit": "GB", "status": "PASS" if need_gb <= storage else "FAIL"},
        "preview": upload < rate,
    }


def brief_from(choice: dict) -> str:
    ir = _option(choice, "ir_camera")
    rate = choice.get("dataRateMbps") or CATALOG["default"]["dataRateMbps"]
    hours = choice.get("retentionHours") or CATALOG["default"]["retentionHours"]
    upload = choice.get("uploadMbps") or CATALOG["default"]["uploadMbps"]
    uplink = _option(choice, "uplink")["uplinkMbps"]
    text = (f"A harbor patrol unmanned surface vessel carries a visible camera drawing {_option(choice, 'visible_camera')['drawW']} W "
            f"and an edge computer drawing {_option(choice, 'computer')['drawW']} W. ")
    if ir["drawW"]:
        text += f"Add an infrared camera drawing {ir['drawW']} W. "
    text += (f"The vessel power limit is 60 W. Imagery is recorded locally at {rate:g} Mbps for {hours:g} hours "
             f"on {_option(choice, 'storage')['storageGB']} GB of storage. ")
    if float(upload) < float(rate):
        text += f"A {upload:g} Mbps preview is uploaded to shore over one {uplink} Mbps uplink; the full-rate upload is not required."
    else:
        text += f"Imagery is uploaded to shore at {upload:g} Mbps over one {uplink} Mbps uplink."
    return text


def propose_tradeoffs(brief: str, failing: list[str]) -> dict:
    """The model picks catalogue changes. Code recomputes every proposal; the model's numbers are not trusted."""
    menu = {slot: dict(spec["options"]) for slot, spec in CATALOG["slots"].items()}
    params = {name: spec["choices"] for name, spec in CATALOG["params"].items() if not spec.get("fixed")}
    reply = chat([
        {"role": "system", "content": (
            "You propose design trade-offs for a synthetic vessel. You may only choose options from the catalogue and values from the parameter choice lists. "
            "Reply with one JSON object: {\"proposals\": [{\"title\": \"...\", \"rationale\": \"...\", "
            "\"choice\": {\"visible_camera\": \"eo_std\", \"ir_camera\": \"ir_std\", \"computer\": \"edge_std\", \"uplink\": \"cell_8\", \"storage\": \"ssd_128\", "
            "\"dataRateMbps\": 18, \"retentionHours\": 8, \"uploadMbps\": 18}}]}. Give 3 proposals that differ. The 60 W limit cannot change."
        )},
        {"role": "user", "content": f"Brief:\n{brief}\n\nFailing checks: {', '.join(failing) or 'none'}\n\nCatalogue:\n{json.dumps(menu, ensure_ascii=False)}\n\nParameter choices:\n{json.dumps(params)}"},
    ], max_tokens=1200)
    parsed = extract_json(reply["text"])
    proposals = parsed.get("proposals") if isinstance(parsed, dict) else None
    if not isinstance(proposals, list):
        raise ValueError("The model returned no list of proposals")
    cleaned = []
    for item in proposals[:4]:
        choice = item.get("choice") or {}
        valid = all(choice.get(slot) in spec["options"] for slot, spec in CATALOG["slots"].items())
        for name, spec in CATALOG["params"].items():
            if spec.get("fixed"):
                continue
            try:
                if float(choice.get(name)) not in [float(v) for v in spec["choices"]]:
                    valid = False
            except (TypeError, ValueError):
                valid = False
        entry = {"title": item.get("title") or "Proposal", "rationale": item.get("rationale") or "", "choice": choice, "valid": valid}
        if valid:
            entry["budgets"] = budgets(choice)
            entry["feasible"] = all(entry["budgets"][key]["status"] == "PASS" for key in ("power", "link", "store"))
            entry["brief"] = brief_from(choice)
        cleaned.append(entry)
    return {"proposals": cleaned, "model": reply.get("model"), "usage": reply.get("usage")}


def numbers_in(text: str) -> set[str]:
    return {f"{float(raw):g}" for raw in NUMBER.findall(text or "")}


def load_memory() -> list[dict]:
    if not MEMORY.is_file():
        return []
    return [json.loads(line) for line in MEMORY.read_text(encoding="utf-8").splitlines() if line.strip()]


def _library():
    """MaritimeISR's official parse plus every approved design's official parse."""
    from bench.graph_query import build_graph, maritime_parse, official_parse
    cards, neighbors, kinds = build_graph(maritime_parse(), "MaritimeISR::")
    source_of = {ident: "MaritimeISR" for ident in cards}
    sources = [{"name": "MaritimeISR", "label": "Existing maritime model MaritimeISR",
                "path": "scenario/maritime-isr/MaritimeISR.sysml", "cards": len(cards)}]
    for entry in load_memory():
        saved = Path(entry["run_dir"])
        source = ROOT / entry["source"] if entry.get("source") else None
        if not (saved / "sysml" / "model.json").is_file() and not (source and source.is_file()):
            continue
        run_dir = official_parse(saved, [source] if source else [], entry["package"])
        extra_cards, extra_neighbors, extra_kinds = build_graph(run_dir, entry["package"] + "::")
        tag = f"approved {entry['run_id']}·{entry['design']}"
        for ident, text in extra_cards.items():
            cards[ident] = text
            source_of[ident] = tag
        for ident, near in extra_neighbors.items():
            neighbors.setdefault(ident, set()).update(near)
        kinds.update(extra_kinds)
        sources.append({"name": tag, "label": f"Approved design {entry['run_id']} · {entry['design']}",
                        "path": str(run_dir.relative_to(ROOT)), "cards": len(extra_cards)})
    return cards, neighbors, kinds, source_of, sources


def _node(ident: str, text: str) -> dict:
    parts = text.split(" ")
    kind, name = parts[0], parts[1] if len(parts) > 1 else ""
    node = {"id": ident, "text": text, "type": kind, "name": name, "short": name.split("::")[-1]}
    if kind == "AttributeUsage" and len(parts) >= 3:
        try:
            node["value"] = float(parts[2])
        except ValueError:
            pass
    if kind == "ConnectionUsage" and len(parts) >= 4:
        node["ends"] = parts[2:4]
    return node


def retrieve_existing(brief: str, limit: int = 12) -> dict:
    """Stage 1, the GRAG step: keyword-scored seed elements, then their one-hop neighbours.

    No embeddings. The brief's own words and numbers are the query; cards are "type qualifiedName [literal]".
    A word scores when it appears inside the card text; a number scores only when the card holds the same value."""
    cards, neighbors, kinds, source_of, sources = _library()
    words = sorted({word.lower() for word in re.findall(r"[A-Za-z]+", brief) if len(word) > 2} - STOPWORDS)
    values = numbers_in(brief)
    query = words + sorted(values, key=float)
    score = {ident: sum(word in text.lower() for word in words) + len(values & numbers_in(text)) for ident, text in cards.items()}
    ranked = sorted(cards, key=lambda ident: (-score[ident], cards[ident]))
    seeds = [ident for ident in ranked[:4] if score[ident] > 0]
    picked: list[dict] = []
    seen: set[str] = set()
    for ident in seeds:
        seen.add(ident)
        picked.append({**_node(ident, cards[ident]), "role": "seed", "score": score[ident], "source": source_of[ident]})
    edges = []
    for seed in seeds:
        for hop in sorted(neighbors.get(seed, ()), key=lambda ident: cards.get(ident, "~")):
            if len(picked) >= limit:
                break
            if hop not in cards or hop in seen:
                continue
            seen.add(hop)
            picked.append({**_node(hop, cards[hop]), "role": "neighbor", "via": seed, "score": score[hop], "source": source_of[hop]})
            edges.append({"from": seed, "to": hop, "kind": kinds.get((seed, hop), "owner")})
    numbers = {node["name"]: node["value"] for node in picked if "value" in node}
    prompt_cards = [node["text"] if node["source"] == "MaritimeISR" else f"[{node['source']}] {node['text']}" for node in picked]
    return {
        "sources": sources,
        "library_size": len(cards),
        "query_words": query,
        "words": [word for word in words if any(word in text.lower() for text in cards.values())]
                 + [value for value in sorted(values, key=float) if any(value in numbers_in(text) for text in cards.values())],
        "nodes": picked,
        "edges": edges,
        "cards": prompt_cards,
        "numbers": numbers,
        "path": "reuse" if numbers else "new",
        "note": "Reusable values found in existing models: reuse path." if numbers else "No related values in existing models: new-design path.",
    }


def write_requirements(brief: str) -> dict:
    reply = chat([
        {"role": "system", "content": (
            "You turn a short mission brief into numbered system requirements for a SysML v2 model. "
            "Reply with one JSON object: {\"requirements\": [{\"id\": \"R1\", \"text\": \"...\", "
            "\"quantity\": {\"name\": \"powerLimitW\", \"value\": 60, \"unit\": \"W\"} | null}], "
            "\"questions\": [\"...\"]}. Use only numbers that appear in the brief. "
            "If a number needed for a check is missing, put a question in questions and leave quantity null. "
            "Quantity names must be SysML attribute names: powerLimitW, drawW, uplinkMbps, uploadMbps, dataRateMbps, storageGB, retentionHours. "
            "dataRateMbps is the local recording rate; uploadMbps is the rate actually sent to shore; uplinkMbps is the link capacity. "
            "At most 9 requirements."
        )},
        {"role": "user", "content": brief},
    ], max_tokens=1500)
    parsed = extract_json(reply["text"])
    requirements = parsed.get("requirements") if isinstance(parsed, dict) else None
    if not isinstance(requirements, list):
        raise ValueError("The model returned no list of requirements")
    questions = parsed.get("questions") if isinstance(parsed, dict) else []
    allowed = numbers_in(brief)
    unsourced = []
    for item in requirements:
        quantity = item.get("quantity") or None
        values = numbers_in(item.get("text", ""))
        if quantity and quantity.get("value") is not None:
            values.add(f"{float(quantity['value']):g}")
        extra = sorted(value for value in values if value not in allowed)
        item["unsourced_numbers"] = extra
        if extra:
            unsourced.append({"id": item.get("id"), "numbers": extra})
    return {"requirements": requirements, "questions": questions if isinstance(questions, list) else [],
            "unsourced": unsourced, "model": reply.get("model"), "usage": reply.get("usage")}


DESIGN_RULES = SYSML_RULES + (
    "- The first line inside the package is exactly: private import ScalarValues::*;\n"
    "- Declare attributes as `attribute name : Real = 12.0;` inside part usages, not part definitions, so values are literals.\n"
)


def write_design(brief: str, requirements: list[dict], package: str, variant: str, retrieved: list[str] | None = None) -> dict:
    listing = "\n".join(f"{item.get('id')}: {item.get('text')}" for item in requirements)
    quantities = []
    for item in requirements:
        quantity = item.get("quantity") or {}
        if quantity.get("name") and quantity.get("value") is not None:
            quantities.append(f"attribute {quantity['name']} : Real = {float(quantity['value']):g};  // {item.get('id')}")
    contract = "\n".join(quantities) or "(none)"
    instruction = (
        f"Package name: {package}. Write one SysML v2 package that satisfies these requirements. "
        "Structure: one top-level part usage for the vessel; inside it one part usage per device; ports and connect statements between devices. "
        "The checker reads only these exact attribute declarations, each placed inside the part usage it belongs to "
        "(powerLimitW, uplinkMbps, uploadMbps, storageGB, dataRateMbps, retentionHours on the vessel part; drawW on each powered device part):\n"
        f"{contract}\n"
        "Use these attribute names verbatim. Do not rename them. Do not write attributes inside requirement usages. "
        "Add one requirement def per requirement id with a doc comment quoting that id. "
        f"Variant: {variant}"
    )
    notes = "\n".join(retrieved or [])
    messages = [
        {"role": "system", "content": DESIGN_RULES},
        {"role": "user", "content": f"Mission brief:\n{brief}\n\nRequirements:\n{listing}\n\n"
                                    + (f"Related elements already in the existing maritime model (for naming consistency; do not import them):\n{notes}\n\n" if notes else "")
                                    + instruction},
    ]
    reply = chat(messages)
    parts = [
        {"key": "rules", "label": "Rules", "paper": "p3", "text": DESIGN_RULES},
        {"key": "contract", "label": "Template · attribute contract", "paper": "p3", "text": contract},
        {"key": "examples", "label": "Examples · retrieved existing elements", "paper": "p2", "text": notes or "(no retrieval results)"},
        {"key": "task", "label": "Brief + requirements", "paper": "", "text": f"{brief}\n\n{listing}"},
        {"key": "variant", "label": "What this variant must do", "paper": "", "text": variant},
    ]
    return {"text": reply["text"], "model": reply.get("model"), "usage": reply.get("usage"), "messages": messages, "prompt_parts": parts}


def repair_design(messages: list[dict], previous: str, diagnostics: list[str]) -> dict:
    follow = messages + [
        {"role": "assistant", "content": previous},
        {"role": "user", "content": "The official SysML v2 validator rejected this. Fix only the syntax. Keep every number unchanged.\n" + "\n".join(diagnostics)},
    ]
    reply = chat(follow)
    return {"text": reply["text"], "model": reply.get("model"), "usage": reply.get("usage")}


def parsed_numbers(run_dir: Path) -> tuple[dict, list, list]:
    from mvp.engine import ModelView, exported_elements
    sysml = run_dir / "sysml"
    elements = exported_elements(json.loads((sysml / "model.json").read_text(encoding="utf-8")))
    ast = json.loads((sysml / "ast-elements.json").read_text(encoding="utf-8"))
    view = ModelView(elements, ast)
    numbers = {}
    for element in elements:
        if element.get("@type") != "AttributeUsage":
            continue
        link = view.value_links.get(element["@id"])
        if not link:
            continue
        value = view.by_id.get((link.get("value") or {}).get("@id"), {})
        if value.get("@type") in {"LiteralInteger", "LiteralRational"}:
            numbers[element.get("qualifiedName") or ""] = float(value["value"])
    connections = []
    for element in elements:
        if element.get("@type") != "ConnectionUsage":
            continue
        ends = [view.reference_name(ref["@id"]) or "?" for ref in element.get("relatedFeature") or []]
        if len(ends) == 2:
            connections.append(ends)
    names = sorted(e["qualifiedName"] for e in elements if e.get("qualifiedName") and e.get("declaredName"))
    return numbers, connections, names


def simulate(numbers: dict, connections: list, requirements: list[dict]) -> list[dict]:
    def tail(suffix: str) -> dict:
        return {name: value for name, value in numbers.items() if name.endswith("::" + suffix)}
    checks = []
    limits, draws = tail("powerLimitW"), tail("drawW")
    if limits and draws:
        limit = next(iter(limits.values()))
        total = sum(draws.values())
        checks.append({"id": "POWER", "label": "Total power vs limit", "formula": "sum of all drawW ≤ powerLimitW",
                       "status": "PASS" if total <= limit else "FAIL", "actual": total, "limit": limit, "unit": "W"})
    else:
        checks.append({"id": "POWER", "label": "Total power vs limit", "formula": "sum of all drawW ≤ powerLimitW", "status": "UNKNOWN",
                       "detail": "The model does not state both powerLimitW and drawW."})
    uplink, upload, rate = tail("uplinkMbps"), tail("uploadMbps"), tail("dataRateMbps")
    sent = upload or rate
    if uplink and sent:
        link = next(iter(uplink.values()))
        need = sum(sent.values())
        checks.append({"id": "LINK", "label": "Upload vs uplink", "formula": ("uploadMbps" if upload else "dataRateMbps") + " ≤ uplinkMbps",
                       "status": "PASS" if need <= link else "FAIL", "actual": need, "limit": link, "unit": "Mbps"})
    else:
        checks.append({"id": "LINK", "label": "Upload vs uplink", "formula": "uploadMbps (or dataRateMbps) ≤ uplinkMbps", "status": "UNKNOWN",
                       "detail": "The model does not state both uplinkMbps and an upload rate."})
    storage, hours = tail("storageGB"), tail("retentionHours")
    if storage and hours and rate:
        need_gb = sum(rate.values()) * next(iter(hours.values())) * 3600 / 8000
        cap = next(iter(storage.values()))
        checks.append({"id": "STORE", "label": "Recording storage", "formula": "dataRateMbps × retentionHours × 3600 ÷ 8000 ≤ storageGB",
                       "status": "PASS" if need_gb <= cap else "FAIL", "actual": round(need_gb, 2), "limit": cap, "unit": "GB"})
    else:
        checks.append({"id": "STORE", "label": "Recording storage", "formula": "dataRateMbps × retentionHours × 3600 ÷ 8000 ≤ storageGB", "status": "UNKNOWN",
                       "detail": "Needs dataRateMbps, retentionHours and storageGB."})
    covered = 0
    for item in requirements:
        quantity = item.get("quantity") or {}
        name = quantity.get("name")
        if not name:
            continue
        hit = tail(name)
        wanted = quantity.get("value")
        ok = bool(hit) and wanted is not None and any(abs(v - float(wanted)) < 1e-9 for v in hit.values())
        item["in_model"] = ok
        covered += 1 if ok else 0
    with_quantity = sum(1 for item in requirements if (item.get("quantity") or {}).get("name"))
    checks.append({"id": "TRACE", "label": "Numbered requirements in the model", "formula": "each requirement's attribute name and value appear in the official parse",
                   "status": "PASS" if covered == with_quantity else "FAIL", "actual": covered, "limit": with_quantity, "unit": "reqs"})
    checks.append({"id": "CONNECT", "label": "Connections", "status": "INFO", "actual": len(connections), "unit": "links"})
    return checks


def align(stamp: str, design: dict, design_path: Path, retrieval: dict) -> dict:
    """Stage 4: the model proposes mappings; code checks both names exist; the official Pilot then parses a
    separate alignment package together with both untouched source files."""
    from mvp.engine import run_submitted_model
    existing = sorted({node["name"] for node in retrieval.get("nodes", []) if node.get("source") == "MaritimeISR" and node.get("name")})
    elements = design.get("elements") or []
    if not existing:
        return {"mappings": [], "verified": 0, "proposed": 0, "note": "Retrieval found no MaritimeISR elements; alignment skipped."}
    reply = chat([
        {"role": "system", "content": (
            "Propose semantic mappings between elements of a new SysML design and elements of an existing model. "
            "Reply with one JSON object {\"mappings\": [{\"design\": \"<qualified name from the design list>\", \"existing\": \"<qualified name from the existing list>\", \"reason\": \"...\"}]}. "
            "Use only names from the two lists. At most 6 mappings. Do not invent names."
        )},
        {"role": "user", "content": "Design elements:\n" + "\n".join(elements) + "\n\nExisting elements:\n" + "\n".join(existing) + "\n\nDesign source:\n" + design["source"][:3000]},
    ], max_tokens=900)
    parsed = extract_json(reply["text"])
    rows = parsed.get("mappings") if isinstance(parsed, dict) else []
    design_set, existing_set = set(elements), set(existing)
    checked = []
    for row in rows if isinstance(rows, list) else []:
        left, right = row.get("design"), row.get("existing")
        checked.append({"design": left, "existing": right, "reason": row.get("reason") or "",
                        "design_exists": left in design_set, "existing_exists": right in existing_set,
                        "ok": left in design_set and right in existing_set})
    result = {"mappings": checked, "verified": sum(1 for row in checked if row["ok"]), "proposed": len(checked),
              "existing_names": existing, "model": reply.get("model"),
              "note": "Mappings are proposals. Code checks both names exist, then the official Pilot parses the alignment package. Neither source model is edited. A person decides whether to adopt them."}
    ok_rows = [row for row in checked if row["ok"]]
    if not ok_rows:
        return result
    name = f"Align{design['key']}_{stamp}"
    lines = [f"package {name} {{",
             "    doc /* Alignment package written by the agent. Neither source model is edited. */"]
    for index, row in enumerate(ok_rows, 1):
        lines.append(f"    dependency map{index} from {row['design']} to {row['existing']};")
    lines.append("}")
    source = "\n".join(lines) + "\n"
    path = design_path.parent / f"{name}.sysml"
    path.write_text(source, encoding="utf-8")
    validated = run_submitted_model([MARITIME_FILE, design_path, path], name, label=f"discover-align-{design['key']}")
    result["package"] = {
        "name": name, "source": source, "files": ["MaritimeISR.sysml", design_path.name, path.name],
        "sysml_status": validated["sysml"]["status"], "run_id": validated["run_id"],
        "diagnostics": [{"line": item.get("line"), "message": item.get("message", "")} for item in validated["sysml"].get("diagnostics", [])[:6]],
    }
    return result


def read_back(source: str) -> dict:
    reply = chat([
        {"role": "system", "content": "Restate only the requirements that are written in the given model. Plain sentences. Do not add numbers that are not in the model."},
        {"role": "user", "content": source},
    ], max_tokens=800)
    return {"text": reply["text"], "model": reply.get("model")}


def approval_block(record: dict, design: dict) -> str:
    """Empty string when the design may be approved into memory, otherwise the reason it may not."""
    if (record.get("requirements") or {}).get("unsourced"):
        return "The requirements contain numbers that are not in the brief; it cannot go into memory."
    if design.get("sysml_status") != "PASS":
        return "The official parse did not pass; it cannot go into memory."
    status = {check["id"]: check for check in design.get("checks") or []}
    for key in GATED_CHECKS:
        check = status.get(key) or {}
        if check.get("status") != "PASS":
            return f"The {key} check did not pass ({check.get('status', 'missing')}); it cannot go into memory."
    return ""


def keep_source(run_id: str, key: str, run_dir: Path) -> Path:
    """Copy the parsed design file next to the memory file; mvp/runs/ is not in git."""
    original = run_dir / "model" / f"Design{key}.sysml"
    if not original.is_file():
        raise ValueError("The source file of this design was not found.")
    copy = MEMORY.parent / "designs" / f"{run_id}-{key}" / original.name
    copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(original, copy)
    return copy


def approve(run_id: str, key: str) -> dict:
    if not re.fullmatch(r"\d{8}T\d{6}", run_id or ""):
        raise ValueError("Invalid run id.")
    path = ROOT / "analysis" / f"discover-{run_id}.json"
    if not path.is_file():
        raise ValueError("No such run.")
    record = json.loads(path.read_text(encoding="utf-8"))
    design = next((item for item in record.get("designs", []) if item.get("key") == key), None)
    if not design:
        raise ValueError("No such design.")
    reason = approval_block(record, design)
    if reason:
        raise ValueError(reason)
    if any(entry["run_id"] == run_id and entry["design"] == key for entry in load_memory()):
        raise ValueError("This design is already in memory.")
    source = keep_source(run_id, key, Path(design["run_dir"]))
    entry = {"run_id": run_id, "design": key, "package": f"Design{key}", "run_dir": design["run_dir"],
             "source": str(source.relative_to(ROOT)),
             "approved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "brief": record.get("brief", ""),
             "numbers": design.get("numbers") or {}}
    MEMORY.parent.mkdir(parents=True, exist_ok=True)
    with MEMORY.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    record.setdefault("approvals", []).append({"design": key, "approved_at": entry["approved_at"]})
    text = json.dumps(record, ensure_ascii=False, indent=2)
    path.write_text(text, encoding="utf-8")
    latest = ROOT / "analysis" / "discover-latest.json"
    if latest.is_file() and json.loads(latest.read_text(encoding="utf-8")).get("id") == run_id:
        latest.write_text(text, encoding="utf-8")
    record["file"] = path.name
    return {"record": record, "memory": load_memory()}


def _validate_design(key: str, written: dict, folder: Path, progress) -> dict:
    from mvp.engine import run_submitted_model
    text = written["text"]
    attempts = []
    path = folder / f"Design{key}.sysml"
    validated = None
    while True:
        progress("syntax", "run", f"Official Pilot parses design {key}, attempt {len(attempts) + 1}.")
        try:
            source = extract_sysml(text)
        except ValueError:
            source = ""
        if source:
            path.write_text(source, encoding="utf-8")
            validated = run_submitted_model([path], f"Design{key}", label=f"discover-{key}")
            status = validated["sysml"]["status"]
            diagnostics = [{"line": item.get("line"), "message": item.get("message", "")} for item in validated["sysml"].get("diagnostics", [])[:6]]
        else:
            status = "FAIL"
            diagnostics = [{"line": None, "message": "The model output contains no SysML package."}]
        sha = hashlib.sha256(source.encode()).hexdigest()[:12]
        attempts.append({"attempt": len(attempts) + 1, "status": status, "diagnostics": diagnostics, "sha": sha,
                         "same_as_previous": bool(attempts) and attempts[-1]["sha"] == sha,
                         "run_id": validated["run_id"] if source and validated else None,
                         "text": (source or text)[:4000]})
        if status == "PASS" or len(attempts) >= 3:
            break
        progress("repair", "run", f"Design {key}: the official errors from attempt {len(attempts)} go back to the model verbatim; fix syntax only, keep the numbers.")
        text = repair_design(written["messages"], text, [item["message"] for item in diagnostics])["text"]
    design = {"key": key, "source": source, "sysml_status": status, "attempts": attempts,
              "repair_rounds": len(attempts) - 1, "diagnostics": [item["message"] for item in attempts[-1]["diagnostics"]],
              "run_dir": validated["run_dir"] if validated else None, "model": written.get("model"),
              "usage": written.get("usage"), "prompt_parts": written.get("prompt_parts"), "path": str(path)}
    return design


def run(brief: str, progress) -> dict:
    from agents.llm import USAGE_LOG, usage_summary
    load_env()
    calls: list[dict] = []
    USAGE_LOG.set(calls)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    folder = ROOT / "mvp" / "exam-inbox" / f"discover-{stamp}"
    folder.mkdir(parents=True)
    record = {"id": stamp, "brief": brief, "synthetic": True}
    progress("brief", "pass", "Brief recorded. This is everything the agent receives.")

    progress("retrieve", "run", "Search memory for elements matching the brief's words, then take one hop of neighbours.")
    try:
        record["retrieval"] = retrieve_existing(brief)
        found = record["retrieval"]
        progress("retrieve", "pass", f"Memory has {found['library_size']} cards; {len(found['nodes'])} elements matched, {len(found['numbers'])} with values. {found['note']}")
    except Exception as exc:
        record["retrieval"] = {"nodes": [], "edges": [], "cards": [], "numbers": {}, "path": "new", "sources": [],
                               "error": f"{type(exc).__name__}: {exc}", "note": "Retrieval did not finish."}
        progress("retrieve", "fail", "Retrieval did not finish.")

    progress("requirements", "run", "The model splits the brief into numbered requirements.")
    req = write_requirements(brief)
    record["requirements"] = req
    progress("requirements", "pass", f"{len(req['requirements'])} requirements, {len(req['questions'])} questions.")
    progress("source", "fail" if req["unsourced"] else "pass",
             f"{len(req['unsourced'])} requirements carry numbers that are not in the brief." if req["unsourced"] else "Every number in the requirements is in the brief.")

    designs = []
    for key, variant in (("A", "Design A: the straightforward allocation that follows the brief literally."),
                         ("B", "Design B: same attribute names and the same numbers, but a different arrangement: for example route imagery through a separate recorder part, or share one data port between the two cameras. Keep the same structure rules as Design A.")):
        progress("design", "run", f"The model writes design {key}. The prompt holds the rules, the attribute contract and the retrieved elements.")
        written = write_design(brief, req["requirements"], f"Design{key}", variant, record["retrieval"].get("cards"))
        design = _validate_design(key, written, folder, progress)
        if design["sysml_status"] == "PASS":
            numbers, connections, names = parsed_numbers(Path(design["run_dir"]))
            design.update({"numbers": numbers, "connections": connections, "elements": names,
                           "checks": simulate(numbers, connections, [dict(item) for item in req["requirements"]])})
        else:
            design["checks"] = [{"id": "SYNTAX", "label": "Official syntax", "status": "FAIL", "detail": "The parse failed, so nothing was computed."}]
        designs.append(design)
        progress("syntax", "pass" if design["sysml_status"] == "PASS" else "fail",
                 f"Design {key}: official Pilot {design['sysml_status']} after {len(design['attempts'])} parse(s).")
    record["designs"] = designs
    progress("design", "pass", "Both designs are written.")
    syntax_ok = all(item["sysml_status"] == "PASS" for item in designs)
    progress("syntax", "pass" if syntax_ok else "fail", "Both designs pass the official Pilot." if syntax_ok else "A design failed the official Pilot.")
    rounds = sum(item["repair_rounds"] for item in designs)
    progress("repair", "skip" if not rounds else ("pass" if syntax_ok else "fail"),
             f"{rounds} repair round(s) in total." if rounds else "Both passed on the first attempt; no repair.")

    progress("align", "run", "The model proposes mappings between design A and MaritimeISR; code checks both ends; the Pilot parses the alignment package.")
    first = designs[0]
    if first["sysml_status"] == "PASS" and record["retrieval"].get("nodes"):
        try:
            record["alignment"] = align(stamp, first, Path(first["path"]), record["retrieval"])
            package = record["alignment"].get("package") or {}
            ok = bool(record["alignment"]["verified"]) and package.get("sysml_status") == "PASS"
            progress("align", "pass" if ok else "fail",
                     f"{record['alignment']['proposed']} mappings proposed, {record['alignment']['verified']} with both ends present; alignment package official Pilot {package.get('sysml_status', 'not generated')}. Waiting for a person to review.")
        except Exception as exc:
            record["alignment"] = {"mappings": [], "verified": 0, "proposed": 0, "error": f"{type(exc).__name__}: {exc}"}
            progress("align", "fail", "No mappings were generated.")
    else:
        record["alignment"] = {"mappings": [], "verified": 0, "proposed": 0, "note": "Design A failed the parse or retrieval found nothing; alignment skipped."}
        progress("align", "skip", "Alignment skipped.")

    progress("simulate", "run", "Compute power, upload, storage and traceability from the officially parsed numbers.")
    failing = sorted({check["label"] for design in designs for check in design.get("checks", []) if check["status"] == "FAIL"})
    progress("simulate", "fail" if failing else "pass", ("Failing: " + ", ".join(failing)) if failing else "All four budget checks pass.")

    if failing:
        progress("tradeoff", "run", "The model proposes alternatives, choosing only from the parts catalog.")
        try:
            record["tradeoffs"] = propose_tradeoffs(brief, failing)
            feasible = sum(1 for item in record["tradeoffs"]["proposals"] if item.get("feasible"))
            progress("tradeoff", "pass" if feasible else "fail", f"{len(record['tradeoffs']['proposals'])} proposals; {feasible} feasible when code recomputes them from the catalog.")
        except Exception as exc:
            record["tradeoffs"] = {"proposals": [], "error": f"{type(exc).__name__}: {exc}"}
            progress("tradeoff", "fail", "No proposals were generated.")
    else:
        record["tradeoffs"] = {"proposals": []}
        progress("tradeoff", "skip", "All checks pass; no trade-off needed.")

    progress("readback", "run", "The model reads only its own model and restates it as sentences.")
    brief_numbers = numbers_in(brief)
    for design in designs:
        if design["sysml_status"] == "PASS":
            design["read_back"] = read_back(design["source"])["text"]
            design["read_back_numbers"] = {value: value in numbers_in(design["read_back"]) for value in sorted(brief_numbers, key=float)}
    progress("readback", "pass", "Read-back done; code checked every number from the brief.")

    eligible = [design["key"] for design in designs if not approval_block(record, design)]
    if req["unsourced"]:
        gate = {"answer": "needs-person", "eligible": [], "effect": "The requirements contain numbers that are not in the brief. Nothing can go into memory until a person supplies them."}
    elif eligible:
        gate = {"answer": "awaiting-person", "eligible": eligible,
                "effect": f"{'Designs' if len(eligible) > 1 else 'Design'} {', '.join(eligible)} {'pass' if len(eligible) > 1 else 'passes'} all four checks "
                          "and may be approved into memory by a person. The script does not choose."}
    else:
        gate = {"answer": "awaiting-person", "eligible": [],
                "effect": "Both designs fail a check, so neither can go into memory. Pick a trade-off, go back to the design space, and give it to the agent again."}
    record["gate"] = gate
    record["usage"] = usage_summary(calls)
    progress("gate", "pass" if eligible else "fail", gate["effect"])
    out = ROOT / "analysis" / f"discover-{stamp}.json"
    text = json.dumps(record, ensure_ascii=False, indent=2)
    out.write_text(text, encoding="utf-8")
    (ROOT / "analysis" / "discover-latest.json").write_text(text, encoding="utf-8")
    record["file"] = out.name
    return record
