# SysML-AgentBench 完整执行计划

**项目**：Agentic AI for Systems Engineering Discovery and Design（RTRC / UConn Senior Design）
**版本**：v1.0，2026-10-02
**状态**：执行计划。本文件是团队唯一的"做什么、怎么做、何时做完"的权威来源；改动须记入第 16 节决策记录。
**上游依据**：`research/source-extracts/rtx-brief.txt`（赞助方 brief 原文）；与 Prof. Bollas 的首次会议纪要（2026-10）。
**与既有工作的关系**：保留 `mvp/toolchain/`、`mvp/engine.py` 的校验与工程检查、证据包纪律；放弃 Workbench 作为产品的定位，改为评分器与单次运行查看器。原因见第 16 节。

---

## 0. 一句话

搭一个"考场"：出一套海事 ISR 的系统工程题，让几种 AI agent 来做（需求→SysML v2、改模型、读模型、发现需求缺陷、模型→需求反向生成），用官方 SysML v2 工具与独立工程检查当阅卷器，人做最终裁决，最后告诉 RTRC：**现在的 AI 能做到哪一步、哪种做法最好、哪里不能信、下一步投什么。**

---

## 1. Word 文档的问题与本项目的回答

### 1.1 四个核心问题

| # | brief 原文 | 大白话 | 产出答案的环节 |
|---|---|---|---|
| Q1 可行性 | how requirements can be automatically translated into SysML v2 / feasibility, performance | AI 能不能把需求文字变成能用的 SysML v2？到什么程度？ | 生成类题目得分 |
| Q2 最佳做法 | what workflows or architectures are most effective | 直接写 / 工具挑错再改 / 先列提纲 / 带资料写 / 现成 coding agent——哪种最好？ | 同一模型 × 5 种配置对比，按算力归一 |
| Q3 可靠性与局限 | reliably applied / limitations | 哪里会错？会不会"看着对其实错"？第二个 AI 校验靠谱吗？模型翻回需求还对吗？ | 失败分类、误通过率、校验器一致率、round-trip 一致率、运行方差 |
| Q4 建议 | recommended next steps | RTRC 该怎么用、哪些必须人管、下一步投什么 | 报告建议章节 |

### 1.2 覆盖矩阵（验收用）

| brief 条目 | 交付物 | 验收证据 |
|---|---|---|
| benchmark AI agents … requirements → SysML v2 | 24 题冻结题库；≥4 配置；本地模型 ×3 次 + 前沿模型 ×1 次 | Inspect 日志 + 结果表 |
| first evidence-based evaluation（限定：多平台任务 × 工程语义 × 受控修改 × round-trip × 人工决策门） | 评测报告 D4 | 报告 + 归档运行 |
| generating system requirements and design concepts（背景） | T5 需求侧题（PURE 抽取、歧义检测）；修改题中的候选方案 | T5 结果 |
| interpreting system models（背景） | T2 读模型题 | T2 结果 |
| maritime ISR：多平台、多传感模态、协同信息共享 | 合成 ISR 参考模型包 D6（4 平台） | 可加载 .sysml + 题库 |
| 三篇指定论文 | 第 3 节：三篇各成为一个零件 | 文献章节 + 配置设计 |
| PURE / SysEngBench | PURE → T5 原文；SysEngBench → 模型知识诊断附录 | 结果 + 许可登记 |
| 活动 (5) 优化 agent 工作流 | P0–P3 消融 | Q2 数据 |
| 活动 (6) benchmark 测试 agent | 整个项目 | — |
| 活动 (9) 需求一致性/完整性/设计-模型对齐仿真 | 工程检查 + 歧义题 + round-trip | Q3 数据 |
| Interoperability | 官方 pilot vs Syside/Cameo 判定一致性；UMAA 风格接口题 | 分歧矩阵 |
| Reliability & dependability | 运行方差；失败分类 | Q3 数据 |
| Safety | 审批门实现 + 测试证明 agent 调不动；STPA 库 2 条 hazard | 测试 + 模型 |
| 无 EAR/ITAR、无 NDA | 全部公开/合成；`datasets/SOURCES.md` 登记许可 | 文件 |
| Bollas 全链路（需求→模型→AI 校验→反向需求） | 环节 ②④⑤ | A4 结果 |

---

## 2. 系统架构（7 个环节）

```
 ①题库                 ②被测 agent（考生）                 ③工具箱（所有考生同一套）
 海事 ISR 场景     ┌── 自建工作流 P0/P1/P2/P3 (LangGraph) ──┐   validate  官方 SysML v2 校验
 24 道题        →  │                                        │ → check     工程检查（单位/接口/预算）
 每题有断言        └── 现成 agent：OpenCode / Claude Code ───┘   diff/query 模型差异/查询
                                   │                            （MCP server 暴露）
                                   ▼
                      ④第二个 AI：校验器 + 反向翻译器（被评测对象，不是裁判）
                                   │
                                   ▼
                      ⑤阅卷（Inspect AI）：工具判定 + 断言 + 校验器一致率 + 人工抽审
                                   │
                      ⑥人工审批门：需求取舍类决定，agent 只能提议
                                   │
                                   ▼
                      ⑦记录与报告：runs/ 证据包；Studio / Inspect View / Workbench 页面；STATUS.md
```

设计原则（继承自既有 MVP）：检查只读解析后模型；SysML PASS ≠ 工程验收；需求决策人持有；gold 对运行进程不可见；全部数据合成/公开。

---

## 3. 三篇指定论文的使用

| 论文 | 原文做了什么 | 用在哪 | 作用 | 我们补什么 |
|---|---|---|---|---|
| **P1** Li/Husung/Wang, *LLM-Assisted Semantic Alignment and Integration in Collaborative MBSE Using SysML v2*, ISSE 2025 (arXiv 2508.16181) | 七阶段：抽元素→LLM 提映射→人审→独立对齐包，不改源模型 | T3 修改/对齐题（无人机雷达 ICD vs 指挥舰融合接口）；审批门设计 | "保留源模型 + 独立对齐包 + 人审"的方法论依据 | 原文 1 案例无统计；我们 4–5 题 × 3 次量化映射正确率；用官方校验器替代 LLM 自检 |
| **P2** Bader et al., *Integrating SysML v2 into a GRAG LLM Pipeline*, ISSE 2025 | API→RDF 图→一跳邻居→向量检索→GPT；3 问检索 F1 0.904 | P3 配置（检索增强）；T2 读模型题对照 | "结构化检索喂上下文"的方法 | 原文只测检索不测生成；重实现并绑定模型版本；文本 vs 图检索对比 |
| **P3** Longshore/Bell/Madachy, *Leveraging Generative AI to Create, Modify, and Query MBSE Models*, NPS SYM-AM-24-048/138 | 自行车模型；规范+模板+示例；人工纠错迭代；创建/修改/查询三类 | P1/P2 配置设计（示例增强 + 工具反馈纠错）；题型三分法；SysEngBench 同团队 | "示例 + 迭代纠错"最早证据；题型框架；其"未来工作"即本项目 | 玩具案例→24 题统计；人工纠错→官方工具自动反馈 |

---

## 4. 场景规格：合成海事 ISR 参考模型（D6）

**所有数值均为合成，标注 `synthetic`，不代表任何 RTX 规格。首次赞助方会议后按 Francesca 的用例调整边界；题型不变。**

### 4.1 平台与节点

| 节点 | 传感/功能 | 关键约束（合成） |
|---|---|---|
| USV（无人水面艇） | EO 相机、红外相机、AIS 接收 | 功率上限 60 W；上行 8 Mbit/s；本地存储 128 GB；8 h 任务 |
| UAV（固定翼无人机） | 海面搜索雷达、EO | 功率上限 120 W；下行 20 Mbit/s；2 h 续航 |
| 指挥舰（有人） | 航迹融合、任务指挥 | 融合时延 ≤ 2 s；可接 2 条上行 |
| 岸站 | 中继、存档 | 回传链路 50 Mbit/s；存档 30 天 |

### 4.2 共享的信息流

航迹（目标 ID、位置、速度、置信度、时间戳）；任务指令；健康状态。每条流有：源、宿、速率、时延要求、优先级、丢失策略。接口词汇参考 UMAA 6.0 ICD（Sensor & Effector Management、Situational Awareness、Communications）的公开定义；功能分解参考 NPS 公开报告（detect / correlate / track / relay）。

### 4.3 建模范围

需求 20–25 条（含 2 条 STPA hazard，使用 DLR 开源 SysML v2 STPA 库）；部件 12–15；端口/接口定义 8–10；连接 15–20；数值约束 5（带宽 ×2、功率 ×2、存储 ×1）；satisfy/verify 关联；至少 3 个文件（需求 / 结构 / 接口），验证跨文件引用。

### 4.4 MVP-0 子场景（第 1–2 周）

仅 USV + 岸站；EO + AIS；一条上行。需求 10–12 条；部件 5–8。

---

## 5. 题库规格（D2）

### 5.1 分布（24 题，封存；另 8 题开发集）

| 类型 | 代号 | 数量 | 说明 |
|---|---|---|---|
| 生成 | GEN | 5 | 需求 + ICD 节选 → 新建模型（含 1 题跨文件） |
| 修改 | MOD | 5 | 基线模型 + 变更 → patch；含 1 题对齐（论文 1） |
| 读模型 | QRY | 5 | 结构/追溯问题，答案为确切 ID 集合或数值 |
| 歧义/缺信息 | AMB | 4 | 缺阈值、单位不一致、冲突需求；正确行为是询问或显式标注假设 |
| round-trip | RT | 5 | 模型 → 人类可读需求 → 与原文比对 |

开发集 8 题（每类 1–2 题）供调试提示词；封存集 24 题在第 4 周冻结后，运行进程不可见。

### 5.2 题目目录格式

```
bench/tasks/t4_maritime_isr/heldout/<case-id>/
  case.yaml            # id, type, scenario_family, source, license, frozen_at, difficulty
  input/
    requirements.md    # 原文（不可变），每条需求带 ID 与 span
    icd_excerpt.md     # 接口节选（可选）
    baseline/*.sysml   # MOD/QRY/RT 题的起始模型
  gold/
    assertions.yaml    # 见 5.3
    trace-links.json   # 需求 ID → 预期模型元素 → 验证项
    ambiguities.yaml   # AMB 题：必须询问的点；允许显式声明的假设
    review.json        # 双人评审记录与仲裁
```

### 5.3 断言格式（gold/assertions.yaml）

```yaml
must_exist:              # 必须出现的元素/关系（允许命名变体，匹配按类型+角色+关系）
  - kind: part_usage
    role: thermal_camera
    typed_by_any: [Camera, Sensor]
  - kind: connection
    from_role: thermal_camera
    to_role: processor
  - kind: attribute
    owner_role: thermal_camera
    name_any: [power, powerDraw]
    unit: SI::W
must_preserve:           # MOD 题：不许动的
  - element_id: USV::aisReceiver
  - requirement_id: R-07
must_not_add:            # 不许凭空出现的假设
  - kind: attribute_change
    target: powerLimit
checks_expected:         # 工程检查的预期结果
  - id: R-POWER-001
    status: PASS
  - id: R-UPLINK-001
    status: FAIL          # 题目设计为超限，agent 应如实报出而非改需求
should_ask:              # AMB 题
  - about: track_update_rate
decision_required: true  # 是否触发审批门
```

### 5.4 MVP-0 的 5 道题（草稿）

| ID | 类型 | 题面摘要 | 核心断言 |
|---|---|---|---|
| GEN-01 | GEN | 根据 6 条需求 + 上行 ICD 节选，建 USV 的 EO 相机→处理器→无线电→岸站数据链 | 4 部件、3 连接、带宽属性含单位、R-01..R-06 各有 requirement |
| GEN-02 | GEN | 同上，但需求里加 AIS 接收并要求"航迹与影像时间戳对齐" | 增加 AIS 部件与时间同步约束；不许把"对齐"实现成删除某条流 |
| MOD-01 | MOD | 给基线模型，加热成像相机（12 W），功率上限不变 | 新部件 + 连接；功率 56/60 PASS；上行 9.6/8 FAIL 如实报出；AIS 未动；触发审批门（降帧提议） |
| QRY-01 | QRY | 哪些部件的数据最终到达岸站？经过几跳？ | 确切 ID 集合 + 跳数 |
| AMB-01 | AMB | "航迹要实时共享给岸站"，未给时延与带宽 | 应询问时延/带宽或显式标注假设；不许自行填数 |

### 5.5 外部公开数据的使用（降级为校准与种子）

| 数据 | 用途 | 许可 |
|---|---|---|
| SysMBench 151 prompt（经 cmuchancel 仓库再发布） | 抽 15 题作 T0 管线校准：若我们 P1 合规率远低于文献 51%→100%，说明管线有 bug | 仓库未声明许可；使用前邮件确认 |
| cmuchancel 439 个失败样本（带诊断） | 失败分类法的种子 | 同上 |
| PURE 2–3 份文档（传感/通信类） | T5 需求侧题原文 | 逐文档登记来源 |
| SysEngBench | 模型知识诊断附录 | MIT |
| 官方 SysML-v2-Release 示例 | few-shot 示例池（仅开发集） | EPL-2.0 |
| DLR STPA 库 | 场景中的 hazard 建模 | 见仓库 |
| UMAA 6.0 ICD、NPS 报告 | 场景词汇与接口参考 | 公开 Distro A |

其余（rohhaiil 修复集、nomograph 读模型集、Apollo 11）**不进主线**；有余力再作扩展。

---

## 6. 被测配置（D4）

### 6.1 自建工作流（LangGraph）

同一张状态图，按配置开关节点：

```
[read_task] → [retrieve](P3) → [outline_json](P2,P3) → [write_sysml]
   → [validate] → errors && round<3 ? ──yes──► [feed_back_diagnostics] → [write_sysml]
                                   └──no───► [check] → decision_needed ? ──yes──► interrupt()  ⏸
                                                                      └──no───► [submit]
```

| 配置 | 开启节点 | 测什么 |
|---|---|---|
| P0 | write → validate → check → submit（无修复环） | 裸能力 |
| P1 | + 修复环（≤3 轮） | 工具反馈的价值 |
| P2 | + outline_json | 结构化中间表示的价值 |
| P3 | + retrieve（文本检索 vs 图检索两个子配置） | 检索的价值；论文 2 的方法 |

实现要点：
- 工具参数用 Pydantic 模型定义，LLM 只能提交 schema 内的 patch
- checkpointer：SQLite（`runs/checkpoints.db`）
- `interrupt()` 作为审批门；测试用例 `test_agent_cannot_self_approve`
- 预算：每次运行 token 上限（默认 60k）+ 每日总额（env `BENCH_DAILY_TOKEN_CAP`），超限即停并记录
- `graph.get_graph().draw_mermaid()` 输出到 `docs/workflow.mmd`
- `langgraph dev` + `LANGSMITH_TRACING=false` 供开会演示
- **备选**：若第 2 周演示后确认不需要实时流程图，可用纯 Python（扩展 `mvp/agent.py`）实现同一张图；工具层不变

### 6.2 现成 coding agent

| | OpenCode（主对照） | Claude Code（可选） |
|---|---|---|
| 版本 | `npm i -g opencode-ai@<pin>`，写入 run manifest | 手动安装并记录版本；注意自动更新与闭源 |
| 模型 | `opencode.json` Ollama provider，`qwen3.5:27b-64k` Modelfile 变体 | `ANTHROPIC_BASE_URL=http://localhost:11434`、`ANTHROPIC_AUTH_TOKEN=ollama` |
| 工具 | `opencode mcp add` 挂我们的 MCP server | 同（MCP） |
| 规则 | `AGENTS.md`（附录 A） | 读 `CLAUDE.md`，同内容 |
| 权限 | `edit: allow`；`bash: ask`；`requirements/` 目录 `deny` | 等价 settings |
| 运行 | `opencode run --model ollama/qwen3.5:27b-64k "<题>"`（Inspect solver 调用） | `claude -p "<题>"` 或 `inspect-swe` |

角色：开箱即用基线。OpenCode ≈ P1 → "RTX 不必自建，接上校验器即可"；OpenCode ≪ P1 → "专门工作流值得投资"。

### 6.3 模型

| 模型 | 用途 | 说明 |
|---|---|---|
| **Qwen 云 API**（阿里云百炼 OpenAI 兼容端点，机器上 claude-code-router 已配置：`qwen3.8-flash` / `qwen3.8-max`） | `flash` 做开发与调试；`max` 做主力被测（全题 ×3） | 便宜、无需本地显存；自建工作流与 OpenCode 直接接 OpenAI 兼容端点，Claude Code 经现有 CCR。**在 run manifest 里记录完整模型名**，实验期间不换版本。端点在中国区（cn-beijing）：本项目数据全部合成/公开，可用；若赞助方要求数据驻留，正式实验改用 RTRC 提供的端点 |
| 1 个前沿模型（RTRC Copilot/Bedrock 或 OpenAI/Anthropic API） | 全题 ×1，验证结论不随模型变 | 预算封顶（估 $50–150） |
| 本地 Ollama（Qwen3.5-27B / 35B-A3B） | **可选**：只在要测"本地 vs 云"差距时安装 | 机器 RTX 4090 24 GB，当前已被其他进程占 15.7 GB；27B dense + 64k 上下文很紧 |

配置：复制仓库根 `.env.example` 为 `.env`（git 忽略），填入密钥。预算护栏 `BENCH_RUN_TOKEN_CAP` / `BENCH_DAILY_TOKEN_CAP` 由 harness 强制。

---

## 7. 工具箱与 MCP（③）

从 `mvp/engine.py` / `mvp/toolchain/validate.py` 抽出纯函数：

| 函数 | 输入 | 输出 | 来源 |
|---|---|---|---|
| `validate(files: list[Path]) -> Diagnostics + SemanticExport` | .sysml 文件 + 库 | 诊断（行/列/级别/消息）、API delta JSON、AST | 现有 `SysMLHeadless` 封装 |
| `check(export, contracts) -> list[CheckResult]` | 解析后导出 + 领域契约 | `R-*/D-*` 各 PASS/FAIL/UNKNOWN，含实际值/限值/单位 | 现有 engine 检查 |
| `diff(old_export, new_export) -> ModelDiff` | 两版导出 | 增删改的命名元素、连接、属性 | 现有 diff.json 逻辑 |
| `query(export, q) -> Answer` | 导出 + 结构化问题 | 确切 ID 集合/数值 | 新增（简单图遍历） |

**必须的改动**：engine 当前只按 `case_name` 渲染模板；新增入口接受任意 `.sysml` 路径与契约文件。其余逻辑不动。

MCP server：`tools/mcp_server.py`（官方 `modelcontextprotocol/python-sdk`），暴露上述 4 个工具，stdio 传输；OpenCode / Claude Code / 自建工作流共用。

---

## 8. 阅卷规格（⑤，Inspect AI）

### 8.1 Task 结构

```python
Task(
  dataset = json_dataset("bench/tasks/.../index.jsonl"),
  solver  = one_of(p0, p1, p2, p3_text, p3_graph, opencode, claude_code),
  scorer  = [toolchain_scorer, assertion_scorer, check_scorer,
             regression_scorer, ambiguity_scorer, roundtrip_scorer,
             validator_agreement_scorer, cost_scorer],
  config  = GenerateConfig(max_tokens=..., temperature=0.2, seed=...)
)
```

### 8.2 指标（分层，不合成总分）

| 层 | 指标 | 定义 |
|---|---|---|
| 语言有效性 | first_pass, pass_at_3, repair_rounds | 官方 pilot 零错误 |
| 结构 | assertion_P/R | must_exist 命中 / 预期总数；多余元素计入 P |
| 需求语义 | req_coverage, unsourced_additions | trace-links 覆盖；must_not_add 违反数 |
| 工程检查 | checks_match | checks_expected 与实际 PASS/FAIL/UNKNOWN 一致 |
| 修改 | target_achieved, preserve_rate, regressions | must_preserve 保持率；新增 FAIL |
| 歧义 | asked_rate, fabricated_value_rate | should_ask 命中；擅自填数 |
| round-trip | rt_recall, rt_precision | 反向需求与原文逐条匹配（断言 + 人审） |
| 校验器 | validator_agreement, validator_false_pass | LLM 校验器 vs 工具+人工 |
| 可靠性 | run_variance | 3 次运行的指标方差 |
| 误通过 | false_pass_count | 设计为不可满足的题被标通过 |
| 成本 | tokens, calls, latency_p50/p95, usd | 按配置、按题 |
| 完整性 | reproducible | 从归档重跑 scorer 结果一致 |

### 8.3 统计

- 单位是"题 × 配置 × 模型"，重复 3 次报均值与范围
- 按题型分组报；按场景族做 bootstrap 区间；不把同一场景的题当独立样本
- 算力归一：报告每千 token 的 pass/assertion 收益曲线
- 人工评审：每类抽 2 题 × 全部配置，两人盲评，报 Cohen's κ；写 gold 的人不评自己题

### 8.4 LLM 校验器（④）协议

固定提示词；输入 = 需求 + 生成模型（文本）；输出 = 每条需求 satisfied / partial / missing + 理由。与 `check` 和人工判定逐条比较。它的输出**不参与**任何得分，只产出一致率。

---

## 9. 实验协议

1. 第 4 周末冻结：封存 24 题、断言、评分代码、提示词、工具链版本、模型版本；写 `bench/FREEZE.md` 并 git tag
2. 预注册目标值（写入 FREEZE.md，之后不改）：如 P1 pass_at_3 ≥ 80%、false_pass = 0、preserve_rate ≥ 95%
3. 防泄漏：gold 目录仅 scorer 进程挂载；检索索引、few-shot、AGENTS.md 不含封存题任何内容；记录检索命中 chunk 哈希
4. 预算：每次运行 token 上限；每日总额；前沿模型总额上限写入 FREEZE.md
5. 顺序：开发集调试 → 冻结 → 本地模型全量 ×3 → 前沿模型 ×1 → 现成 agent → 人工评审 → 分析
6. 复现：第 10 周在干净机器上 `bootstrap` + 重跑 scorer，结果须一致
7. 版本：OpenCode/Claude Code 版本、Ollama 版本、模型 digest 全部进 run manifest

---

## 10. 可视化与同步（⑦）

| 页面 | 工具 | 回答 |
|---|---|---|
| 流程图 + 实时运行 | LangGraph Studio（`langgraph dev`，tracing off） | 工作流长什么样、跑到哪、每步看见什么 |
| 评测结果 | `inspect view --log-dir runs/inspect` | 跑了多少、哪些过、哪种配置好、花了多少 |
| 单次运行放大镜 | 现有 Workbench 页面（`python3 -m mvp.app`，`?run=<id>`） | 某次运行的拓扑、来源哈希、证据 ZIP |
| 一页状态板 | `scripts/make_status.py` → `STATUS.md`（samples_df 生成） | 本周数据点、各层指标、失败分类、累计费用 |
| 决策记录 | `docs/decisions/NNN-*.md` | 为什么这样选 |

会议模板（10 分钟）：STATUS 2 分钟 → 现场点开一个失败运行 3 分钟 → 决策/阻塞 5 分钟。

---

## 11. 仓库结构（目标态）

```
RTX agent/
  README.md
  STATUS.md                      # 自动生成
  mvp/                           # 保留：toolchain/, engine.py, reopen.py, verification/, app/(查看器)
  tools/                         # validate / check / diff / query 纯函数 + mcp_server.py
  agents/
    graph.py                     # LangGraph 状态图；配置开关
    prompts/                     # 版本化提示词（哈希进 manifest）
    approvals.py                 # interrupt 审批门
    external/                    # OpenCode / Claude Code 适配（AGENTS.md、opencode.json 模板、桥）
  bench/
    tasks/
      t0_calibration/            # SysMBench 15 题
      t4_maritime_isr/{dev,heldout}/
      t5_requirements/           # PURE + round-trip
    scorers/
    inspect_tasks.py
    FREEZE.md
  scenario/                      # D6：海事 ISR 参考模型包（.sysml ×3+，需求，ICD 节选，synthetic 声明）
  datasets/
    SOURCES.md                   # 外部数据：来源、日期、SHA-256、许可、用途
  runs/                          # Inspect 日志、checkpoints.db、证据包
  analysis/                      # 出图脚本、失败标注表
  docs/
    workflow.mmd
    failure_taxonomy.md
    decisions/
    report/                      # D4
  plans/                         # 本文件、项目书
  research/                      # 既有文献与审计（只读保留）
```

首次 `git commit` 在第 1 周第 1 天完成（当前仓库 0 次提交）。

---

## 12. 十二周逐周计划

三人：**A** 场景/SysML/领域 gold；**B** 工具箱/评分器/基础设施；**C** agent/实验/分析。每周五各自更新 STATUS。

| 周 | A（场景与 gold） | B（工具与评分） | C（agent 与实验） | 周末验收 |
|---|---|---|---|---|
| **1** | 写 MVP-0 子场景（USV+岸站）10 条需求 + 基线 .sysml，官方校验通过 | git 初始化；抽出 `validate/check/diff` 为纯函数；engine 接受任意 .sysml 路径 | 本地 Ollama + Qwen3.5 跑通（64k Modelfile，`tools` 能力确认）；P0 用纯 Python 写出 | `validate` 能判 agent 生成的文件；P0 在 GEN-01 上有输出 |
| **2** | 写 MVP-0 的 5 道题 + 断言；STPA 库试加载 | Inspect Task 骨架；toolchain_scorer + assertion_scorer；MCP server | P1（修复环）；OpenCode pin + AGENTS.md + MCP 接通；5 题各跑一次 | **给 Bollas 演示**：Inspect View 看 P0 vs P1 vs OpenCode 在 5 题上的差异 |
| **3** | 完整 4 平台场景；GEN/MOD 各 5 题草稿；与 Francesca 会议后调整边界 | check_scorer、regression_scorer；STATUS 脚本 | LangGraph 版状态图（若需要）；P2 outline_json；预算护栏 | 10 题在 P0/P1/P2 跑通 |
| **4** | QRY/AMB/RT 题；24 题全部断言；双人评审 | ambiguity/roundtrip/validator_agreement scorer | AI 校验器 + 反向翻译器；T0 校准 15 题 | **冻结**：FREEZE.md + git tag；预注册目标值 |
| **5** | T5：PURE 2 份文档选段 + 需求抽取 gold | 官方 pilot vs 第二检查器交叉判定脚本。候选：Syside `syside check`（**CLI 在付费 Modeler 内，免费版仅 VS Code 编辑器**；用 30 天试用窗口覆盖第 5–8 周，或申请学术许可）；Cameo SysML v2 CE（免费，GUI 校验，自动化待验证） | P3 文本检索；前沿模型接入与预算配置 | 开发集全配置跑通 |
| **6** | STPA 2 条 hazard 入场景；SysEngBench 附录脚本 | 人工评审表单与盲评流程 | P3 图检索（论文 2 方法重实现）；Claude Code 适配（可选） | 全配置在开发集完成 |
| **7** | 人工评审第一轮（与 C 交叉） | 运行监控与失败落盘 | **全量实验**：本地模型 24 题 × 6 配置 × 3 次 | 本地模型数据齐 |
| **8** | 人工评审第二轮；κ 计算 | 现成 agent 运行桥稳定性 | 前沿模型 ×1；OpenCode/Claude Code 全题 | **主实验完成**；数据冻结 |
| **9** | 失败样本标注 50 个 | 干净机器复现（bootstrap + 重跑 scorer） | 失败样本标注 50 个；失败分类表 | 复现一致；100 个失败已分类 |
| **10** | 海事 ISR 演示脚本（MOD-01 全链路：修复→审批门→round-trip） | STATUS 终版；图表 | 消融分析；算力归一曲线；校验器一致率 | 演示可跑；全部图表出 |
| **11** | 报告：场景、局限、建议 | 报告：方法、复现、工具 | 报告：结果、失败分析 | 报告初稿 |
| **12** | 终稿、知识库写法；赞助方评审 | 交付包打包 | 演示彩排 | **D1–D6 交付** |

---

## 13. 风险与对策

| 风险 | 对策 |
|---|---|
| 前沿模型端点迟迟不到 | 第 1 周起全用本地模型；前沿模型只需第 8 周前到位；换端点只改 env |
| GPU 显存不够 27B | 用 Qwen3.5-35B-A3B（激活 3B）；仍不够则 8B + 云端前沿模型承担主结果 |
| 24 题 gold 标注量超预期 | 24 是下限；宁可 20 题干净也不要 30 题含糊；第 4 周冻结是硬日期 |
| Francesca 的用例与海事默认差别大 | 题型不变，只换场景数据；第 3 周留出调整时间 |
| 本地模型在 SysML v2 上太弱、全部失败 | 这本身是 Q1 的结论；同时用前沿模型给出上界 |
| 多 agent/检索没优势 | 照实报告；正是 Q2 的答案 |
| 外部数据许可不明 | 不进主线；主线只用自建 + 官方 EPL + PURE 登记 |
| 现成 agent 版本漂移 | pin 版本；manifest 记录；报告只声明该版本行为 |
| API 费用失控 | 每次运行与每日硬上限；STATUS 显示累计费用 |
| 导师坚持 Langflow | 第 2 周用 Studio + Inspect View 演示可见性；仍坚持则第 10 周加薄壳 |

---

## 14. 诚实声明（写进报告）

- 海事数值全部合成，不代表 RTX 规格
- SysML 校验 PASS ≠ 工程验收；无证据的工程状态为 UNKNOWN
- 需求决策人持有；agent 不自批
- 公开数据集可能在模型训练语料内；自建题库为"无污染"证据，分开报
- 24 题 × 3 次支撑可行性与失败分析，不支撑跨 RTX 业务泛化
- 现成 agent 内部提示词随版本变；只报告锁定版本
- "first evidence-based evaluation" 限定于：多平台任务 × 工程语义评分 × 受控修改 × round-trip × 人工决策门

---

## 15. 待确认事项

**Francesca（首次会议）**：
1. 是否有可公开/可脱敏的海事 ISR 场景描述、需求样例或 SysML（v1/v2）模型作为种子？
2. 场景边界：几个平台、哪些传感模态、信息共享粒度？
3. 更看重"从零生成"还是"修改已有模型"？
4. 可用模型端点（Copilot / Bedrock）与预算？
5. 评测结果由谁签认？

**Bollas**：
6. Cameo 许可版本是否含 SysML v2 插件？——补充（2026-10-02 核实）：Dassault 已发布**免费的 CATIA Magic/Cameo SysML v2 Community Edition**（2026x），含文本编辑器 + 评估插件 + 图形/文本双向同步；无论学校许可如何，第 2 周先装 CE 做图形查看与人工校验对照；无头批量校验未见官方文档（TWC REST API 需服务器），自动化路径待验证（社区 `cameo-mcp-bridge`，MIT，162 工具，需 Cameo 运行中）。
7. 评分导师最终确认（Prof. Kubita）。

**团队内部**：
8. ~~GPU 显存~~ → 已查：RTX 4090 24 GB；主力改用 Qwen 云 API，本地模型降为可选（决策 011）。
9. LangGraph vs 纯 Python（第 2 周演示后定）。

---

## 16. 决策记录

| # | 决定 | 理由 | 日期 |
|---|---|---|---|
| 001 | 项目重心从"升级工作台产品"转为"agent 评测台" | brief 核心交付是 benchmark/evaluation；原 MVP 零 LLM 运行、零实验 | 2026-10-02 |
| 002 | 保留官方工具链封装、工程检查、证据包；放弃 Workbench 产品定位 | 工具层是最难搭且正确的部分，直接成为评分器 | 2026-10-02 |
| 003 | 不采用 Langflow 作系统组件 | 搭建器非评测器；无原生审批门与可观测性；双实现分叉破坏证据纪律；导师的"可见性"需求由 Studio + Inspect View 满足 | 2026-10-02 |
| 004 | agent 层用 LangGraph（备选纯 Python），不用 Pydantic AI | 开会可视化成为优先级；Studio 本地免费、tracing 可关；Pydantic AI 无实时画布（Logfire 闭源托管） | 2026-10-02 |
| 005 | 现成 agent 对照以 OpenCode 为主，Claude Code 可选 | OpenCode MIT 可 pin 可读源码；Claude Code 闭源自动更新 | 2026-10-02 |
| 006 | 外部 benchmark 降为校准与种子，不进主线 | 与海事多平台无关、无工程语义；主线是自建题库 | 2026-10-02 |
| 007 | 评测框架用 Inspect AI | 任务/评分/日志/外部 agent 支持最成熟；MIT | 2026-10-02 |
| 008 | 不采用 AutoGen / CrewAI / Swarm / AutoGPT | AutoGen 已停更；CrewAI 多角色无证据优势且难控；其余不相关 | 2026-10-02 |
| 009 | 项目书"no evidence-based evaluation exists"改为限定表述 | SysMBench 2025、CMU 2026、RADIANT 2026 已存在 | 2026-10-02 |
| 010 | 仓库根迁至 `/data/robotics/RTRC`；原目录只读归档；`vendor/` 符号链接 | 沙盒可写、空间大、git 从 0 次提交开始 | 2026-10-02 |
| 011 | 主力模型用已配置的 Qwen 云 API（qwen3.8-flash 开发 / qwen3.8-max 实验），本地 Ollama 降为可选 | 便宜、无显存压力、4090 已被占用；数据合成/公开可出站；manifest 记录模型名保证可复现 | 2026-10-02 |
| 012 | 模型可视化用 Cameo SysML v2 Community Edition（免费）为主、SysON 为备；第二检查器优先 Syside CLI（试用/学术许可），Cameo 为备 | Cameo CE 免费且图形/文本双向同步，导师熟悉；Syside 是唯一有 CI 级 CLI 的第二检查器；两者都不替代官方 Pilot 的主裁地位 | 2026-10-02 |

---

## 附录 A：AGENTS.md 草稿（给 OpenCode / Claude Code）

```markdown
# Rules for this SysML v2 modeling task

You are editing SysML v2 textual models (.sysml) for a maritime ISR system.

1. After every edit, run the `validate` tool on all .sysml files and fix reported errors
   before finishing. Do not finish with validation errors.
2. Then run `check`. Report every FAIL verbatim in your final answer. Do NOT change
   requirement values (limits, rates, budgets) to make a check pass.
3. Files under `requirements/` are read-only source requirements. Never modify them.
4. If the task is ambiguous or a required value is missing, stop and ask; do not invent
   a number. If you must assume, state the assumption explicitly in a comment.
5. If a requirement must be relaxed or replaced to satisfy constraints, propose it and
   stop. A human must approve it. Do not apply it yourself.
6. Keep unrelated model elements unchanged. Minimal diffs.
7. All physical quantities must carry SI units from the standard library (e.g., SI::W).
8. Final answer: list files changed, validation status, check results, assumptions,
   and any open questions.
```

## 附录 B：外部数据来源表（`datasets/SOURCES.md` 初稿）

| 名称 | 来源 | 日期 | 许可 | 用途 | 状态 |
|---|---|---|---|---|---|
| SysML-v2-Release examples + library | github.com/Systems-Modeling/SysML-v2-Release @ 2026-08 | 2026 | EPL-2.0 | 工具链库；few-shot 池 | 已 pin |
| SysML-v2-Pilot-Implementation 0.62.0 | github.com/Systems-Modeling/SysML-v2-Pilot-Implementation | 2026-08 | EPL-2.0 | 校验器 | 已 pin |
| SysMBench prompts（再发布） | github.com/cmuchancel/NL-to-SysMLv2-via-Conformance-Driven-Refinement | 2026-03 | 未声明 | T0 校准 | 待确认许可 |
| PURE | zenodo.org/records/7118517 | 2018 | 逐文档 | T5 | 待选文档 |
| SysEngBench | huggingface.co/datasets/rabell/SysEngBench | 2025 | MIT | 附录 | 待下载 |
| DLR SysMLv2LibrarySTPA | github.com/DLR-FT/SysMLv2LibrarySTPA | 2024–25 | 见仓库 | 场景 hazard | 待下载 |
| UMAA 6.0 ICDs | auvsi.org（Distro A） | 2023-12/2024 | 公开 | 接口词汇 | 待下载 |
| NASA cFE requirements | 已在 mvp/public-data | — | 已登记 | 需求导入通路原型 | 已有 |
| NPS MDUSV / BlueBoat 报告 | calhoun.nps.edu | 2019 / 2026 | 公开 | 场景参考 | 待下载 |

## 附录 C：文献清单（报告用）

赞助方指定：Li/Husung/Wang 2025（arXiv 2508.16181）；Bader et al. 2025（ISSE）；Longshore/Bell/Madachy 2024（NPS SYM-AM-24-048/138）；Bell/Longshore/Madachy 2024 SysEngBench；Ferrari et al. 2017 PURE。
2025–2026 相关：Jin et al. SysMBench（arXiv 2508.03215）；LaVoie/Topcu/Kara 2026 conformance-driven refinement（arXiv 2607.14162）；RADIANT（arXiv 2607.16708）；SysTemp（arXiv 2506.21608）；Topcu et al. 2026 requirements quality LLM benchmark（arXiv 2609.03230）；ReqElicitGym（arXiv 2602.18306）；VeriMed（arXiv 2605.13817）；单/多 agent 算力归一（arXiv 2604.02460）；CMU SEI 2026 "Native AI Integration for MBSE"；DLR STPA library；AI4MBSE scoping review 2026；LLMs for MDE survey 2026。
