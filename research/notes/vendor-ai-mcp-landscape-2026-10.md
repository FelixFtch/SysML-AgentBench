# SysML v2 工具厂商的 AI / MCP / agent 能力现状（核实日期 2026-10-02）

目的：回答"厂商工具是否已经自带 agent 能力、做到了什么程度、极限在哪"，以决定它们在 SysML-AgentBench 中的角色。来源分三类并分别标注：**官方文档/官方发布**、**厂商员工在社区的演示帖**、**第三方/社区项目与用户反馈**。未亲自运行任何厂商 AI 功能。

## 1. 结论先行

| 厂商 / 工具 | 自带 AI 生成 | 官方 MCP | 社区 MCP | agent 能用的无头接口 | 对我们的可用性 |
|---|---|---|---|---|---|
| **Dassault CATIA Magic / Cameo** | **有**：2026x 内置 AI Assistant（从 stakeholder needs 生成候选架构）+ 3DEXPERIENCE 平台的 LEO Virtual Companion 做分析/精炼 | **有原型/早期可用**："CATIA Magic SysML v2 MCP（基于 Teamwork Cloud REST API）"，Dassault 员工 2025-12 与 2026-02 两次演示；下载链接在社区登录墙后 | `ajhcs/cameo-mcp-bridge`（MIT，162 工具，**仅 v1**）；`jgs-magic-sysmlv2-mcp`（商业） | Teamwork Cloud 的 OMG 标准 REST API（需企业服务器）；桌面端无官方无头校验 CLI | AI Assistant 需 Magic Cyber Systems Engineer / SoS Architect 2026x 许可（CE 是否含**未证实**，大概率不含）；MCP 需 TWC 服务器 → 对本项目**基本不可达**，除非 Bollas 的许可是 2026x 全功能版 |
| **Sensmetry Syside** | 无生成功能；定位"AI 可读可写的模型" | **尚无**；路线图 **2026 Q3 承诺** "Syside & Sysand MCP servers for Claude, Copilot"，截至 10-02 未见发布公告 | 用户自制：把 `syside check` CLI 包成 MCP 或 Claude Code skill（论坛 2026-03/05） | `syside check` CLI、Python Automator API（均在付费 Modeler/Automator 内）；Syside Cloud 预装 Claude Code | CLI 需付费/试用；方法论上与我们一致（检查器在环） |
| **Eclipse SysON（Obeo）** | 原型：2025-05 博客演示 LLM 助手（Mattermost 界面）；企业版定价表 "AI Integration: Soon" | 无 | `Casys-AI/mcp-syson`（MIT，31 工具：编辑、AQL 查询、需求追溯、图、值读写；自托管） | GraphQL / Sirius Web API；SysML v2 标准 API 交换 | 可用（Docker 自托管），作为图形查看与"读模型"工具的备选 |
| **Siemens Systems Modeler for SysML v2** | 未见公开 AI 功能 | 无 | 无 | REST / OSLC | 无许可，不考虑 |
| **OMG 官方 API 服务（pilot）** | — | — | `jgs-sysmlv2-api-mcp`（专有许可，35 工具，分阶段提交、每 agent 会话一个分支；兼容任何 OMG 标准 API 端点，含官方 pilot 与 TWC）；`redsteve/SysML-v2-API-MCP-Server`（MIT，C++） | OMG Systems Modeling API 1.0 REST（我们已克隆 `SysML-v2-API-Services`，未部署） | 可部署；是连接 Cameo TWC / SysON / 官方实现的**标准互操作层** |

**没有任何厂商提供"判断模型在工程语义上对不对"的能力。** 全部 AI/MCP 产物都属于三类：① 让 agent **读写**模型的管道（API/MCP）；② **语法/一致性检查器**（CLI）；③ Dassault 的"生成候选架构 → 人精炼"助手（**无公开评测数据**）。

## 2. 逐家细节

### 2.1 Dassault Systèmes（CATIA Magic / Cameo）

**官方来源**
- 产品矩阵（docs.nomagic.com，2022x–2026x）：`AI Assistant` 行出现在 **Magic Cyber Systems Engineer 2026x / 2026x Refresh1、Magic Systems of Systems Architect、MagicDraw、Cameo Systems Modeler** 下。`SysML v2` 行同样自 2026x 起。
- 网络研讨会 "AI for SysML v2"（events.3ds.com）：演示"内置 AI Assistant 从 stakeholder needs 生成初始候选架构 → LEO Virtual Companion（3DEXPERIENCE 平台）分析并迭代精炼"；议程明确包含"哪里仍需工程判断"。
- 网络研讨会 "Integrating Tools Using AI Within SysML v2"（Daniel Brookshier，OMG 架构委员会成员）：主题是用 **Codex / Claude Code 等现成 coding agent 编写 Cameo 插件与 SysML v2 Open API 脚本**，含 "agents, test harnesses, best practices"。→ Dassault 的姿态：coding agent 当**扩展开发者**，通过 REST API 操作模型。
- SysML v2 Community Edition（免费）：100% 标准一致、文本/图形双向同步、**≤500 主要元素**、面向学习。页面**未提及** AI Assistant。
- Teamwork Cloud：完全符合 OMG SysML v2 API & Services；CI/CD 可创建/查询/评估；另有专有 Model Evaluation 扩展。

**厂商员工社区帖（3DSwym，作者 "SP"）**
- 2025-12-18："SysML v2 Simulation, 3D CAD Result Visualization, and Report Generation using MCP"——MCP 串联仿真、CAD、报告。
- 2026-02-24："Jama MCP + CATIA Magic SysML v2 MCP"——从 SysML v2 仿真抽需求 → 推到 Jama → 生成测试用例 → 回读执行仿真 → 结果写回 Jama。文末："CATIA Magic SysML v2 MCP (TWC REST API based) is available at -"（链接需登录）。
- 另一帖（机械臂数字孪生）明确写 "prototype demo"。

**第三方**
- `ajhcs/cameo-mcp-bridge`（MIT，2026-03 创建，21★，162 工具，Java 插件直连运行中的 Cameo）：原生校验、报告向导、需求导入导出（JSON/CSV）、仿真预览、Teamwork 只读探针。**已知限制**：图布局是主要痛点；不能重新归属元素；无批量操作；纯请求/响应无事件；**"SysML v2 profile support" 列在"欢迎贡献"——即当前仅 v1**。
- `jgsystemsconsulting/jgs-magic-sysmlv2-mcp`：驱动运行中的 Cameo 做 v2，**专有许可**（免费层 + PRO 授权文件）。

**能做到的极限（基于公开信息）**
- 生成：有，但是黑盒（LLM 来源、提示、是否可配置第三方模型均未公开），输出是"候选架构"，官方自己把"人精炼"列为必需步骤；无任何公开成功率/质量数据。
- MCP：真实存在、可用于集成演示（Jama、仿真、CAD），但**绑定 Teamwork Cloud 企业服务器**；桌面 CE 无法使用。
- 无头校验：桌面端无官方 CLI；只能经 TWC API 或社区桥。

### 2.2 Sensmetry（Syside / Sysand）

**官方来源**
- 产品页："With Syside, your AI assistant can read your models and contribute to them."——指通过 CLI/Python API，不是内置生成。
- 路线图 2026 Q1：Syside Cloud "pre-configured with Syside Modeler, Automator, Sysand, **and Claude Code**"，1000+ 用户。
- 路线图 2026 Q2（2026-05-13）：Q3 目标含 "**Syside & Sysand MCP servers** — to make it even easier for AI assistants (Claude, Copilot, etc.) to work with your SysML v2 models"；Syside/Sysand 同步到 v1；Derisker（ISO 26262/21434 安全分析，含 STPA/FMECA/FTA）Q3 公开稳定版。截至 2026-10-02 未检索到 MCP 发布公告。
- 0.9.0（2026-05-10）：需求评估（`assumptions implies requirements`）、ReqIF、标准库 2026-03。
- 许可：Editor 免费（仅 VS Code）；`syside check` CLI 与 Automator 在付费 Solo/Business；30 天试用。

**用户反馈（论坛 "Claude Code / AI Agent Sharing Thread"，2026-03-13 至 05-21）**
- 做法演进：自制 MCP 包 `syside check` → 改为 Claude Code **skill**（减少 JSON 开销）；CLI 二进制在 VS Code 扩展目录 `bundled/syside-cli/bin/`。
- 配合 `nomograph/sysml`（GitLab 团队出品）做模型索引：按名查元素、列相关元素，替代"agent 读一堆文本自己推连接"。
- 用手写 `sysml-patterns.md` 规定建模模式（抽象 part + 多重性、ISQ 属性 `:>` vs `:` 的选择规则等）。
- **核心未解问题（原话）**："defining what counts as 'good' modeling, aside from syntactically correct code… With better way to assess model quality, there could be a subagent write and check loop."——这正是本项目 Q3 与 gold-assertions 要解决的问题。

**极限**：没有生成功能；MCP 未发布；检查器只管语法/语义一致性，不管工程正确性；付费墙。

### 2.3 Obeo（Eclipse SysON）

- 博客 2025-05-12：原型"AI 作为建模助手 / AI 作为模型的自然语言接口"，LLM + SysON + Mattermost；明确"AI 是助手不是决策者"；计划产品化。
- Obeo Enterprise for SysON 定价表：**AI Integration = Soon**（标准版与定制版皆然）。
- 社区 `Casys-AI/mcp-syson`（MIT，31 工具，7 类，含 6 个 MCP App 查看器；Docker 一键）。设计说明值得注意：**删除了早期的 LLM 驱动工具**，理由是"调用方已经是语言模型，再让宿主跑一个模型只增加间接性；生成 SysML 是调用方的事，`syson_element_insert_sysml` 负责写入"。
- 极限：无官方 AI；社区 MCP 面向读写与查询，无校验以外的判断。

### 2.4 Siemens

未检索到 Systems Modeler for SysML v2 的 AI 助手或 MCP 公开信息（2026-10-02）。

### 2.5 标准 API 层（厂商中立）

- `jgs-sysmlv2-api-mcp` v1.0.1/2.0.0：35 工具，分五类（导航读、分阶段写、项目生命周期、分支/标签、基础设施）；写入经 **staged commit + token 确认**；支持"每个 agent 会话一个分支"；提供 Claude Code / Cursor / Codex / Gemini CLI 插件清单；文档含"本地 Docker 运行 OMG 参考 pilot"的配方。专有许可（免费 + PRO）。
- 意义：**OMG 标准 REST API 是唯一同时被官方 pilot、Cameo TWC、SysON 实现的接口**。若部署官方 API 服务，agent 经同一 MCP 可对三种后端做同样操作——这是 Interoperability 维度可测的东西。

## 3. 相关学术工作（同一时期）

- UC3M（e-archivo）"An agent-based approach for the automatic generation of valid SysMLv2 models in industrial contexts"：LLM agent + RAG（检索 SysML v2 代码示例）+ 形式校验引擎的自纠正循环；对比 LLM_Raw / +RAG / +校验配置——与我们 P0/P2/P1 的消融结构同形。
- LangGraph 多 agent 语义校验（14 模型，GPT-4o-mini vs DeepSeek-R1）：两模型在欠规格模型上分歧——印证"LLM 校验器需被评测"。

## 4. 对 SysML-AgentBench 的影响

1. **修正此前判断**："Dassault 只有宣传原型"不准确。Dassault 在 2026x 已把 AI Assistant 做进产品，并有基于 TWC 的 SysML v2 MCP 在内部/早期使用。但两者都在**企业许可与服务器**之后，公开信息不含任何质量数据。
2. **新增可选被测配置 P-VENDOR**：若 Bollas 的许可是 Magic Cyber Systems Engineer 2026x（含 AI Assistant），把它当"厂商黑盒 agent"放进 T4 生成题：用其 AI Assistant 生成 → 导出 .sysml 文本 → 走我们的官方校验 + 断言 + 工程检查。这对 RTRC 价值很高（他们用 Cameo），但要先确认许可条款允许评测与发表。
3. **设计路线被业界印证**：Obeo 社区 MCP "生成是调用方的事，工具只负责读写与查询"；SEI 三层；Sensmetry 用户用 CLI 当裁判——都与我们"工具层确定性、生成与判断分离"一致。
4. **"什么是好模型"无人解决**：Sensmetry 论坛用户、Obeo 博客、Dassault 研讨会都把人工判断列为必需。我们的 gold assertions + 工程语义检查 + 失败分类是对这个空白的直接回答，应在报告里引用这些来源作为需求佐证。
5. **标准 API 作为互操作实验**（可选，第 6 周后）：部署官方 API 服务（已克隆），经 `jgs-sysmlv2-api-mcp` 或自写薄桥，让同一 agent 对"官方 API 后端"操作；若日后拿到 TWC 或 SysON，可复用同一流程比较后端差异。
6. **Syside MCP**：等待 Sensmetry 发布（原定 2026 Q3）；发布后可替代用户自制的 CLI 包装，但判定逻辑不变。

## 5. 待确认

- Bollas 的 Cameo 许可：产品名与版本（是否 Magic Cyber Systems Engineer / SoS Architect 2026x）；是否含 AI Assistant；是否有 Teamwork Cloud；许可条款是否允许评测结果发表。
- Dassault SysML v2 MCP 的实际获取途径（社区登录后链接）与前置条件。
- Sensmetry MCP 是否已发布；学术许可申请。
