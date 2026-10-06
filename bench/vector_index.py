"""Vector retrieval over element cards: the embedding step of the GRAG paper, on our own parses.

Cards are the one-line element descriptions that `bench.graph_query.build_graph` makes from an
official Pilot parse ("type qualifiedName [literal | connection ends]"), or text notes. Each card is
embedded with sentence-transformers/all-MiniLM-L6-v2, the model the paper used, and kept in a FAISS
inner-product index over unit vectors, so the score is the cosine similarity. Seeds are the best
cards above a threshold; the caller adds one-hop neighbours from the parse graph, as the paper does.

The paper searched an L2 index with a fixed radius (0.35 on its electric-vehicle model). That radius
was calibrated on that model and is not reused here; `bench/eval_retrieval.py` calibrates the cosine
threshold on our own labelled questions and records the result.

The FAISS file is a derived cache keyed by the hash of the card texts and the model name. It lives
under analysis/vector-index/ and is rebuilt when the cards change; only manifests are committed.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
CACHE = ROOT / "analysis" / "vector-index"
DEFAULT_THRESHOLD = float(os.environ.get("BENCH_VECTOR_THRESHOLD", "0.30"))
REQUIREMENTS = ROOT / "requirements-retrieval.txt"
INSTALL = "pip install --user -r requirements-retrieval.txt"

_MODEL = None


def snapshot(download: bool = False) -> Path:
    """Local folder of the pinned MiniLM snapshot. Loading from it never touches the network; only
    `python3 bench/vector_index.py --download` fetches it."""
    try:
        from huggingface_hub import snapshot_download
        from huggingface_hub.errors import LocalEntryNotFoundError
    except ImportError as exc:
        raise ImportError(f"MiniLM + FAISS retrieval needs huggingface-hub: {INSTALL}") from exc
    try:
        return Path(snapshot_download(EMBEDDING_MODEL, revision=EMBEDDING_REVISION, local_files_only=not download))
    except LocalEntryNotFoundError as exc:
        raise OSError(f"{EMBEDDING_MODEL} snapshot {EMBEDDING_REVISION} is not in the local Hugging Face cache: "
                      "python3 bench/vector_index.py --download") from exc


def model():
    """The sentence-transformer at the pinned snapshot, loaded once per process (CPU is enough for a few thousand cards)."""
    global _MODEL
    if _MODEL is None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ImportError(f"MiniLM + FAISS retrieval needs sentence-transformers: {INSTALL}") from exc
        _MODEL = SentenceTransformer(str(snapshot()), device="cpu")
    return _MODEL


def _faiss():
    try:
        import faiss
    except ImportError as exc:
        raise ImportError(f"MiniLM + FAISS retrieval needs faiss-cpu: {INSTALL}") from exc
    return faiss


def embed(texts: list[str]) -> np.ndarray:
    vectors = model().encode(list(texts), normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)
    return np.asarray(vectors, dtype="float32")


def cards_key(cards: dict[str, str]) -> str:
    digest = hashlib.sha256()
    digest.update(EMBEDDING_MODEL.encode())
    for ident in sorted(cards):
        digest.update(ident.encode())
        digest.update(b"\0")
        digest.update(cards[ident].encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()[:16]


class CardIndex:
    """FAISS index over one card dictionary, cached on disk by content hash."""

    def __init__(self, cards: dict[str, str], name: str):
        faiss = _faiss()
        self.cards = dict(cards)
        self.ids = sorted(self.cards)
        self.name = name
        self.key = cards_key(self.cards)
        CACHE.mkdir(parents=True, exist_ok=True)
        self.path = CACHE / f"{name}-{self.key}.faiss"
        manifest = CACHE / f"{name}-{self.key}.json"
        if self.path.is_file() and manifest.is_file():
            self.index = faiss.read_index(str(self.path))
            self.built = False
        else:
            vectors = embed([self.cards[ident] for ident in self.ids])
            self.index = faiss.IndexFlatIP(vectors.shape[1])
            self.index.add(vectors)
            faiss.write_index(self.index, str(self.path))
            manifest.write_text(json.dumps({"name": name, "key": self.key, "model": EMBEDDING_MODEL,
                                            "cards": len(self.ids), "dimension": int(vectors.shape[1]),
                                            "metric": "cosine (inner product over unit vectors)"},
                                           indent=2), encoding="utf-8")
            self.built = True

    def search(self, query: str, k: int = 8) -> list[tuple[str, float]]:
        """Best k cards for the query as (id, cosine), highest first."""
        if not self.ids:
            return []
        vector = embed([query])
        scores, rows = self.index.search(vector, min(k, len(self.ids)))
        return [(self.ids[int(row)], float(score)) for score, row in zip(scores[0], rows[0]) if row >= 0]


NAME_BONUS = 0.1


def name_bonus(query: str, card: str) -> float:
    """Exact-token match between the query and the card's name segments (not its type).

    Model questions name elements literally ("usv", "powerLimitW"); a 384-dimensional sentence
    vector blurs those short identifiers, so an exact match adds a fixed bonus. This is the
    lexical half of the hybrid retrieval the paper review recommended."""
    tokens = {token.lower() for token in re.findall(r"[A-Za-z][A-Za-z0-9]*", query) if len(token) > 2}
    parts = card.split(" ")
    if len(parts) < 2:
        return 0.0
    segments = {segment.lower() for segment in re.split(r"::|\[|\]|→|\.|\s", parts[1]) if segment}
    return NAME_BONUS * len(tokens & segments)


def retrieve(query: str, cards: dict[str, str], neighbors: dict[str, set], *, name: str,
             k_seeds: int = 4, limit: int = 12, threshold: float | None = None, hybrid: bool = True) -> dict:
    """Paper 2's two steps on our cards: vector seeds above the threshold, then their one-hop neighbours.

    With hybrid=True the ranking score is cosine plus an exact-name bonus; the threshold still
    applies to the cosine alone. Returns the picked ids in order with their role, the scores, and
    the settings used, so the record can say exactly how the context was chosen.
    """
    threshold = DEFAULT_THRESHOLD if threshold is None else threshold
    index = CardIndex(cards, name)
    ranked = index.search(query, k=len(cards))  # libraries are small; scoring every card gives neighbours a score too
    cosine = {ident: score for ident, score in ranked}
    if hybrid:
        ranked = sorted(((ident, score + name_bonus(query, cards[ident])) for ident, score in ranked),
                        key=lambda item: -item[1])
    scores = {ident: score for ident, score in ranked}
    seeds = [ident for ident, score in ranked if cosine[ident] >= threshold][:k_seeds]
    picked: list[dict] = []
    seen: set[str] = set()
    for ident in seeds:
        seen.add(ident)
        picked.append({"id": ident, "role": "seed", "score": round(scores[ident], 4)})
    edges = []
    for seed in seeds:
        for hop in sorted(neighbors.get(seed, ()), key=lambda ident: cards.get(ident, "~")):
            if len(picked) >= limit:
                break
            if hop not in cards or hop in seen:
                continue
            seen.add(hop)
            picked.append({"id": hop, "role": "neighbor", "via": seed, "score": round(scores.get(hop, 0.0), 4)})
            edges.append({"from": seed, "to": hop})
    return {"method": "hybrid" if hybrid else "vector", "embedding_model": EMBEDDING_MODEL, "threshold": threshold,
            "k_seeds": k_seeds, "name_bonus": NAME_BONUS if hybrid else 0.0,
            "index_key": index.key, "library_size": len(cards), "picked": picked, "edges": edges,
            "top": [{"id": ident, "score": round(score, 4), "cosine": round(cosine[ident], 4), "text": cards[ident]}
                    for ident, score in ranked[:8]]}


def check() -> dict:
    """Raise unless every package in requirements-retrieval.txt is installed at its pinned version and the pinned
    MiniLM snapshot embeds and searches. Nothing is written to the index cache."""
    from importlib.metadata import PackageNotFoundError, version
    pins = dict(line.strip().split("==", 1) for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.strip().startswith(("#", "-")))
    wrong = {}
    for name, pinned in pins.items():
        try:
            installed = version(name)
        except PackageNotFoundError:
            installed = None
        if installed != pinned:
            wrong[name] = {"pinned": pinned, "installed": installed}
    if wrong:
        raise RuntimeError(f"retrieval stack differs from requirements-retrieval.txt: {wrong}. {INSTALL}")
    faiss = _faiss()
    cards = embed(["part def RadioUnit", "attribute powerLimitW = 60.0"])
    index = faiss.IndexFlatIP(cards.shape[1])
    index.add(cards)
    scores, rows = index.search(embed(["what is the power limit"]), 2)
    if cards.shape[1] != 384 or int(rows[0][0]) != 1:
        raise RuntimeError(f"retrieval self-test failed: dimension {cards.shape[1]}, best card {int(rows[0][0])}")
    return {"packages": pins, "model": EMBEDDING_MODEL, "revision": EMBEDDING_REVISION, "dimension": int(cards.shape[1]),
            "self_test_cosine": [round(float(score), 4) for score in scores[0]]}


if __name__ == "__main__":
    if sys.argv[1:] not in (["--check"], ["--download"]):
        raise SystemExit("usage: python3 bench/vector_index.py --check | --download")
    try:
        if sys.argv[1] == "--download":
            print(snapshot(download=True))
        print(json.dumps(check(), indent=2))
    except (ImportError, OSError, RuntimeError) as exc:
        raise SystemExit(f"retrieval check FAILED: {exc}")
