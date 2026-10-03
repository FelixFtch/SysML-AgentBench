# 附录：SysEngBench

SysEngBench（Bell、Longshore、Madachy，与第三篇论文同一团队）是系统工程知识选择题，不是 SysML 模型题。Hugging Face 上的 `rabell/SysEngBench` 许可是 MIT，大约一千一百道四选一，字段是题干、四个选项、答案和解释。卷子里没有可交给官方 Pilot 的 `.sysml`。

它不进入 24 道海事题的主评分。主评分只比较需求到模型、修改、读模型、缺信息和回写。SysEngBench 若以后要做，只能单独报“模型懂不懂系统工程术语”，不能和语法通过率或功率 FAIL 加在一起。
