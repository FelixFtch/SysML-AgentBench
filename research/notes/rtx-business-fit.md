# RTX 业务、招聘证据与三人 SysML v2 MVP 选题

调研截至 2026-09-22。关键业务和技术判断以 RTX 官方一手资料为主；第三方转帖及职业线索另标边界。引用发布日期与页面抓取时间不混同。以下“事实”来自公开资料，“建议/判断”是基于三人团队与项目 brief 的工程取舍。按团队已有 RTX 合作和访问支持来规划；本研究没有接触 RTX 内部工程资料。

## 推荐结论

**同意主报告的新方向：跨业务工程知识复用与可验证 SysML 建模、变更平台。第一例默认服务 brief 的多平台海事观测数据子系统；用一个真实历史变更证明语义对齐、影响分析、模型更新和检查证据的闭环。航空、发动机健康监测和制造系统是候选迁移方向，不事先锁定。**

以下判断由公司近期业务和实际招聘推导。公开资料没有证明 RTX 内部缺少这层能力，也不能据此认定采购意向；需要合作方真实工件检验这个补位假设。Rover 的流程结构可保留为回归样例；飞机外形可以作为未来展示上下文，都不是首先决定题目的理由。

## 已核实的招聘信号

核验日为 **2026-09-22**。“可见 Apply”只说明当时官方页面仍展示职位及申请入口，不保证 HR 实时招聘状态；职位 Date Posted 与搜索引擎抓取日期分开记录。对 JavaScript Workday 页面，web 抽取器空白不能解释为职位关闭。

| 职位 | 发布日期 / 地点 | 核验状态 | 对本项目的证据意义 |
| --- | --- | --- | --- |
| **RTRC Agentic AI Researcher (Hybrid), 01868376** | **2026-08-20 / East Hartford, CT**；Advanced Learning and Analytics / AI Discipline | 本子任务实际在 Chrome 打开官方 Workday 搜索与完整详情，看到 **Apply**、Date Posted、ID | 明确期待 grounded、explainable、verifiable 系统，LLM/RL 结合符号推理、知识图谱、形式方法；工程问题建模、多模态、LangGraph/AutoGen。强支持“LLM 提议 + 工具独立验证”，岗位本身未指定 SysML |
| **BBN Agentic AI Engineer, 01855543** | **2026-06-25 / Arlington, VA** | 根任务已核验官方全文及 Apply；本子任务未重复浏览器核验 | production Python、推理/规划/多步执行、实验评估、memory architectures。支持真实执行与评测，不应仅展示角色名 |
| **Raytheon Enterprise Architect (Associate Director) — Digital Connected Factory, 01867433** | **2026-08-18 / Tucson, AZ / Hybrid** | 本子任务实际在 Chrome 读取官方全文及 **Apply** | SAP/MES/知识图谱/机器人端到端架构；Agent 框架与运行时；digital thread；可复用参考实现；偏好 LLM/RAG/KG 及 SysML/Cameo。说明制造系统也值得候选，不能预定航空 |
| **Collins Lead Engineer / DEMPA, 01868964** | 官方索引 **2026-09-06 / Bengaluru** | 根任务直接打开 careers 页返回 **410 Gone**，仅保留历史/索引信号 | 摘要涉及 document→model、SysML/Cameo、需求/变更/版本/追溯。不能称当前开放，也不能把摘要包装为完整岗位正文 |
| **Pratt Associate Director, Solutions Architect — Data, Analytics & AI/ML Platforms, 01844760** | 官方索引 **2026-05-28 / US-CT-REMOTE** | 官方搜索正文可读；本子任务未核验当日页面是否仍有 Apply | 数据治理/血缘、KG/ontology、质量与平台集成；作为主题补充，当前在招未核验 |
| **Pratt Lead Ontology & Knowledge Engineer, 01817009** | 原始日期仅第三方镜像称 2026-01-15；CDFAM 2026-03-27 是转帖日期 | 从转帖 Apply 追到官方页，明确 **posting is no longer available** | 已关闭历史岗位；不把转帖正文当当前需求或关键技术事实 |

官方原文链接：

- [RTRC 01868376](https://globalhr.wd5.myworkdayjobs.com/en-US/REC_RTX_Ext_Gateway/job/US-CT-EAST-HARTFORD-RTRC-K--411-Silver-Ln--RTRC-K/Agentic-AI-Researcher--Hybrid-_01868376)
- [BBN 01855543](https://globalhr.wd5.myworkdayjobs.com/en-US/REC_RTX_Ext_Gateway/job/Agentic-AI-Engineer_01855543)
- [Raytheon 01867433 完整官方地址](https://globalhr.wd5.myworkdayjobs.com/en-US/REC_RTX_Ext_Gateway/job/Enterprise-Architect--Associate-Director----Digital-Connected-Factory---Hybrid--Tucson--AZ_01867433)
- [Collins DEMPA 历史链接](https://careers.rtx.com/global/en/job/01868964/Lead-Engineer)
- [Pratt 01844760 官方索引来源](https://globalhr.wd5.myworkdayjobs.com/REC_RTX_Ext_Gateway/job/US-CT-REMOTE/Associate-Director--Solutions-Architect---Data--Analytics---AI-ML-Platforms--Remote-_01844760)
- [Pratt 01817009 官方关闭页](https://careers.rtx.com/global/en/job/01817009/Lead-Ontology-Knowledge-Engineer-Remote)、[CDFAM 转帖](https://cdfam.com/job/lead-ontology-knowledge-engineer/)

旧 RTRC Agentic AI Researcher **01823715** 已由根任务核验填补。它与上述仍有官方详情的 **01868376** 是不同 requisition，不能混淆。[旧职位](https://careers.rtx.com/mx/es/job/01823715/Agentic-AI-Researcher)

RTX 当前技术方向页还明确把 agentic/generative/physical AI 用于工程师效率，数字生命周期强调可信模型和关联数据。页面未标发布日期，本次核验日不能写成其发布日期。[RTX Transformative technologies](https://www.rtx.com/what-we-do/transformative-technologies)

### 导师公开关联的边界

brief 的导师为 George Bollas、Francesca Stramandinoli、Kunal Srivastava、Andrew Radlbeck。ERAS 2025 官方程序将 Francesca 与 RTRC 及边缘 AI 可靠性研究关联；历史 RoboTASK 简历描述机器人语言及系统之系统契约验证。这些是研究背景，不代表当前职级或本项目采购要求。[ERAS 2025 程序](https://erasrobotics.org/2025/ERAS2025Program.pdf)、[RoboTASK 历史简历](https://robotask.eu/fellow.html)

Kunal 与 Andrew 的公开职业页也提供 Agent/自主系统研究语境，但转发或职业标签不足以认定 sponsor 要某种产品；本建议以 brief、官方职责和可用工件为主。[Kunal 公开职业页](https://www.linkedin.com/in/kunal-srivastava-20b603b)、[Andrew 公开职业页](https://www.linkedin.com/in/andrew-radlbeck)

## 证据到 MVP 的推断矩阵

| 官方事实 | 需求推断（待验证） | MVP 功能 | 确定性与反证 |
| --- | --- | --- | --- |
| RTX 强调可信模型与全生命周期数据 | 跨文档、版本和工具的一致性有价值 | 受控文件库；来源定位；模型 revision；索引/运行绑定；可回滚补丁 | 公司方向高，具体痛点中；已有 PLM/MBSE 能力若完整解决，应直接复用 |
| RTRC 01868376 期待可验证 Agent + KG/formal | LLM 需要外部语义与独立判定 | 真 SysML parser；类型/引用/单位检查；工具验证；缺资料 UNKNOWN；失败证据 | 技术期待高；SysML 来自本项目 brief，并非该岗位指定 |
| BBN 要多步执行与实验评估 | 可复现行为比多角色展示重要 | 结构化工具调用；基线对照；版本化记忆；运行日志；失败恢复 | 能力主题高；不能将 BBN 职位领域当 sponsor 首例 |
| Collins DEMPA 历史索引提 document→model/change | 存量工程文档转换可能有人工瓶颈 | 语义对齐候选；歧义确认；影响子图；satisfy/verify 追溯 | 中；原页失效，不能单靠广告选题 |
| Raytheon 01867433 同时要 Agent、KG、SysML | 企业工具和工程模型之间需要连接 | 可替换连接器；外部工具结果归档；模型化系统接口 | 主题高；没有 MES/SAP sandbox 时不宜将工厂作为三人首例 |
| DISCOVER 已做架构搜索 | 可补位模型准备、受控变更与证据串接 | 输入语义与模型导出；适配器；候选来源与计算证据 | 中；若 DISCOVER 已有该层，缩小为转换器或评测，避免重建 |
| MRO 已有 Aiir/Ascentia/FlightSense | 设计构型与服役证据关联可能有价值 | 监测数据链配置变更；信号/采集/验证关联 | 中；若目标实际是维护预测准确率，应调整本项目，而非强塞 SysML |

## 已核实的业务事实

### 1. RTX 已经有架构搜索能力，我们应接入其工程链条

RTX 2025-12-09 官方报道：RTRC 与 Collins 开发的 **DISCOVER** 已用于从组件及设计规则产生可行架构，并调用数值模型评价物理表现、成本和可靠性。文中列举 Collins 飞机厨房、Pratt 混合电推进等应用，也称正在扩大 AI/ML 设计空间探索。这意味着“自动架构探索”不是 RTX 尚未考虑的空白。[RTX：DISCOVER 的工程应用](https://www.rtx.com/news/2025/12/09/discover-engine-build)

**判断：**最有价值的定位，是把非结构化需求与供应商输入转成可信 SysML v2，完成语义对齐、变更传播、工具调用与审查证据。可以设计 DISCOVER 适配接口，但公开资料未证明其可用 API、输入 schema、许可或我们已可调用；这些应从合作方获得，首版用可替换适配器隔离，不把它设为唯一关键路径。

### 2. Collins 的飞机系统广度直接匹配跨子系统集成

RTX 于 2026-02-06 发布的 2025 年 10-K 列举 Collins 的发配电、环境控制、空气数据与传感、航电、通信导航及航空数字服务业务。这支持将问题定义在多个子系统交界处，而不是只做单个零件推荐。[RTX 2025 Form 10-K](https://investors.rtx.com/static-files/215f060a-9dc5-44c2-813a-04aca054e56e)

Collins 商用航空官方产品页说明，二级配电包括 SSPC 与 RPDU；空气管理覆盖通风及液体冷却；Pro Line Fusion 采用便于更新的模块化航电环境，并集成飞机系统与传感器。[配电系统](https://www.rtx.com/collinsaerospace/what-we-do/industries/commercial-aviation/power-and-controls/power-distribution-and-management-system)、[空气管理](https://www.rtx.com/collinsaerospace/what-we-do/industries/commercial-aviation/power-and-controls/air-management-systems)、[Pro Line Fusion](https://www.rtx.com/collinsaerospace/what-we-do/industries/business-aviation/flight-deck/pro-line-fusion)

**判断：**新增一个设备需要同时重新检查接口、供电、热、重量和功能分配，最能让 Collins 工程师看见实用价值。飞机外形只是上下文；真实产品价值在这种连锁影响被发现、解释和修复。

### 3. 民用搜救是现成业务桥梁

Collins 民用直升机页明确把 DF-500 列为搜救平台方向寻找设备。其公开 brochure 区分 DF-500C 民用型号与其他型号，给出总线适用差异、各部件尺寸重量和温度条件。因此可以构建真实来源驱动的输入资料与“不能混用型号能力”负例。[Collins 民用直升机](https://www.rtx.com/collinsaerospace/what-we-do/industries/helicopters/commercial-helicopters)、[DF-500 官方 brochure](https://www.collinsaerospace.com/-/media/CA/product-assets/Files/public/products/product-brochures/navigation-and-guidance/direction-finding/df-500-brochure)

注意：brochure 页脚为 **2019-01**，不是 2026 发布；公开网页仍提供该文件，不意味着它是最新受控构型。公开 brochure 不是完整 ICD，未提供足以闭合电源/热设计的所有参数。MVP 可用它验证资料溯源与型号隔离；真实 integration baseline 应采用合作方当前受控资料。这里不做无线电定位算法、目标识别或飞控实现。

### 4. Pratt 的业务联系很强，是否前置由受控资料决定

Pratt 官方 FAST 描述全飞行数据采集、存储与传输；EngineWise 描述发动机健康、趋势与维护服务。适合把“新增传感通道/提高采样与存储需求”建成系统集成变更，但公开材料不等于可访问真实发动机模型或维护标注。[FAST](https://www.prattwhitney.com/services/pwc-engine-services/digital-engine-health-management/fast-solution)、[EngineWise Intelligence](https://www.prattwhitney.com/en/services/enginewise/intelligence)

RTX 2026-09-18 报道把设计、测试、制造与服役数据贯通，形成整机生命周期能力，列为下一步方向；其中已有 Ascentia、FlightSense 及 AI 检测能力。因此我们的平台应提供可接入的设计证据和版本语义，不另做一个泛化维护预测产品。[RTX：AI 与数据用于航空维护](https://www.rtx.com/news/2026/09/18/how-rtx-is-using-ai-and-data-in-mro)

### 5. 混合电推进适合长期愿景，首版只取集成问题

RTX 2026-03-03 官方资料描述 regional hybrid-electric demonstrator 的跨公司组合及不同飞行阶段用能；2025-09-09 PHARES 公告也明确 Pratt、Collins 与机体厂合作。这是跨组织系统工程的强案例。[混合电飞行示范项目](https://www.rtx.com/news/2026/03/03/rtxs-hybrid-electric-plane-is-one-step-closer-to-the-sky)、[PHARES](https://www.rtx.com/news/news-center/2025/09/09/rtxs-pratt-whitney-canada-selected-by-clean-aviation-to-lead-phares-hybrid-ele)

**判断：**三人团队不应在第一阶段承担完整推进构型优化、发动机物理模型或航空高压硬件；可以后续把已稳定的平台迁移到一个电源/热接口变更案例。宣传中的燃油效率目标是项目目标，不能当作我们的设计计算结果。

### 6. Raytheon 可用民用环境传感业务证明扩展性

RTX 2024-04-08 官方新闻说明 VIIRS 用于陆地、海洋、大气环境观测，支持火灾、空气质量、洪水与海冰数据产品。可据此提出未来环境监测仪器集成的扩展方向。[RTX：VIIRS 环境测试里程碑](https://www.rtx.com/news/news-center/2024/04/08/rtxs-raytheon-completes-critical-milestone-for-viirs-program)

这里仅使用该日期的业务与应用事实，不把旧产品页上的在轨数量当 2026 状态。首个 MVP 不需要包含 VIIRS 硬件模型。

## 四个具体首例候选比较（证据优先）

以下高/中/低是方案取舍判断，并非调查评分。三人可做度以“真实 SysML 工具、真实 Agent 调用、可验证模型级闭环”计，不包含适航或实体飞机交付。

| 候选 | 具体变更故事 | 业务贴合 | 与 maritime brief 关系 | 三人可做度 | 可公开输入与关键不足 | 独立可验证约束 |
| --- | --- | --- | --- | --- | --- | --- |
| **A. 多平台观测数据子系统（marine 默认）** | 在已有平台增加/替换观测或记录功能，比较两个集成候选；可含岸、海、空节点 | 高：跨业务传感、计算与系统集成 | **最高：直接服务 brief** | **高，默认首例** | 通用产品资料可做开放测试；真实平台预算、消息字段和批准理由需受控包 | 类型与单位、接口方向、链路容量、记录存储、功率、原需求保留 |
| **B. 航电设备舱计算设备换代** | 新处理器满足软件资源要求，但增加热耗；比较更换电源支路/冷却方案 | 很高：Collins 设备与系统集成 | 中：可迁移为海上平台设备舱，任务层联系较弱 | 高；适合作为 A 的内部技术切片 | 公开计算平台/配电/冷却架构丰富；真实机型容量与接口经常需合作方资料 | 峰值/稳态功率、热耗与条件、资源容量、端口兼容、安装包络、故障状态需求追溯 |
| **C. 发动机健康监测数据链升级** | 新增传感通道或提高采样率，重新分配采集、机载存储和地面上传职责 | 高：Pratt FAST/EngineWise、Collins Ascentia | 中偏低：共享传感数据链，偏离系统发现主例 | 中 | 公开业务说明充足；有效通道定义、真实时间序列及故障标签可能依赖内部数据 | 采样/时间戳契约、吞吐与存储、断连缓存、单位、数据完整性、保留周期；不承诺故障预测准确率 |
| **D. 制造检验工站/数字工厂接口变更** | 检验设备或工站替换后，更新生产事件、质量证据、系统接口和需求 | 高：近期 Raytheon 招聘直接对应 | 中低：可复用系统工程底座，但偏离 maritime 原例 | 中：有现成 sandbox 才适合首例 | 公开资料能证明方向；工站模型、SAP/MES 契约、gold reference 需合作方提供 | 事件与数据契约、状态/接口一致、配置版本、需求追溯、检查证据完整性 |

**默认 A，并按真实历史工件完整度重新排序。** 若合作方可立即提供 B、C 或 D 的完整变更包、独立检查和 reviewer，且认可它对 brief 的代表性，则可前置。完整混合电推进只作长期愿景。平台边界与选择标准不变：能真实复现一次系统工程变更，比题目外观更重要。

## 建议的三人 MVP 截止线

以“一个已批准的子系统基线 + 一个真实历史变更 + 两个候选 + 独立检查 + 人工评审 + 重开复现”为验收。

- 模型规模建议：约 15–25 条需求、20–40 个有用元素/部件、3 份供应方或专业域输入包；数目是初始控制范围，不是 KPI。
- 涵盖三个视角：任务/功能链、逻辑接口、物理设备与资源。顶层平台只提供边界与可分配预算。
- 第一变更：新增/替换记录或观测设备。第二变更：提高数据率/工作时长。第三负例：一个接口或余量不满足，系统必须拒绝宣称通过并保留失败证据。
- 结果必须是能在固定 SysML v2 工具中加载的完整工程；关系图从工具解析结果生成。独立计算器从同一模型 revision 取值。
- 模型、源资料、需求定位、toolchain、Agent 运行、候选、检查、审批、派生索引都落盘，关闭重开可复现。
- 约束至少包括引用/类型、接口方向、物理量单位、所选案例的功率/数据率/存储、需求保留、版本与索引一致；热、质量及安装包络只在有数据和模型支持时加入。未知参数输出 UNKNOWN/需证据，不自动置零。
- 展示平台上下文→点开新增设备→看受影响需求/接口/资源→失败候选→修改后检查→人工选择→导出可加载工程。UI 展示应服务可验证闭环。

三人分工建议：A 负责 SysML 工具链、领域模型与检查器；B 负责文件/版本/工作流及 Agent 工具；C 负责输入资料/benchmark、评测和可视化。由合作方系统工程师定期核对 baseline、ICD 与判断依据，团队内部保留代码/模型交叉审查。时间取决于资料完整度，宜按 8–12 周的单闭环计划，而不是承诺在同一阶段完成四个领域。

## 用已有 RTX 支持拿到什么

无需一开始索取全公司的数据。首个受控数据包有五类即可：

1. 一个边界明确的已批准子系统 baseline，包含需求及接口。
2. 一个已完成的真实 change request，及当时工程师接受/拒绝的理由。
3. 该子系统涉及的 2–3 个供应/专业域模型或 ICD；不能只有营销 brochure。
4. 现有独立规则、计算工具或受控验证结果，用作 gold reference。
5. 能对工具输出作判断的系统工程 reviewer；如果 DISCOVER 可用，再提供其接口契约。

访问权限让这些材料更容易得到，但不能把“有权限”写成“数据/接口已经接通”。先把一个真实工程师审过的变更复现出来，商业说服力会高于演示许多未验证飞机组件。

## 与海事 brief 的桥接边界

保留统一的上层模型：任务需求→平台分配→传感/计算/通信/能源功能→接口契约→验证证据。第一套默认从 marine brief 取有代表性的观测数据链；后续可增加民用航空搜救/环境观测节点，由船或岸端接收带时间戳的数据。第二套小数据集换平台边界和预算，复用 Agent 工具、模型映射、版本流程和检查框架。

这种复用能证明“跨平台系统工程”，但民用搜救/环境监测不能自动等同原 brief 全部 maritime ISR 要求；应由 sponsor 确认代表性与验收映射。这里不实现军事识别、打击任务、飞行路径控制，也不声称覆盖整架飞机适航。

## 可用于对外说明的一句话

“我们先在一个真实子系统变更上，证明 AI 能把需求和供应商资料转成可加载、可验证、可追溯的 SysML v2 工程，并把每次变更对接口、资源和验证的影响交给工程师审查；同一基础设施随后在 RTX 不同业务场景复用。”

这句话是建议的项目定位，不是对 RTX 当前采购意向或内部痛点的已证实陈述。

## 何时应改变推荐：明确反证条件

1. **工件反证：**marine 只有演示资料，航空/MRO/制造已有完整受控历史包与 reviewer，则优先后者，并让 sponsor 确认代表性。
2. **重复建设反证：**DISCOVER 或既有 MBSE 平台已经完整支持文档映射、模型更新和追溯审批，则缩小为它缺少的适配器、转换器或评测。
3. **瓶颈反证：**工程师主要时间花在物理仿真、故障建模或数据清洗，SysML 维护不是关键成本，则调整工作流与指标，不能为了生成 SysML 制造需求。
4. **工具链反证：**真实基线是旧格式而短期无法可靠转换，则把受控迁移与转换验证列为首版核心，减少 Agent/UI 功能，不能用伪 SysML 冒充交付。
5. **验收反证：**sponsor 只认可 maritime 原例，则按它验收，飞机仅作迁移愿景，不替代 brief。

在现有证据下同意主报告路线。第一例具体哪个业务最有价值仍是条件判断；最有效的下一步是复现工程师实际做过的一件变更，测量遗漏、错误建议、人工修改量与审查时间。
