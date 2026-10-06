# Public engineering material: follow-up checks and actual integration

Date: 2026-09-22. Scope: only two sets of material that can be demonstrated end to end; every original file is kept in `mvp/public-data/` and not mixed into application source. Public material is not called RTX internal data, and tutorial models are not called formal designs of a physical system.

## 1 NASA cFE: traceable, real public requirements as input

- Primary source: [nasa/cFE](https://github.com/nasa/cFE), [CSV at a fixed version](https://github.com/nasa/cFE/blob/7d283938c9af5bd6e439f3fc307e61b0c7799640/docs/cFE_FunctionalRequirements.csv).
- Downloaded version: `7d283938c9af5bd6e439f3fc307e61b0c7799640`, a snapshot of the `dev` branch; it is not called a formally accepted release.
- License: the repository states [Apache-2.0](https://github.com/nasa/cFE/blob/7d283938c9af5bd6e439f3fc307e61b0c7799640/LICENSE); LICENSE, README and the original documents are kept, and the content is not re-declared as this project's own.
- Actually downloaded: the complete `cFE_FunctionalRequirements.csv`, `cfe requirements.docx`, LICENSE and README, 440,647 bytes in total. The manifest records the original URL, commit, byte counts and SHA-256.
- Measured: the CSV is not 596 independent requirements but 596 data records: 414 distinct non-empty requirement IDs plus 182 text continuation lines without an ID. The continuation lines hold lists and requirement text and must not be dropped.
- Deterministic parsing done: continuation lines are merged into the nearest preceding non-empty ID, keeping every field of each original record, the CSV record number, the physical line range and the source-file hash. Output: 414 `imported_candidate` items, 82 of them Software Bus requirements. The merge rule is written into the report explicitly; whether the requirements apply to a new project still needs a domain expert.
- Eight selected for the demonstration: cSB4301, cSB4303, cSB4305, cSB4305.3, cSB4305.6, cSB4307, cSB4332, cSB4328, covering message queues, subscription routing, overflow, size limits, timeouts, default configuration and checksums. They fit as historical requirement references for a message gateway; they do not automatically become a new baseline for the maritime system.
- No `MISSION_DEFINED` / `PLATFORM_DEFINED` value was filled in, and no camera rate, storage capacity or power figure was invented from the NASA documents.

### Real requirements → SysML import

Generated `mvp/public-data/nasa-cfe/derived/NASA_CFE_Imported.sysml`: one RequirementDefinition and eight RequirementUsages. Each keeps the original ID, the commit, the original CSV SHA, the CSV record location and the status `TEXT_IMPORTED_SEMANTIC_MAPPING_PENDING`. The natural-language text stays in documentation; no formal predicate, satisfy relation or false verification result was generated.

Actual result with the official 0.62.0 parser and the pinned release library: **PASS, 0 diagnostics, 273 AST elements, 3.932 s**; the official model export confirms 8 RequirementUsages and 1 RequirementDefinition. Full run evidence is in `mvp/public-data/nasa-cfe/validation/`.

This shows that a real public document has entered a parseable SysML project. It does not show that the natural-language requirements have been formalized semantically, and it cannot serve as a human gold pairing dataset.

## 2 The official Vehicle project: interoperability with an external multi-file model

- Primary source: [the official Vehicle Example](https://github.com/Systems-Modeling/SysML-v2-Release/tree/fb97b754f29588b8e9c7a35f370880cd15eb29e7/sysml/src/examples/Vehicle%20Example).
- Fixed version: `fb97b754f29588b8e9c7a35f370880cd15eb29e7`, 2026-08.
- Downloaded the unmodified VehicleDefinitions.sysml and VehicleUsages.sysml, plus that version's LICENSE and README; 25,447 bytes for the four files.
- The [repository notes](https://github.com/Systems-Modeling/SysML-v2-Release) state that the included KerML/SysML models are EPL-2.0; the original code and notices are kept separately, and this license is not applied to the NASA files or to our own code.
- Actual run of the official tool: **PASS, 0 diagnostics, 493 AST elements, 6.68 s**, producing the native API delta JSON and an EMF reference/location summary. Evidence is in `mvp/public-data/sysml-official-vehicle/validation/`.
- It demonstrates real cross-file imports, types, ports/interfaces and variant model import. It is not real vehicle data, not a requirements-to-model accuracy benchmark, and does not show physical safety.

Both examples ship a `reference.json`, whitelisted as IDs `nasa-cfe` and `sysml-official-vehicle`. The application reads the original model by relative path, creates a new run that actually calls the tool, and binds the file hashes. Choosing these two public examples does not change the product's cross-domain positioning and does not presuppose that RTX must work on vehicles or spacecraft.

## 3 Hugging Face, checked in practice: samples exist, but they are not high-quality gold

Checked the author-published [rqualis/sysml_v2_instruction](https://huggingface.co/datasets/rqualis/sysml_v2_instruction) at repository commit `9ae0e29051b58e84dc88cc21aeccd07af74494c0`. The README text states Apache-2.0, but the data card still says v0.0.3, and the cardData returned by the API is empty. Actually reading `data/v0.5/train.jsonl` gives 11 lines with only 4 distinct records; test has 2 lines and 2 distinct records. These counts come from the files, not from search-result summaries.

No evidence of compile validation, independent engineering review or complete dependencies was established, so it is not put into the formal gold evaluation and not downloaded into our training or retrieval library. It can be used to inspect a few prompt templates by hand, after de-duplication, version pinning, real tool validation and re-review of the tasks. Tutorial summaries and the SysEngBench knowledge multiple-choice questions are not requirement–model gold either.

Also found [Model Management Challenge 2026 satellite-config](https://github.com/mom-challenge/satellite-config): its OWL directory, JSON BOM / communication network, CSV requirements, reports and two versions are close to the topic of heterogeneous model change. However, the repository API did not identify a license and the Zenodo record's license was not checked further, so it is only recorded as a later candidate; it was not downloaded into the demonstration and is not called licensed data or a result of this work.

## 4 Direct implications for the product positioning

Integrating legacy material should first keep the originals and their versions, then produce located requirement/entity candidates, using deterministic parsing for known formats. Agents are suited to proposing applicability judgments, questions about missing configuration, and semantic modeling suggestions. A knowledge graph as a derived query view can help trace across artifacts; it cannot replace the source files, and it cannot turn "text imported successfully" into "requirement satisfied".

There are now two real, re-runnable entry points: a public engineering model → the official semantic export, and public legacy requirements → SysML requirement elements with their sources. The second deliberately exposes the semantic mapping that is not yet done, which is a clear input for the next agent work.
