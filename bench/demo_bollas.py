"""Print the ten-minute demonstration from saved results. No model call."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ablation = json.loads((ROOT / "analysis" / "ablation.json").read_text(encoding="utf-8"))
    demo = json.loads((ROOT / "analysis" / "demo-mod01.json").read_text(encoding="utf-8"))
    graph = json.loads((ROOT / "analysis" / "graph-query-max.json").read_text(encoding="utf-8"))
    print("1. Task: add an infrared camera to the USV. The power limit stays 60 W.")
    print(f"   Replay: syntax {demo['sysml_status']}, checklist {demo['checklist_status']}, approval gate {demo['approval']['answer']}.")
    print("2. MOD-05 is over power on purpose: 41+25+12=78, limit 60. Syntax passes.")
    print("   Design verdict FAIL (it reports the overrun honestly). The limit and the values that must be kept are unchanged, the checks match the key, so the task verdict is PASS. Raising the limit, or lowering a draw to hit 60 W, fails the task.")
    print("3. Passes for the four approaches (qwen3.8-flash, 72 cells each, current scorer; the archived scorer is in parentheses):")
    for name in ("P0", "P1", "P2", "P3"):
        item = ablation[name]
        print(f"   {name}: {item['pass']}/72 ({item['archived_pass']}), {item['matches_per_1k_tokens']} passes per 1,000 tokens")
    print("4. Graph retrieval (qwen3.8-max; one-hop neighbors only, not the whole model):")
    for row in graph:
        print(f"   {row['task_id']} {row['status']}")
    print("5. The assistant inside Cameo cannot be run this time: it needs a full 2026x license, and this machine does not have one.")


if __name__ == "__main__":
    main()
