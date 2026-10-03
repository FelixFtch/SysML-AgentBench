# 剩下九项：2026-10-03 核对

模型已改为 qwen3.8-max（`.env` 的 `MVP_LLM_MODEL`）。端点返回的模型名就是 `qwen3.8-max`。下面每项写明查到了什么、做成了什么、为什么停。

## 图检索

第二篇（Bader 等，ISSE 2025）测的是：已有模型先变成图，按问题和节点的相似度取出节点，再带上它的一跳邻居，交给 GPT。他们只有 1 个电动车模型、3 个问题。阈值 0.45 时检索 F1 0.904，这是“相关元素找得准不准”，不是答案对不对。作者代码把演示服务器地址写死，排序参数算了却没用，评估数字是手填的，所以没有重跑他们的笔记本。

我们做的是同一类步骤：用官方解析过的海事模型（428 个元素，56 个有名字），按问题里的词选节点，加上一跳邻居，不把整份 `.sysml` 交给模型。qwen3.8-max 五道读模型题：QRY-01、02、04、05 通过，QRY-03 答成 0 条连接，标准答案是 3。连接计数这题，只给邻居片段不够。没有用 MiniLM 向量，所以这不是他们那个 0.904 的复现。

## Claude Code

本机 `claude -p` 在 20 秒内没有答出内容，返回 `unrecognized_model`，模型名是 `glm-5.3`。3456 端口上的路由没有在听。24 题因此没有跑。要跑的话，先把 Claude 指到能用的 qwen3.8-max，再整批重试。没有改 Claude 的全局配置。

## Cameo 助手

2026-10-02 的厂商核对仍然成立：AI Assistant 在 Magic Cyber Systems Engineer / SoS Architect 2026x 里，社区版页面没有写它包含助手。桌面版没有无头命令。没有 Bollas 的许可和登录，这项不能跑，也不编造成绩。

## PURE

Zenodo 7118517 的数据集页是 CC BY 4.0，但整理者写明：原始需求文档自己的版权他们没有逐份确认。因此没有把 79 份 PDF 放进仓库。XML 子集已下载到 `datasets/pure/`（不进 git）。从中抽了两句短摘录做成题：铁路无线电 EIRENE，内容分发网络对等（peering）。摘录标明来源。这是“从原文抽出需求”的题面，还没有用 max 跑分。

## STPA

DLR 的 SysML v2 STPA 库是 MIT 或 Apache-2.0，用 `#hazard` 这类元数据。官方 Pilot 不加载那份库时，这种写法过不了。场景里另写了两份普通需求：`LossOfSeparation`（碰撞这一损失）和 `HazardTrackNotShared`（航迹没送到指挥舰这一危险）。官方校验 PASS，运行 `20261003T011336-a33d5bdc`。数字仍是合成的。

## SysEngBench

MIT 许可的选择题，大约一千一百道，没有 SysML 文件。附录在 `docs/sysengbench-appendix.md`。不进 24 题主评分。

## 151 道 SysMBench

Jin 等 arXiv:2508.03215 写了 151 道场景，并说会公开。读到的论文 HTML 没有给出带许可证的仓库地址。网上同名的 SysMoBench（Apache-2.0）是操作系统形式化建模，不是这 151 道。cmuchancel 的仓库是另一篇 2026 年论文，许可证未标明。151 道题没有下载，没有混进检索，也没有拿来打分。

## 给 Bollas 的演示

`python3 bench/demo_bollas.py` 用已经保存的结果讲五分钟：MOD-01 回放、MOD-05 的功率 FAIL、四种做法的对齐和 token、max 的图检索五题、Cameo 为什么没跑。还没有当着人演示。

## 第二个模型看完全部 288 次

已完成。裁判是 qwen3.8-max，看的是 flash 交过的 288 份卷，不改原来的分数。一致 157/288（54.5%）。工具判失败的 76 份里，max 把 70 份说成通过，其中 MOD-05 的 12 份超功率全部被说成通过。结果在 `analysis/validator-all-max.jsonl`。
