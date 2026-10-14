"""PURE file-protocol side experiment: the document as a workspace FILE worked with tools, not a chat prompt.

Hypothesis under test (2026-10-10): the 5-20% PURE scores of the chat protocol are caused by the protocol
(the whole document pushed through the chat window, the answer recited verbatim from memory), not by the
extraction itself. Arm B gives the sandboxed agent the same document as a file and a short instruction, and
the agent must process it with its tools and write the sentences verbatim into answer.json.

Both arms are scored by bench.score_answer on the unmodified datasets/pure/tasks gold (decision: same
function, same tolerance, no local variant). Arm A is not rerun: the existing opencode chat-protocol run
(analysis/side-pure-opencode-qwen3.8-flash-20261009T185531, all 609 rows) is sliced to the same 30 documents.

Sampling (deterministic, seed 20261010): all five documents whose passage holds fewer than five requirement
sentences, plus 25 of the 198 five-sentence documents drawn from short/mid/long character terciles of that
stratum (8/9/8, one seeded draw per tercile). The tercile boundaries also label the five small-stratum
documents for the by-length report.

Budget: at most 120 sandbox invocations (90 planned rows plus retries of infrastructure-error rows; every
appended row, scored or not, counts). Rows whose reply is empty or whose session crashed are errors and are
redone on resume; a genuine FAIL (an answer that does not match the key) stands.

    python3 bench/run_pure_file_protocol.py --model qwen3.8-flash --workers 3
    python3 bench/run_pure_file_protocol.py --summary-only     # rewrite summary/report from results.jsonl

Output: analysis/side-pure-file-protocol-opencode-<ts>/ with results.jsonl, summary.json, report.md and
selected-docs.json.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import shutil
import socket
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.external.opencode_run import run_opencode  # noqa: E402
from bench.experiment import load_env  # noqa: E402
from bench.run_opencode import usage_from_log  # noqa: E402
from bench.score_answer import score_answer  # noqa: E402

PURE_TASKS = ROOT / "datasets" / "pure" / "tasks"
BASELINE = ROOT / "analysis" / "side-pure-opencode-qwen3.8-flash-20261009T185531"
SEED = 20261010
N_DOCS = 30
BUDGET = 120  # sandbox invocations, the red line of the experiment brief
PREFIX = "side-pure-file-protocol-opencode"
LOCK = threading.Lock()

# Arm B instruction: the document stays a file; the chat message is only this. The excerpt.md given to the
# workspace is byte-identical to the one the chat protocol pushed through the prompt (information parity:
# its own trailer states how many sentences the answer must hold).
INSTRUCTION = """The document for this task is the file `input/excerpt.md` in this workspace. Its text is not repeated in this message.

Task: extract the requirement sentences from that document. The document's own closing Task line states how many sentences the answer must have.

Work with your file tools, not from memory:
1. Read `input/excerpt.md` (in chunks if it is long). The document interleaves requirement sentences with non-requirement paragraphs.
2. Pick out every requirement sentence.
3. Copy each one VERBATIM out of the file - character for character, no paraphrase, no punctuation or casing changes. Copy text from the file; do not rewrite it from recollection.
4. Write the answer as one JSON object {"requirements": ["...", ...]} into the file `answer.json` in this workspace root (answer.json, not answer.md): one list entry per requirement sentence, exactly as many entries as the document states, in document order.
5. Verify before finishing: re-read the document and `answer.json`, check every entry matches the document character for character, and fix any entry that does not.

`answer.json` must contain that JSON object and nothing else."""


# ---------- deterministic sample ----------

def pure_index() -> list[dict]:
    rows = []
    for task in sorted(PURE_TASKS.iterdir()):
        reqs = json.loads((task / "gold" / "answer.json").read_text(encoding="utf-8"))["requirements"]
        rows.append({"id": task.name, "dir": task, "nreq": len(reqs),
                     "chars": len((task / "input" / "excerpt.md").read_text(encoding="utf-8"))})
    return rows


def sample_docs(index: list[dict]) -> tuple[list[dict], dict]:
    """All nreq<5 documents plus a seeded 8/9/8 tercile draw of the nreq=5 stratum, by excerpt characters."""
    small = [row for row in index if row["nreq"] < 5]
    five = sorted((row for row in index if row["nreq"] == 5), key=lambda row: (row["chars"], row["id"]))
    t1, t2 = len(five) // 3, 2 * len(five) // 3
    buckets = {"short": five[:t1], "mid": five[t1:t2], "long": five[t2:]}
    alloc = {"short": 8, "mid": 9, "long": 8}
    picked = list(small)
    for name, bucket in buckets.items():
        picked += random.Random(f"{SEED}:{name}").sample(bucket, min(alloc[name], len(bucket)))
    picked.sort(key=lambda row: row["id"])
    bounds = {"short_max": five[t1]["chars"], "mid_max": five[t2]["chars"]}
    return picked, bounds


def length_group(chars: int, bounds: dict) -> str:
    if chars < bounds["short_max"]:
        return "short"
    if chars < bounds["mid_max"]:
        return "mid"
    return "long"


# ---------- arm A: the existing chat-protocol run, sliced ----------

def baseline_rows(ids: set[str]) -> list[dict]:
    rows = []
    for line in (BASELINE / "results.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("item") in ids and row.get("status") in {"PASS", "FAIL"}:
            rows.append(row)
    return rows


# ---------- arm B: one sandboxed file-protocol session ----------

def stage_task(task: dict, repeat: int, scratch: Path) -> Path:
    """A task folder for run_opencode: the document as input/excerpt.md, the short instruction as
    input/requirements.md (the chat message). No gold ever enters the staging folder."""
    folder = scratch / f"{task['id']}-r{repeat}"
    if not (folder / "input" / "excerpt.md").is_file():
        (folder / "input").mkdir(parents=True, exist_ok=True)
        shutil.copy2(task["dir"] / "input" / "excerpt.md", folder / "input" / "excerpt.md")
        (folder / "input" / "requirements.md").write_text(INSTRUCTION, encoding="utf-8")
        (folder / "case.yaml").write_text(yaml.safe_dump({"id": folder.name, "type": "SIDE"}), encoding="utf-8")
    return folder


def reply_text(workspace: Path, stdout: str) -> tuple[str, str]:
    """answer.json first (the protocol asked for it), then the answer.md the PROMPT_SUFFIX mentions, then
    the session stdout - the same fallback chain the chat protocol's rows were read with."""
    for name in ("answer.json", "answer.md"):
        path = workspace / name
        if path.is_file() and path.read_text(encoding="utf-8").strip():
            return path.read_text(encoding="utf-8"), name
    return stdout, "stdout"


def sentence_diff(expected: list, actual) -> dict:
    """Multiset diff of the two sentence lists, for the failure write-up only; never used for scoring."""
    if not isinstance(actual, list):
        actual = []
    exp, act = Counter(expected), Counter(s for s in actual if isinstance(s, str))
    missing, extra = list((exp - act).elements()), list((act - exp).elements())

    def loose(s: str) -> str:
        return re.sub(r"\s+", " ", s.lower().strip())

    near = sum(1 for s in missing if any(loose(s) == loose(t) for t in extra))
    return {"missing": len(missing), "extra": len(extra), "near_miss_whitespace_case": near,
            "missing_examples": missing[:2], "extra_examples": extra[:2]}


# ---------- run, resume, budget ----------

def _rows(folder: Path) -> list[dict]:
    path = folder / "results.jsonl"
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _open_folder(model: str) -> Path:
    matches = sorted((ROOT / "analysis").glob(PREFIX + f"-{model}-*"))
    for folder in reversed(matches):
        meta = folder / "meta.json"
        if meta.is_file():
            try:
                if json.loads(meta.read_text(encoding="utf-8")).get("model") == model:
                    return folder
            except json.JSONDecodeError:
                pass
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    folder = ROOT / "analysis" / f"{PREFIX}-{model}-{stamp}"
    folder.mkdir(parents=True)
    (folder / "meta.json").write_text(json.dumps({"model": model, "started": stamp}, indent=2), encoding="utf-8")
    return folder


def _page_running() -> bool:
    with socket.socket() as probe:
        probe.settimeout(0.3)
        return probe.connect_ex(("127.0.0.1", 8770)) == 0


def run_one(task: dict, repeat: int, args, folder: Path, scratch: Path) -> dict:
    record = {"bench": "pure", "protocol": "file", "candidate": "opencode", "model": args.model,
              "repeat": repeat, "item": task["id"], "doc_chars": task["chars"], "nreq": task["nreq"]}
    try:
        staged = stage_task(task, repeat, scratch)
        solved = run_opencode(staged)
        text, source = reply_text(Path(solved["workspace"]), solved["text"])
        if not str(text).strip():
            raise RuntimeError("empty reply (no answer.json, no answer.md, empty stdout)")
        record["reply_source"] = source
        record["returncode"] = solved["returncode"]
        record["usage"] = usage_from_log(Path(solved["workspace"]).parent / "stdout.jsonl")
        record["answer"] = text[:4000]
        scored = score_answer(task["dir"], text)
        actual = scored.get("actual") if isinstance(scored.get("actual"), dict) else {}
        record.update({"status": scored["status"], "expected": scored.get("expected"), "actual": scored.get("actual"),
                       "reason": scored.get("reason"),
                       "diff": sentence_diff(scored["expected"]["requirements"], actual.get("requirements"))
                       if scored.get("expected") else None})
    except Exception as exc:
        record["error"] = f"{type(exc).__name__}: {exc}"
        record["scored"] = False
        record["status"] = "ERROR"
    return record


def run_experiment(args, docs: list[dict], bounds: dict) -> Path:
    if _page_running():
        raise SystemExit("the results page (8770) is up and serves answer keys; stop it before a sandboxed run")
    load_env()
    os.environ["MVP_LLM_MODEL"] = args.model
    folder = _open_folder(args.model)
    rows = _rows(folder)
    done = {(row.get("repeat"), row.get("item")) for row in rows if not row.get("error")}
    attempts = len(rows)
    jobs = [(task, repeat) for repeat in range(1, args.repeats + 1) for task in docs
            if (repeat, task["id"]) not in done]
    if args.limit:
        jobs = jobs[:args.limit]
    if attempts + len(jobs) > BUDGET:
        jobs = jobs[: max(0, BUDGET - attempts)]
        print(f"budget cap: only {len(jobs)} of the pending rows fit under {BUDGET} invocations", flush=True)
    print(f"{folder.name}: {len(jobs)} rows to run, {attempts} invocations already spent "
          f"(cap {BUDGET})", flush=True)
    scratch = ROOT / "mvp" / "exam-inbox" / f"pure-file-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"

    def run(job):
        task, repeat = job
        record = run_one(task, repeat, args, folder, scratch)
        with LOCK:
            with (folder / "results.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            note = f" via {record['reply_source']}" if record.get("reply_source") else ""
            print(f"r{repeat} {record['item']} {record.get('status', 'ERROR')}{note}"
                  + (f" :: {record['error']}" if record.get("error") else ""), flush=True)

    try:
        if jobs:
            with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
                list(pool.map(run, jobs))
    finally:
        if scratch.is_dir():
            shutil.rmtree(scratch, ignore_errors=True)
    return folder


# ---------- summary and report ----------

def _bucket(rows: list[dict]) -> dict:
    n = len(rows)
    hits = sum(row.get("status") == "PASS" for row in rows)
    return {"rows": n, "pass": hits, "pass_rate": round(hits / n, 4) if n else None}


def _grouped(rows: list[dict], key) -> dict:
    out: dict[str, dict] = {}
    for row in rows:
        out.setdefault(str(key(row)), []).append(row)
    return {name: _bucket(group) for name, group in sorted(out.items())}


def _usage_total(rows: list[dict]) -> dict:
    total = {"rows": 0, "calls": 0, "input": 0, "cached": 0, "output": 0}
    for row in rows:
        usage = row.get("usage") or {}
        total["rows"] += 1
        total["calls"] += usage.get("calls") or 0
        for name in ("input", "cached", "output"):
            total[name] += usage.get(name) or 0
    return total


def write_outputs(folder: Path, docs: list[dict], bounds: dict, model: str) -> dict:
    ids = {row["id"] for row in docs}
    experiment = [row for row in _rows(folder) if not row.get("error")]
    base = baseline_rows(ids)
    by_id = {row["id"]: row for row in docs}
    group = lambda row: length_group(row.get("doc_chars") or by_id[row["item"]]["chars"], bounds)

    per_doc = []
    for row in docs:
        exp = [r for r in experiment if r["item"] == row["id"]]
        old = [r for r in base if r["item"] == row["id"]]
        per_doc.append({"id": row["id"], "chars": row["chars"], "nreq": row["nreq"],
                        "group": length_group(row["chars"], bounds),
                        "file_pass": sum(r.get("status") == "PASS" for r in exp), "file_rows": len(exp),
                        "chat_pass": sum(r.get("status") == "PASS" for r in old), "chat_rows": len(old)})
    invocations = len(_rows(folder))
    summary = {
        "experiment": "PURE file protocol vs chat protocol (opencode sandbox, same scorer)",
        "hypothesis": "the 5-20% PURE low scores are protocol-caused (whole document in the chat window + "
                      "verbatim recitation); the document as a file worked with tools raises the pass rate",
        "model": model, "seed": SEED, "documents": len(docs), "repeats": 3,
        "sampling": "all nreq<5 documents (5) plus 8/9/8 from the character terciles of the nreq=5 stratum "
                    "(198), seeded draws; tercile bounds also label the small documents",
        "scoring": "bench.score_answer QRY on datasets/pure/tasks gold, unmodified: canon-sorted exact "
                   "multiset equality of the requirements list (case- and whitespace-sensitive, duplicates kept)",
        "baseline": {"folder": str(BASELINE.relative_to(ROOT)), "protocol": "chat (document = the prompt)",
                     "model": base[0]["model"] if base else None},
        "file_protocol": {"instruction_chars": len(INSTRUCTION), "document_file": "input/excerpt.md (byte-identical to the chat prompt's document)",
                          "answer_file": "answer.json (fallback answer.md, then stdout)"},
        "budget": {"cap_invocations": BUDGET, "invocations_spent": invocations},
        "file_protocol_overall": _bucket(experiment),
        "chat_protocol_overall": _bucket(base),
        "file_protocol_by_length": _grouped(experiment, group),
        "chat_protocol_by_length": _grouped(base, group),
        "file_protocol_by_nreq": _grouped(experiment, lambda row: by_id[row["item"]]["nreq"]),
        "chat_protocol_by_nreq": _grouped(base, lambda row: by_id[row["item"]]["nreq"]),
        "per_document": per_doc,
        "usage": {"file_protocol": _usage_total(experiment), "chat_protocol_slice": _usage_total(base),
                  "chat_protocol_full_609": _usage_total(_rows(BASELINE))},
    }
    (folder / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    (folder / "selected-docs.json").write_text(
        json.dumps([{"id": row["id"], "nreq": row["nreq"], "chars": row["chars"],
                     "group": length_group(row["chars"], bounds)} for row in docs], indent=2), encoding="utf-8")
    write_report(folder, summary, experiment)
    return summary


def write_report(folder: Path, summary: dict, experiment: list[dict]) -> None:
    file_all, chat_all = summary["file_protocol_overall"], summary["chat_protocol_overall"]
    lines = [
        "# PURE: file protocol vs chat protocol (opencode sandbox, qwen3.8-flash)",
        "",
        f"Scorer: bench.score_answer on the unmodified datasets/pure/tasks gold (canon-sorted exact multiset",
        f"equality, case/whitespace sensitive, duplicates kept). Arm A (chat): the existing full run",
        f"{summary['baseline']['folder']} sliced to the same {summary['documents']} documents.",
        "Arm B (file): the document is input/excerpt.md in the workspace, byte-identical to arm A's prompt",
        "document; the chat message is the short instruction; the agent works with tools and writes answer.json.",
        "",
        "| arm | pass | rows | rate |",
        "| --- | --- | --- | --- |",
        f"| chat (document = prompt) | {chat_all['pass']} | {chat_all['rows']} | {chat_all['pass_rate']} |",
        f"| file (document = workspace file) | {file_all['pass']} | {file_all['rows']} | {file_all['pass_rate']} |",
        "",
        "## by document length",
        "",
        "| group | chat pass/rows | file pass/rows |",
        "| --- | --- | --- |",
    ]
    for name in sorted(set(summary["chat_protocol_by_length"]) | set(summary["file_protocol_by_length"])):
        chat = summary["chat_protocol_by_length"].get(name, {})
        new = summary["file_protocol_by_length"].get(name, {})
        lines.append(f"| {name} | {chat.get('pass')}/{chat.get('rows')} | {new.get('pass')}/{new.get('rows')} |")
    lines += ["", "## by gold requirement count", "", "| nreq | chat | file |", "| --- | --- | --- |"]
    for name in sorted(set(summary["chat_protocol_by_nreq"]) | set(summary["file_protocol_by_nreq"]), key=str):
        chat = summary["chat_protocol_by_nreq"].get(name, {})
        new = summary["file_protocol_by_nreq"].get(name, {})
        lines.append(f"| {name} | {chat.get('pass')}/{chat.get('rows')} | {new.get('pass')}/{new.get('rows')} |")
    fails = [row for row in experiment if row.get("status") == "FAIL"]
    lines += ["", f"## failure examples ({len(fails)} FAIL rows in arm B)", ""]
    for row in fails[:3]:
        diff = row.get("diff") or {}
        lines += [f"### {row['item']} r{row['repeat']} ({row['doc_chars']} chars, {row['nreq']} reqs, "
                  f"reply via {row.get('reply_source')})",
                  f"- {diff.get('missing')} missing, {diff.get('extra')} extra, "
                  f"{diff.get('near_miss_whitespace_case')} near-miss (case/whitespace only)"]
        for miss in (diff.get("missing_examples") or [])[:1]:
            lines.append(f"- missing: {miss[:300]}")
        for extra in (diff.get("extra_examples") or [])[:1]:
            lines.append(f"- extra: {extra[:300]}")
        lines.append("")
    usage = summary["usage"]
    lines += ["## cost", "",
              f"- sandbox invocations spent: {summary['budget']['invocations_spent']} (cap {summary['budget']['cap_invocations']})",
              f"- arm B model calls {usage['file_protocol']['calls']}, tokens in/cached/out "
              f"{usage['file_protocol']['input']}/{usage['file_protocol']['cached']}/{usage['file_protocol']['output']}",
              f"- arm A slice (chat, same 30 docs): {usage['chat_protocol_slice']['calls']} calls, tokens in/cached/out "
              f"{usage['chat_protocol_slice']['input']}/{usage['chat_protocol_slice']['cached']}/{usage['chat_protocol_slice']['output']}"]
    (folder / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="qwen3.8-flash")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--limit", type=int, default=0, help="run at most N pending rows (smoke test)")
    parser.add_argument("--summary-only", action="store_true", help="no runs; rewrite summary and report")
    args = parser.parse_args()
    index = pure_index()
    docs, bounds = sample_docs(index)
    if args.summary_only:
        folder = _open_folder(args.model)
    else:
        folder = run_experiment(args, docs, bounds)
    summary = write_outputs(folder, docs, bounds, args.model)
    print(f"file: {summary['file_protocol_overall']}  chat: {summary['chat_protocol_overall']}")
    print(folder)


if __name__ == "__main__":
    main()
