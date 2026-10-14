# Jev 复现竞技场 — PURE 分类协议试点报告

时间：2026-10-10 ｜ 机器：RTX 4090 24GB（空闲显存 ~15.9GB，另有桌面/UnrealEditor 占用）｜ 产物：`analysis/jev-arena-pilot-20261010-105531/`（逐句预测 jsonl + metrics.json + 运行日志）

## 1. 候选仓库确认（真/伪/装不上）

| 候选 | 确认仓库 | 真伪 | 结果 |
|---|---|---|---|
| NanoJev | github.com/TianyuCodings/NanoJev（2524★, MIT, 2026-09） | 真 | 已装已跑。Qwen3-0.6B+决策头，但训练目标是游戏（Maze/Snake/ViZDoom），文本判定是 OOD |
| MoJev | github.com/MoLeMo-Lab/mojev（29★, MIT） | 真 | **后补批次已跑通**：初次因权重 gated（403）跳过；用户在 HF 批准权限后重测成功（见 §3a 与 §6） |
| Kev | github.com/jaredpalmer/kev（Apache-2.0） | 真 | 已装已跑 0.8B。9B 无量化支持（仅 fp32/bf16），bf16 权重 ~18GB > 空闲显存，且可用内存仅 ~8GB，**9B 放不下** |
| Laya | github.com/NandhaKishorM/laya（Apache-2.0, ~840★） | 真 | 已装已跑（PyPI `laya`，ModernBERT-large 421M） |
| Von | github.com/wfzyx/von（877★, Apache-2.0） | 真 | 已装已跑。PyPI `von-sdk` 本镜像索引缺失，源码安装且要求 Python≥3.12 |
| system-one-open | github.com/mithalouni/system-one-open（38★） | 真（但无本地权重） | 权重"HF upload pending"，仅 Modal 托管演示；以作者公开端点参与（免本地安装） |
| 官方 Jev | api.typesafe.ai（.env 的 TYPESAFE_API_KEY） | — | 已探通并参与 |

无"查表/规则伪装"：所有本地考生均真实加载权重（kev=LoRA 适配器+Qwen3.5-0.8B-Base；laya=ModernBERT ckpt；von=option_marker.pt；nanojev=best.safetensors GPU 前向）。system-one-open 例外：托管端点，无法本地验证权重，已标注。

## 2. 试点协议

- 数据：`datasets/pure/requirements-xml.zip` 解出 18 篇真实 XML（另有 18 个 __MACOSX 副本）。**仅 6 篇带 `<req>` 标注**（peering/keepass/gamma-j/cctns/ertms/eirene_fun_7-2），其余 12 篇无任何正例标注，当负类会污染 gold → 试点 = 全部 6 篇标注文档（任务要求的 20 篇不可行，如实记录），共 **4217 句，正例 2167（51.4%）**。gold 规则：句子位于 `<req>` 子树内=1（含 req 内 itemize 片段），否则 0。
- 判定：每考生按 TypeSafe System One 原生协议，一次请求带 12–48 个 noul 问题（问题共享文档片段 state，一次前向批量打分），阈值 0.5。
- 官方 API 调用预算：**19 次**（1 次探针 + 18 次评测，每文档均匀抽 120 句，共 720 句）≤50。
- gold 与判分隔离：考生只见 `pilot_texts.jsonl`（无标签），gold 仅在 `common/score.py` 判分阶段读入。

## 3. 结果（句级 P/R/F1，阈值 0.5）

| 排名 | 考生 | n | F1 | P | R | 每句延迟 | 峰值资源 | 安装难度 |
|---|---|---|---|---|---|---|---|---|
| 1 | **kev-0.8b**（本地 GPU） | 4217 | **0.711** | 0.597 | 0.878 | 7.6ms | 显存 7.7GB（闲 4.4GB） | 中（需 uv+py3.12；PyPI 有同名包坑） |
| 2 | nanojev（本地 GPU） | 4217 | 0.679 | 0.514 | **1.000** | 8.2ms | 显存闲 4.6GB/峰 12.3GB | 中高（游戏型服务、state 必须带 id、单线程、大 chunk 会崩） |
| 3 | laya（CPU） | 4217 | 0.676 | 0.513 | 0.991 | 29.5ms | 内存 4.3GB | 低（pip 即装） |
| 4 | **MoJev（后补批次）**（本地 GPU） | 4217 | 0.640 | 0.587 | 0.702 | 4.2ms | 显存 2.8GB | 中（gated 权重+内核坑，见 §6） |
| 5 | 官方 Jev API（jev-1.13.0） | 720 | 0.629 | 0.616 | 0.643 | 6.8ms | 托管 | — |
| 6 | system-one-open（托管 e2b-full） | 4217 | 0.610 | 0.628 | 0.592 | 59.5ms | 托管（Modal） | 零本地 |
| 7 | von（395M） | 4217 | 0.456 | 0.518 | 0.407 | 41ms | 显存 3.7GB(auto-cuda)/内存 3.0GB | 中（源码装，py≥3.12） |

### 3a. MoJev 后补批次说明（2026-10-10 补测）

用户在 HF 批准 gated 权限后，用本机原有 token 成功下载（43 文件）。运行需两处排障：①transformers 提示须装 `flash-linear-attention`（0.85B 底座 Qwen3.5-0.8B 为线性注意力混合结构；CPU 模式 fla triton 内核直接报错，必须 GPU）；②装后仍报 `invalid dtype for bias`——上游 `build_mask` 返回 float32 加性树掩码，torch 2.14 CUDA SDPA 拒绝与 bf16 query 混用。以独立启动脚本 `mojev/run_serve_patched.py` 在自己的代码里 monkeypatch 将掩码 cast 为 encoder dtype（加性 0/-inf 掩码，数值等价），**未改动仓库任何文件**。结果：F1=0.6396@0.5（非退化解，P/R 均衡），最优 0.6849@0.4，子样本 0.5533；108 次调用 17.8s 全场最快（4.2ms/句），峰值显存 2.8GB 全场最低，零解析失败。**不改变"kev-0.8b 首选"结论**（kev 0.711 仍领先 7 个点），但 MoJev 是非退化考生中速度最快、显存最省的，若域内校准到 0.4 阈值可作高吞吐备选。

- 官方子样本（720 句）同口径对比：kev 0.660 > system-one-open 0.645 > 官方 0.629 > nanojev/laya 0.584 > MoJev 0.553 > von 0.485。
- 最优阈值 F1（参考）：kev 0.711@0.5（原生阈值即最优）、von 0.693@0.4、MoJev 0.685@0.4、laya 0.679@0.25、nanojev 0.679@0.05、s1open 0.677@0.05、官方 0.666@0.05。
- nanojev 与 laya 在 0.5 阈值近似"全判 yes"（R≈1、P≈基率），是退化解而非能力证明；von 原生概率在本域严重失准，调阈值后大幅回升。

## 4. 结论与建议

- **接入分类协议全量跑：首选 kev-0.8b**。唯一在原生阈值下 F1 最高且阈值即最优、零解析失败、GPU 常驻 4.4GB、`/v1/systemone` 与官方 SDK 兼容，可平移替换 base_url。MoJev 为次选：非退化、最快（4.2ms/句）、显存最低（2.8GB），但需域内重校准阈值（0.4）且安装排障成本高。
- 官方 Jev 未领先（子样本口径低于 kev-0.8b 与 s1open），且按量计费；建议仅作金标准抽检。
- laya 适合无 GPU 场景但需先在域内微调 + 重校准阈值；nanojev 不适合文本判定（游戏专精）；von 需域内 `von calibrate` 后才可用；system-one-open 依赖他人托管，不可控。
- 已知问题：①PURE 仅 6 篇可标注文档，试点规模受限；②正类含 req 内 item 片段（"By user;"等），对所有人都是噪声；③jev-api 指标基于 720 句子样本，与全量口径有偏差；④官方 18+1 次调用均值 0.27s/次（40 问/次），成本极低。

## 5. 复现

`tools/jev-arena/common/`：`build_pilot.py`（解析+抽样）、`systemone_client.py`（协议）、`run_http_judge.py`（官方/kev/mojev 线协议）、`run_laya.py`、`run_von.py`、`run_nanojev.py`、`run_s1open.py`、`score.py`（gold 只在此读）。各项目独立 venv 于 `tools/jev-arena/<name>/venv`，权重在 `tools/jev-arena/models/`（~6.9GB）。
