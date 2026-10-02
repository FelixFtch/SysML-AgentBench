# 历史工程知识与 Agent 经验记忆：供 RTX 三人 MVP 采用的方案

调研日期：2026-09-22。以下把一手文献事实与方案建议分开。本次未克隆/运行候选框架，未向服务商上传项目资料，也未复现其 benchmark。

## 核心判断

值得做的是“从历史项目提取可引用、可判断适用性的工程证据，再帮助新项目建模”，同时独立积累工具使用经验。历史的正确答案、今天生效的要求、在某次试验中有效的做法、LLM 总结出的经验，必须有不同的身份和更新规则。

对三人 MVP，第一优先级是带来源、基线、适用条件的证据记录和受审查的复用包；第二优先级是 **ACE 风格的增量工作经验库**；GEPA 放到有稳定评测以后做离线 prompt 优化。A-MEM 与 Jev-Mem 可作为对照，不需要首期同时部署。不要把记忆框架的存在当成已经完成企业知识治理。

## 1. 三个代表性 Agent 方法

| 方法/核验版本 | 一手证据与机制 | 本项目采用判断 |
|---|---|---|
| A-MEM，Xu 等；2025-02 初稿，本文读 v11（2025-10-08） | [论文 §3–4、§6](https://arxiv.org/html/2502.12110v11)：原子笔记保存内容、时间、标签、上下文、嵌入、连接；新记忆可修改旧笔记的上下文/标签。主要在 LoCoMo/DialSim 对话问答验证。原文承认组织质量依赖底层 LLM。[开源实现 MIT](https://github.com/agiresearch/A-mem)。 | 借鉴“原子知识卡片+关联检索”。工程事实本体和源记录应固定，自动演化只能产生新的派生版本；不直接用会替换旧记录的默认模式维护发布基线。对话分数不能证明接口/需求语义保真。 |
| ACE，Zhang 等；ICLR 2026，arXiv v3 2026-03-29 | [论文 §3、§5](https://arxiv.org/html/2510.04618v3)：Generator 产生轨迹，Reflector 提取经验，Curator 写增量条目；条目有 ID、helpful/harmful 计数，轻量逻辑合并。作者说明弱 Reflector 会带来无用甚至有害上下文；主要评估 AppWorld、领域推理。[作者开源 Apache-2.0](https://github.com/ace-agent/ace)。 | **最适合首期借鉴。** 保存“某工具版本下某诊断如何修复、何时先查标准库、哪类修改必须回归”等经验。先用简单 JSONL/YAML 实现增量条目，不要求引入完整框架。经验晋升需回归证据。 |
| GEPA，Agrawal 等；arXiv v2 2026-02-14 | [论文](https://arxiv.org/abs/2507.19457)：用运行轨迹和文字反馈迭代改写 prompt，按 Pareto 候选选择/组合；报告六类任务上较 GRPO 更少 rollout 的优势。[作者仓库 MIT](https://github.com/gepa-ai/gepa)。 | 它是**优化器**，不负责历史工件、权限或事实时态。适合第二阶段在开发集上优化“抽取/生成/修复”提示，约束调用预算、冻结验证集；不能在线自改发布中的工程规则。 |

三者的共同边界：均没有在本次核验来源中证明其能自动、可靠地把某企业多年混合 SE 档案转成符合当前 SysML v2 的可交付模型。采用的是算法思想与可运行软件，不是拿已有实验替代我们自己的评估。

### ACE 风格经验条目应长什么样

下例是项目自定义 schema，而非 SysML 标准或 ACE 原生 schema：

```yaml
lesson_id: lesson-0042
kind: tool_workflow
applicability:
  sysml_release: pinned-release
  validator: pinned-tool-and-version
  operation: cross_file_change
trigger: unresolved_reference_after_rename
action: inspect_semantic_references_before_changing_imports
supporting_runs: [run-0101, run-0137]
counterexamples: [run-0142]
status: candidate
reviewed_by: null
supersedes: null
```

正式条目应表达可验证的动作和适用条件，不能仅写“多思考”“注意质量”。流程经验不能携带当前任务的隐藏 gold 答案，也不能自行覆盖 sponsor 的明确需求。

## 2. 更贴近企业历史 SE 的两项研究

### 2.1 工件、版本与工作流应一起保存

[Ryś、Lima、Exelmans、Janssens、Vangheluwe：Model management to support systems engineering workflows using ontology-based knowledge graphs](https://arxiv.org/html/2512.09596v1)，本次核验版本 arXiv v1 2025-12-10。§3–4 用 OML/OWL/RDF 描述工作流、执行事件、输入/输出工件及版本关系；§5 用传动系统传感研究展示模型与实验数据管理；§7.1 坦承以整份拷贝做版本管理难以扩展，未支持语言演化。该工作不是 LLM 自动抽取论文，但其工程记录范围比一般聊天记忆更匹配本项目。

作者提供 [本体/示例仓库](https://msdl.uantwerpen.be/git/lucasalbertins/DTDesign/src/main/examples/oml)、[转换服务](https://msdl.uantwerpen.be/git/jexelmans/drawio2oml/src/master/backend)、[工作流引擎入口](https://msdl.uantwerpen.be/git/lucasalbertins/wee/wiki)。这些链接来自论文；本次未核验其当前可安装性或代码许可。不能把 arXiv 上传日期误写为所有研究/软件首次发布时间。

我们的推论：复用的是“某版本模型在某条件下，通过某活动产生某结论”的证据链，而不只是一个漂亮模型文件。三人组先以关系表和 JSON 实现这些关系，无需先造 RDF/OML 平台。

### 2.2 SysML 已经是结构数据，应优先保留其语义

[Quast、Jacobs、Dehn、Höpfner，Enabling Humans and AI Systems to Retrieve Information from System Architectures in Model-Based Systems Engineering](https://publications.rwth-aachen.de/record/1026259/files/1026259.pdf)，Systems 2026, 14, 83，2026-01-12；[DOI](https://doi.org/10.3390/systems14010083)。§3.1 把 RFLP SysML v2 模型映射到图；§4 用合成电动汽车模型和 100 问评估，最高 93%。§5.5 明确仅有特定 RFLP/语法适配的正则与模式匹配解析器，未覆盖工业脏数据/规模，也没有用户研究。数据声明为向作者申请，不是已开放的通用 benchmark。

我们的推论：有模型 API/XMI/AST 时应确定性提取元素 ID、类型、关系，再建检索索引；不要让 LLM 从模型截图重新猜关系。该论文的 93% 是特定模型问答成绩，不是需求转 SysML 正确率；其正则解析器也不能充当我们的标准合规验证器。

## 3. 历史 SysML v1 的正确入口

OMG 已有 [SysML 2.0 Part 2：SysML v1 to SysML v2 Transformation](https://www.omg.org/spec/SysML/2.0/Transformation/PDF)。本次在线 PDF 显示文档号 formal/2026-03-03、封面日期 September 2025；§2 明确映射是 v1 抽象语法到 v2 抽象语法，并允许声明限定范围的部分符合。一个支持 SysML v2 的工具不必自动实现该迁移规范。

建议区分两条路线：

1. **迁移既有模型**：源工具导出/API→保留源 ID/profile/stereotype→用明确支持的映射转换→报告未映射概念与工具扩展→真实 v2 工具检查→工程师确认意图。不能用“把 block 替换成 part”完成迁移。
2. **借用历史设计知识**：从源模型提取一个有上下文的 pattern，例如接口分层/冗余结构/验证方法；在新需求下重新建立 v2 usage 和可验证约束。旧模型不必全量迁移，也不能连旧性能结论一起默认继承。

如果只有 PDF/截图，标记为文档证据，提取结果保持 candidate；它不具有源模型语义导出的确定性。首期只支持一条稳定导出路径，加一个小规模人工核准的迁移样例。

## 4. Jev 对应关系：现在有可核验候选

用户已通过官网链接确认“jev”指 **TypeSafe Jev**。本次另找到相关但独立的研究工件 **Jev-Mem**；两者不能混称同一个产品。

- [TypeSafe 官方文档](https://docs.typesafe.ai/introduction)：Jev 接收状态与 typed questions，返回 Choice、Score、Noul 等结构化判断/概率。它是决策模型，不是完整文档库或 SysML 建模器。
- [Jev-Mem 论文](https://arxiv.org/abs/2609.23986)为 Dongming Jiang、Yi Li、Bingzhe Li，**2026-09-21** 刚提交。控制层负责记忆/检索选择，另一模型综合回答；实验为 LoCoMo，不能外推到 SE。
- [Jev-Mem 作者仓库](https://github.com/libingzheren/Jev-Mem)为 MIT，README 明确离线 demo 使用 mock、不测质量；真实调用向所配服务商发送文本。更值得注意：README 说明继承的 `best-of-n=3` 使用 reference-aware selection，可能抬高准确率，建议单回答评测设 `1`。这不是本次复现结果，而是上游自己的提示。

独立审查发现：该论文 §4.2 部分文字与表 1 的分项数值不一致，例如 temporal 与 multi-hop 描述；因此若引用成绩要以具体表格/版本为准并复核。当前仅一天历史的新预印本，不宜直接成为 sponsor 交付承诺的依据。

采用判断：MVP 先学其“控制决策与回答推理分离、保留原始证据、预算有界”的架构；只有确实需要高频检索路由且基线成本测量支持时，才在公开/合成材料上做对照。对当前三人组，不把额外外部模型调用引入关键链路作为前置条件。

## 5. 最小历史知识提取 pipeline

以下全为项目方案建议。目标样本先取 2–3 个原创/可授权历史微型项目，每个有需求、接口、模型、测试、变更五类材料，并包含两个以上修订。

### 5.1 存储分工

| 数据层 | 内容 | 更新规则 |
|---|---|---|
| Source evidence | 原文档、原导出模型、测试原始数据、变更单 | 不变对象；新修订新增对象，hash+源 URI+版本可定位 |
| Engineering claims | 结构化需求、接口性质、参数、假设、结论及证据关系 | candidate→reviewed；保留事实来源/生效上下文，冲突并存 |
| Reuse packages | 核准的模型模式、参数适用范围、限制、验证配方 | 独立版本；新项目显式采纳并重新验证 |
| Agent lessons | 检索/建模/修复过程中的可复用工作技巧 | 从运行日志提案，经开发集回归后晋升；可弃用/撤回 |

物理实现优先复用当前项目数据库和文件库：对象文件+Git 管理 manifest/模型/规则，SQLite 或 PostgreSQL 关系表管理元数据，全文索引+一个向量索引做候选召回；源材料不必搬进全部图数据库。图关系初期可用 edges 表，证明确有多跳需求后再加专门图引擎。

### 5.2 八个步骤

1. **登记**：每个源文件分配 immutable `artifact_version_id`；记录 source URI、文件 hash、文档 revision、导出工具、导出时间、所有者/允许使用范围。保留原目录结构和 manifest。
2. **解析**：DOCX/PDF 保留页、段、表格单元格；ReqIF/CSV 保留需求 ID；模型 API/XMI 保留原生 ID 与关系；测试记录保留配置、数据、脚本版本及单位。解析错误独立列出。
3. **抽取**：规则先提取 ID、数字、单位和显式连接；LLM 对剩余文本提出 requirement/assumption/interface/decision/rationale/verification/result/change 等候选，必须逐项挂 source span。文档中的操作性文字只作为内容，不能变成 agent 指令。
4. **对齐**：优先基于源 ID、明确 cross-reference、组件型号/接口端点对齐；相似名字只产生候选合并建议。既保留 claim 身份，也保留提出该 claim 的来源身份。
5. **检查**：检查缺源、单位/量纲、适用模式、修订引用、冲突、缺失条件、被替代项；事实冲突不能用 embedding 平均或 LLM 总结消除。
6. **晋升**：工程师核准可复用条目、绑定适用范围；“这是历史事实”“这是设计建议”“这是尚未验证的推断”分别标记。现项目未采纳的历史条目不能生成当前 baseline 的强制需求。
7. **检索**：先按权限、项目/产品族、模式、配置、有效时间、证据状态过滤，再做关键词/向量召回，必要时沿明确 trace 关系补充。输出证据卡、来源、适配理由、限制与冲突，而非直接拼接旧答案。
8. **应用与学习**：生成新 SysML v2 变更提案→编译/语义/约束/回归检查→记录 reviewer、采用/拒绝理由→从工具轨迹中单独提出 workflow lesson。每次生成都保存所用证据包 hash。

## 6. 时态、配置、冲突：最小 schema

这是项目自定义数据契约，**不是 OMG API 字段**：

```text
claim_id, claim_revision, claim_kind, status
subject_id, predicate, value, unit, condition, modality
project_id, product_family, configuration_id, operating_mode
source_artifact_version_id, source_span, source_element_id
valid_from, valid_to                  # 工程上何时生效；未知可 null
recorded_at                          # 本系统何时获知
baseline_id, approval_state, owner
supersedes_claim_id, conflicts_with, derived_from
extraction_model, extraction_prompt_version, reviewer
```

一个典型坑：ICD r2 于 6 月上传，但仅对 B 配置生效；ICD r1 对仍服役的 A 配置继续生效。不能按“最新上传”覆盖所有接口事实。又如测试已通过只覆盖某 firmware、硬件配置、环境与脚本版本；换一项后应标记证据适用性待确认，而不是继续显示绿色。

冲突处理采用明确的 sponsor/项目 authority 规则：已发布基线和有效变更的先后关系由项目定义；LLM 不决定谁权威。检索若发现同一适用域存在未决冲突，返回双方来源并阻止生成确定性合规结论。语义相似和置信度不能替代批准状态。

复用包最少包含 `intent`、`applicability`、`assumptions`、`parameters_and_units`、`model_fragment`、`verification_recipe`、`supporting_evidence`、`known_failure_modes`、`version`、`review`。这里“故障经验”只有在有变更/试验支持时才成为事实；模型自述原因是候选。

## 7. 面向三人组的可验收范围

建议人力分工：一人负责源/版本/索引与 UI 证据回跳，一人负责真实 SysML v2 与检查链，一人负责数据集、gold、评测和 sponsor 的模型评审。所有人共用同一工件 manifest 与 run schema。

一期只交付四种真实能力：

- 在历史文件中检索一条适用需求/接口/测试证据，并回到精确版本/位置。
- 对同一事实的两个修订回答“某配置/某时点哪条有效”，保留冲突和未知。
- 选择一个核准的历史设计模式，在新需求下生成可编译的 SysML v2 变更；展示复用关系和重新验证结果。
- 从两次真实工具失败中积累经验，证明第三个独立开发案例的错误减少，且没有引入语义回归。

一期不承诺全企业自动 ingest、全量 v1→v2 迁移、自动资格认定、多用户权限平台或自主改写全部知识库。此处为范围建议，不是对用户额外请求审批。

## 8. 评测与防止历史答案污染 heldout

建议建立约 40–60 个小任务，至少覆盖 6 个来源/场景族，包含下列具有判别力的对照：

| 测试 | 必须验证 |
|---|---|
| 来源准确性 | 引用是否真的支持结论、页/段/元素是否正确；不得只评引用非空 |
| 修订/时间 | 按配置与生效日期命中正确版本；未来版本/迟到文档不能污染历史时点 |
| 冲突 | 未决冲突召回率和错误自动合并率 |
| 复用适配 | 在功耗/时延/模式等改变后，是否拒绝不适用旧方案并保留必要条件 |
| 建模 | 首次与限次修复后编译率、语义 assertion、需求追踪正确率 |
| 经验收益 | 同模型同预算，有/无经验条目的成功率、重犯错误率、人工分钟、成本 |
| 更新回滚 | 新文档导入、源撤回、条目纠正后能否撤销派生索引并重放旧 baseline |

对照顺序：无记忆→带 metadata 的全文/向量检索→加明确关系遍历→加已核准工作经验。只有前一项的不足被测量出来，才增加下一层复杂度。

**评测设计必须区分“合法的历史上下文”与“泄漏”：**

1. 做“基于已知历史方案完成新变体”评测时，旧方案可以合法检索，但新变体参考答案、隐藏验收断言及 reviewer 最终判定不允许进上下文；应明确称为有历史上下文的复用任务。
2. 做独立泛化评测时，按项目/系统家族和所有派生血缘切分。旧项目及其改名、改数值、迁移版本不能横跨开发与测试。
3. ACE/GEPA 只在 train/dev 更新；最终测试前冻结 lesson、prompt、索引 snapshot。测试运行产生的笔记留在隔离区，不能立刻改善后续同一测试分布又汇总为一次未污染测试。
4. 若专门评测持续学习，预注册时间序列：每时点只能见此前已释放的反馈；记录每次记忆版本，另报在线成绩，不能与 frozen-test 成绩混用。
5. 标注员可以看 gold；被测生成器/检索器和候选选择程序不能看 gold。禁止 reference-aware best-of-n 选择后仍报告单次成功率。
6. 版本化所有源、索引、embedding、抽取模型、prompt、工具、gold 与分割 manifest；保存候选检索与最终使用的证据 ID，才能排查“是模型会做还是检索到了答案”。

## 9. 最终采用优先级

**现在就做**：源工件不变存储、声明/证据/经验分层、配置/版本/时态字段、来源回跳、真实 SysML 解析与检查、核准复用包、冻结评测。

**第一轮闭环后加**：ACE 风格受控增量经验，把确定工具反馈转成可验证 lesson。

**有数据证明需要时加**：GEPA 离线优化；A-MEM 关联检索对照；Jev-Mem 检索路由成本对照。不要用它们替代当前项目的版本库与工件目录，也不要让它们越过明确的工程权威来源。
