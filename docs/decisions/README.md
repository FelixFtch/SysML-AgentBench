# Decision records

One short file per significant decision: `NNN-slug.md` with date, options considered, decision, reason, and what would reverse it.

The first nine decisions (2026-10-02) are recorded in the execution plan, section 16: `plans/SysML_AgentBench_完整执行计划.md`. New decisions go here as separate files and are also summarized in that table.

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
