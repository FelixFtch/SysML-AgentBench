# Public engineering data used by the MVP

Two small source packages are downloaded locally, version-pinned, hashed, and kept separate from application code. They serve different purposes. Neither is RTX material, an RTX-endorsed design, or a collection of accepted requirements-to-SysML gold pairs.

| Source package | Upstream version and license | Actual local use |
|---|---|---|
| `nasa-cfe/` | NASA cFE commit `7d283938c9af5bd6e439f3fc307e61b0c7799640`, a pinned `dev` snapshot; Apache-2.0 repository license | Complete original requirements CSV and DOCX retained; CSV ingested into traceable candidate requirements; eight software-bus requirements actually imported into SysML and validated |
| `sysml-official-vehicle/` | Systems-Modeling SysML-v2-Release commit `fb97b754f29588b8e9c7a35f370880cd15eb29e7`, release `2026-08`; EPL-2.0 | Original two-file VehicleDefinitions/VehicleUsages example loaded by the real official parser, linked, validated and exported |

`catalog.json` lists the packages. Each package has a `manifest.json` containing source URLs, commit, artifact type, license, retrieval time, byte size and SHA-256 for every original file. `upstream/` files are unchanged. Their upstream licenses and READMEs remain with them; the application's own license must not be used to relicense these third-party artifacts.

## NASA cFE requirements: real public engineering documents

Sources:

- [NASA cFE repository](https://github.com/nasa/cFE)
- [Pinned original requirements CSV](https://github.com/nasa/cFE/blob/7d283938c9af5bd6e439f3fc307e61b0c7799640/docs/cFE_FunctionalRequirements.csv)
- [Pinned repository license](https://github.com/nasa/cFE/blob/7d283938c9af5bd6e439f3fc307e61b0c7799640/LICENSE)

The downloaded CSV has **596 data records, comprising 414 unique identified requirements and 182 continuation records without IDs**. Those continuations contain real text; dropping them would lose parts of the requirements. `ingest_nasa_requirements.py` groups each continuation with its preceding ID and preserves every original row field, CSV record number and physical line range for review. The output is an imported candidate registry, not a newly approved requirements baseline.

There are 82 identified Software Bus requirements. The eight-record demo subset covers pipe creation, subscription/routing, pipe overflow, maximum message size, receive timeout, subscription defaults and checksum validation. This can demonstrate:

1. Import an actual source document and locate an exact requirement.
2. Retrieve related requirements and their rationale.
3. Identify unresolved `MISSION_DEFINED` or `PLATFORM_DEFINED` configuration values.
4. Propose reuse with a source citation and an explicit applicability decision.

Use `nasa-cfe/derived/demo-requirements.md` as the readable English input, `demo-bus-requirements.json` as the eight-record source-backed sample, or `requirements.jsonl` for the complete 414-record candidate registry. The JSONL is derived deterministically from source CSV structure; it is not an LLM-generated summary. The DOCX is retained as an original reference and was not treated as a byte-equivalent source for the CSV extraction.

`nasa-cfe/derived/NASA_CFE_Imported.sysml` is an actual deterministic text-to-SysML import, containing one `requirement def` and eight `requirement` usages, each with the original ID, commit, artifact hash, record locator and `TEXT_IMPORTED_SEMANTIC_MAPPING_PENDING` status. It does not fabricate executable constraints, a system design or `satisfy` relationships. Official validation returned **PASS, zero diagnostics, 273 AST elements, 3.932 seconds**. Inspection of the official export confirmed eight `RequirementUsage` and one `RequirementDefinition` elements. Evidence is under `nasa-cfe/validation/`.

Both example directories have `reference.json` with the package name and model paths relative to that directory. The MVP can whitelist `nasa-cfe` and `sysml-official-vehicle`, then rerun the actual files into a fresh evidence directory. Existing successful logs are evidence of the recorded run; they do not substitute for validating a changed file.

These are cFE software-service requirements. They do not specify the synthetic maritime gateway's camera rate, battery power, storage capacity or link speed. They have no corresponding official SysML v2 gold model in this package. They cannot establish RTX internal needs, certify a new system, or justify copying mission-defined values from one configuration to another.

## Official SysML reference project: actual language/tool interoperability

Source: [official Vehicle Example directory](https://github.com/Systems-Modeling/SysML-v2-Release/tree/fb97b754f29588b8e9c7a35f370880cd15eb29e7/sysml/src/examples/Vehicle%20Example).

The two preserved files are a coherent definitions/usages example with parts, ports, connections, quantity expressions and variant specialization. It is an illustrative official model, not the as-built design or validation record of a real vehicle. The surrounding upstream repository contains other examples; this package does not claim to contain all of them.

Actual validation was performed using the project's Java 21 / official kernel 0.62.0 adapter and the matching locked standard library:

- Status: **language PASS**.
- Official diagnostics: **0**.
- Parsed source-model AST elements: **493**.
- Measured validation/export wall time: **6.68 seconds** in this environment.
- Evidence: `sysml-official-vehicle/validation/validation.json`, actual stdout/stderr logs, official `model.json`, and EMF-derived `ast-elements.json`.

These results demonstrate that a downloaded public multi-file model, rather than only a handcrafted demo template, can be processed. They do not demonstrate physical feasibility, a requirement-to-model success rate or complete SysML specification conformance. The derived export remains associated with the upstream model's license and provenance.

## Reproduce acquisition and ingestion

From the project root:

```bash
python3 mvp/public-data/fetch_sources.py
python3 mvp/public-data/ingest_nasa_requirements.py
```

The fetcher uses fixed commit URLs and does not install or execute upstream source code. The original acquisition manifests record file hashes. Keep raw originals unchanged; generate new derived outputs under a new version when changing extraction rules.

To validate the official example again, choose an empty output directory:

```bash
python3 mvp/toolchain/validate.py --package VehicleUsages --output mvp/public-data/sysml-official-vehicle/validation-repeat "mvp/public-data/sysml-official-vehicle/upstream/sysml/src/examples/Vehicle Example/VehicleUsages.sysml" "mvp/public-data/sysml-official-vehicle/upstream/sysml/src/examples/Vehicle Example/VehicleDefinitions.sysml"
```

## Hugging Face candidate reviewed but not used as a benchmark

[rqualis/sysml_v2_instruction](https://huggingface.co/datasets/rqualis/sysml_v2_instruction) contains actual instruction/output examples and declares Apache-2.0 in its README. At pinned commit `9ae0e29051b58e84dc88cc21aeccd07af74494c0`, the inspected `data/v0.5/train.jsonl` contains 11 rows but only four unique rows; its test file contains two unique rows. The README still describes `v0.0.3` and an older split. No compiler-validation or independent engineering acceptance evidence was established in this review. It is therefore a candidate for manual example inspection, not the MVP's gold evaluation set. Its raw records are not copied into this package.

SysEngBench is a separate multiple-choice knowledge benchmark and is not a source of gold engineering models. Do not merge its scores with requirement-to-model or design-change success rates.
