"""Score the two PURE excerpts. Gold stays out of the prompt."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.llm import chat  # noqa: E402
from bench.experiment import load_env  # noqa: E402
from bench.score_answer import score_answer  # noqa: E402

TASKS = [
    ROOT / "bench" / "tasks" / "t5_requirements" / "PURE-EIRENE",
    ROOT / "bench" / "tasks" / "t5_requirements" / "PURE-PEERING",
]


def main() -> None:
    load_env()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    out = ROOT / "analysis" / f"pure-{stamp}"
    out.mkdir(parents=True)
    for task_dir in TASKS:
        excerpt = (task_dir / "input" / "excerpt.md").read_text(encoding="utf-8")
        completed = chat([
            {"role": "system", "content": "Extract only requirements written in the excerpt. Reply with one JSON object and no other text."},
            {"role": "user", "content": excerpt},
        ], max_tokens=800, temperature=0)
        scored = score_answer(task_dir, completed["text"])
        record = {"task_id": task_dir.name, "provider_model": completed["model"],
                  "status": scored["status"], "answer": completed["text"], "score": scored}
        (out / f"{task_dir.name}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        print(task_dir.name, scored["status"], flush=True)
    print(out)


if __name__ == "__main__":
    main()
