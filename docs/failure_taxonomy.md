# 失败分类

对象：qwen3.8-flash，24 题 × P0/P1/P2/P3 × 3 次，共 288 格，其中 FAIL 76 格。分类读的是已保存的官方诊断和答卷，没有重新调用模型。明细在 `analysis/failure-classes.jsonl`。

| 类别 | 格数 | 含义 |
|---|---|---|
| designed-budget-fail | 12 | MOD-05。官方语法 PASS，四个规定数字都在，功率 78 W 超过 60 W。清单事先要求这一项为 FAIL。 |
| syntax-real-or-import | 22 | 模型文本没有通过官方语法。常见是 `Real` 没有按 `private import ScalarValues::*;` 引入，或属性写法非法。GEN-03 的一份答卷写了 `import ScalarValues::Real;`，官方校验拒绝。 |
| syntax-connection | 8 | 连接写不成合法的两端。GEN-05 里出现过 `no viable alternative at input '.'`。 |
| syntax-other | 4 | 其他官方语法错误，例如自造类型名 `ImageConnection`。 |
| query-renamed | 16 | 读模型题的数值或成员是对的，合格名没用 `::`。例如平台写成 `usv` 而不是 `MaritimeISR::usv`，60 这个数本身是对的。 |
| query-wrong-number | 1 | QRY-03 有一次把指挥舰上的连接数答成 2，标准答案是 3。 |
| missed-topic | 6 | 提了问，但没有问到缺的带宽或功率单位。没有擅自写入数字。 |
| no-question | 4 | 缺信息的题没有提出问题。 |
| missing-phrase | 3 | RT-05 的 P1 三次都没有写回 “2 seconds” 和 “two uplinks”。 |

76 格里，12 格是题目设计的功率 FAIL，64 格是答卷没有对上清单。64 格里 34 格死在官方语法，16 格是名称写法，只有 1 格是读错了数。

把 MOD-05 的 12 格按“清单对齐”另计之后，P0 对齐 57/72，P1 对齐 51/72，P2 对齐 58/72，P3 对齐 58/72。按报错再改的 P1 没有高于直接写的 P0。
