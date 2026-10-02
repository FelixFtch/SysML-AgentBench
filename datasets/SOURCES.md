# External data sources registry

Every external artifact used by the benchmark is listed here with source, retrieval date, SHA-256, license, and role. Update this file in the same commit that adds or changes a dataset. Nothing enters `bench/` or `scenario/` without an entry.

| Name | Source | Retrieved | SHA-256 | License | Role | Status |
|---|---|---|---|---|---|---|
| SysML-v2-Release (examples + standard library) | https://github.com/Systems-Modeling/SysML-v2-Release @ fb97b754… (2026-08) | 2026-09-22 | see `mvp/toolchain/kernel.lock.json` (`library_content_sha256`) | EPL-2.0 | toolchain library; few-shot pool (dev only) | pinned |
| SysML-v2-Pilot-Implementation 0.62.0 (jupyter kernel jar) | https://github.com/Systems-Modeling/SysML-v2-Pilot-Implementation/releases/tag/2026-08 | 2026-09-22 | see `mvp/toolchain/kernel.lock.json` | EPL-2.0 | official validator | pinned |
| NASA cFE requirements | see `mvp/public-data/catalog.json` | 2026-09-22 | in catalog | NASA open source | requirements-import pathway prototype (T5) | present |
| SysMBench prompts (re-release) | https://github.com/cmuchancel/NL-to-SysMLv2-via-Conformance-Driven-Refinement | — | — | **not declared** | T0 calibration (15 prompts) | license inquiry pending |
| SysMBench negative artifacts (439, with Syside diagnostics) | same repo | — | — | not declared | failure-taxonomy seed | license inquiry pending |
| PURE (2–3 selected documents) | https://zenodo.org/records/7118517 | — | — | per-document | T5 requirements extraction | to select |
| SysEngBench | https://huggingface.co/datasets/rabell/SysEngBench | — | — | MIT | model SE-knowledge appendix | to download |
| DLR SysMLv2LibrarySTPA | https://github.com/DLR-FT/SysMLv2LibrarySTPA | — | — | see repo | scenario hazards | to download |
| UMAA 6.0 ICDs | https://www.auvsi.org/advocacy/advocacy-initiatives/unmanned-maritime-autonomy-architecture/ | — | — | public release (Distro A) | interface vocabulary for scenario | to download |
| NPS MDUSV / BlueBoat SysML v2 reports | https://calhoun.nps.edu | — | — | public | scenario reference | to download |

Not in the main line (optional extensions only): rohhaiil/SysMLv2_Repair_with_SLMs (CC-BY-4.0), nomograph/sysml-v2-reasoning-benchmark (MIT), airbus/apollo-11-sysml-v2 (custom license), GfSE/SysML-v2-Models (BSD-3).
