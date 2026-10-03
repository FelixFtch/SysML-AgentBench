"""Write STATUS.md from the newest held-out experiment directory."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis"


def main() -> None:
    runs = sorted(path for path in ANALYSIS.glob("heldout-*") if (path / "results.jsonl").is_file())
    if not runs:
        raise SystemExit("No held-out results yet")
    latest = runs[-1]
    rows = [json.loads(line) for line in (latest / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    by_config = defaultdict(lambda: {"PASS": 0, "FAIL": 0})
    by_type = defaultdict(lambda: {"PASS": 0, "FAIL": 0})
    for row in rows:
        by_config[row["configuration"]][row["status"]] += 1
        by_type[row["type"]][row["status"]] += 1
    lines = ["# STATUS", "", f"Latest run: `{latest.name}`", "", "## By configuration", ""]
    for name in sorted(by_config):
        item = by_config[name]
        lines.append(f"- {name}: PASS {item['PASS']}, FAIL {item['FAIL']}")
    lines.extend(["", "## By task type", ""])
    for name in sorted(by_type):
        item = by_type[name]
        lines.append(f"- {name}: PASS {item['PASS']}, FAIL {item['FAIL']}")
    lines.append("")
    text = "\n".join(lines)
    (ROOT / "STATUS.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
