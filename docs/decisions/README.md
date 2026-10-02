# Decision records

One short file per significant decision: `NNN-slug.md` with date, options considered, decision, reason, and what would reverse it.

Decisions 001–015 (2026-10-02) are recorded in the execution plan v2.0, section 18: `plans/SysML_AgentBench_完整执行计划.md`. New decisions go here as separate files and are also summarized in that table.

| # | Decision |
|---|---|
| 001 | Project centre moves from "upgrade workbench product" to "agent benchmark" |
| 002 | Keep official toolchain, engine checks, evidence packs; drop Workbench-as-product |
| 003 | Langflow not a system component (optional demo shell only) |
| 004 | Agent layer: LangGraph (fallback plain Python); not Pydantic AI |
| 005 | Off-the-shelf agent baseline: OpenCode primary, Claude Code optional |
| 006 | External benchmarks are calibration/seed only, not the main line |
| 007 | Evaluation framework: Inspect AI |
| 008 | Not using AutoGen / CrewAI / Swarm / AutoGPT |
| 009 | Project statement wording corrected: evaluations exist; ours is "first" only for the stated intersection |
| 010 | Repository root moved to `/data/robotics/RTRC`; original folder kept as read-only archive; `vendor/` symlinked |
| 011 | Primary model: existing Qwen cloud API (qwen3.8-flash dev / qwen3.8-max experiments); local Ollama optional |
| 012 | Model visualization: Cameo SysML v2 Community Edition (free) primary, SysON fallback; second checker: Syside CLI (trial/academic) primary, Cameo fallback; official Pilot remains the adjudicator |
| 013 | Conditional configuration P-VENDOR: CATIA Magic 2026x built-in AI Assistant as a black-box agent, if the license permits |
| 014 | No RSI; the LLM validator is an object of evaluation, never an adjudicator |
| 015 | Superseded plans (2026-09-22 ×2, v1.0) archived under `research/archive/plans-2026-09/`; plan v2.0 is the single authority |
