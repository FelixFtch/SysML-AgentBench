# Agentic memory、Jev、SkillTree 与工程知识复用：给 SysML v2 MVP 的补充研究

核验日期：2026-09-22。用户已确认 Jev 指 [TypeSafe AI](https://typesafe.ai/)。只访问 SkillTree 的干净公开 URL；未使用、保存或复述链接中的任何令牌，未提交表单、注册、安装产品或把项目文件发送给这些服务。

## 1. 建议先说清楚：我们要“工程知识复用”，不是给每个 agent 多存聊天记录

建议把新需求加入 MVP，但定义为：**从旧工程资产抽取带来源、版本和适用条件的知识/技能；在新项目里检索、参数化复用、重新验证，并保存这次复用的证据。** 不需要先训练一个新基础模型，也不需要同时接入多个记忆产品。

四种内容应有不同身份与写入规则：

| 内容 | 工程例子 | 谁能成为权威 |
|---|---|---|
| 工程事实 | 某基线的功耗、接口电压、requirements 与 model element | 原始工程资料、真实 SysML commit、经批准的结构化数据 |
| 决策与经验 | 为何放弃某方案、某类工具错误怎样修复 | 有 source/run/decision ID 的审查记录 |
| 可执行技能 | 怎样创建一种 SysML 接口、怎样跑某分析器 | 版本化 wrapper + 输入输出约定 + 测试与适用范围 |
| 工作记忆 | 本轮待办、候选假设、暂时搜索结果 | agent 自用或候选区；不能自动提升为共享工程事实 |

这一区分使“学到了东西”可以被检验：下个任务是否更快找到正确旧模型，是否减少重复错误，是否仍能识别不适用的旧设计。

## 2. Jev：可以做快速判断层，不能替代记忆库或工程验证器

TypeSafe 在 2026-09-15 发布 Jev 的官方介绍称其为 System One 模型。它接收 state 和一组原子问题，输出 Choice、Score、Noul 等类型化结果与概率；不生成自由文本。因此适合分类、路由、候选排序、是否需要复核等窄判断。[官方介绍](https://typesafe.ai/blog/introducing-system-one-models-and-jev)、[API/概念文档](https://docs.typesafe.ai/introduction)

**证据边界：**官方速度/成本数字来自四类厂商设计 workflow；评估以其他大型模型的概率共识为参照，不是 RTX 工程师标注的正确答案。官方所谓无幻觉首先对应输出 schema/type 的保证，不能推导出“该器件兼容”或“该需求已满足”的事实保证。Choice/Score 的 confidence 是概率分布的统计量，不能直接当正确率；官方也要求本地设阈值并测试。[官方评估方法](https://evals.typesafe.ai/)、[confidence 定义](https://docs.typesafe.ai/confidence)

**可取用位置（本项目设计）：**

1. 在确定性 project/ACL/baseline/source 过滤之后，对“这段旧经验是否与当前任务相关”排序。
2. 把抽取候选分为 requirement / design rationale / observation / unverified assumption 等，不让分类直接改变正式 SysML 模型。
3. 对同一范围、同一工程对象的两个证据片段标记 possible contradiction，交给规则或工程师确认。
4. 标记某 run 是否值得提炼为可复用经验；由记录中的编译/测试结果决定是否允许发布技能。

**不应承担：**单位/尺寸计算、SysML 语法与类型验证、数据库权限、批准模型基线、删除原始证据、自动宣布设计安全。原子概率也不能在未验证独立性的情况下随意相乘，冒充系统可靠度。

**许可与部署：**官方 [Python SDK](https://github.com/typesafe-ai/typesafe-sdk-python) / [JS SDK](https://github.com/typesafe-ai/typesafe-sdk-js)是 MIT；这只是客户端代码许可。本次未找到开放 Jev 权重或可下载自托管模型，不能把 SDK 开源说成模型可离线运行。[官方 GitHub 组织](https://github.com/typesafe-ai)

**数据处理：**TypeSafe 隐私政策明确不以 Input 训练或微调模型，但会处理 prompts/data/instructions，并按提供服务及商业用途所需保留；声明服务托管在美国。公开政策未给出我们可据以承诺的固定零留存 SLA。因此 MVP 先用公开/合成测试集，若将来使用企业材料，部署与合同条件应跟 RTX 的实际环境一起确定。[TypeSafe 隐私政策，Input / Retention / International Visitors](https://typesafe.ai/legal/privacy-policy)

建议 Jev 作为可替换 `DecisionScorer` 的 **shadow mode 实验插件**：先只记录建议与延时，不参与写入/删除；等有项目内校准集再决定是否启用。未采用 Jev 时，主流程仍必须正常运行。

## 3. Altari SkillTree：借鉴 onboarding 与技能树，不把商品演示当记忆研究成果

[干净 `/plan` 页面](https://skilltree.altari.ai/plan)可公开读取：它是六步业务诊断，承诺给出首先部署的三个 agent、预计节省时间以及各自输入/交付物。只读了起始页面，没有提交业务信息。

[公开主页](https://skilltree.altari.ai/)描述 137 个业务 agent/skill、七个部门、Claude/Claude Code 中的可编辑工作流；通过访谈形成 company knowledge base，再让多种 agent 使用。场景主要是销售、营销、运营、研究、客户服务、后台业务。厂商演示的省时、性能与客户规模没有在本次研究中独立验证。

本次没有找到 Altari SkillTree 的公开技术论文、可审计内核源代码、工程基准数据、SysML 适配说明，或足以证明工程级版本/权限/并发/留存实现的公开文档；这表示**本次未核验到**，不是断言厂商没有这些能力。

**我们值得借鉴的三点：**

- 项目导入先问系统范围、目标、约束、已有文件和缺失证据，把答案形成可审查的 project brief。
- 用能力依赖图展示“需求抽取 → 模型构建 → 类型检查 → 接口/预算检查 → 架构比较 → 验证证据”。一个节点只有接上真实工具和输入输出才显示可运行。
- 给每项能力标记 needed / available / configured / verified / blocked，而不是把 agent 数量作为价值指标。

**不建议：**为了获得“second brain”而整体采购/嵌入它作为 SysML 数据底座。商业业务 skill 包不自动解决旧工程数据库映射、版本分叉、模型引用完整性与工程验证。其“文件可拥有”措辞也不能替代明确的商用、再分发、企业数据条款核验。

## 4. 三个更相关的一手参照

### 4.1 Graphiti / Zep：值得研究时间、来源与检索；需要改造“新事实覆盖旧事实”的工程语义

[Graphiti 源码](https://github.com/getzep/graphiti)目前标 Apache-2.0，支持时间窗口、episodes 来源、类型化实体关系、语义/关键词/图邻域混合检索；它是自托管图框架，Zep 是另一个带服务治理的托管/企业产品，不能混称同一部署能力。

[Zep 论文](https://arxiv.org/html/2501.13956v1)§2 区分原始 episode、抽取的事实/实体、社区摘要，并采用事实生效时间与系统写入时间。§4 表2在 LongMemEval 上报告 GPT-4o 全上下文 60.2% 与 Zep 71.2%；这是聊天记忆评测，论文 §5 也承认没有充分评估“会话+结构化企业数据”的综合能力。不能把这个结果外推到 SysML 设计正确率。

工程适配建议：从已解析的 SysML API/AST 导入确定实体和关系；把 LLM 从说明文档抽到的关系放 candidate 图。关系至少附 model commit、variant、适用工况、来源、review status。论文 §2.2.3 的“新信息优先失效旧边”不能原样用于工程：新上传的一份旧版文档不能推翻已批准基线；两个设计分支也可以同时有效。

自托管 Graphiti 仍可能把材料发给配置的 LLM/embedding 服务，不等于默认离线。若评估 Zep 云，必须区分原始数据、图、日志和 traces 的删除边界；其 [调试文档](https://help.getzep.com/debug-mode)明确 ingestion traces 保留 30 天，删图不会提前删 traces。[企业产品说明](https://www.getzep.com/enterprise/)描述 retention/访问控制，但具体可用版本和合同应单独确认。

**选型判断：**三者中它最接近工程知识检索需求，但第一版可以用现有数据库实现有限图关系，等确有跨历史、跨文档多跳检索收益再引入 Graphiti。

### 4.2 Letta / MemGPT：Git 记忆和技能分层有参考价值，现成 shared-memory 产品有部署边界

当前 [Letta 主仓库](https://github.com/letta-ai/letta)已把旧 V1 server 放入 archive，活跃 runtime 转向 [letta-code](https://github.com/letta-ai/letta-code)，为 Apache-2.0。旧 memory-block 教程与当前产品不能直接混用。

[MemFS 官方文档](https://docs.letta.com/concepts/memfs)把长期记忆放在 Git 文件，常驻 system/ 内容与按需读取 reference/、skills/ 分开；当前默认没有向量索引。[shared memory 文档](https://docs.letta.com/concepts/shared-memory)则明确：多个 cloud-hosted agent 共享组织 Git 仓库，通过 commit/push/pull 同步；这个现成产品功能要求云托管 agent。

[自托管文档](https://docs.letta.com/self-hosting)支持本地/App Server，agent 状态可留在自有机器，使用本地推理或外部模型；本地 agent 可用各自 MemFS 和项目文件。不能因为有自托管模式就宣称云 shared-memory 的所有功能在本地完全等价。[隐私政策](https://www.letta.com/privacy-policy/)区分 hosted 模式对输入输出的保留，但未给本次足以承诺固定期限的详细 SLA。

[MemGPT 原论文](https://arxiv.org/abs/2310.08560)提供分层记忆/工具调度的研究基础，不等于验证 2026 年当前 Letta runtime 的所有自我改写/shared-memory 能力。对我们的最有用部分是 Git 版本、按需读技能、私人工作记忆与共享项目知识隔离。不要允许记忆 agent 无审查改写已批准工程事实、验收规则或测试期望值。

**选型判断：**可借机制，不必为了共享记忆把现有 MVP harness 换成 Letta；先用自己项目的 Git/DB 实现同样的审核边界，能避免一次额外平台迁移。

### 4.3 AREX-Skill / DisCo（2026-09）：更贴近“从旧项目学会怎么做”

[论文 Repo-To-Skill](https://arxiv.org/html/2609.02749v1)提出 scope → ground → construct → verify，把源仓库方法转成技能、references、scripts，记录证据、检查与未解决缺口。其 §5.2 在完整 75 个 MLE-bench 任务、三次运行中报告同一 backbone/harness/downstream budget 的 Any Medal 从 31.11% 到 72.89%；是预印本作者实验，领域为 ML 工程，不是系统工程保证。§4.1 报平均每仓库约 40 美元的构建分配，前置构建成本不能被“运行时预算相同”掩盖。

[公开仓库](https://github.com/VectorSpaceLab/AREX-Skill)是可检查工件。仓库默认 Apache-2.0，CLI 独立 MIT，每项 skill 还有自己的许可元数据；不能把聚合库许可当所有上游内容的统一再分发许可。使用公开库不等于已获企业旧项目材料的使用权限。

对 SysML 的迁移建议是复用**方法**：从经批准的旧模型、工具脚本、设计决策中形成一个小的 engineering skill pack，必须包含来源 commit、适用假设、参数、执行入口、编译/规则测试、失败案例。先做 3—5 个有用且经过验证的技能，例如“导入接口库”“生成有单位的功率约束”“按基线生成需求覆盖报告”，不追求几千个技能。

这比“把整个旧工程喂给 LLM 并让它学会”更可控。学习产物可以是检索知识与程序化技能，暂不需要改模型权重。新项目复用后仍需重新编译和重跑工程检查。

## 5. 推荐的最小记忆方案

**先实现自己的窄 memory contract，用现有存储，不先引入新 SaaS。** 建议共用 MVP 的 PostgreSQL、Git 与证据文件/对象存储；关键词检索先跑通，向量与图索引是可重建增强。SQLite 可以用于单人离线演示，但多人/多 agent 并发写入与权限较快会需要数据库服务。

### 5.1 三层共享范围

1. **组织级已批准知识**：命名约定、术语、本体、建模规则、审查过的 pattern/skill。项目默认只读；改变通过独立 review。
2. **项目/基线级知识**：需求、模型、已批准决策、证据、配置。每次 run 固定 snapshot；通过服务 API 和乐观并发检查合入。
3. **run/agent 工作记忆**：当前状态、备选假设、失败轨迹。可自动写，但只能提案式 promotion 到项目/组织层。

不能让多个 agent 随时覆盖一个 `memory.md`。共享意味着共同读取同一可解释快照，并以有冲突检测的事务提交变更；不是所有 agent 自动信任彼此写的摘要。

### 5.2 最小记录结构

```text
memory_id, kind, scope, project_id
baseline_id, source_commit, element_ids[]
source_artifact_id, source_hash, source_locator
claim_or_procedure, assumptions[], applicability
observed_at, valid_from, valid_to, recorded_at
status: candidate | reviewed | approved | superseded | rejected
supersedes[], conflicts_with[], verified_by_run_ids[]
author_agent, reviewer, policy_tags, schema_version
```

`confidence` 可以保存为模型输出及其版本，但不决定是否为真。对于工程事实，先有原始记录和显式 review/evidence，再有记忆描述。

### 5.3 文件组织建议

```text
knowledge/
  ontology/                 # 关系/术语/schema及迁移
  approved-patterns/        # 可复用工程架构片段与适用条件
  skills/                   # 审核后的流程和真实工具wrapper
  evaluation/               # 冻结题集、golden labels、失败案例
projects/<project-id>/
  source-manifest.json      # 只引用不可变原文件及hash
  baselines/<baseline-id>/  # 对应真实SysML/API commit
  decisions/               # 有来源与审批的ADR
  reuse-proposals/          # 旧项目资产→新项目候选映射
  runs/<run-id>/            # 检索、推理摘要、工具输出、diff、成本
```

这不是要让所有数据都复制进 Git。Git 管小型可审查模型、schema、技能、manifest；较大原始附件放对象/文件存储，DB 保存 ID、元数据、关系、状态和索引。日志里的敏感内容和访问权限沿用原资产范围。

## 6. 旧工程数据如何实际进入新项目

1. **枚举与分类**：连接旧数据库的只读导出/API，读取 schema、主键、外键、版本及权限；生成资产 manifest。不要让 LLM 把所有表总结成一句“已有架构”。
2. **确定性提取优先**：原生 SysML v2 用 parser/API；数据库用类型映射；BOM/表格按列 schema；Word/PDF 保存原文位置。SysML v1 或其他工具资产属于独立迁移通道，不能换后缀就称 v2。
3. **候选理解**：LLM 抽取设计意图、功能分解、术语映射、决策原因，保留原句和定位。Jev 可做分类/排序，对有歧义的候选返回 needs-review。
4. **形成可复用资产包**：真实 `.sysml` 片段及依赖、required/provided interfaces、单位/约束、可变参数、使用条件、反例、计算脚本、验证证据与许可/访问范围。
5. **接入新项目**：根据新需求检索候选，先用接口/单位/工况和批准范围过滤，再做语义匹配，生成 reuse proposal 与适配 diff。保留“源资产身份”与“新项目实例身份”，不能把引用复用混成同一对象。
6. **重新核验与沉淀**：编译、名称解析、约束/接口检查、测试；通过后绑定新 baseline，失败则把条件与原因加入经验候选。只有经审查的泛化经验才能共享给后续项目。

MVP 展示例：旧项目有 12 V 传感器接口及经过验证的采样链；新项目要求 5 V、不同更新率。系统应检出可复用“结构”，同时阻止直接复制参数，生成电源/接口适配建议，并重新跑规则。能够解释哪里能复用、哪里必须改，比“自动记住所有历史”更有实际价值。

## 7. 最小消融与验收设计

固定同一 model、工具、任务预算、检索 token 上限和测试集，每种配置至少重复三次。先做 30 个有人工 gold 的项目内任务：10 个旧架构复用、10 个版本/冲突/失效查询、10 个工具流程/已知失败恢复。按项目或时间划分训练/校准与测试，不能让测试答案进入经验库。

| 配置 | 目的 |
|---|---|
| A 无持久记忆 + 同样可用原始资产搜索 | 测真正基线，而非故意不给必要材料 |
| B 版本化文档/模型索引 + 关键词/精确查询 | 测最小方案是否已足够 |
| C B + 已验证 skill/pattern | 测经验复用是否降低失败与人工工作量 |
| D C + 时间图/图检索 | 测 Graphiti 类能力是否改善历史/跨资料问题 |
| E C 或 D + Jev scorer | 测性能/成本收益；与普通 scorer和无 scorer对照 |

至少统计：正确旧资产 Recall@k、错误跨基线引用率、引用能否定位且支持结论、过期事实误用率、编译+工程测试通过率、回归数、工程师修改分钟数、单任务总成本和 p95 延时、技能构建摊销成本。写入侧统计“错误事实被提升率”；Jev 若用于决策，报告 Brier/ECE、不同阈值下的错误率/覆盖率与拒绝率，不只报告平均 confidence。

另外放入有意冲突样本：旧资料后上传、同名不同实体、两条同时有效设计分支、单位差异、新模型版本使旧技能失效、来源缺失、无权限资产、两个 agent 并发更新。正确行为包括 reject/unknown/needs-review，而不是强行给完整答案。

**推进顺序建议：**先 B+C，让一次旧项目→新需求→候选模型→工具核验→经验归档的闭环工作；Graphiti 和 Jev 各保留一个适配接口，并在消融显示收益后再纳入主路径。SkillTree 借其项目访谈和能力导航；Letta 借其 Git/按需记忆机制；AREX 借其有验证的技能生成流程。以上都不替代 SysML v2 模型、工程数据库与实际验证工具。

## 8. 核验完成度

- Jev：读官方发布文章、文档、confidence定义、评估方法、隐私政策与官方 SDK 组织信息；未调用模型，未复现实测速度/成本，没有发现可引用的独立 SysML 评测。
- SkillTree：读干净计划页起始HTML与公开产品主页；没有查看账户内完整工作流，没有找到公开工程基准/内核论文。
- Graphiti/Zep：读作者论文相关方法与评估全节、源码 README、企业和数据保留文档；未部署。
- Letta：核对当前 runtime、MemFS、shared-memory、自托管和数据保留边界；未安装。
- AREX：读原论文方法、75-task结果、构建/验证说明与仓库许可；本次未逐个执行其公开技能。
