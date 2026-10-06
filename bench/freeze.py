"""Write bench/FREEZE.md: the sealed state of the task bank, scorers, prompts and toolchain before a matrix run.

Re-running it after the freeze must print the same hashes; `--check` exits 1 when anything listed has changed.
No model is called.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

HELD = ROOT / "bench" / "tasks" / "t4_maritime_isr" / "heldout"
OUT = ROOT / "bench" / "FREEZE.md"
CODE = ["bench/score_task.py", "bench/score_answer.py", "bench/score_alignment.py", "bench/experiment.py", "agents/solve.py",
        "agents/llm.py", "bench/vector_index.py", "bench/graph_query.py", "bench/corpus/sysml-syntax.md", "bench/corpus/maritime-vocabulary.md",
        "analysis/vector-index/examples/cards.json", "analysis/vector-index/examples/neighbors.json",
        "mvp/toolchain/kernel.lock.json", "mvp/engine.py", "mvp/toolchain/validate.py"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def task_hash(task: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in task.rglob("*") if p.is_file()):
        digest.update(str(path.relative_to(task)).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\n")
    return digest.hexdigest()


def main() -> None:
    check = "--check" in sys.argv
    tasks = [json.loads(line) for line in (HELD / "index.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = [(item["id"], item["type"], task_hash(HELD / item["id"])) for item in tasks]
    code = [(name, sha(ROOT / name)) for name in CODE if (ROOT / name).is_file()]
    lock = json.loads((ROOT / "mvp" / "toolchain" / "kernel.lock.json").read_text(encoding="utf-8"))
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    from agents.solve import DEFAULT_ROUNDS, IDENTICAL_STOP
    from bench.vector_index import DEFAULT_THRESHOLD, EMBEDDING_MODEL
    body = [
        "# FREEZE",
        "",
        f"Sealed {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} at commit `{commit[:12]}` after the second review (`bench/tasks/t4_maritime_isr/heldout/REVIEW.md`).",
        "Anything listed here is not edited while a matrix runs; a change means a new freeze and a new batch. `python3 bench/freeze.py --check` verifies the hashes.",
        "",
        "## Task bank: 27 sealed tasks (hash over case.yaml, input/, gold/)",
        "",
        "| Task | Type | SHA-256 |",
        "|---|---|---|",
        *[f"| {tid} | {kind} | `{digest[:16]}` |" for tid, kind, digest in rows],
        "",
        "## Scoring, prompts, retrieval library, toolchain",
        "",
        "| File | SHA-256 |",
        "|---|---|",
        *[f"| `{name}` | `{digest[:16]}` |" for name, digest in code],
        "",
        "## Rules in force",
        "",
        f"- Official SysML v2 Pilot {lock.get('kernel_version', '?')} (release {lock.get('release', '?')}, kernel sha256 `{str(lock.get('sha256', ''))[:16]}`); it is the only syntax judge.",
        "- Task verdict and design verdict are separate (decision 019). Judges by model are not used (decision 025).",
        f"- Repair loop (decision 022): complete error list, one cumulative conversation, at most {DEFAULT_ROUNDS} repairs, stop after {IDENTICAL_STOP} identical resubmissions. P0 never repairs; P1, P2, P3 repair.",
        f"- Retrieval (decisions 023, 027): {EMBEDDING_MODEL}, cosine ≥ {DEFAULT_THRESHOLD} plus the exact-name bonus, one hop; cards carry each element's documentation text; the exam uses the official-examples library only.",
        "- AMB: an imperative clarification request counts as asking; a number with a unit that the statement does not contain counts as invented only when the answer also writes SysML (decision 028). RT: phrases match after number-word and `.0` normalisation (second review, 2026-10-06).",
        "- Candidates: direct qwen3.8-flash (P0–P3), OpenCode on qwen3.8-flash, Claude Code on qwen3.8-flash, direct qwen3.8-max (P0–P3); 3 repeats each.",
        "",
        "## What will be compared (stated before the run)",
        "",
        "- Within the direct candidates: P0→P1 isolates repair, P1→P2 the outline, P2→P3 retrieval; first-attempt pass inside each repaired cell is reported next to the final pass.",
        "- Across candidates on the same model: the three ways of running flash, 27 tasks × 3 repeats each.",
        "- No numeric target is pre-registered; the 2026-10-03 matrix (224/288 under its rules) is the archived point of comparison, not a baseline for the new rules.",
        "",
    ]
    text = "\n".join(body)
    if check:
        if not OUT.is_file():
            raise SystemExit("no FREEZE.md")
        old = OUT.read_text(encoding="utf-8")
        same = all(line in old for line in body if line.startswith("| ") and "`" in line)
        print("unchanged" if same else "CHANGED since the freeze")
        raise SystemExit(0 if same else 1)
    OUT.write_text(text, encoding="utf-8")
    print(f"{len(rows)} tasks, {len(code)} files -> {OUT}")


if __name__ == "__main__":
    main()
