# Engineering Change Workbench

> **Role since 2026-10-02 (plan v2.0, decision 002):** this directory is no longer the project's product. Its pinned official SysML v2 toolchain, independent engineering checks, evidence packs, and viewer are retained as the **scorer and single-run inspector** of the SysML-AgentBench evaluation described in `../plans/execution-plan-v2.md`. The "next integration step" paragraph at the end of this file reflects the earlier direction and is superseded. The 2026-10-02 first real LLM run through `agent.py` is recorded under `agent-runs/20261002T204611-agent-d0a63097/`.

A local, working SysML v2 engineering slice for evaluating legacy-system reuse and controlled design changes. The application, model descriptions, fixtures and demonstration are in English.

## Start the workbench

From the repository workspace:

```bash
python3 -m mvp.app
```

Open **http://127.0.0.1:8765**. The project-local Java 21 runtime and official SysML distribution are already installed in this workspace. Python uses only the standard library for the application and direct validator path.

On another **Linux x64** machine, recreate the pinned checkouts and runtime first:

```bash
python3 -m mvp.bootstrap --all-references
python3 -m mvp.app
```

The bootstrap makes complete Git clones, checks out recorded commits and verifies download hashes. It does not install Java globally. The official **2026-08 / 0.62.0** implementation and model library are pinned separately in `toolchain/` and `reference-projects.json`. This implementation contains development material beyond formal SysML 2.0; the tested subset is not a general language-conformance certification.

## What is actually executed

1. Read configuration rows from `fixtures/legacy.sqlite` using a read-only SQLite connection.
2. Apply explicit rate/link overrides and the operator's preview-replacement decision.
3. Write a complete SysML package, including both supplier imports and immutable source copies.
4. Start the official implementation on Java 21. Load the real files and library into its Xtext/EMF resource set; collect actual linking, syntax and semantic diagnostics.
5. Export the official semantic model as API delta JSON and source-located AST records.
6. Read numeric literals and relationships from that export. Calculate storage, bandwidth and power independently; verify the active upload policy, scoped connection endpoints and the exact supported unit-conversion expressions.
7. Save the source hashes, model revision, toolchain hashes, diagnostics, results, model differences and explicit requirement decision in a new run directory.
8. Reopen a stored run or export its complete evidence ZIP.

The interface and calculator do not maintain an independent hard-coded graph. A model that fails language validation cannot receive budget results from configuration values instead.

Three active budget requirements are represented in the marine model: storage, power and the selected upload policy. The source package contains additional requirements that are not all formally modeled or verified in this first slice.

## Five-minute demonstration

Use the two input fields to override the legacy record. Empty fields use the selected database row. **Preview approval is off by default.**

| Action | Expected evidence |
| --- | --- |
| Run `baseline` | Actual SysML PASS. Raw storage: 21.6 / 51.2 GB. Uplink: 7.2 / 8 Mbit/s. Power: 44 / 60 W. |
| Run `upgraded_legacy` | The higher rate makes the existing storage and full-upload path fail. |
| Select `candidate_a`, explicitly approve P2 | Actual SysML PASS; storage 64.8 / 102.4 GB, uplink 2.4 / 8 Mbit/s, power 54 / 60 W. The model includes a preview-processing path and keeps raw recording. |
| Select `candidate_b`, approve P2 | Language-valid model, but 68 W exceeds the 60 W engineering budget. |
| Run A with **30 Mbit/s** | Recomputed storage is 108 GB, exceeding 102.4 GB. This is a new parameterized run, not a prerecorded green state. |
| Run A without preview approval | The original full-upload requirement remains active: 21.6 Mbit/s exceeds 8 Mbit/s. |
| Run `degraded_link`, approve P2 | The 2.4 Mbit/s profile exceeds the new 1.5 Mbit/s link. The tool does not silently lower the requirement. |
| Select a prior run and download its ZIP | Inspect the real model, both supplier files, source mapping, original SQLite snapshot and validation output. |

**Overall acceptance remains UNKNOWN when only the modeled checks pass.** Preview quality, latency, hardware conditions and long-duration behavior have not been tested. The fixed values are labeled synthetic; they are not RTX product specifications or measured hardware performance.

The rendered model view uses actual parsed named elements, owners and connection references. The full official JSON and source-located AST are available in each run. Semantic differences cover named elements and supported fields; a full textual difference is also retained.

## Public engineering sources

The workbench also runs two independently sourced reference imports:

- **Official SysML vehicle example:** actual model files from the pinned Systems Modeling release, including their dependency, validated with the same implementation.
- **NASA cFE requirements:** original public cFE requirements records with source commit, license and file hashes; eight selected software-bus requirements are deterministically imported as real SysML requirement definitions/usages. Their text and source IDs are preserved. Formal constraints and satisfaction are not invented.

Use the public-project buttons to create fresh validation runs. These examples demonstrate real public model loading and legacy requirements ingestion. They do not turn NASA requirements into RTX requirements, and they do not substitute text import for semantic engineering review. Dataset selection, downloads, provenance and limitations are documented in [public-data/README.md](public-data/README.md).

## Agent connection

The natural-language entry point uses a real, bounded tool-calling loop when an approved provider is configured. It can read the legacy database, read the fixture requirements/ICDs/reuse records, choose a candidate and execute the real design tool. It must read the database and requirements before running a design. It cannot approve a requirement replacement on the operator's behalf.

Configure these environment variables before starting the server:

```bash
export MVP_LLM_URL='https://your-approved-service.example/v1/chat/completions'
export MVP_LLM_MODEL='your-approved-tool-calling-model'
# Supply MVP_LLM_API_KEY locally through your normal secret-management method.
```

The endpoint is the complete chat-completions URL. For a compatible Azure deployment, use its deployment URL and `MVP_LLM_AUTH_HEADER=api-key`. A local compatible service can use a loopback HTTP endpoint. No credential has been configured by this project.

Example request after configuring a provider:

> Read the legacy records and requirements. Evaluate candidate A at 30 Mbit/s, compare it with candidate B, and explain every failed constraint with its source and run ID. Preserve the current requirements decision.

Without a configured provider, the app explicitly reports **Agent not connected**. The structured engineering workflow still runs. No successful LLM session is claimed. The current agent supports bounded candidate/parameter changes; arbitrary document-to-architecture synthesis is not implemented.

The reference graph-retrieval and memory repositories are complete clones, but are not production dependencies. `Graphiti`, `ACE`, `CMBSE`, the GRAG paper implementation and the official API repositories remain inspectable references. The official API server has not been deployed. Clone and execution status are recorded in [reference-projects.json](reference-projects.json).

## Reproduce and challenge the result

```bash
python3 -m mvp.engine baseline
python3 -m mvp.engine candidate_a --approve-preview
python3 -m mvp.engine candidate_a --data-rate 30 --approve-preview
python3 -m mvp.verify_negative_cases
python3 -m unittest discover -s mvp/tests -v
```

Revalidate an original or extracted run directory containing `result.json`:

```bash
python3 -m mvp.reopen /absolute/path/to/run-directory
```

Reopening verifies the complete evidence inventory, the model/source package, and the requirement-decision binding. It runs the real validator again and compares toolchain/code fingerprints, check ID sets and results. The inventory provides integrity checking, not a cryptographic signature or enterprise approval. New evidence is written under that run's `revalidation/` directory; earlier evidence is retained.

The adversarial suite tests a valid control and six failures: a missing supplier input, a deleted recording connection, a wrong power unit, a wrong conversion factor, unauthorized upload reduction and a miswired connection with an unchanged name. The official implementation does not detect every dimensional or engineering error. The project preserves its actual language verdict and independently rejects violations of the declared domain contracts.

## Files and provenance

```text
mvp/
  app/                      English workbench and loopback HTTP service
  fixtures/                 Synthetic legacy SQLite, requirements and supplier sources
  models/                   SysML rendering adapter and complete example packages
  public-data/              Licensed public source snapshots and imports
  toolchain/                Official JVM bridge, pinned runtime and source hashes
  runs/<run-id>/
    model/                  Complete model, supplier dependencies and mapped source pack
    sources/                Run-specific immutable source copies
    sysml/                  Actual diagnostics, official model export and AST
    source-manifest.json    Source file hashes
    model-manifest.json     Model file hashes
    evidence-manifest.json  Complete integrity inventory, including decisions/mappings
    checks.json             Independent check results
    decision.json           Explicit local requirement-replacement decision
    diff.json               Named-element and textual difference
    result.json             Complete run record
  agent-runs/               Provider/tool transcripts when a provider is connected
  verification/             Adversarial integration evidence
vendor/                     Full Git clones, excluded from the parent repository
```

This is a local engineering MVP, not an enterprise release system. The local preview checkbox is not enterprise authentication, and the workflow does not write into an RTX production system. The next integration step is to replace the synthetic source adapter with one approved historical RTX change package and connect the approved model endpoint. Keep the same model, source, tool and evidence contracts.
