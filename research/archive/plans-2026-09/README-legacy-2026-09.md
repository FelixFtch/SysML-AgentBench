# RTX SysML v2 MVP：运行工程与调研资料

本目录保存2026年9月22日的项目审查、公开资料调研，以及随后实现的英文工程工作台。用户原始附件未修改。

**先看可运行项目：[MVP 使用说明](mvp/README.md)。** 从本目录执行 `python3 -m mvp.app`，打开 `http://127.0.0.1:8765`。当前已实现真实 SQLite 导入、官方 SysML v2 解析/语义导出、独立工程检查、变更对比、来源快照和完整工程导出；并接入 NASA 公开需求及官方多文件模型。LLM 工具调用接口已写好，尚未接入用户批准的模型服务，不将其称为已完成的 Agent 端到端验收。

[HTTP 实际运行证据](mvp/app/verification-results.json)与[公开数据说明](mvp/public-data/README.md)记录了真实执行范围。预算可行不等于硬件或系统整体验证成功，工作台保留 UNKNOWN 状态。

从 [主计划](plans/RTX_SysML_v2_MVP_落地计划.md) 开始阅读。它按三人团队组织，区分RTX已公开的事实、需求推断、拟开发功能与验收目标。

需要直接看产品要做成什么，请看 [首个 MVP 的具体产品与演示规格](plans/MVP_具体产品与演示规格.md)：历史系统升级工程台，以海事观测数据网关为首例，列出旧系统接入、候选方案、可见工作区、真实执行边界与开工关口。

配套资料：

- [RTX近期业务与招聘证据](research/notes/rtx-business-fit.md)
- [HTML与源码审查](research/html-audit/HTML_AUDIT_中文.md)
- [前两篇SysML研究核验](research/notes/papers-1-2.md)
- [NPS文献和公开benchmark核验](research/notes/paper-3-benchmarks.md)
- [Jev及agentic memory产品研究](research/notes/agentic-memory.md)
- [历史工程资产与经验复用研究](research/notes/legacy-engineering-memory.md)

`research/inputs/`是三个用户附件的归档副本，[输入清单](research/input-manifest.json)保存原路径、大小和SHA-256。`research/source-extracts/`是文本抽取，`research/paper-artifacts/`是只用于研究的作者公开工件；不要将这些资料直接当作MVP运行依赖或经批准工程数据。

研究阶段执行了输入哈希核对、包清单检查及 [JavaScript内核独立检查](research/html-audit/check_core.cjs)。[结果](research/html-audit/independent-core-checks.json)展示原 HTML 删除模型关系时现有 diff/配置检查的局限。后续新 MVP 已运行真实 SysML 工具及反例验证；原包完整浏览器测试、论文实验和实体硬件未重跑。研究文档中的“尚未实现”保留其成文时状态，当前实现范围以 MVP 使用说明与运行记录为准。

后续已完整克隆官方工具、论文和记忆参考工程，版本与用途见 [reference-projects.json](mvp/reference-projects.json)。实际执行的是固定版本的官方 SysML 工具链；Jev、记忆框架与官方模型 API 服务尚未接入运行。没有注册外部服务、提交 Altari 表单或向这些服务发送用户项目资料。保存的外部参考链接不包含用户提供的跳转令牌。
