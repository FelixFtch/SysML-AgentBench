# 023 · Paper 2's retrieval, implemented: MiniLM + FAISS over Pilot-parsed element cards

Date: 2026-10-06. Status: accepted. Affects `bench/vector_index.py` (new), `bench/graph_query.py`, `bench/discover.py`, `agents/solve.py`, `bench/build_examples_library.py` (new), `bench/eval_retrieval.py` (new).

## Before

Retrieval was a word-and-number match over the element cards: a card scored when a brief word appeared in its text or it held the same number; the top 4 were seeds, plus one hop. No embeddings. The page said "No vectors and no FAISS" under paper 2. Connections (`connect a to b;`) have no name in the Pilot export, so they had no card at all; that is why the graph-retrieval run of QRY-03 answered 0 connections.

## Now

- `bench/vector_index.py`: every card is embedded with `sentence-transformers/all-MiniLM-L6-v2`, the model the paper used, into a FAISS inner-product index over unit vectors (cosine). Seeds are the best cards with cosine ≥ 0.30 (`BENCH_VECTOR_THRESHOLD`), ranked by cosine plus an exact-name bonus of 0.10 per query token that equals a segment of the card's qualified name. One hop of neighbours from the parse graph is added, as in the paper. The index is a cache keyed by card content and is rebuilt when the cards change; only manifests are committed.
- `bench/graph_query.build_graph` now makes a card for every unnamed connection, `Owner::connect[a → b]`, so connections are retrievable. MaritimeISR goes from 53 to 63 cards.
- Part 2 `① Retrieve` and the graph-retrieval QRY experiment use it over the memory library (MaritimeISR plus approved designs). Each record states `method`, `embedding_model`, `threshold`, `name_bonus` and `index_key`; if the embedding stack is missing the record says `keyword` and names the fallback reason.
- Exam P3 uses it over a separate library: official SysML-v2-Release examples (20 of 21 folders parsed by the Pilot; the Vehicle Example timed out) plus the notes corpus, 761 cards, built by `bench/build_examples_library.py` with a leak check against the held-out names. MaritimeISR is not in that library because the QRY tasks read it and GEN-03's `fusionLatencyS = 2.0` is in it.

## Measured

`bench/eval_retrieval.py`, five QRY questions, relevant elements taken from the answer keys (15 in all), up to 4 seeds + one hop, 12 cards:

| Method | Recall | Precision | Hits |
|---|---|---|---|
| keyword (previous) | 0.80 | 0.29 | 11/15 |
| vector only, cosine ≥ 0.30 | 0.80 | 0.40 | 11/15 |
| hybrid (vector + name bonus), cosine ≥ 0.30 | 0.90 | 0.48 | 13/15 |

Thresholds 0.20–0.40 give the same hits; 0.50 returns nothing. 0.30 is kept so that longer briefs still produce seeds. The misses are two of QRY-01's four platform names, which compete with four processor cards for four seed slots.

Graph-retrieval QRY with qwen3.8-max, context = retrieved cards only: 5/5 (`analysis/graph-query-20261006T053755.json`); the 2026-10-03 keyword run was 4/5 (`graph-query-max.json`, QRY-03 answered 0). GEN-03 under P3 with the new library and the new repair loop: PASS in one trial (`analysis/trial-p3-20261006T054209/`).

## Not reproduced from the paper

Its input is the SysML v2 API's JSON-LD turned into RDF; ours is the Pilot's JSON export. Its radius search on an L2 index with 0.35 was calibrated on its vehicle model and is not reused. Its F1 of 0.904 is on its own three questions. The exact-name bonus is ours, added because 384-dimensional sentence vectors blur short identifiers like `usv`.
