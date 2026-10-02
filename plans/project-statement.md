# Agentic AI for Systems Engineering Discovery and Design

**Sponsor:** RTX Technology Research Center (RTRC)
**Faculty Advisor:** Prof. George Bollas
**Industry Advisors:** Francesca Stramandinoli, Kunal Srivastava, Andrew Radlbeck (RTRC)
**Student Team:** Thomas Johanns, Tianchonghui Fang, Tedi Naqo
**University of Connecticut**
**Version:** 1.0, 2026-10-02 (draft for sponsor review)

## 1. Background

Early-stage systems engineering—architecture discovery, requirements development, and concept exploration—remains largely manual, time-consuming, and expertise-intensive. As system functionality and stakeholder expectations expand, driven by autonomy, societal needs, and sustainability, the burden of requirements development and design exploration grows accordingly. Emerging technologies in agentic AI, AI-assisted model-based systems engineering (AI-MBSE), and automated reasoning—AI-based requirement generation, SysML v2 model parsers, and AI agents for structured reasoning—offer a feasible path toward decision-support tools that automate and accelerate these activities, with an initial focus on automatically generating system requirements and corresponding design concepts.

## 2. Problem Statement

Benchmarks of LLM-based SysML v2 generation have begun to appear, but they evaluate single, self-contained textbook models, stop at syntactic or tool-conformance validity, and do not assess engineering-semantic correctness, controlled modification of existing models, ambiguity handling, round-trip fidelity between requirements and models, or multi-platform mission contexts. The three sponsor-specified references demonstrate feasibility on small cases but report no reproducible performance evidence. No evidence-based evaluation exists for agent workflows under the conditions that matter for early-stage systems engineering, and without such evidence RTRC cannot judge whether, where, or how to invest in these workflows. This project closes that gap.

## 3. Objective

Design and execute a reproducible benchmark of AI agents that translate requirements into SysML v2 models, validated on public natural-language requirements datasets and on a representative maritime ISR mission context, and deliver the first evidence-based evaluation of agent feasibility, performance, limitations, and recommended next steps on engineering-semantic, modification, round-trip, and multi-platform tasks.

Specific, measurable aims:

- **A1.** Assemble a frozen benchmark of at least 24 held-out tasks (plus a development set) across five task types: requirements-to-model generation; constrained modification of existing models; structure and traceability queries; ambiguity or missing-information detection; and round-trip regeneration of human-readable requirements from models.
- **A2.** Evaluate at least two agent configurations—direct generation versus tool-diagnostic repair, structured intermediate representation, and retrieval-augmented generation—plus at least one off-the-shelf coding agent, under fixed model versions, fixed token budgets, and a fixed official SysML v2 toolchain.
- **A3.** Produce a failure taxonomy and quantitative results covering validity, requirement-property recall, structural correctness, traceability, round-trip consistency, and cost and latency, with statistical reporting that respects task-family structure.
- **A4.** Evaluate the full chain envisioned by the advisors—requirements → generated model → model validation → regenerated requirements—by measuring agreement between an LLM-based validator and deterministic toolchain checks and human adjudication. The LLM validator is an object of evaluation, not a source of ground truth.
- **A5.** Demonstrate the evaluated workflow end to end on a maritime ISR representative scenario involving multiple platforms, varied sensing modalities, and coordinated information sharing.
- **A6.** Synthesize the findings into prioritized recommended next steps for RTRC.

## 4. Scope

**In scope:** literature and tool survey; benchmark and gold-assertion design; agent pipeline implementation on the official SysML v2 pilot toolchain; controlled experiments; public-dataset validation using PURE and SysEngBench; a maritime ISR demonstration model; the final evaluation report and process knowledge base.

**Out of scope:** hardware development; deployment into RTX production systems; classified or export-controlled (EAR/ITAR) data; enterprise security hardening; full language-conformance certification of any tool.

**Scenario flexibility.** The representative scenario defaults to the maritime ISR context specified in the sponsor brief. Its concrete system boundary and use case will be confirmed with RTRC in the first sponsor meeting; the benchmark task families are scenario-agnostic so that a redirected use case can be accommodated without changing the method.

## 5. Technical Approach

The work is organized into six phases over twelve weeks.

**Phase 1 — Survey and setup (Weeks 1–2).** Study the three specified references and their artifacts; stand up the official SysML v2 toolchain and public datasets; run a thin end-to-end pipeline (requirements → model → toolchain diagnostics) on local models so that infrastructure is validated before frontier-model costs are incurred.

**Phase 2 — Benchmark design (Weeks 3–4).** Define task families, gold acceptance assertions (not reference text), anti-leakage splits, and the maritime ISR scenario thread. Freeze the held-out set and pre-register evaluation thresholds.

**Phase 3 — Agent pipelines (Weeks 5–6).** Extend the pipeline to tool-diagnostic repair, structured intermediate representation, and retrieval-augmented configurations with bounded tool-calling loops and human approval gates; connect the approved frontier model; integrate an off-the-shelf coding agent through the same tool interface.

**Phase 4 — Controlled experiments (Weeks 7–8).** Run all configurations on the frozen benchmark under fixed budgets; archive every attempt with full evidence.

**Phase 5 — Analysis and demonstration (Weeks 9–10).** Score results, classify failures, analyze trade-offs and constraints; run the maritime ISR demonstration including a requirement change, model diff, human approval, and round-trip regeneration.

**Phase 6 — Synthesis (Weeks 11–12).** Write the evaluation report, recommendations, and process knowledge base; present at the sponsor review.

**Method foundations.** The three sponsor-specified references frame the method space: LLM-assisted semantic alignment and integration in collaborative MBSE using SysML v2 (Li, Husung, Wang, ISSE 2025) informs the alignment/modification tasks and the human-review principle; integrating SysML v2 into a GRAG LLM pipeline (Bader et al., ISSE 2025) informs the retrieval-augmented configuration; and leveraging generative AI to create, modify, and query MBSE models (Longshore, Bell, Madachy, NPS 2024) informs the example-augmented, feedback-driven configurations and the create/modify/query task typology. Public validation uses PURE (nlreqdataset.isti.cnr.it) and SysEngBench (rabell/SysEngBench) as specified, supplemented by public SysML v2 corpora with compatible licenses (e.g., official SysML-v2-Release examples), each recorded with source hash and license. Contamination controls are documented in the report.

**Tooling.** Agent workflows are implemented as a stateful, checkpointed graph (LangGraph) with human approval gates and hard token budgets; the live workflow graph and every step's prompts, tool calls, and diagnostics are inspectable by advisors through its local Studio interface with tracing disabled, so no data leaves the local machine. Benchmark runs use an evaluation harness (Inspect AI) whose log viewer shows every sample, step, and score. Model validity is adjudicated by the official SysML v2 pilot implementation (pinned version). An off-the-shelf open-source coding agent (OpenCode, version-pinned) is evaluated as a baseline through the same tool interface. Development uses local models via Ollama; frontier-model access (OpenAI/Anthropic API, or RTRC-provided Copilot/Bedrock, to be confirmed) is reserved for frozen experiments under a pre-approved budget with per-run and daily caps. Cameo Systems Modeler (license available) is used for SysML v1/v2 orientation and graphical review and, where its SysML v2 support permits, as a second conformance checker for cross-checker agreement analysis. A visual low-code front end (e.g., Langflow) may be added for the final sponsor demonstration, wrapping the same tools, if desired by the advisors.

## 6. Evaluation Metrics

Evaluation is layered; no single aggregate score is reported.

- **Language validity:** first-pass toolchain pass rate; pass rate after bounded repair; diagnostic categories.
- **Requirement semantics:** requirement-property recall; unsupported or un-sourced additions; unit and condition correctness.
- **Structure:** required elements and relations; typing, direction, multiplicity; cross-file reference resolution.
- **Traceability:** correctly mapped requirements; broken links; source-locatable answers.
- **Change behavior (modification tasks):** target change achieved; unrelated elements preserved; no regressions.
- **Round-trip consistency:** semantic agreement between source and regenerated requirements, adjudicated by assertion matching and human review, not text overlap.
- **Validator agreement:** agreement of the LLM validator with toolchain checks and human adjudication; false-pass and false-fail rates.
- **Uncertainty handling:** correct refusal or clarification rate when information is insufficient.
- **Cost:** tokens, calls, wall-clock latency, human revision minutes; results reported per unit of compute.
- **Integrity:** every scored artifact reproducible from archived inputs, prompts, diagnostics, and tool versions.

All released conclusions are backed by archived runs. Text-overlap similarity is not accepted as a measure of semantic correctness.

## 7. System Capabilities Addressed

**Interoperability.** All modeling uses standard SysML v2 textual notation validated by the official pilot implementation; checker cross-agreement is measured; models and requirements are exchangeable as public artifacts.

**Reliability and dependability.** Agent outputs are adjudicated by deterministic toolchain checks and human review; run-to-run variance and failure modes are first-class study outputs.

**Safety.** Requirement-acceptance decisions remain human-owned; no acceptance is inferred from language validity alone; hazard-related requirements in the scenario use the open-source SysML v2 STPA library where applicable.

## 8. Deliverables

1. Frozen benchmark task suite with gold acceptance assertions and review records.
2. Reproducible benchmark harness and agent pipeline implementations on the official toolchain.
3. Controlled-experiment dataset with all runs and evidence archived.
4. Evidence-based evaluation report: feasibility, performance, limitations, recommended next steps.
5. Maritime ISR demonstration package: scenario, models, requirement-change, approval, and round-trip walkthrough.
6. Process and knowledge-base write-up for future systems engineering efforts.

## 9. Constraints and Administrative Requirements

The method references are the three papers in Section 5, as specified by the sponsor; the specified public datasets are PURE and SysEngBench. No export-controlled (EAR/ITAR) data will be used; no NDA or IP agreements are required; there is no citizenship requirement. All engineering values in the maritime scenario are synthetic or publicly sourced and labeled as such. Frontier-model spending is capped and reported.

## 10. Team Organization

Thomas Johanns — benchmark and evaluation lead. Tianchonghui Fang — SysML toolchain and agent pipelines lead. Tedi Naqo — scenario, data, and documentation lead. The team meets biweekly with the faculty advisor, alternating with RTRC sponsor meetings; formal checkpoints at the end of Phases 2, 4, and 6. Status is tracked in a shared repository with an auto-generated status page regenerated after each experiment.

## 11. Acceptance Criteria

The project is complete when the sponsor receives Deliverable 4 containing quantitative results for at least two agent configurations and one off-the-shelf agent over at least 24 frozen tasks, a failure taxonomy grounded in archived evidence, validator-agreement and round-trip results, the maritime ISR demonstration walkthrough, and prioritized next-step recommendations—all reproducible from the archived evidence of Deliverable 3.

Sponsor (RTRC): ______________________  Faculty Advisor: ______________________
Team: ______________________  Date: ______________________
