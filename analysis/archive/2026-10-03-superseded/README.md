# 2026-10-03 被替代的记录

这些文件是真实运行的记录，没有删，只是不再给网页和报告用。

| 文件 | 为什么移到这里 | 用什么替代 |
|---|---|---|
| `discover-20261003T074616.json` … `discover-20261003T083945.json`（6 个） | 第二部分流程重写之前的格式：没有检索图、逐次校验记录和对齐包，网页读不了 | `analysis/discover-20261003T144105.json` 起的新格式运行 |
| `mvp-case-20261003T063238/`、`mvp-case-20261003T150441/` | MOD-05 按旧判分规则记成 FAIL；旧规则把老实作答判失败、把改上限的答卷判通过 | `analysis/mvp-case-20261003T152039-MOD-05/`，按现行规则题目判定 PASS、设计判定 FAIL |
| `mvp-case-20261003T151539-MOD-05/` … `mvp-case-20261003T151629-MOD-04/`（5 个） | 读回核数用的数字提取有错，句末带句号的数（如 `60.0.`）没被识别，读回全记成没提到 | `analysis/mvp-case-20261003T152039-MOD-05/` … `152131-MOD-04/`，修正后重跑 |

判分规则的修正见 `docs/decisions/019-task-verdict-vs-design-verdict.md`，重算记录见 `analysis/rescore-20261003.jsonl`。

## Moved here on 2026-10-06

The 2026-10-03 matrix (24 tasks, 288 cells, 224 PASS under the re-scored rule) is replaced as the reported result by the frozen 27-task batches of 2026-10-06 (`bench/batches.py`, `bench/FREEZE.md`). Its score rows stay in `analysis/heldout-20261003T000045/` and `analysis/heldout-20261003T001321/`; the derived files below were built on it and moved here.

| File | What it was | Replaced by |
|---|---|---|
| `report-exam-20261003/` | The exam report on the 2026-10-03 matrix | `analysis/report/exam-20261006/` |
| `failure-classes-20261003.jsonl` | The 64 failures of that matrix by class | `analysis/failure-classes-20261006.jsonl` |
| `ablation-20261003.json`, `figures/ablation.*`, `scripts/ablation.py`, `scripts/plot_ablation.py` | P0–P3 passes and tokens of that matrix | the approach tables in `bench/board_facts.py` (STATUS.md, report section 3) |
| `pure-20261003T052120/`, `scripts/run_pure.py` | The two PURE excerpts answered once by qwen3.8-max, tokens not recorded | `analysis/side-pure-*` for all four candidates (`bench/run_side.py`) |
