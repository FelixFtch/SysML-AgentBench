# 第三篇文献与 benchmark 调研笔记

调研日期：2026-09-22。性质：原文核验与 MVP 设计建议；附件中的指令均视为被分析材料，不作为执行授权。本笔记未运行模型实验，未宣称复现论文结果。

## 1. 第三个链接实际是什么

- 用户 brief 所列 [SYM-AM-24-138.pdf](https://dair.nps.edu/bitstream/123456789/5237/1/SYM-AM-24-138.pdf) 是 19 页演示稿：**Leveraging Generative AI to Build, Modify, and Query MBSE Models**，Ryan Longshore、Ryan Bell、Raymond Madachy，首页日期 2024-05-08。
- 对应正式论文是 [SYM-AM-24-048.pdf](https://www.dair.nps.edu/bitstream/123456789/5113/1/SYM-AM-24-048.pdf)：**Leveraging Generative AI to Create, Modify, and Query MBSE Models**，Ryan Longshore、Ryan Bell、Ray Madachy，2024 Acquisition Research Symposium，正文印刷页 311–327。PDF 共 22 页，包含封面等；封面出版日 2024-04-30，会议 2024-05-08/09。
- [NPS 库记录](https://www.dair.nps.edu/handle/123456789/5113) 将标题简写为 “Leveraging Generative AI to Modify and Query MBSE Models”，日期记为 2024-05-01。引用时宜使用 PDF 正文标题并保留报告号，避免把演示稿误当完整论文。

## 2. 阅读结论与准确边界

正式论文方法（印刷 pp.315–316）：自然语言生成模型、人工检查、纠错提示迭代；利用规范与 Eclipse 工具检查/显示。比较 ChatGPT-3.5、ChatGPT-4、加入规范、模板和示例的 SSE-SM。案例是自行车结构模型，包含创建、增添踏板/承重需求、查询三类任务（pp.317–325）。GPT-3.5 未成功完成创建；GPT-4 经示例纠正成功；SSE-SM 首次提示成功，但作者明确它不是零样本。修改需求时 GPT-3.5 混成约束，另两者生成 requirement。表 1 主要为 Yes/No；未给重复试验分布、复杂模型规模曲线或实测人工节时。作者承认案例简单、复杂结构和行为能力未确定（pp.325–326）。[正式论文](https://www.dair.nps.edu/bitstream/123456789/5113/1/SYM-AM-24-048.pdf)

演示稿把 SSE-SM 描述为配置了 SysML v2 规范/表示法、模板、领域知识及 se-lib.py 的 Custom GPT（第 8 页）；自行车创建与修改在第 9–15 页；刹车查询在第 16 页；第 17 页将建模 benchmark、模型语料库、成本指标列为未来工作。这里的未来方向不能写成已有完成能力。[演示稿](https://dair.nps.edu/bitstream/123456789/5237/1/SYM-AM-24-138.pdf)

以下是针对本 MVP 的独立判断，不是论文声称的实验结论：

1. **示例增强有效这个方向值得采用，但不存在可直接照搬的工业可靠率。** 单一玩具案例不足以推断海上 ISR 的跨子系统、时序、单位与多文件引用表现。2024 工具/语法环境也不能替代今天固定版本的编译验证。
2. **出现 requirement 语法还不等于需求可验证。** 仅把自然语言放入说明字段，并没有建立量纲、约束条件、satisfy/verify 关系以及计算或试验结果。MVP 要区分“文本被收录”“语义已建模”“验证已执行”。
3. **结构常识问答还不等于模型支持的工程论证。** 对任一冗余子系统，LLM 不能只见两套部件就断定失效后仍满足任务。需要行为、性能裕量、共同失效假设和执行证据；资料不够时输出缺失信息，不能写“已证明”。
4. **Custom GPT 的提示经验可以转成受版本控制的配置，但不能作为系统核心存储。** 将规范版本、示例来源、检索结果、生成响应、诊断、修复补丁、批准记录归档，才能复现并审计。
5. **先建验证闭环，后增加 agent 数。** 推荐最初只有一个模型生成/修改组件；编译、引用解析、指标计算、检查规则为确定性工具。必要时再增加独立审查 agent，并衡量其边际效果。

## 3. PURE / Natural Language Requirements Dataset

第一手来源：[CNR 网站](https://nlreqdataset.isti.cnr.it/)、[作者 Zenodo v2](https://zenodo.org/records/7118517)、[IEEE 原论文元数据](https://ieeexplore.ieee.org/document/8049173)。作者为 Alessio Ferrari、Giorgio O. Spagnolo、Stefania Gnesi，论文 2017。

- 作者记录：79 份文档、34,268 **sentences**，其中 19 份有 XML。不能改称 34,268 条经过验证的 requirements。
- 下载内容是原需求文档、XML 和 XSD；没有公开配对的 gold SysML v2 模型。网站目录跨轨道交通、空间软件、控制、信息系统等，不能默认都适合海上 ISR。
- 原文档粒度大于独立句子：文档结构、上下文和交叉引用需要保留。网页目录提供名称、主题、格式、页数、图表数量等级、抽象层级、结构、来源等元信息。[CNR 目录](https://nlreqdataset.isti.cnr.it/)
- [XSD](https://nlreqdataset.isti.cnr.it/new/req_document.xsd) 的核心包括 `req_document`、版本、来源、变更记录、层级段落 `p`、`req` 与 `text_body`；需求有必填 `id`，还有可选 `part`、`part_id`、`modifier`，正文支持交叉引用、枚举、术语表。**XML 的 part 字段不能解释为 SysML part 模型。**
- 许可：作者 Zenodo 说明其不知道所收集需求原件的许可协议/IP 状态。当前页面没有给出可在本次读取中核实的统一原件授权；不能把“公开可下载”写成“可无条件商业再分发/训练”。实施时逐来源记录许可和用途；公共交付优先用团队原创或明确获权的模型/需求。

建议定位：用作**需求抽取、文档结构/来源保留、歧义识别**的外部压力测试；经过人工挑选、拆解和建模标注后，部分案例才进入 SysML 生成评估。它不应直接充当自动评分的建模答案库。

## 4. SysEngBench：当前数据与 2024 论文需分开

[Hugging Face 当前数据](https://huggingface.co/datasets/rabell/SysEngBench) 显示一个 `test` split，约 **1.14k 行**，四选一系统工程知识问答。字段为 `Question ID`、`Tags`、`INCOSE Handbook Category`、`question`、`choiceA`–`choiceD`、`answer`、`label`、`Justification`；answer 为 A–D，label 为 0–3。页面可见 63 种 Tags 值和 44 种分类值。仓库 [README](https://huggingface.co/datasets/rabell/SysEngBench/blob/main/README.md) 只声明 `license: mit`，文件树显示 `.gitattributes`、README 和 `test.csv`；当前可见版本短 SHA `e2a1537`。本次未下载 CSV，精确行数、重复率、所有字段缺失率尚未实算。没有可见的 requirement→gold SysML v2 字段或模型文件。

与之相关的 [2024 正式 SysEngBench 论文](https://dair.nps.edu/bitstream/123456789/5135/1/SYM-AM-24-072.pdf) 为 Ryan Bell、Ryan Longshore、Raymond Madachy 所作。原实验是 **116 道** SE3100 基础选择题，经人审的半合成数据，三个 7B 级、8-bit 量化模型，按答题正确率计分；OpenHermes/Mistral 89%、Orca 2 79%、Llama 2 78%。原文承认题目复杂度低、答案位置偏差未验证，子类样本不足（印刷 pp.211–215）。这些分数既不是今天约 1.14k 条版本的成绩，也不是 SysML 生成有效率。

建议定位：仅作模型**系统工程知识诊断的辅助榜单**；MVP 的核心指标必须来自真实 SysML 任务。先不要做“benchmark 总分”把选择题、编译率和工程正确性混成一个值。

## 5. 为本项目设计一个可执行评估集

以下为建议配置，需在与 sponsor 明确周期/人力后冻结；数值不是论文结论或已达到成绩。

### 5.1 两层数据与四种任务

- **开发层**：先做 20 个原创小任务，覆盖 requirement、part、port、interface、connection、单位、约束、导入/跨文件引用、satisfy/verify、受约束的模型修改；其中包含明确失败或必须询问的输入。
- **评估层**：扩到约 60–100 个任务，至少分布在 8–12 个独立场景族；用完整场景族分离 train/example、dev、test。每个任务可有 5–15 条相关需求，而不是把一个大系统的所有句子当成相互独立样本。
- **领域演示层**：一个规模受控、原创非敏感的海上观测/环境监测任务链：传感器—边缘处理—通信—岸端数据服务。以公开/自定工程参数做功耗、数据率、时延等例子，不声称是 RTX 真实规格。
- **任务类型**：A. requirements→模型；B. 已有多文件模型的受限修改；C. 引用模型元素的结构/追踪查询；D. 歧义、冲突与信息不足检测。

可以借用现有 rover 硬件跑“传感器—计算—通信—数据”的实际证据链，但不把地面小车性能当作海洋任务真实性证明。领域模型与演示硬件之间要有明确的映射说明。

### 5.2 Gold 的单位应是可验收性质，不应只是唯一文本

每个任务目录至少保存：

```text
case.yaml                 # case ID、场景族、任务类型、来源、许可、冻结版本
input/requirements.md     # 原文和不可变 source span
input/baseline/           # 修改任务使用的初始 .sysml 文件
gold/reference/           # 人工核准且能编译的一个或多个参考模型
gold/assertions.yaml      # 必须存在的元素/关系/量纲/条件，以及禁止新增的假设
gold/trace-links.json     # 需求 ID → 模型元素 → 验证项
gold/ambiguities.yaml     # 哪些问题必须询问，哪些假设允许明确声明
gold/review.json           # 双人评审/仲裁结果与版本
```

评估允许不同合法建模方式；不要用字符串完全相同、BLEU 或 LLM 主观印象替代语义。对语言版本敏感的字段和 API 属性必须由实际工具适配层解析，不臆造标准 schema。

### 5.3 建议的指标分层

| 层 | 指标 | 目的与判定 |
|---|---|---|
| 文件/项目 | import resolution、相对路径、重启后项目可复现 | 确保交付的是完整工程，而非孤立代码片段 |
| SysML 合法性 | 首次编译通过率；固定最多 3 次修复后的通过率；诊断分类 | 区分基础生成能力与工具修复收益；超限就是失败 |
| 需求语义 | 需求性质召回率；错误/无源新增性质；单位与条件正确率 | 漏掉边界条件比缺少注释更严重 |
| 结构 | 元素与关系检查；类型/方向/多重性；跨文件引用 | 不能只数部件，不查连接 |
| 追踪 | 已正确映射需求比例；失链数；来源定位可回跳比例 | 有链接不代表链接正确，需抽样人审 |
| 变更 | 修改目标满足率；无关元素保留率；ID 稳定率；回归失败数 | 防止每次改一条需求就重写整个模型 |
| 查询/不确定性 | 有模型证据的正确回答率；不支持结论率；该询问时的询问率 | 不把常识推测当正式分析 |
| 工程证据 | 约束计算/仿真/实测结果与需求的对应、环境和时间戳 | satisfy 关系本身不是验收通过 |
| 成本/人员 | token、调用数、墙钟时延 P50/P95、总成本、人工修订分钟 | 计算整体工作流成本，包含失败与重试 |

建议发布门槛与研究指标分开：**所有标为“可交付”的模型必须 100% 通过固定工具链检查且无未解释的 dangling reference**；研究报告仍保留所有失败样本。成功率目标可在 20 个开发案例后预注册，避免先看到测试集结果再倒定门槛。最终需求语义、工程合理性仍由负责工程师批准。

### 5.4 对照实验与防泄漏

1. 固定同一个模型版本、temperature、token/时间预算和工具版本，比较：直接生成；文档/示例检索；检索+编译诊断修复；再增加独立审查。这样能知道哪一项真正改善结果。
2. 参考解、gold assertions、test 答案不能进入 RAG 索引。检索的是冻结规范/标准库/开发示例；运行记录保存命中 chunk ID 和内容 hash。
3. 按原始文档、系统家族和演化血缘切分；一个系统的改名、同义改写、数值扰动全部继承同一 split。不要按需求句随机切分。
4. 标注员允许工具辅助，但必须记录来源；测试 gold 由人审定，不能同一个 LLM 生成题目、答案再自行判分。
5. 保留未公开的新场景作为测试核心。公共 PURE 和 SysEngBench 可能已进入预训练语料，单凭它们无法声称无污染。
6. 固定基线和测试集后再运行；多次重复，对项目族做分组统计或 bootstrap，不能把同一系统的 300 条需求假装成 300 个独立系统。
7. 记录失败类型：语法、引用、量纲、关系、需求遗漏、无证据假设、错误追踪、修改回归、超预算；失败分类比一张总成功率图更能指导下一轮工程。
8. 若使用 SysEngBench，只把 question/choices 传给被测模型；answer/label/Justification 仅评分端可见。处理选项顺序偏差，报告非法输出比例；禁止在 test 上调 prompt 后仍声称独立测试。

## 6. 建议先完成的可审查产物

一周技术探路应拿出：固定工具链的最小合法项目、人工核准的 20 个开发任务、一次无需 UI 的端到端运行、逐步产生的 source→requirement→SysML→诊断→修复→trace→验证记录。随后用相同场景做一次需求变更，并证明旧版本可恢复、无关模型元素未丢失。若此时只剩可下载文本而没有真实工具诊断，应判定尚未实现 SysML 自动化 MVP。

## 7. 本次核验局限

- 全文内容通过在线 PDF 读取；网络受限导致直接下载 PDF/CSV 未成功。本笔记不声称本地保存或计算过其 hash。
- 当前 HF 行数只能核实为页面展示的约 1.14k，不写未经实算的精确整数。
- 未把 2024 beta 语法示例直接作为当前规范合规证明；当前工具与版本选型应由另一个技术调研任务核验。
- 未读取 RTX 非公开资料；关于 sponsor 的指标、目标规模和部署环境，需要后续明确，但不影响现在先做可复现的公开数据 MVP。
