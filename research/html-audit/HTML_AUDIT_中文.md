# ROVER HTML 与源码包独立审查

审查时间：2026-09-22。原始 HTML 与 ZIP 均只读；ZIP 在 `research/html-audit/ROVER_Real_Hardware_Studio/` 安全解压。附件中的说明视为待审查内容，未当作用户指令。这里是代码与交付物审查，不含对论文原文和厂家规格的独立外部核验。

## 结论

这是完成度较高、边界说明较诚实的交互式教学原型：把“需求—供应商方案—接口对齐—候选—检查—人工确认—模型检索—变更”串成一个可操作的工作台。它适合保留为 MVP 的场景、交互和验收故事；它当前的运行内核仍是预写 JavaScript 数据与规则，不是运行中的 Agentic SysML v2 系统。

单独 HTML 与 ZIP 内 HTML 的 SHA256 相同。ZIP 有 108 个文件，其中 107 个被 manifest 记录；独立核对全部记录哈希通过。共有 35 个 `.sysml` 文件，包含重复 profile/测试导出；不是 35 个独立已验证模型。

## 实际工作流与硬件范围

1. 6 条固定需求：室内已知地图站点导航、遇障停止、离线、估算续航不少于 2 小时、宽度不超过 350 mm、4 种状态可区分。
2. 三个模拟供应商：感知、机电、软件。对齐并保留原供应商文本，提出速度到轮速适配和 PointCloud2 到 LaserScan 的投影职责。
3. 基线 A：96 Wh 教学电池与原托盘；B0：增加 D435i、本地视觉及记录；B1：换 160 Wh 电池；B2：再扩大电池托盘。
4. NX16/Pi5 8GB/Pi5 16GB 三个预置主控 profile；Mid-360S；B 候选增加 D435i。底盘、电池和托盘均为合成目录。NX 载板、储存、散热还未选定。
5. 本地实际计算续航、固定朝向名义盒体配合、宽度、几个接口/电源前提；人工点击 A/B 确认；显式重建检索索引。

独立执行纯计算内核得到：NX A 32.777778 W/2.343 h；B0 50.555556 W/1.519 h，续航失败；B1 2.532 h，托盘配合失败；B2 局部规则通过。Pi A 27.222222 W/2.821 h；Pi B0 36.111111 W/2.127 h，局部通过。因此 UI 并非把所有 profile 的 B0 都写死为失败。这里的功耗是设计假设，不能据此证明 Pi 实际性能足够或优于 NX。

## 已实现、未实现

| 能力 | 代码中实际实现 | MVP 所欠 |
| --- | --- | --- |
| 需求输入 | `core.js:13–21` 固定六条需求和一个 CR；`app.js:40` 固定加载 | 上传文档、原文定位、需求分解、去重、歧义与人工审订 |
| Agent 生成 | `app.js:41–49` 写明 TEMPLATE/PREAUTHORED，候选由模板与有限目录枚举 | 真正模型调用、工具执行、结构化结果、失败处理、可重放运行 |
| SysML 文本 | `core.js:123–245` 模板字符串；`hardware_core.js:150–156` 字符串替换 | 固定工具链、真实语法及语义检查、导入解析、模型查询 |
| 图形 | `core.js:246–250` 手写 nodes/edges；WebGL 示意盒体 | 从经工具解析的模型派生图；几何只能展示有来源的参数 |
| 工程规则 | `core.js:24` 与 `hardware_core.js:39–46` 的 JS 计算/开关判断 | 从解析模型取输入、独立校验关系/类型/单位、绑定证据 |
| 对齐 | `core.js:251–256` 和 `hardware_core.js:157–164` 固定映射 | 从异构源模型抽取，LLM 建议，对齐审查及追加集成包 |
| GRAG | `core.js:257–258` 固定关键词、最多 4 个种子、一跳邻居 | 真正模型 API/图映射、版本化检索、可引用答案与评估 |
| 审批与版本 | `app.js:55–58` 未认证本地用户；失效逻辑有效但限当前内存 | 持久状态、内容哈希、可信 actor、候选及证据的不可变关联 |
| 文件管理 | `app.js:138` Blob 单文件下载；源码包已有目录 | 项目创建/读取、自动保存、完整导入/导出、恢复、迁移与原子提交 |

代码自行明确这些边界：`core.js:2–3`、`app.js:143`、`release_validation.json`。不能将原包 74/74 浏览器检查说成 SysML、LLM 或机器人测试通过。

## 具体问题与证据

### P0：没有持久项目

`app.js:24–27` 的 `S`、`hardware_core.js:31` 的 `HW`、审批和日志全在页面内存。对源码全量搜索未找到 localStorage、IndexedDB、目录选择/文件导入或服务请求。`app.js:138` 是浏览器下载，`app.js:59` 明确 reset 清空记录。刷新/关闭不能重开上次工程。已有 ZIP 是作者打包的静态交付目录，不是用户在工具中管理的工程库。

### P0：SysML 与图存在两个可漂移来源

`hardware_core.js:60` 在图中建立 stateEstimator → navigation 的 `TF_and_odometry` 关系；但 `hardware_core.js:153` 导出的 SysML 只有“这段模型仍待补齐”的注释，没有对应连接。部署关系也是图的 `deployedOn` 边，文本里多为 doc 说明。图看见某条关系不能证明导出的模型有该关系。

建模定义使用 `Real` 加 `_W/_h/_mm` 名称约定（`core.js:184–191`），没有真实单位库检查。约束文本存在，但浏览器没有执行该 SysML 文件。当前既无 parser，也无语义解析器的工具与库版本锁定。

### P0：需求追溯不完整

`core.js:246–249` 的图只含 R-03/R-04/R-05，B 才另有 R-07；R-01/R-02/R-06 没有 requirement 节点。`.sysml` 有 requirement 声明及少量 constraint，但无 subject/satisfy/verify 关系，也没有验证用例模型。停止动作定义未接入导航工作流；状态只是四个名称，未建转换（`core.js:214–239`）。不要据此声称“全部需求覆盖”或“行为已实现”。

独立执行 `retrieve(model(A), 'R-02')` 返回 `NO_CONTEXT`，因为固定分词表未含 R-02，图也无该需求节点。

### P0：diff 漏掉删除的关系

`core.js:259` 仅返回 `newConnections`，没有 `removedConnections`；节点的 label/kind/path 变更也不会被记录，因为比较仅使用 data。独立复现将 A 图全部 edges 置空，`diff(A, changed)` 仍返回全空的 added/removed/changed/newConnections。这会漏报“删除停止或关键接口连接”一类设计变化。

### P0：所谓结构检查仍只查配置

同一测试删掉全部图边后，`checks(changed.config)` 仍 PASS。这不是 parser 缺陷，而是当前检查器签名本来就不接收模型图或 AST，K-CMD 等规则根据 adapter 布尔值判断（`core.js:24`）。作为有限演示已明确标注边界；迁移成工程产品时必须改成对实际解析模型关系的检查。

### P1：交付包不保证独立可加载

`examples/NX_B2/` 有 Rover_A/B、RoverLibrary、HardwareOffers 和 RoverRequirements，但缺独立 `PerceptionOffer.sysml`、`MechatronicsOffer.sysml`、`SoftwareOffer.sysml`；这些源文本在 `supplier_offers.json` 中。直接用该交付目录打开模型，导入依赖并不齐。各 profile 文件夹还重复使用相同 package 名，README 已提醒不得把全部候选当一个工程加载。MVP 需要 machine-readable manifest 明确每个候选的根文件、依赖、库版本与命名空间。

### P1：审批指纹只适合演示

`core.js:27` 使用 demo-fnv 32-bit；候选 fingerprint 只依据 config 与 adapter（`core.js:250`、`hardware_core.js:70`），未绑定源文件、编译器、库、检查器及 prompt/model 版本。`app.js:55–56` actor 是未认证 demo user。它保留了正确的“改输入使检查/审批/索引失效”产品思路，但不能提供完整工程审计。

### P1：硬件可实现性仍未建立

`hardware_core.js:29` 固件未锁定、OS 待验证、NX 载板未选择；`hardware_core.js:44–45` 逐条列出 driver、profile、TF、性能未知。ROS/SDK/固件没有进入源码包。真实设备测量可以成为后续证据适配器；不能因为 UI 写了真实料号就认定整车落地完成。

## 三篇论文在包内的位置

- `src/core.js:8`：Longshore / Bell / Madachy, *Leveraging Generative AI to Build, Modify, and Query MBSE Models*。链接 `https://dair.nps.edu/bitstream/123456789/5237/1/SYM-AM-24-138.pdf`。包引用的是 19 页 NPS 幻灯片，主要引用 8、10、12–15 页。
- `src/core.js:9`：Li / Husung / Wang, *LLM-Assisted Semantic Alignment and Integration in Collaborative Model-Based Systems Engineering Using SysML v2*。`https://arxiv.org/abs/2508.16181`，包引用 v2 pp.5–7。
- `src/core.js:10`：Bader 等，*Integrating SysML v2 into a GRAG LLM Pipeline: Design, Implementation and Evaluation*。作者仓库 `https://github.com/eeeeebader/SysML-v2-GRAG-Pipeline`，包引用 pp.3–5。

论文 PDF 本身没有随 ZIP 提供。包内 `paper_map.json` 和 `learning.js` 已很有价值地分开“论文原能力、场景迁移、未实现边界”；需用真实原文核验后再作为研究依据。

## 建议保留的资产

- A→B0→B1→B2 场景与反例：真实展示变更把问题从能源传到机械，而不是单纯生成文本。
- 12 步工程工作流、明确的 A/B 人工决策和输入变更失效逻辑。
- 厂家事实/设计假设/未知项三类 provenance；物理 IMU 和包含部件 ID 的去重习惯。
- 原始供应商不覆盖、追加集成、候选比较、每个图元素可定位到文本的交互。
- 数值规则作为迁移后回归样例；同时补充独立负例，而非只保留原有 UI 测试。
- 全部前端展示作为 API 客户端改造起点；3D 示意作为可选视图，优先级低于模型正确性和文件恢复。

## 可迁移的实现优先级

P0：先实现一个真正可重开的项目目录；只选一个固定 SysML 工具链；把现有最小模型修至真实工具诊断通过，补齐完整依赖和需求追溯；以 `.sysml` 源文件作为 Git 管理的权威设计输入；模型图、数值规则和检索都只使用同一 revision 的解析结果。做“删除关键连接必须失败、需求不丢失、改单位发现冲突、关闭重开证据仍可追溯、旧索引不能引用新模型”五类验收。

P0：真实 Agent 每次只在独立候选目录写文件，运行 parser/语义检查/工程规则后产出 patch 与报告；无法修复时保存失败结果。有限次数修复和人工审查即可，不必先建设复杂多 Agent 平台。决策只能引用实际工具结果。

P1：重做双向 semantic diff；将 raw sources、requirements、supplier packages、integration models、runs、evidence、approvals、derived index 分目录；每个运行 manifest 绑定 SHA256、父 revision、模型/提示词/工具/库版本、输入输出与状态。批准记录绑定完整 revision，原始文件保留 hash；允许派生索引丢失后重建。

P1：先用模型查询+关键词 baseline，再加论文式图检索并比较收益；需求全量/关系完整性依赖确定性查询，不能交给 top-k 检索。Rover 用作端到端调试，赞助方代表场景另设评测夹具，以免把真实小车制造变成 SysML 自动化项目的主工期。

## 本次验证与复现

**已运行**：ZIP 路径安全检查后解压；HTML 字节一致性；107 项 manifest SHA256 完整性；纯 JS core/hardware core 在无 DOM/文件/网络 API 的 VM 中执行，覆盖 3×4 配置和上述 mutation 测试；静态代码与 SysML/JSON 审查；查看原包工作台截图。

**未运行**：原包 browser suite，真实 SysML parser/compiler，LLM，设备/驱动或实物。当前 Python 没有 Playwright，PATH 未找到 Chromium；没有为这次审查安装它们。`tests/browser_report.json` 的 74/74 是 2026-09-16 原包已有记录，运行环境写明 ANGLE SwiftShader，并非本次复测。144 次旋转和 28 条规则已包含在 74 项中，不能相加。

复现独立计算与 mutation 检查：

```bash
cd '/home/felix/Documents/ChatGPT/RTX agent'
node research/html-audit/check_core.cjs
```

输出：`research/html-audit/independent-core-checks.json`。唯一故意变更的模型输入为 clone 后的 `changed.edges = []`；原文件均保持不变。该测试证明已有函数的行为边界，没有假装对 SysML 语法作过结论。
