"""Print the ten-minute demonstration from saved results. No model call."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ablation = json.loads((ROOT / "analysis" / "ablation.json").read_text(encoding="utf-8"))
    demo = json.loads((ROOT / "analysis" / "demo-mod01.json").read_text(encoding="utf-8"))
    graph = json.loads((ROOT / "analysis" / "graph-query-max.json").read_text(encoding="utf-8"))
    print("1. 题：给无人艇加红外相机，功率上限保持 60 W。")
    print(f"   回放：语法 {demo['sysml_status']}，清单 {demo['checklist_status']}，审批门 {demo['approval']['answer']}。")
    print("2. 故意超功率的 MOD-05：41+25+12=78，上限 60。语法可以通过，功率检查是 FAIL。")
    print("3. 四种做法的清单对齐（qwen3.8-flash，72 格）：")
    for name in ("P0", "P1", "P2", "P3"):
        item = ablation[name]
        print(f"   {name}: {item['checklist_match']}/72，每千 token {item['matches_per_1k_tokens']}")
    print("4. 图检索（qwen3.8-max，只给一跳邻居，不给整份模型）：")
    for row in graph:
        print(f"   {row['task_id']} {row['status']}")
    print("5. Cameo 里的助手这次不能跑：要 2026x 全功能许可，本机没有。")


if __name__ == "__main__":
    main()
