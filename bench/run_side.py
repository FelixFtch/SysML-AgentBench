"""Side benchmarks named in the sponsor brief, put to the same four candidates as the exam. Not added to the exam score.

- SysEngBench (rabell/SysEngBench, MIT): systems-engineering knowledge, four options each. A fixed subset of 100
  question ids drawn once with seed 20261006 (analysis/sysengbench/ids-100.txt), asked 10 per prompt. The dataset
  answer is read only when scoring. The answer key is lopsided (B 557, C 394, A 124, D 69 of 1,144), so the score of
  always answering B on the same subset is reported next to every candidate.
- PURE (Zenodo 7118517, CC BY 4.0): the two sealed excerpts in bench/tasks/t5_requirements, scored by
  bench.score_answer exactly as before (the extracted requirement sentences must equal the key).

Candidates: direct (one call per prompt through agents/llm.py, model selectable), OpenCode and Claude Code (one
sandboxed session per prompt, agents/external/jail.py, the same workspace setup as the exam).

    python3 bench/run_side.py --bench sysengbench --candidate direct --model qwen3.8-flash --repeats 3
    python3 bench/run_side.py --bench pure --candidate claude --model qwen3.8-flash --repeats 3

Output: analysis/side-<bench>-<candidate>-<model>-<stamp>/results.jsonl and summary.json.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import shutil
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.llm import USAGE_LOG, chat, extract_json, usage_summary  # noqa: E402
from bench.experiment import load_env  # noqa: E402
from bench.score_answer import score_answer  # noqa: E402

SEB = ROOT / "analysis" / "sysengbench"
SEB_CSV = SEB / "test.csv"
SEB_URL = "https://huggingface.co/datasets/rabell/SysEngBench/resolve/main/test.csv"
SEB_IDS = SEB / "ids-100.txt"
SEED = 20261006
BATCH = 10
PURE = ROOT / "bench" / "tasks" / "t5_requirements"
PURE_TASKS = ["PURE-EIRENE", "PURE-PEERING"]
SEB_INSTRUCTION = ("Multiple-choice systems engineering questions. For each question choose the best option: A, B, C or D. "
                   "Reply with one JSON object that maps each question id to one letter, for example {\"q12\": \"B\", \"q40\": \"D\"}, "
                   "and no other text.")
LOCK = threading.Lock()


def seb_rows() -> dict[str, dict]:
    if not SEB_CSV.is_file():
        import urllib.request
        SEB.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(SEB_URL, SEB_CSV)
    return {row["Question ID"]: row for row in csv.DictReader(SEB_CSV.open(encoding="utf-8"))}


def seb_subset(rows: dict) -> list[str]:
    if not SEB_IDS.is_file():
        ids = sorted(rows, key=int)
        chosen = sorted(random.Random(SEED).sample(ids, 100), key=int)
        SEB_IDS.write_text("\n".join(chosen) + "\n", encoding="utf-8")
    return [line.strip() for line in SEB_IDS.read_text(encoding="utf-8").splitlines() if line.strip()]


def seb_prompts(rows: dict, ids: list[str]) -> list[tuple[str, str, list[str]]]:
    """(prompt id, prompt text, question ids) per batch of ten. The answer column is never included."""
    prompts = []
    for start in range(0, len(ids), BATCH):
        chunk = ids[start:start + BATCH]
        blocks = []
        for qid in chunk:
            row = rows[qid]
            blocks.append(f"q{qid}: {row['question']}\nA. {row['choiceA']}\nB. {row['choiceB']}\nC. {row['choiceC']}\nD. {row['choiceD']}")
        prompts.append((f"SEB-{start // BATCH + 1:02d}", SEB_INSTRUCTION + "\n\n" + "\n\n".join(blocks) + "\n", chunk))
    return prompts


def seb_score(text: str, chunk: list[str], rows: dict) -> list[dict]:
    try:
        answers = extract_json(text)
    except Exception:
        answers = {}
    if not isinstance(answers, dict):
        answers = {}
    out = []
    for qid in chunk:
        picked = answers.get(f"q{qid}") or answers.get(qid)
        picked = str(picked).strip().upper()[:1] if picked else None
        out.append({"id": qid, "picked": picked, "key": rows[qid]["answer"], "correct": picked == rows[qid]["answer"]})
    return out


def synthetic_task(prompt_id: str, prompt: str, folder: Path) -> Path:
    """A task folder the agent runners accept: input/requirements.md holds the prompt; no gold inside."""
    task = folder / prompt_id
    (task / "input").mkdir(parents=True, exist_ok=True)
    (task / "input" / "requirements.md").write_text(prompt, encoding="utf-8")
    (task / "case.yaml").write_text(yaml.safe_dump({"id": prompt_id, "type": "SIDE"}), encoding="utf-8")
    return task


def ask(candidate: str, model: str, prompt_id: str, prompt: str, system: str, scratch: Path) -> dict:
    """Run one prompt through one candidate. Returns text and usage."""
    if candidate == "direct":
        calls: list[dict] = []
        USAGE_LOG.set(calls)
        os.environ["MVP_LLM_MODEL"] = model
        reply = chat([{"role": "system", "content": system}, {"role": "user", "content": prompt}], max_tokens=1500)
        return {"text": reply["text"], "usage": usage_summary(calls)}
    task = synthetic_task(prompt_id, prompt, scratch)
    if candidate == "opencode":
        from agents.external.opencode_run import run_opencode
        from bench.run_opencode import usage_from_log
        os.environ["MVP_LLM_MODEL"] = model
        solved = run_opencode(task)
        return {"text": solved["text"], "usage": usage_from_log(Path(solved["workspace"]).parent / "stdout.jsonl"),
                "workspace": solved["workspace"]}
    if candidate == "claude":
        from bench.run_claude_qwen import run_claude, usage_of
        run = run_claude(task, model=model, max_turns=30, timeout=900, label="SIDE-CL")
        return {"text": run["text"], "usage": usage_of(run["result"]), "workspace": str(run["workspace"])}
    raise ValueError(candidate)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", choices=["sysengbench", "pure"], required=True)
    parser.add_argument("--candidate", choices=["direct", "opencode", "claude"], required=True)
    parser.add_argument("--model", default="qwen3.8-flash")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    load_env()
    os.environ["MVP_LLM_MODEL"] = args.model
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    out = ROOT / "analysis" / f"side-{args.bench}-{args.candidate}-{args.model}-{stamp}"
    out.mkdir(parents=True)
    scratch = ROOT / "mvp" / "exam-inbox" / f"side-{args.bench}-{args.candidate}-{stamp}"
    meta = {"bench": args.bench, "candidate": args.candidate, "model": args.model, "repeats": args.repeats, "started": stamp}
    if args.bench == "sysengbench":
        rows = seb_rows()
        ids = seb_subset(rows)
        prompts = seb_prompts(rows, ids)
        meta.update({"dataset": "rabell/SysEngBench test.csv", "sha256": hashlib.sha256(SEB_CSV.read_bytes()).hexdigest(),
                     "subset": str(SEB_IDS.relative_to(ROOT)), "seed": SEED, "questions": len(ids), "per_prompt": BATCH,
                     "always_B_on_subset": sum(rows[q]["answer"] == "B" for q in ids)})
        system = "Answer the multiple-choice questions. One JSON object, no prose."
        jobs = [(repeat, pid, text, chunk) for repeat in range(1, args.repeats + 1) for pid, text, chunk in prompts]
    else:
        jobs = []
        for name in PURE_TASKS:
            excerpt = (PURE / name / "input" / "excerpt.md").read_text(encoding="utf-8")
            jobs += [(repeat, name, excerpt, None) for repeat in range(1, args.repeats + 1)]
        system = "Reply with one JSON object and no prose, using the field names required by the task."
        rows = None
    (out / "summary.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    def run(job):
        repeat, pid, text, chunk = job
        record = {"bench": args.bench, "candidate": args.candidate, "model": args.model, "repeat": repeat, "item": pid}
        try:
            reply = ask(args.candidate, args.model, f"{pid}-r{repeat}", text, system, scratch)
            record["usage"] = reply.get("usage")
            record["answer"] = reply["text"][:4000]
            if args.bench == "sysengbench":
                graded = seb_score(reply["text"], chunk, rows)
                record.update({"questions": graded, "correct": sum(item["correct"] for item in graded), "n": len(graded)})
            else:
                scored = score_answer(PURE / pid, reply["text"])
                record.update({"status": scored["status"], "expected": scored.get("expected"), "actual": scored.get("actual")})
        except Exception as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"
            if args.bench == "sysengbench":
                record.update({"correct": 0, "n": len(chunk)})
            else:
                record["status"] = "FAIL"
        with LOCK:
            with (out / "results.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            print(f"r{repeat} {pid} " + (f"{record.get('correct')}/{record.get('n')}" if args.bench == "sysengbench" else record.get("status", "?")), flush=True)

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        list(pool.map(run, jobs))
    shutil.rmtree(scratch, ignore_errors=True)
    print(out)


if __name__ == "__main__":
    main()
