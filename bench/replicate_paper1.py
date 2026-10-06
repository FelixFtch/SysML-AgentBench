"""Run paper 1's seven-stage alignment prompt, verbatim, on the authors' own OEM / supplier example.

Purpose: check that the method, run with our model, produces mappings comparable to the authors'
published stage-3 file before we apply it to the maritime models. Nothing here touches the exam.

Inputs are the authors' files under research/paper-artifacts/CMBSE-main/prompts/ (prompt, OEM
model, supplier model, extension library, published results). The prompt asks a person to type
"confirmed, proceed to Stage N" between stages; this script types it, so the model never gets a
human correction. Stage 0 and stage 5 are done by the official Pilot, not by the model, which is
the one deliberate departure from the paper and is recorded in the output.

Output: analysis/paper1-replication-<stamp>/ with every stage's text, the Pilot results for the
authors' inputs, for the authors' published package and for the generated package, and the overlap
between the generated mappings and the authors' 13 stage-3 mappings.
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

from agents.llm import USAGE_LOG, chat, usage_summary  # noqa: E402
from bench.experiment import load_env  # noqa: E402
from mvp.engine import run_submitted_model  # noqa: E402

ART = ROOT / "research" / "paper-artifacts" / "CMBSE-main" / "prompts"
PROMPT = ART / "sysmlv2_alignment_process.md"
OEM = ART / "examples" / "OEM model.txt"
SUPPLIER = ART / "examples" / "Supplier model.txt"
EXTENSION = ART / "examples" / "extension library.txt"
PUBLISHED_MAPPINGS = ART / "examples" / "results" / "stage3_validated_mappings.json"
PUBLISHED_PACKAGE = ART / "examples" / "results" / "IntegratedModel_Alignment.txt"


def pilot(files: list[tuple[str, str]], package: str, folder: Path, label: str) -> dict:
    """Validate the named texts together with the official Pilot; returns status and messages."""
    paths = []
    for name, text in files:
        path = folder / name
        path.write_text(text, encoding="utf-8")
        paths.append(path)
    result = run_submitted_model(paths, package, label=label)
    return {"status": result["sysml"]["status"], "run_id": result["run_id"],
            "diagnostics": [f"{item.get('file', '').rsplit('/', 1)[-1]} L{item.get('line')}: {item.get('message')}"
                            for item in result["sysml"].get("diagnostics", []) if item.get("severity") != "WARNING"]}


def json_blocks(text: str) -> list:
    found = []
    for block in re.findall(r"```(?:json)?\s*\n(.*?)```", text, flags=re.S):
        try:
            found.append(json.loads(block))
        except json.JSONDecodeError:
            continue
    if not found:
        match = re.search(r"(\[\s*\{.*\}\s*\])", text, flags=re.S)
        if match:
            try:
                found.append(json.loads(match.group(1)))
            except json.JSONDecodeError:
                pass
    return found


def sysml_block(text: str) -> str:
    blocks = re.findall(r"```(?:sysml)?\s*\n(package .*?)```", text, flags=re.S)
    return blocks[-1] if blocks else ""


def pairs(mappings) -> set[tuple[str, str]]:
    out = set()
    for item in mappings or []:
        if isinstance(item, dict) and item.get("oem_element") and item.get("supplier_element"):
            out.add((str(item["oem_element"]).split("::")[-1].strip(), str(item["supplier_element"]).split("::")[-1].strip()))
    return out


def main() -> None:
    load_env()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    out = ROOT / "analysis" / f"paper1-replication-{stamp}"
    out.mkdir(parents=True)
    calls: list[dict] = []
    USAGE_LOG.set(calls)
    oem, supplier, extension = OEM.read_text(encoding="utf-8"), SUPPLIER.read_text(encoding="utf-8"), EXTENSION.read_text(encoding="utf-8")
    record: dict = {"id": stamp, "prompt_file": str(PROMPT.relative_to(ROOT)), "departures": [
        "Stage 0 syntax confirmation and stage 5 consistency check are done by the official Pilot 0.62, not by the model.",
        "Every 'confirmed, proceed to Stage N' is typed by this script; no human edits any stage output.",
        "No SysML v2 specification PDF is uploaded; the prompt allows best-effort mode without it.",
    ]}

    # Stage 0 by the Pilot: do the authors' inputs parse on their own?
    stage0 = out / "stage0"
    stage0.mkdir()
    record["stage0_pilot"] = {
        "oem": pilot([("OEM.sysml", oem)], "OEMRequirements", stage0 / "oem", "paper1-oem") if (stage0 / "oem").mkdir() is None else None,
        "supplier": pilot([("Supplier.sysml", supplier)], "LoadCellSolution", stage0 / "supplier", "paper1-supplier") if (stage0 / "supplier").mkdir() is None else None,
        "extension": pilot([("AllocationExtension.sysml", extension)], "AllocationExtension", stage0 / "extension", "paper1-extension") if (stage0 / "extension").mkdir() is None else None,
    }
    (stage0 / "published").mkdir()
    record["published_package_pilot"] = pilot(
        [("OEM.sysml", oem), ("Supplier.sysml", supplier), ("AllocationExtension.sysml", extension),
         ("IntegratedModel_Alignment.sysml", PUBLISHED_PACKAGE.read_text(encoding="utf-8"))],
        "IntegratedModel_Alignment", stage0 / "published", "paper1-published-package")

    # Stages 1-4 by the model, with the authors' prompt as the system message.
    messages = [{"role": "system", "content": PROMPT.read_text(encoding="utf-8")},
                {"role": "user", "content": "Stage 0 inputs. There is no SysML v2 specification PDF and no UID list; proceed in best-effort mode.\n\n"
                                            f"OEM model (OEM model.txt):\n```sysml\n{oem}\n```\n\n"
                                            f"Supplier model (Supplier model.txt):\n```sysml\n{supplier}\n```\n\n"
                                            f"Extension library (extension library.txt):\n```sysml\n{extension}\n```\n\n"
                                            "Both source models already passed the official SysML v2 Pilot syntax check. confirmed, proceed to Stage 1"}]
    stages = {}
    for number, instruction in (
        (1, "confirmed, proceed to Stage 1. Return the JSON summary and the table."),
        (2, "Stage 1 summary confirmed. confirmed, proceed to Stage 2. Return the candidate mappings as the JSON structure in the prompt."),
        (3, "I confirm every Stage 2 candidate without edits. confirmed, proceed to Stage 3. Return the validated mappings as JSON, with status and rationale."),
        (4, "confirmed, proceed to Stage 4. Generate the integration package. The two source packages are named OEMRequirements and LoadCellSolution exactly as in the files; the extension library package is AllocationExtension. Return the package in one fenced sysml block."),
    ):
        messages.append({"role": "user", "content": instruction})
        reply = chat(messages, max_tokens=6000, temperature=0.2)
        messages.append({"role": "assistant", "content": reply["text"]})
        (out / f"stage{number}.md").write_text(reply["text"], encoding="utf-8")
        stages[number] = reply["text"]
        print(f"stage {number}: {len(reply['text'])} chars", flush=True)
    (out / "conversation.json").write_text(json.dumps(messages, ensure_ascii=False, indent=2), encoding="utf-8")

    generated = sysml_block(stages[4])
    (out / "generated_package.sysml").write_text(generated, encoding="utf-8")
    package_name = (re.search(r"package\s+('[^']+'|[A-Za-z_][A-Za-z0-9_]*)", generated) or [None, "IntegratedModel_Alignment"])[1].strip("'")
    (out / "stage5").mkdir()
    record["stage5_pilot"] = pilot(
        [("OEM.sysml", oem), ("Supplier.sysml", supplier), ("AllocationExtension.sysml", extension), (f"{package_name}.sysml", generated)],
        package_name, out / "stage5", "paper1-generated-package") if generated else {"status": "FAIL", "diagnostics": ["no sysml block in stage 4"]}

    published = json.loads(PUBLISHED_MAPPINGS.read_text(encoding="utf-8"))
    stage3_json = next((block for block in json_blocks(stages[3]) if isinstance(block, list)), None)
    stage2_json = next((block for block in json_blocks(stages[2]) if isinstance(block, list)), None)
    ours = pairs(stage3_json if stage3_json is not None else stage2_json)
    theirs = pairs(published)
    record["mappings"] = {
        "published_count": len(published), "published_pairs": sorted(theirs),
        "generated_count": len(stage3_json or stage2_json or []), "generated_pairs": sorted(ours),
        "shared": sorted(ours & theirs), "only_generated": sorted(ours - theirs), "only_published": sorted(theirs - ours),
        "note": "Pairs compared by short names of (oem_element, supplier_element); mapping_type ignored.",
    }
    record["usage"] = usage_summary(calls)
    (out / "record.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"stage0": {k: v["status"] for k, v in record["stage0_pilot"].items()},
                      "published_package": record["published_package_pilot"]["status"],
                      "generated_package": record["stage5_pilot"]["status"],
                      "shared": len(record["mappings"]["shared"]), "published": len(theirs), "generated": len(ours),
                      "usage": record["usage"]}, ensure_ascii=False))
    print(out)


if __name__ == "__main__":
    main()
