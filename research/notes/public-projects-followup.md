# 公开工程资料补充核验与实际接入

日期：2026-09-22。范围：只选取能落地演示的两套资料；原始文件全部保留在 `mvp/public-data/`，未混入应用源码。本次不把公开资料称作 RTX 内部数据，也不将教程模型称作物理系统的正式设计。

## 1 NASA cFE：可追溯的真实公开需求输入

- 一手来源：[nasa/cFE](https://github.com/nasa/cFE)，[固定版本CSV](https://github.com/nasa/cFE/blob/7d283938c9af5bd6e439f3fc307e61b0c7799640/docs/cFE_FunctionalRequirements.csv)。
- 下载版本：`7d283938c9af5bd6e439f3fc307e61b0c7799640`，来自 `dev` 分支快照，不把它称为正式已验收发行版本。
- 许可：仓库明确 [Apache-2.0 LICENSE](https://github.com/nasa/cFE/blob/7d283938c9af5bd6e439f3fc307e61b0c7799640/LICENSE)；保留LICENSE与README及原文档，不重新声明为本项目独占内容。
- 已实际下载：完整 `cFE_FunctionalRequirements.csv`、`cfe requirements.docx`、LICENSE、README，共440,647字节。manifest记录原URL、commit、字节数与SHA-256。
- CSV实测不是596条独立需求，而是596条数据记录：414个不同非空需求ID，另有182条无ID的文本续行。这些续行包含列表和要求正文，不能丢弃。
- 已执行确定性解析：按紧邻前一个非空ID归并续行，保留每条原记录的所有字段、CSV记录号、物理行区间、源文件hash；输出414条 `imported_candidate`，其中82条Software Bus需求。归并规则显式写入报告，仍需领域人员确认新项目适用性。
- 演示选择8条：cSB4301、cSB4303、cSB4305、cSB4305.3、cSB4305.6、cSB4307、cSB4332、cSB4328。涉及消息队列、订阅路由、溢出、尺寸上限、超时、默认配置与校验和。它们适合作为消息网关的历史需求参考，不能自动成为海事系统的新基线。
- 没有填入`MISSION_DEFINED`/`PLATFORM_DEFINED`值；没有从NASA文档捏造相机速率、存储容量或功耗。

### 实际需求→SysML导入

已生成 `mvp/public-data/nasa-cfe/derived/NASA_CFE_Imported.sysml`：1个RequirementDefinition、8个RequirementUsage。每项保留原ID、commit、原CSV SHA、CSV记录定位与`TEXT_IMPORTED_SEMANTIC_MAPPING_PENDING`状态。自然语言正文仍放在documentation中；没有生成形式谓词、satisfy关系或虚假的验证结论。

官方0.62.0解析器、固定Release库实际执行结果：**PASS、0诊断、273 AST元素、3.932秒**；官方模型导出确认8个RequirementUsage和1个RequirementDefinition。完整运行证据在 `mvp/public-data/nasa-cfe/validation/`。

此结果证明真实公开文档已进入可解析SysML工程，不能证明自然语言要求已完成语义形式化，也不能当作人工金标配对数据集。

## 2 官方Vehicle工程：外部多文件模型互操作

- 一手来源：[官方Vehicle Example](https://github.com/Systems-Modeling/SysML-v2-Release/tree/fb97b754f29588b8e9c7a35f370880cd15eb29e7/sysml/src/examples/Vehicle%20Example)。
- 固定版本：`fb97b754f29588b8e9c7a35f370880cd15eb29e7`，2026-08。
- 下载了未修改的VehicleDefinitions.sysml与VehicleUsages.sysml，以及该版本LICENSE、README。四文件共25,447字节。
- [仓库说明](https://github.com/Systems-Modeling/SysML-v2-Release)明确包括的KerML/SysML模型采用EPL-2.0；原始代码及声明独立保留，不将此许可套到NASA文件或我们自己的代码。
- 实际运行官方工具：**PASS、0诊断、493 AST元素、6.68秒**，输出原生API delta JSON和EMF引用/定位摘要。证据在 `mvp/public-data/sysml-official-vehicle/validation/`。
- 可演示真实跨文件import、类型和port/interface、变型模型导入；不是实车参数，不是需求→模型正确率基准，不证明物理安全性。

两套例子都提供`reference.json`，分别白名单ID `nasa-cfe` 和 `sysml-official-vehicle`。应用可按相对路径读取原模型，创建新run实际调用工具，并绑定文件hash。选择这两个公开例子不改变主产品的跨领域定位，也不预设RTX必须做车辆或航天。

## 3 Hugging Face实际核验：有样例，但不能直接当高质量gold

核验了作者直接发布的 [rqualis/sysml_v2_instruction](https://huggingface.co/datasets/rqualis/sysml_v2_instruction)，固定仓库commit `9ae0e29051b58e84dc88cc21aeccd07af74494c0`。README文本声明Apache-2.0，但数据卡版本说明仍为v0.0.3；API返回的cardData为空。实际读取 `data/v0.5/train.jsonl` 为11行、仅4条不同记录，test为2行、2条不同记录。不是仅依赖搜索摘要中的行数。

此次没有建立其编译验证、独立工程评审或完整配套依赖证据，因此不放入正式gold评测，不下载混入我们的训练/检索库。可用于人工检查少量提示模板，但需去重、固定版本、真工具校验并重新审题。教程摘要类资料与SysEngBench知识选择题亦不等于需求—模型金标。

另发现[Model Management Challenge 2026 satellite-config](https://github.com/mom-challenge/satellite-config)，其OWL目录、JSON BOM/通信网、CSV需求、报告及两个版本很贴近异构模型变更主题。不过本次仓库API没有识别到许可证，未进一步核验Zenodo记录许可，因此只记录为后续候选，未下载进演示，不将其称作已许可数据或本次实现成果。

## 4 对产品定位的直接含义

旧资料接入应先保留原件与版本，再产生有定位的需求/实体候选；对确定格式使用确定性解析。Agent适合提出适用性判断、缺失配置问题和语义建模建议。知识图谱作为派生查询视图可辅助跨工件追溯；它不能替代源文件，也不能把“文本导入成功”升级成“需求已满足”。

当前已经有两个真实可复跑入口：公开工程模型→官方语义导出，以及公开旧需求→带来源的SysML requirement元素。后者刻意把尚未完成的语义映射暴露出来，是下一步agent工作的明确输入。
