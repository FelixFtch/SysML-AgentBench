"""Replicate paper 2 (Bader et al., GRAG over SysML v2) on the authors' own EV model and compare with our retrieval.

Purpose: check that our retrieval does what the authors' published code does before trusting it on the maritime
models. Nothing here touches the exam or a frozen file.

Inputs are the authors' files under research/paper-artifacts/SysML-v2-GRAG-Pipeline-main/ (commit d910822, MIT):
the notebook grag-pipeline.ipynb, the cached RDF graph of their EV model, and EVModel.sysml.

- The authors' functions (load_graph, extract_snippets, build_vector_index, retrieve_nodes, fetch_subgraph,
  serialize_subgraph, answer_query) are executed verbatim from the notebook cells, on their cached graph, at the
  three thresholds of the paper's Table I.
- "authors, URI fix" is the same run with one change: fetch_subgraph receives full URIs. The notebook strips the URI
  prefix to make keys and passes those keys to fetch_subgraph, which then finds no triples (its saved output shows
  14 retrieved elements and 0 bytes of context).
- "ours" is bench.graph_query.retrieve (MiniLM + FAISS, cosine ≥ 0.30 plus the exact-name bonus, 4 seeds + one hop)
  over cards built from the official Pilot parse of EVModel.sysml; "ours + doc" adds each element's documentation
  text to its card, which our frozen cards leave out and the authors' snippets include.

Departures from the paper, recorded in the manifest: the answering model is qwen3.8-max (the authors used gpt-4.1,
reached through the same instruction and input text); questions 1 and 3 are written from the paper's description
(torque value, the vehicle's composition), question 2 is the notebook's; the relevant-element labels are ours,
because the paper does not publish them per question; every retrieved set is saved so they can be relabelled.

Output: analysis/paper2-replication-<stamp>/ (manifest.json, retrieval.json, answers.json, contexts/).
"""
from __future__ import annotations

import os

os.environ.setdefault("HF_HUB_OFFLINE", "1")  # the authors load MiniLM by name; the pinned snapshot is in the local cache

import json  # noqa: E402
import sys  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from pathlib import Path  # noqa: E402
from types import SimpleNamespace  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import faiss  # noqa: E402
import numpy as np  # noqa: E402
import rdflib  # noqa: E402
from rdflib import Graph, Namespace  # noqa: E402
from sentence_transformers import SentenceTransformer  # noqa: E402

from agents.llm import MODEL_OVERRIDE, USAGE_LOG, chat, usage_summary  # noqa: E402
from bench.experiment import load_env  # noqa: E402
from bench.graph_query import build_graph, official_parse, retrieve as our_retrieve  # noqa: E402
from mvp.engine import exported_elements  # noqa: E402

GRAG = ROOT / "research" / "paper-artifacts" / "SysML-v2-GRAG-Pipeline-main"
TTL = GRAG / "cache" / "sysml_model_477e1397-b094-4b94-a097-2cf8218d3110.ttl"
EV_MODEL = GRAG / "EVModel.sysml"
ANSWER_MODEL = "qwen3.8-max"
THRESHOLDS = [0.35, 0.40, 0.45]
ANSWER_THRESHOLDS = [0.35, 0.45]

QUESTIONS = {
    "Q1": {"text": "What is the torque of the motor in the high performance electric vehicle?",
           "source": "written from the paper's description (a torque value)",
           "relevant": ["VehicleInstances/highPerformanceEV", "VehicleInstances/highPerformanceEV/motor",
                        "VehicleInstances/highPerformanceEV/motor/torque"],
           "answer_must": [["600"]]},
    "Q2": {"text": "What is the the high performance electric vehicle for?",
           "source": "verbatim from the authors' notebook, cell 12",
           "relevant": ["VehicleInstances/highPerformanceEV", "VehicleInstances/highPerformanceEV/battery",
                        "VehicleInstances/highPerformanceEV/motor"],
           "answer_must": [["upgraded", "upgrade"], ["battery"], ["motor"]]},
    "Q3": {"text": "What does the electric vehicle consist of?",
           "source": "written from the paper's description (the vehicle's composition)",
           "relevant": ["PartDefinitions/ElectricVehicle", "PartDefinitions/ElectricVehicle/battery",
                        "PartDefinitions/ElectricVehicle/motor", "PartDefinitions/ElectricVehicle/cooling"],
           "answer_must": [["battery"], ["motor"], ["cooling"]]},
}

# Table I of the paper (averages over its three questions), for comparison only.
PAPER_TABLE = {"0.35": {"P": 0.180, "R": 1.0, "F1": 0.284}, "0.40": {"P": 0.347, "R": 1.0, "F1": 0.456},
               "0.45": {"P": 0.833, "R": 1.0, "F1": 0.904}}


def authors_namespace() -> dict:
    """The notebook's function cells, executed verbatim. The OpenAI client is replaced by one with the same
    `responses.create(model, instructions, input).output_text` interface that calls our endpoint."""

    class Responses:
        def create(self, model, instructions, input):  # noqa: A002 - the authors' keyword names
            reply = chat([{"role": "system", "content": instructions}, {"role": "user", "content": input}], max_tokens=1200)
            return SimpleNamespace(output_text=reply["text"])

    ns = {"rdflib": rdflib, "Graph": Graph, "Namespace": Namespace, "SentenceTransformer": SentenceTransformer,
          "faiss": faiss, "np": np, "SYSML": Namespace("http://example.org/sysml#"),
          "OPENAI_MODEL": ANSWER_MODEL, "client": SimpleNamespace(responses=Responses())}
    notebook = json.loads((GRAG / "grag-pipeline.ipynb").read_text(encoding="utf-8"))
    wanted = ("def load_graph", "def extract_snippets", "def build_vector_index", "def retrieve_nodes",
              "def fetch_subgraph", "def serialize_subgraph", "def answer_query")
    used = []
    for cell in notebook["cells"]:
        source = "".join(cell.get("source", []))
        if cell.get("cell_type") == "code" and source.lstrip().startswith(wanted):
            exec(compile(source, f"grag-pipeline.ipynb:{source.split('(')[0].split()[-1]}", "exec"), ns)
            used.append(source.split("(")[0].split()[-1])
    missing = [name.split()[-1] for name in wanted if name.split()[-1] not in used]
    if missing:
        raise RuntimeError(f"notebook cells not found: {missing}")
    return ns


def score(retrieved: list[str], relevant: list[str]) -> dict:
    """The paper's definitions: P = relevant retrieved / retrieved, R = relevant retrieved / relevant."""
    found = sorted(set(retrieved) & set(relevant))
    missed = sorted(set(relevant) - set(retrieved))
    precision = len(found) / len(set(retrieved)) if retrieved else 0.0
    recall = len(found) / len(relevant) if relevant else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"retrieved": len(set(retrieved)), "relevant_retrieved": len(found), "missed": missed,
            "precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3)}


def answer_checks(text: str, must: list[list[str]]) -> dict:
    lowered = text.lower()
    hits = [any(word in lowered for word in group) for group in must]
    return {"pass": all(hits), "groups": [{"any_of": group, "found": hit} for group, hit in zip(must, hits)]}


def short(name: str) -> str:
    """Element path without the root package, in the authors' slash form."""
    name = name.replace("::", "/")
    return name.split("ElectricVehicleModel/", 1)[-1] if name.startswith("ElectricVehicleModel/") else name


def main() -> None:
    load_env()
    MODEL_OVERRIDE.set(ANSWER_MODEL)
    log: list = []
    USAGE_LOG.set(log)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    out = ROOT / "analysis" / f"paper2-replication-{stamp}"
    (out / "contexts").mkdir(parents=True)
    ns = authors_namespace()

    graph = ns["load_graph"](str(TTL))
    snippets = ns["extract_snippets"](graph)
    full_uri = {str(subject).replace("http://example.org/sysml#", "").replace("http://example.org/", ""): str(subject)
                for subject in set(graph.subjects())}
    model, index, uris = ns["build_vector_index"](snippets, "sentence-transformers/all-MiniLM-L6-v2", str(out / "authors-faiss.index"))

    parse = official_parse(Path("/nonexistent"), [EV_MODEL], "ElectricVehicleModel")
    cards, neighbors, _kinds = build_graph(parse, "ElectricVehicleModel::")
    elements = exported_elements(json.loads((parse / "sysml" / "model.json").read_text(encoding="utf-8")))
    by_id = {element["@id"]: element for element in elements}
    docs: dict[str, list[str]] = {}
    for element in elements:
        if element.get("@type") == "Documentation" and element.get("body"):
            for target in element.get("annotatedElement") or []:
                docs.setdefault(target["@id"], []).append(" ".join(element["body"].split()))
    cards_doc = {ident: text + (f" doc: {' '.join(docs[ident])}" if ident in docs else "") for ident, text in cards.items()}
    name_of_card = {ident: short(by_id[ident].get("qualifiedName") or text.split(" ")[1]) for ident, text in cards.items()}
    text_to_name = {text: name_of_card[ident] for ident, text in cards.items()}
    text_to_name.update({text: name_of_card[ident] for ident, text in cards_doc.items()})

    model_bytes = len(EV_MODEL.read_bytes())
    retrieval, answers = [], []
    for qid, question in QUESTIONS.items():
        for threshold in THRESHOLDS:
            keys = ns["retrieve_nodes"](question["text"], model, index, uris, threshold=threshold, sort=True)
            names = [short(key) for key in keys]
            published = ns["serialize_subgraph"](ns["fetch_subgraph"](keys, graph))
            fixed = ns["serialize_subgraph"](ns["fetch_subgraph"]([full_uri[key] for key in keys], graph))
            for variant, context in (("authors as published", published), ("authors, URI fix", fixed)):
                tag = f"{qid}-{variant.replace(' ', '_').replace(',', '')}-{threshold:.2f}"
                (out / "contexts" / f"{tag}.txt").write_text(context, encoding="utf-8")
                retrieval.append({"question": qid, "variant": variant, "threshold": threshold, "retrieved_names": sorted(names),
                                  "context_bytes": len(context.encode("utf-8")),
                                  "context_over_model_bytes": round(len(context.encode("utf-8")) / model_bytes, 3),
                                  **score(names, question["relevant"])})
                if threshold in ANSWER_THRESHOLDS:
                    text = ns["answer_query"](context, question["text"])
                    answers.append({"question": qid, "variant": variant, "threshold": threshold, "answer": text,
                                    "context_bytes": len(context.encode("utf-8")), **answer_checks(text, question["answer_must"])})
        for variant, deck in (("ours", cards), ("ours + doc", cards_doc)):
            texts, settings = our_retrieve(question["text"], deck, neighbors)
            names = [text_to_name[text] for text in texts]
            context = "\n".join(texts)
            tag = f"{qid}-{variant.replace(' ', '_').replace('+', 'plus')}"
            (out / "contexts" / f"{tag}.txt").write_text(context, encoding="utf-8")
            retrieval.append({"question": qid, "variant": variant, "threshold": settings["threshold"], "settings": settings,
                              "retrieved_names": sorted(names), "context_bytes": len(context.encode("utf-8")),
                              "context_over_model_bytes": round(len(context.encode("utf-8")) / model_bytes, 3),
                              **score(names, question["relevant"])})
            text = ns["answer_query"](context, question["text"])
            answers.append({"question": qid, "variant": variant, "threshold": settings["threshold"], "answer": text,
                            "context_bytes": len(context.encode("utf-8")), **answer_checks(text, question["answer_must"])})

    averages = {}
    for row in retrieval:
        key = f"{row['variant']} @ {row['threshold']:.2f}" if row["variant"].startswith("authors") else row["variant"]
        slot = averages.setdefault(key, {"P": [], "R": [], "F1": [], "bytes": []})
        slot["P"].append(row["precision"])
        slot["R"].append(row["recall"])
        slot["F1"].append(row["f1"])
        slot["bytes"].append(row["context_bytes"])
    averages = {key: {metric: round(sum(values) / len(values), 3) for metric, values in slot.items()} for key, slot in averages.items()}
    answer_table = {}
    for row in answers:
        key = f"{row['variant']} @ {row['threshold']:.2f}" if row["variant"].startswith("authors") else row["variant"]
        answer_table.setdefault(key, {})[row["question"]] = row["pass"]

    (out / "retrieval.json").write_text(json.dumps(retrieval, indent=1), encoding="utf-8")
    (out / "answers.json").write_text(json.dumps(answers, indent=1, ensure_ascii=False), encoding="utf-8")
    (out / "manifest.json").write_text(json.dumps({
        "authors_repository": "https://github.com/eeeeebader/SysML-v2-GRAG-Pipeline", "authors_commit": "d910822179cccda2d815121f03aa9d11888cd65f",
        "authors_inputs": [str(TTL.relative_to(ROOT)), str(EV_MODEL.relative_to(ROOT)), "grag-pipeline.ipynb"],
        "authors_snippets": len(snippets), "our_cards": len(cards), "official_parse": parse.name,
        "model_bytes": model_bytes, "authors_hardcoded_model_bytes": 3354,
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2", "answer_model": ANSWER_MODEL,
        "questions": {qid: {key: value for key, value in question.items()} for qid, question in QUESTIONS.items()},
        "paper_table_I": PAPER_TABLE, "averages": averages, "answers_pass": answer_table,
        "departures": [
            "Answering model qwen3.8-max instead of gpt-4.1, with the authors' instruction and input text.",
            "Questions 1 and 3 written from the paper's description; question 2 verbatim from the notebook.",
            "Relevant-element labels are ours; the paper does not publish them per question.",
            "MiniLM is loaded from the local cache (same weights); the authors' FAISS index is written to this folder.",
            "'authors, URI fix' passes full URIs to fetch_subgraph; nothing else in the authors' code is changed.",
        ],
        "usage": usage_summary(log)}, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"out": str(out.relative_to(ROOT)), "averages": averages, "answers_pass": answer_table,
                      "usage": usage_summary(log)}, indent=1))


if __name__ == "__main__":
    main()
