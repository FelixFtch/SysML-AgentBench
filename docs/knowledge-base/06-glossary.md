# 6. Glossary

| Term | Meaning here |
|---|---|
| Pilot | The official OMG SysML v2 Pilot Implementation, version 0.62, run headless; the only syntax judge. |
| Official parse / syntax verdict | PASS when the Pilot parses, links and statically validates the files without an error. |
| Task verdict | PASS when the answer does what the task asked: official parse (for SysML answers), every required name, connection or mapping, no invented number, every value to keep unchanged, every check as the key expects. |
| Design verdict | Whether the design meets its budget (power, uplink, storage), computed from the officially parsed numbers; reported separately from the task verdict. |
| Answer key, gold | The expected result of a task, written before any run and never shown to a candidate (`gold/`). |
| Cell | One task × one approach × one repeat for a direct candidate; for an agent, one run. |
| Repeat group | The three repeats of one task under one approach; it "disagrees" when the repeats do not all give the same verdict. |
| P0 · P1 · P2 · P3 | The four direct approaches: one answer; plus the repair loop; plus an outline first; plus retrieval. |
| Repair loop | Sending the complete official diagnostic list back to the model in the same conversation, at most 20 times, stopping after three identical resubmissions. |
| GEN · MOD · ALN · QRY · AMB · RT | Task types: generate a model, modify a model, align two models, query a model, ask when a number is missing, restate a model as requirements. |
| Alignment package | A separate SysML v2 package that links two models without editing them: `alias` for definitions and their features, `allocation` for usages. |
| Card | One line describing one element of an officially parsed model (type, qualified name, value or connection ends); the unit of retrieval. |
| Seed, one hop | The best cards by vector similarity; and the cards directly linked to them by ownership or a connection. |
| Hybrid retrieval | Cosine similarity of MiniLM embeddings in a FAISS index, plus 0.10 for each query word that equals part of a card's name; seeds need cosine ≥ 0.30. |
| Sandbox | The bubblewrap environment the agents run in: the task, `AGENTS.md`, `./validate`, nothing else of the repository. |
| `./validate` | The agents' wrapper around the Pilot; passes files in the scorer's order. |
| Discarded batch | A batch kept on disk but not scored, with the reason (`bench/batches.py`, `DISCARDED`). |
| Superseded rows | Rows of a batch replaced by a rerun, kept on disk with the reason (`superseded_rows`). |
| Freeze, amendment | The hashed state of tasks, scorers, prompts and toolchain before a batch; a recorded change after it, with evidence that scored results stand. |
| List price | The provider's published price per million tokens (China (Beijing) region, checked 2026-10-03); cached input is billed at about an eighth of fresh input. |
