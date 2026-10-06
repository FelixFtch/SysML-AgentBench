"""Print the ten-minute demonstration from saved results. No model call."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> None:
    from bench.board_facts import facts
    f = facts()
    C = f["cohorts"]
    demo = json.loads((ROOT / "analysis" / "demo-mod01.json").read_text(encoding="utf-8"))
    print("1. Task: add an infrared camera to the USV. The power limit stays 60 W.")
    print(f"   Replay: syntax {demo['sysml_status']}, checklist {demo['checklist_status']}, approval gate {demo['approval']['answer']}.")
    print("2. MOD-05 is over power on purpose: 41+25+12=78, limit 60. Syntax passes.")
    print(f"   Design verdict FAIL (it reports the overrun honestly); the limit and every value to keep are unchanged, so the task verdict is PASS: "
          f"{f['reliability']['mod05_pass']}/12 direct-flash cells. Raising the limit, or lowering a draw to hit 60 W, fails the task.")
    print("3. Four candidates on the 27 frozen tasks (official Pilot + answer keys only):")
    for key in ("flash", "max", "opencode", "claude"):
        item = C[key]
        print(f"   {item['label']}: {item['pass']}/{item['n']}")
    print("4. The same model, four approaches (direct flash, 81 cells each; official parse on the first attempt -> after repair, of 39):")
    for row in C["flash"]["configs"]:
        print(f"   {row['id']}: {row['pass']}/81, parse {row['syntax_first']} -> {row['syntax_final']}, ${row['usd']:.4f}")
    print("5. Graph retrieval (qwen3.8-max; MiniLM + FAISS over the parsed model, one hop, not the whole model):")
    for task, item in f["graph"].items():
        print(f"   {task} {item['status']}")
    print("6. The assistant inside Cameo cannot be run this time: it needs a full 2026x license, and this machine does not have one.")


if __name__ == "__main__":
    main()
