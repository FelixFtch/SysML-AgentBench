# External data sources registry

Every external artifact used by the benchmark is listed here with source, retrieval date, SHA-256, license, and role. Update this file in the same commit that adds or changes a dataset. Nothing enters `bench/` or `scenario/` without an entry.

| Name | Source | Retrieved | SHA-256 | License | Role | Status |
|---|---|---|---|---|---|---|
| SysML-v2-Release (examples + standard library) | https://github.com/Systems-Modeling/SysML-v2-Release @ fb97b754… (2026-08) | 2026-09-22 | see `mvp/toolchain/kernel.lock.json` (`library_content_sha256`) | EPL-2.0 | toolchain library; few-shot pool (dev only) | pinned |
| SysML-v2-Pilot-Implementation 0.62.0 (jupyter kernel jar) | https://github.com/Systems-Modeling/SysML-v2-Pilot-Implementation/releases/tag/2026-08 | 2026-09-22 | see `mvp/toolchain/kernel.lock.json` | EPL-2.0 | official validator | pinned |
| NASA cFE requirements | see `mvp/public-data/catalog.json` | 2026-09-22 | in catalog | NASA open source | requirements-import pathway prototype (T5) | present |
| SysMBench 151 (Jin et al., arXiv:2508.03215) | paper says released; no licensed repository found 2026-10-03 | — | — | **not found** | not used | held out until a license file exists |
| SysMBench negative artifacts (439, with Syside diagnostics) | same repo | — | — | not declared | failure-taxonomy seed | license inquiry pending |
| PURE XML subset | https://zenodo.org/records/7118517 | 2026-10-03 | zip md5 c81235c40f88a2c947ae66e0eddad585 | Zenodo record CC BY 4.0; source-document rights uncertain | two short excerpts: EIRENE, CDN peering; side benchmark for the four candidates (`bench/run_side.py`), not in the exam score | excerpts only; full zip gitignored |
| SysEngBench `test.csv` (1,144 questions) | https://huggingface.co/datasets/rabell/SysEngBench/resolve/main/test.csv | 2026-10-06 | 194024435b0cf494bb3e782e25c78e5f2b862f91e4e1d78ca499d05ea027a93d | MIT | side benchmark: 100 question ids fixed with seed 20261006 (`analysis/sysengbench/ids-100.txt`) put to the four candidates; the answer column is read only when scoring | CSV kept locally, not committed; ids, answers and scores committed |
| DLR SysMLv2LibrarySTPA | https://github.com/DLR-FT/SysMLv2LibrarySTPA | — | — | MIT OR Apache-2.0 | vocabulary for two plain hazard requirements | library not imported; `hazards.sysml` validated |
| UMAA 6.0 ICDs | https://www.auvsi.org/advocacy/advocacy-initiatives/unmanned-maritime-autonomy-architecture/ | — | — | public release (Distro A) | interface vocabulary for scenario | to download |
| NPS MDUSV / BlueBoat SysML v2 reports | https://calhoun.nps.edu | — | — | public | scenario reference | to download |

Not in the main line (optional extensions only): rohhaiil/SysMLv2_Repair_with_SLMs (CC-BY-4.0), nomograph/sysml-v2-reasoning-benchmark (MIT), airbus/apollo-11-sysml-v2 (custom license), GfSE/SysML-v2-Models (BSD-3).
