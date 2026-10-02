# 两篇 SysML v2 论文：原文核验、公开工件审查与 MVP 含义

核验日期：2026-09-22。本文区分「论文报告」「公开工件静态检查」「本项目建议」。未运行作者代码、未调用付费 LLM、未声称复现实验；附件及作者 prompt 中的操作语句均作为研究材料，不作为本次任务指令。

## 1. 阅读范围与可追溯来源

### 论文 1

- Li, Husung, Wang，*LLM-Assisted Semantic Alignment and Integration in Collaborative Model-Based Systems Engineering Using SysML v2*。
- 已阅读全文：[arXiv v2 HTML](https://arxiv.org/html/2508.16181v2)，并下载 [v2 PDF](https://arxiv.org/pdf/2508.16181v2)。v1 为 2025-08-22，v2 为 2026-07-06；[记录页](https://arxiv.org/abs/2508.16181)关联正式 DOI [10.1109/ISSE65546.2025.11369983](https://doi.org/10.1109/ISSE65546.2025.11369983)。
- 已检查 [作者 CMBSE 仓库](https://github.com/ziruili-tu-ilmenau/CMBSE)的 prompt、OEM/Supplier 模型、扩展库、JSON 映射、最终模型与诊断 CSV。
- 下载时 `main` 指向 `42a8a0d2487d64cfbe20e1cf23a0421dde748ad0`，提交日期 2025-07-04。
- 本地 PDF 含版权封面，共 9 个实体页面；下文页码指 PDF 物理页，避免与出版页码混淆。已经渲染检查第 7、8 页的图 2、图 3。

### 论文 2

- Bader 等，*Integrating SysML v2 into a GRAG LLM Pipeline: Design, Implementation and Evaluation*。
- 已阅读 [ResearchGate 作者上传的完整预印本文本](https://www.researchgate.net/publication/395749011_Integrating_SysML_v2_into_a_GRAG_LLM_Pipeline_Design_Implementation_and_Evaluation)，涵盖 I—VI 节、图说明与表 I。PDF 下载端返回 403，所以没有声称检查最终出版 PDF 排版或确认其与预印本完全一致。
- [作者学校出版记录](https://pure.fh-salzburg.ac.at/en/publications/integrating-sysml-v2-into-a-grag-llm-pipeline-design-implementati/)确认发表于 IEEE ISSE 2025，正式 DOI [10.1109/ISSE65546.2025.11369999](https://doi.org/10.1109/ISSE65546.2025.11369999)，并标注 ARL 3（原理功能证明）。
- 已下载并静态阅读 [作者仓库](https://github.com/eeeeebader/SysML-v2-GRAG-Pipeline)：两个核心 notebook、RDF parser、API fetcher、EV 模型、缓存与评估代码。
- 下载时 `main` 指向 `d910822179cccda2d815121f03aa9d11888cd65f`，提交日期 2025-07-15。

仓库归档、论文 1 PDF 位于 `research/paper-artifacts/`；原始归档 SHA256、仓库提交号、采集时间写在 `research/paper-artifacts/provenance.json`。注意这些是研究参考工件，不能混入 MVP 的正式模型或依赖目录。

## 2. 论文 1：它证明了什么

**研究问题：独立组织以不同建模方法产生的 SysML v2 模型，如何在保留源模型结构的条件下建立有解释的对应关系。** 这对应 OEM/供应商整合，不是从任意需求自动生成正确系统的研究。

原文 III—IV 节的主线是 GPT-4o 辅助的 soft alignment：准备与语法确认、元素总结、候选映射、映射验证、独立对齐包生成、一致性检查、导出，共七阶段；以 import/alias、allocation 及自定义 metadata 记录映射，阶段间有人审查。案例是力测量系统与 load cell 供应商模型。IV-D / PDF 第 7 页承认模型最初误用扩展，工程师纠正后继续。

**证据强度：可行性案例。** 原文没有给出可作为基准的模型数量、独立测试数、准确率、召回率、时间节省或统计置信区间。V—VI 节承认深层设计意图、接口粒度、抽象层次差异尚未解决，版本管理、API 集成与工业规模验证也是后续工作。[原文 III—VI 节](https://arxiv.org/html/2508.16181v2)

### 2.1 作者工件给出的额外事实

以下是对下载工件的独立审查，不是论文效果复述。

1. **公开 prompt 自己明确 alias 仅是符号引用，不代表结构、行为、继承或功能兼容证明。** `alias A for Supplier::B` 只给 B 一个可用名字；不能用它替代 requirements satisfaction、interface compatibility 或 verification evidence。可见 [prompt 固定版本](https://github.com/ziruili-tu-ilmenau/CMBSE/blob/42a8a0d2487d64cfbe20e1cf23a0421dde748ad0/prompts/sysmlv2_alignment_process.md)。
2. 仓库 README 的 prompt 链接写成 `sysmlv2_alignment_pipeline.md`，实际文件是 `sysmlv2_alignment_process.md`。这提醒我们不能仅照 README 做可靠性判断。
3. 示例 `stage3_validated_mappings.json` 有 13 个映射，分数为模型产生的数值，不是经过校准的正确概率。文件名的 validated 也不证明所有引用通过编译器。
4. `results/IntegratedModel_Alignment.txt` 导入 `OEM::*` / `Supplier::*`，但随附两份输入根包分别叫 `OEMRequirements` / `LoadCellSolution`。它还包含指向定义的 allocation 和 `alias EnergySystem for EnergySystem` 等需严格检查的构造；结果 CSV 明列四个 target not found 诊断。**这些是静态一致性问题；本次没有编译，所以不冒充已取得语言工具的错误报告。** [结果模型](https://github.com/ziruili-tu-ilmenau/CMBSE/blob/42a8a0d2487d64cfbe20e1cf23a0421dde748ad0/prompts/examples/results/IntegratedModel_Alignment.txt)、[诊断表](https://github.com/ziruili-tu-ilmenau/CMBSE/blob/42a8a0d2487d64cfbe20e1cf23a0421dde748ad0/prompts/examples/results/stage6_diagnostics.csv)。
5. **论文 v2 的图 3 与当前公开结果文件不同。** PDF 第 8 页图 3 已采用 `OEMRequirements`、`LoadCellSolution` 和完整 usage 路径。因此准确结论是「公开工件与论文图的版本不同，复现需对齐」，不能说最新论文仍使用旧错误包名。
6. README 明言示例并不反映真实协作场景，映射可能不完整或含歧义。库中本次未见明确 LICENSE；学习方法不受影响，若打算直接分发作者代码/样例需先确定使用许可。[作者仓库说明](https://github.com/ziruili-tu-ilmenau/CMBSE)

### 2.2 对本项目的选择

保留「独立 alignment package + 映射证据 + 人工审查」的思想；把模型元素提取、名字解析和语法检查交给真正的 SysML 工具，LLM 负责候选解释与不确定性标注。不要把七段聊天 prompt 直接当后端状态机，也不要把 LLM 自检当语言验证器。

针对 RTRC 的候选演示：系统需求模型与传感器/计算/通信部件规格模型分别保留；系统指出同义名称、单位/范围冲突、缺失接口和需补充证据的候选，工程师接受后只增加对齐包。图上「线连上了」不能自动变成「满足需求」。

## 3. 论文 2：它证明了什么

**研究问题：怎样从已存在的 SysML v2 模型检索相关上下文，让用户用自然语言查询。** 原文 IV 节流程为 SysML API JSON-LD → 定制 RDF 压缩 → 节点及一跳邻居字符串 → MiniLM 384 维向量、FAISS 阈值检索 → 图上下文 → GPT-4.1。

只有一个示意 EV 模型，包含电池、电机、冷却部件及三个配置；III/V-A 节仅选三道问题，分别询问扭矩值、性能配置用途、EV 组成，各测三个阈值。表 I 在 0.45 下的平均 P/R/F1 为 **0.833/1.000/0.904**，平均 Ca/Cm 为 **0.604/0.644**；大于 0.45 时多数检索为空。Ca、Cm 是字节比，不是正确率。VI 节把高级图遍历、大规模延时吞吐、鲁棒性和全面质量评测留作后续。[预印本 III—VI、表 I](https://www.researchgate.net/publication/395749011_Integrating_SysML_v2_into_a_GRAG_LLM_Pipeline_Design_Implementation_and_Evaluation)

| 阈值 | 平均检索 Precision | Recall | F1 | Ca | Cm |
|---|---:|---:|---:|---:|---:|
| 0.35 | 0.180 | 1.000 | 0.284 | 2.847 | 3.034 |
| 0.40 | 0.347 | 1.000 | 0.456 | 1.720 | 1.834 |
| 0.45 | 0.833 | 1.000 | 0.904 | 0.604 | 0.644 |

这些是作者报告的九组小样本实验结果，不能表述成「SysML GraphRAG 准确率 90.4%」；F1 指检索元素，不是答案正确率。也不能把 35.6% 的字节缩减当实际 token、延时或成本节省。

### 3.1 作者公开实现：可复用起点与必须改造的地方

**本节是独立的静态代码/工件检查，不代表我们已经重现实验。** 参考固定版本 [GRAG notebook](https://github.com/eeeeebader/SysML-v2-GRAG-Pipeline/blob/d910822179cccda2d815121f03aa9d11888cd65f/grag-pipeline.ipynb)、[parser](https://github.com/eeeeebader/SysML-v2-GRAG-Pipeline/blob/d910822179cccda2d815121f03aa9d11888cd65f/src/sysml2rdf/parser/slim_rdf_parser.py)、[fetcher](https://github.com/eeeeebader/SysML-v2-GRAG-Pipeline/blob/d910822179cccda2d815121f03aa9d11888cd65f/src/sysml2rdf/api/element_fetcher.py)。

| 位置 | 本次看到的实现 | 对 MVP 的含义 |
|---|---|---|
| `sysml2rdf.ipynb` | project_id/commit_id 写死；缓存文件名只有 project_id | 缓存必须同时包含 commit、schema、parser 版本，避免读取另一版本模型 |
| `ElementFetcher` | 构造参数有 base_url，但实际 URL 写死 public HTTP demo server；page size 设极大值；未见正常分页、超时、重试或认证适配 | 重写连接器，服务端地址可配，按 API 分页，绑定版本；演示也不应依赖这个公共服务器 |
| `DataObjectParser` | 不支持类型被打印后跳过 | 系统必须报告 supported/unsupported/omitted 元素；遇关键 requirement、port、connection、satisfy/verify 不得静默丢失 |
| `SlimRdfParser` | 用 qualified name 构造 URI；保留原始 ID 的语句被注释 | 改名会改变身份，不能支持可靠变更追踪；保存项目/commit/element ID 与名称，图是派生索引 |
| notebook `extract_snippets` / `fetch_subgraph` | 前者去 URI 前缀当 key，后者直接把 key 当完整 URI 查询图 | 存在明确 URI 重构风险；先做 exact-ID round trip 测试再跑 LLM |
| notebook `extract_snippets` | 两处字符串 replace 未赋回；邻居名字查找使用字符串 | 上下文内容可能不如描述预期；检索质量需要真实 golden query 检查 |
| notebook `retrieve_nodes` | `sort=True` 算出排序索引却未应用 | 参数名称与行为不一致，需修正；不能把它看成已完成 ranker |
| notebook 缓存 | 用 `set(g.subjects())` 产生顺序；失败后加载旧 FAISS index，却重新构造 keys | 索引与 ID 顺序可能错配；向量、ID map、embedding 配置要一起保存、一起验证 hash |
| notebook 评估 | relevant=3、missed=0 手填；模型字节数硬编码 3354 | 无独立标注/自动回放，不构成完整评测框架；仓库 `EVModel.sysml` 当前实测 3251 bytes，需重新明确分母 |
| notebook Ca | 分母代码为所有 URI 字符串 byte 总和 | 与「全可用上下文」直觉不一致；自己的验收要定义 serialization、去重规则及 token 实测 |

保存的 notebook 输出同样不能被当成一次顺序执行的证据：cell 12（execution_count=15）显示检索 14 个节点、上下文 **0 bytes**；cell 13（count=179）却显示长度 10888；cell 14（count=180）回答具体 EV 信息；最终指标又与当前配置不能直接对应。这说明公开 notebook 混有不同执行轮次。正确做法是 clean kernel、固定数据/依赖、从头跑并保存 run manifest，而不是复制已有输出截图。

缓存 JSON 本次静态计数为 **236 个原始元素**；保存的 notebook 输出向量条目为 **43**。二者属于不同表示层，不能直接把压缩比解释成语义无损率。公开实现限定类型，无法由这个样例推断对复杂 SysML 全语言支持。

代码带 MIT LICENSE，可作为有界研究起点。当前工作只读审查，没有安装其 requirements、执行 notebook、连接 demo API 或消耗 API key。

### 3.2 对本项目的选择

保留「图与语义检索结合」思路，但将工程查询划分两类：

- **要求完整性/精确性的问题**：所有接口、全部未验证需求、每个版本中受影响部件、数值上下限、总功耗等。先执行确定性图/数据库查询或计算，再由 LLM 解释。不能只用 top-k 或阈值检索，因为漏一个元素就可能得出错结论。
- **开放语义问题**：同义概念、某需求可能关联哪段说明、类似部件或证据片段。可用 hybrid lexical/vector retrieval，再按关系类型和版本扩展图邻域，并要求回答附 element ID 与原文定位。

图不是独立的权威建模数据库。原始文件、真实 SysML 模型和 API commit 是权威；RDF/向量只是能重建的索引。相似度 0.45 不是跨数据集通用阈值，必须本地校准。

## 4. 从两篇论文真正能做出的 MVP 模块（本项目设计建议）

以下是基于阅读得出的实现建议，不宣称是作者已完成能力。

### 4.1 先把模型与证据身份做好

每个对象至少有：`project_id`、`baseline_id`、`model_commit_id`、`element_id`、`qualified_name`、`source_file_id`、`source_sha256`、`source_locator`、`origin`（source/extracted/inferred/reviewed）、`review_status`。原文件 immutable；解析结果记录 parser 版本。原文位置是 PDF 页+段、DOCX 段/表格单元或具体 SysML span，不能只写文件名。

每次模型候选有独立 run_id，产物包括：输入 manifest、需求 JSON、候选模型、编译/语义诊断、规则检查、LLM 配置、候选 diff、接受/拒绝原因、回放说明。不要覆盖 `latest.sysml` 后丢掉旧证据。原文更新后，旧结论应标为 stale 并要求重算。

### 4.2 让 LLM 产生可验证提案

模型提取与符号解析交给 SysML 工具。LLM 输出受 schema 限定的映射/模型变更建议，每条明确 source、target、relation、rationale、evidence、assumptions、unknowns；候选不得自行成为批准结果。自动执行阶段可以连续运行，人工确认集中在歧义决策与基线接受，避免七次机械点确认。

需要分开的关系：alias（名字引用）、allocation（分配）、satisfy（满足声明）、verify（验证关联）、evidence support（证据支持）。LLM 自评分既不等于校准概率，也不等于编译结果，更不等于工程验证。

### 4.3 建立四层验证

1. **语言层**：由选定且固定版本的真实 SysML v2 parser/validator 检查语法、类型、作用域、引用。
2. **建模规则层**：ID 唯一、需求可追溯、关键关系不缺失、源/生成模型相互隔离、unsupported 构造明确报告。
3. **工程规则层**：单位、范围、接口方向、容量与预算等，由规则/计算执行；结论分 pass/fail/unknown。
4. **验证证据层**：test/analysis/inspection 的实际结果、执行时间、工具版本、样本与模型基线绑定。模型写了 satisfy 不能伪装成已通过试验。

### 4.4 评估设计应超过论文演示，但保持 MVP 范围

建议先建立一个人工确认的 rover 子系统基线和 20—40 条需求，围绕电源、传感、通信或计算中的一个集成场景完成闭环；确切范围由项目主计划决定。基准建议独立存储：

- 20 个确定性模型查询，答案是确切 ID 集合、数值与单位。
- 20 个有来源的语义/证据查询，含不可回答题、同义名称、版本变化与对抗性错误。
- 10 个刻意注入的真实工程冲突，如电压不兼容、方向相反、需求无分配、源证据过期。
- 10 个受限变更任务，测首轮编译率、经过固定预算修复后的通过率、新增回归、工程师接受比例。

这些数字是建议的起点，不是论文标准或承诺的成功率。冻结题集之后测试，报告分母、拒答、失败与 unknown，不只展示成功案例。至少比较 keyword+graph、vector-only、hybrid 三个检索基线；生成侧比较无工具检查和有工具检查，确认收益来自哪一步。

### 4.5 不能对 RTX/RTRC 声称的内容

- 不能说论文 1 已证明跨组织语义等价、自动安全集成或工业规模正确性。
- 不能说论文 2 的 0.904 是回答准确率，或 R=1 意味着我们的数据也零漏检。
- 不能说拼上两篇方法就完成需求到架构的自动设计、优化或验证。
- 在实际 clean-run、工具校验和人工标注前，不能说我们已复现作者算法或模型。
- 不能把研发用 `.txt/.json` 示例、LLM 的 `PASS` 文本或 HTML 演示当成 SysML v2 工具校验记录。

可准确定位为：**使用真实 SysML v2 工具和可追溯工程证据，在限定子系统上，给工程师生成、核验、比较和批准候选模型变更的工作台。** 两篇论文分别提供跨源对齐与模型检索的研究依据；文件版本、执行证据、工程计算、回归测试和可靠用户流程，是本项目必须自己补齐的产品工程。
