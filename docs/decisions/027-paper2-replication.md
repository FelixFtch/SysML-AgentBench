# 027 · Paper 2 replicated on its own EV model: the published notebook passes an empty context; our retrieval matches the fixed pipeline once cards carry documentation

Date: 2026-10-06. Status: accepted (replication recorded; the proposed change was applied in freeze revision 2, decision 028). Affects `bench/replicate_paper2.py` (new). Output: `analysis/paper2-replication-20261006T165238/`.

## What was run

The authors' notebook functions (`grag-pipeline.ipynb`, commit `d910822`, MIT) were executed verbatim on their cached RDF graph of the EV model (43 node snippets, as in their saved output), at the paper's three thresholds, then with one change, full URIs passed to `fetch_subgraph`. Our retrieval (`bench/graph_query.retrieve`: MiniLM + FAISS, cosine ≥ 0.30 plus the exact-name bonus, 4 seeds + one hop) ran over cards built from the official Pilot parse of the same `EVModel.sysml` (41 cards; the model passes the Pilot), with and without each element's documentation text. All six variants answered the same three questions with the authors' instruction and input text, on qwen3.8-max (the authors used gpt-4.1): 18 calls, 13,039 input and 1,053 output tokens.

Departures: question 2 is the notebook's ("What is the the high performance electric vehicle for?"); questions 1 and 3 are written from the paper's description (a torque value, the vehicle's composition) because the paper's wording was not available; the relevant-element labels are ours (3, 3 and 4 elements), because the paper does not publish them per question. Every retrieved set is saved for relabelling.

## Results

| Variant | Answers right (torque, purpose, composition) | Retrieval P / R / F1, our labels | Context |
|---|---|---|---|
| Authors' code as published, 0.35 and 0.45 | 0 / 3 | as the fixed row (same retrieval) | 0 bytes |
| Authors' code, URI fix, 0.35 | 3 / 3 | 0.177 / 1.000 / 0.297 | 12,058 bytes |
| Authors' code, URI fix, 0.45 | 3 / 3 | 0.466 / 0.583 / 0.373 | 6,133 bytes |
| Ours | 2 / 3 (purpose missed) | 0.208 / 0.556 / 0.303 | 622 bytes |
| Ours, cards with documentation | 3 / 3 | 0.208 / 0.556 / 0.303 | 738 bytes |

The paper's Table I reports 0.180 / 1.000 / 0.284 at 0.35 and 0.833 / 1.000 / 0.904 at 0.45.

## Reading

1. **The published notebook gives the model nothing.** It strips the URI prefix to make keys and passes the keys to `fetch_subgraph`, which then finds no triples; with an empty context the model says it cannot answer. The notebook's saved output shows the same (14 elements retrieved, 0 bytes of context); its saved answer comes from another run. One change, full URIs, fixes it.
2. **The 0.35 row reproduces; the 0.904 does not.** At 0.35 everything relevant is retrieved and precision matches the paper (0.177 against 0.180). At 0.45 the result depends on the question wording and the labels: the verbatim question 2 retrieves a single node, and our labels count the upgraded battery and motor as relevant. Without the paper's wording and labels the gap cannot be attributed further.
3. **Our retrieval answers as well as the fixed pipeline with a tenth of the context, once the cards carry documentation.** Without it, the purpose question fails: the purpose is written only in a `doc` comment, the authors' snippets include comments and our cards do not; the model then says the context does not state the purpose. Label-based recall is low for us on the composition question (we retrieve the three vehicle instances' parts, not the definition's), yet the answer is right, which shows how much these labels decide.
4. **A correction.** Decision 023 and the docstring of `bench/vector_index.py` describe the authors' index as an L2 search with radius 0.35. The code builds `IndexFlatIP` over unit vectors and normalises the query, so 0.35 is a cosine threshold, close to our 0.30. Decision 023 is corrected; the frozen docstring is corrected at the next freeze.

## Proposed, then applied

Add each element's documentation text to its retrieval card (`bench/graph_query.build_graph`). The MaritimeISR model has three `doc` comments and the official-examples library fifteen; the cards carried none of them. The user decided to apply it: freeze revision 2 (decision 028) adds the text, rebuilds the examples library and reruns every P3 cell of both direct batches.
