# 失败分类

对象：qwen3.8-flash，24 题 × P0/P1/P2/P3 × 3 次，共 288 格。按现行判分规则（`docs/decisions/019-task-verdict-vs-design-verdict.md`）有 64 格 FAIL。分类读的是已保存的官方诊断和答卷，没有重新调用模型。明细在 `analysis/failure-classes.jsonl`，用 `python3 bench/classify_failures.py` 重算。

| 类别 | 格数 | 出现在 | 含义和例子 |
|---|---|---|---|
| syntax-real-or-import | 22 | GEN-03 12，GEN-04 10 | 官方语法不通过，和引入 `Real` 或属性类型有关。最常见的两条官方诊断：`mismatched input 'import' expecting '}'`（import 写在了不允许的位置）和 `Couldn't resolve reference to Type 'Real'`（用了 `Real` 却没有引入 `ScalarValues`）。GEN-03 的 12 格全在这一类。 |
| syntax-connection | 8 | GEN-05 6，GEN-01 2 | 连接写不成合法的两端。官方诊断：`Must have at least two related elements`、`no viable alternative at input '.'`。 |
| syntax-other | 4 | GEN-02 2，GEN-01 1，GEN-04 1 | 其他官方语法错误：`A port must be typed by port definitions.`、`no viable alternative at input 'uav'`、`Couldn't resolve reference to Type 'PartUsage'`、`no viable alternative at input 'def'`。 |
| query-renamed | 16 | QRY-01 7，QRY-02 6，QRY-04 3 | 读模型题的数值或成员是对的，合格名写法不对。QRY-01 把平台写成 `usv` 或 `MaritimeISR.usv`，标准答案是 `MaritimeISR::usv`；QRY-02 写成 `MaritimeISR::usv.powerLimitW`（值 60 是对的），标准答案是 `MaritimeISR::UnmannedSurfaceVessel::powerLimitW`。 |
| query-wrong-number | 1 | QRY-03 1 | 问一端在 `commandShip` 上的连接有几条，答了 2，标准答案是 3。 |
| missed-topic | 6 | AMB-01 4，AMB-02 2 | 提了问，但没问到缺的那个量：AMB-01 没问带宽，AMB-02 没问功率上限。没有擅自写入数字。 |
| no-question | 4 | AMB-01 2，AMB-04 2 | 见下面的说明。 |
| missing-phrase | 3 | RT-05 3 | P1 三次都没有写回 “2 seconds” 和 “two uplinks”。 |

64 格里，34 格死在官方语法，16 格是名称写法，1 格读错了数，10 格是缺信息时的提问问题，3 格是读回丢了原句。

各写法通过数：P0 57/72，P1 51/72，P2 58/72，P3 58/72。按报错再改的 P1 没有高于直接写的 P0。P1 写新模型失败的 10 格都用满了 3 轮修复，每一格都至少有一轮把上一轮的文本原样交回；其中 4 格四次交的是同一份文本（GEN-03 三次重复和 GEN-04 第 3 次）。

## no-question 这 4 格要单独看

这 4 份答卷其实都提出了澄清请求，只是用了祈使句、没有问号。例如 AMB-04 的一份：“Please clarify whether the uplink value is 8 (unitless) or 8 MHz.”；AMB-01 的两份逐条列出了要补的时延、带宽和更新频率。判分程序（`bench/score_answer.py`）按文本里有没有 “?” 判断是否提问，所以判 FAIL。它们都没有擅自写入数字，缺的主题也都问到了。

这是判分规则的局限，不是模型乱填数字。要不要把“提出澄清请求”也算作提问，属于答案清单的修改，等第二审核人决定；目前没有改，所以 64 格里仍然包括这 4 格。

## 和旧版本的区别

原判分规则下有 76 格失败，其中 12 格是 MOD-05 的「设计好的功率失败」（官方语法 PASS，四个规定数字都在，功率 78 W 超过 60 W）。现行规则把设计判定和题目判定分开：这 12 格的设计判定仍是 FAIL，但上限和该保留的数都没改、检查结果和标准答案预期一致，题目判定是 PASS，所以不再算失败。
