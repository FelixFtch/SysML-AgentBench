"""Compare keyword and vector retrieval over the MaritimeISR cards on the five QRY questions.

Relevant cards per question come from the answer key: the qualified names it lists, or, for
QRY-03, every connection card with an end on commandShip. Both methods pick up to 4 seeds and add
one-hop neighbours up to 12 cards, as the Part 2 retrieval does. The vector method is scored at
several cosine thresholds so the threshold used later is a recorded choice, not a guess.
No model is called; the Pilot parse is the saved one.
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

from bench.discover import STOPWORDS, numbers_in  # noqa: E402
from bench.graph_query import build_graph, maritime_parse  # noqa: E402
from bench.vector_index import DEFAULT_THRESHOLD, retrieve as vector_retrieve  # noqa: E402

HELD = ROOT / "bench" / "tasks" / "t4_maritime_isr" / "heldout"
THRESHOLDS = (0.0, 0.2, 0.25, 0.3, 0.35, 0.4, 0.5)


def question_of(task_id: str) -> str:
    text = (HELD / task_id / "input" / "requirements.md").read_text(encoding="utf-8")
    return "\n".join(line for line in text.splitlines() if line.strip() and not line.startswith("#"))


def relevant_of(task_id: str, cards: dict[str, str]) -> set[str]:
    gold = json.loads((HELD / task_id / "gold" / "answer.json").read_text(encoding="utf-8"))
    by_name = {}
    for ident, text in cards.items():
        parts = text.split(" ")
        if len(parts) > 1:
            by_name[parts[1]] = ident
    wanted: set[str] = set()
    for value in gold.values():
        for name in (value if isinstance(value, list) else [value]):
            if isinstance(name, str) and name in by_name:
                wanted.add(by_name[name])
    if task_id == "QRY-03":
        wanted = {ident for ident, text in cards.items() if text.startswith("ConnectionUsage") and "commandShip" in text}
    if task_id == "QRY-05":
        wanted = {ident for ident, text in cards.items()
                  if text.startswith("AttributeUsage MaritimeISR::UnmannedSurfaceVessel::")}
    return wanted


def keyword_pick(query: str, cards: dict[str, str], neighbors: dict, limit: int = 12) -> list[str]:
    words = {word.lower() for word in re.findall(r"[A-Za-z]+", query) if len(word) > 2} - STOPWORDS
    values = numbers_in(query)
    score = {ident: sum(word in text.lower() for word in words) + len(values & numbers_in(text)) for ident, text in cards.items()}
    ranked = sorted(cards, key=lambda ident: (-score[ident], cards[ident]))
    seeds = [ident for ident in ranked[:4] if score[ident] > 0]
    picked = list(seeds)
    for seed in seeds:
        for hop in sorted(neighbors.get(seed, ()), key=lambda ident: cards.get(ident, "~")):
            if len(picked) >= limit:
                break
            if hop in cards and hop not in picked:
                picked.append(hop)
    return picked


def measure(picked: list[str], wanted: set[str]) -> dict:
    hit = len(set(picked) & wanted)
    return {"picked": len(picked), "relevant": len(wanted), "hit": hit,
            "recall": round(hit / len(wanted), 3) if wanted else None,
            "precision": round(hit / len(picked), 3) if picked else None}


def main() -> None:
    cards, neighbors, _kinds = build_graph(maritime_parse(), "MaritimeISR::")
    rows = []
    for task_id in ("QRY-01", "QRY-02", "QRY-03", "QRY-04", "QRY-05"):
        query = question_of(task_id)
        wanted = relevant_of(task_id, cards)
        row = {"task_id": task_id, "relevant": sorted(cards[i] for i in wanted),
               "keyword": measure(keyword_pick(query, cards, neighbors), wanted), "vector": {}, "hybrid": {}}
        for threshold in THRESHOLDS:
            for method, hybrid in (("vector", False), ("hybrid", True)):
                result = vector_retrieve(query, cards, neighbors, name="maritime", threshold=threshold, hybrid=hybrid)
                picked = [item["id"] for item in result["picked"]]
                row[method][str(threshold)] = {**measure(picked, wanted),
                                               "seed_scores": [item["score"] for item in result["picked"] if item["role"] == "seed"]}
        row["hybrid_top"] = vector_retrieve(query, cards, neighbors, name="maritime", threshold=0.0)["top"]
        rows.append(row)
    summary = {}
    for method in ["keyword"] + [f"{kind}@{t}" for kind in ("vector", "hybrid") for t in THRESHOLDS]:
        def get(row):
            if method == "keyword":
                return row["keyword"]
            kind, threshold = method.split("@")
            return row[kind][threshold]
        recalls = [get(row)["recall"] for row in rows if get(row)["recall"] is not None]
        precisions = [get(row)["precision"] for row in rows if get(row)["precision"] is not None]
        summary[method] = {"mean_recall": round(sum(recalls) / len(recalls), 3) if recalls else None,
                           "mean_precision": round(sum(precisions) / len(precisions), 3) if precisions else None,
                           "hits": sum(get(row)["hit"] for row in rows), "relevant": sum(get(row)["relevant"] for row in rows)}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    out = ROOT / "analysis" / f"retrieval-eval-{stamp}.json"
    out.write_text(json.dumps({"id": stamp, "library": "MaritimeISR official parse", "cards": len(cards),
                               "default_threshold": DEFAULT_THRESHOLD, "rows": rows, "summary": summary},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{'method':14} {'recall':>7} {'prec':>6} {'hits':>5}")
    for method, item in summary.items():
        print(f"{method:14} {str(item['mean_recall']):>7} {str(item['mean_precision']):>6} {item['hits']:>3}/{item['relevant']}")
    for row in rows:
        kw, vec, hyb = row["keyword"], row["vector"][str(DEFAULT_THRESHOLD)], row["hybrid"][str(DEFAULT_THRESHOLD)]
        print(f"{row['task_id']}: relevant {kw['relevant']} · keyword {kw['hit']}/{kw['picked']} · vector@{DEFAULT_THRESHOLD} {vec['hit']}/{vec['picked']} · hybrid@{DEFAULT_THRESHOLD} {hyb['hit']}/{hyb['picked']} · hybrid seed scores {hyb['seed_scores']}")
    print(out)


if __name__ == "__main__":
    main()
