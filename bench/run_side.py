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
import fcntl
import hashlib
import json
import os
import random
import re
import shutil
import sys
import threading
import time
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


def seb_subset(rows: dict, subset: str) -> list[str]:
    """The published 100-question draw, or every question in the file. The answer column is not used to choose."""
    if subset == "all":
        return sorted(rows, key=int)
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


PACKAGE_DECL = re.compile(r"\bpackage\s+(?:'[^']+'|[A-Za-z_][A-Za-z0-9_]*)")
REQ_HEAD = re.compile(r"\brequirement\b(?:\s+def\b)?[^{;]*\{")
MARKER = re.compile(r"\((?:M|O|I|MI|RI|RR)\)")
MIN_PROSE_WORDS = 8


def _words(text: str) -> list[str]:
    """The words of a text, lower case, numbering and punctuation aside: the unit of the fidelity check."""
    text = MARKER.sub(" ", text)
    text = re.sub(r"^\s*(?:\d+(?:\.\d+)*[a-z]?|REQ-\d+:?)\s+", "", text)
    return re.findall(r"[a-z0-9]+", text.lower())


def _contains(haystack: list[str], needle: list[str]) -> bool:
    if not needle:
        return False
    first = needle[0]
    for index, word in enumerate(haystack):
        if word == first and haystack[index:index + len(needle)] == needle:
            return True
    return False


def _requirement_bodies(source: str) -> list[str]:
    """The text inside every `requirement def X { ... }` or `requirement x { ... }` of the package, braces balanced."""
    bodies = []
    for match in REQ_HEAD.finditer(source):
        depth, start = 1, match.end()
        index = start
        while index < len(source) and depth:
            depth += {"{": 1, "}": -1}.get(source[index], 0)
            index += 1
        bodies.append(source[start:index - 1] if depth == 0 else source[start:])
    return bodies


def pure_score(task_dir: Path, text: str, workspace: Path | None = None) -> dict:
    """Protocol sysml-v2: the reply is a SysML v2 package. PASS when the official Pilot parses it, every marked
    requirement is inside one requirement def (its words in order), no explanatory paragraph is inside one, there is
    no requirement def beyond the marked ones, and no number with a unit is outside the passage. Passages without
    items.json are the two original excerpts and go to bench.score_answer unchanged."""
    items_file = task_dir / "input" / "items.json"
    if not items_file.is_file():
        return score_answer(task_dir, text)
    from agents.llm import extract_sysml
    from bench.score_answer import invented_numbers
    from mvp.engine import run_submitted_model
    case = yaml.safe_load((task_dir / "case.yaml").read_text(encoding="utf-8"))
    expected = json.loads((task_dir / "gold" / "answer.json").read_text(encoding="utf-8"))["requirements"]
    items = json.loads(items_file.read_text(encoding="utf-8"))
    kinds = json.loads((task_dir / "gold" / "units.json").read_text(encoding="utf-8"))
    passage = "\n".join(items[key] for key in sorted(items, key=int))
    result = {"status": "FAIL", "expected": expected, "total": len(expected), "covered": 0, "extra": 0, "prose_inside": 0,
              "invented": [], "pilot": None, "package": None}
    try:
        source = extract_sysml(text)
    except ValueError as exc:
        result["reason"] = str(exc)
        return result
    declared = PACKAGE_DECL.search(source)
    if not declared:
        result["reason"] = "The sysml block declares no package."
        return result
    package = declared.group(0).split(None, 1)[1].strip("'")
    folder = workspace or (ROOT / "mvp" / "exam-inbox" / f"side-pure-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')}")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{package}.sysml"
    path.write_text(source, encoding="utf-8")
    validated = run_submitted_model([path], package, label=f"side-pure-{case['id']}")
    result.update({"package": package, "pilot": validated["sysml"]["status"], "run_dir": str(validated["run_dir"]),
                   "diagnostics": [item.get("message") for item in validated["sysml"].get("diagnostics", [])][:5]})
    bodies = [_words(body) for body in _requirement_bodies(source)]
    covered = []
    used: set[int] = set()
    for number in expected:  # one requirement def per requirement: two identical clauses need two defs
        needle = _words(items[str(number)])
        hits = [index for index, body in enumerate(bodies) if _contains(body, needle)]
        hit = next((index for index in hits if index not in used), hits[0] if hits else None)
        if hit is not None:
            used.add(hit)
        covered.append(hit)
    result["covered"] = sum(1 for hit in covered if hit is not None)
    result["missing"] = [number for number, hit in zip(expected, covered) if hit is None]
    result["extra"] = len(bodies) - len(used)
    prose = [key for key, kind in kinds.items() if kind == "text" and len(_words(items[key])) >= MIN_PROSE_WORDS]
    result["prose_inside"] = sum(1 for key in prose if any(_contains(body, _words(items[key])) for body in bodies))
    result["invented"] = invented_numbers(source, passage)
    result["tp"] = result["covered"]
    result["fn"] = len(expected) - result["covered"]
    result["fp"] = result["extra"]
    ok = (result["pilot"] == "PASS" and not result["missing"] and result["extra"] == 0 and result["prose_inside"] == 0
          and not result["invented"])
    result["status"] = "PASS" if ok else "FAIL"
    if not ok:
        reasons = []
        if result["pilot"] != "PASS":
            reasons.append("official parse failed")
        if result["missing"]:
            reasons.append(f"{len(result['missing'])} requirement(s) not in a requirement def")
        if result["extra"]:
            reasons.append(f"{result['extra']} requirement def(s) beyond the marked requirements")
        if result["prose_inside"]:
            reasons.append(f"{result['prose_inside']} explanatory paragraph(s) inside a requirement def")
        if result["invented"]:
            reasons.append(f"number not in the passage: {', '.join(result['invented'][:3])}")
        result["reason"] = "; ".join(reasons)
    return result


def _ask_direct_approach(approach: str, model: str, prompt_id: str, prompt: str) -> dict:
    """One fresh session of a direct chat flow (P0–P3). A new session each prompt, so nothing carries over."""
    from bench.chat_turns import direct_turn
    result = direct_turn(f"side-{prompt_id}", prompt, approach, model, rounds=20)
    return {"text": result["answer"], "usage": result.get("usage") or {}}


def _job_reply(job_id: str) -> str:
    """The chat text Langflow stores on the job. The message row is often still empty when the job is marked completed."""
    import sqlite3
    from bench.langflow_exam import DB
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    row = con.execute("SELECT result FROM job WHERE job_id=?", (job_id.replace("-", ""),)).fetchone()
    con.close()
    if not row or not row[0] or row[0] == "null":
        return ""
    try:
        data = json.loads(row[0])
    except json.JSONDecodeError:
        return ""
    texts = []
    for item in data.get("outputs") or []:
        content = item.get("content") if isinstance(item, dict) else None
        if isinstance(content, str) and content.strip():
            texts.append(content.strip())
    return texts[-1] if texts else ""


def _session_reply(session: str) -> str:
    """The assistant text for this session. Langflow writes it after the job row flips to completed, and the job's
    error column is the string 'null' when there is no error, so the job row alone cannot be the reply."""
    import sqlite3
    from bench.langflow_exam import DB
    for _ in range(8):
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        rows = con.execute("SELECT text FROM message WHERE session_id=? AND sender='Machine' ORDER BY timestamp", (session,)).fetchall()
        con.close()
        texts = [row[0].strip() for row in rows if row[0] and row[0].strip()]
        if texts:
            return texts[-1]
        time.sleep(1)
    return ""


def _ask_langflow(flow_name: str, model: str, prompt_id: str, prompt: str) -> dict:
    """One message through a Langflow chat flow, model set at run time. The flow file is not edited."""
    import bench.langflow_exam as exam
    exam.NEEDS.setdefault(flow_name, ["tool-memory-search", "tool-validate-sysml", "tool-write-to-memory", "tool-design-pipeline"])
    token = exam._token()
    exam._ensure_provider(token)
    flow = exam._flow(token, flow_name)
    session = f"side-{prompt_id}-{datetime.now(timezone.utc).strftime('%H%M%S')}"
    body = {"flow_id": flow["id"], "input_value": prompt, "mode": "background", "session_id": session,
            "tweaks": exam._model_tweaks(flow, model)}
    job = exam._request("POST", "/api/v2/workflows", token, body, timeout=60)
    final = exam._wait(token, job["job_id"], 900)
    stored = exam._stored_message(session, flow["id"])
    text = ((stored.get("text") or "").strip() or _job_reply(job["job_id"]) or _session_reply(session)
            or ((final.get("output") or {}).get("text") or ""))
    if final.get("status") != "completed" or not str(text).strip():
        raise RuntimeError(f"Langflow job {final.get('status')} produced no reply")
    return {"text": text, "usage": stored.get("usage") or {}}


def ask(candidate: str, model: str, prompt_id: str, prompt: str, system: str, scratch: Path) -> dict:
    """Run one prompt through one candidate. Returns text and usage."""
    if candidate == "direct":
        calls: list[dict] = []
        USAGE_LOG.set(calls)
        os.environ["MVP_LLM_MODEL"] = model
        budget = 6000 if "sysml" in system.lower() else 1500
        reply = chat([{"role": "system", "content": system}, {"role": "user", "content": prompt}], max_tokens=budget)
        return {"text": reply["text"], "usage": usage_summary(calls)}
    if candidate.startswith("direct-"):
        return _ask_direct_approach(candidate.split("-", 1)[1].upper(), model, prompt_id, prompt)
    if candidate == "langflow":
        return _ask_langflow(os.environ["RTRC_SIDE_FLOW"], model, prompt_id, prompt)
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


def _claim_path(args) -> Path:
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_",
                  f"{args.bench}__{args.candidate}__{args.subset}__{args.pure}__{args.flow or ''}__{args.model}")[:180]
    return ROOT / ".langflow" / "side-claims" / name


def _pid_alive(pid: int) -> bool:
    proc = Path(f"/proc/{pid}")
    if pid <= 0 or not proc.exists():
        return False
    try:
        state = (proc / "stat").read_text(encoding="utf-8").rsplit(")", 1)[-1].split()[0]
    except OSError:
        return False
    return state not in {"Z", "X"}


def _slug(args) -> str:
    if args.candidate != "langflow":
        return args.candidate
    return "lf-" + re.sub(r"[^A-Za-z0-9]+", "-", args.flow or "").strip("-").lower()[:40]


def _run_matches(folder: Path, args) -> bool:
    summary = folder / "summary.json"
    if not summary.is_file():
        return False
    try:
        meta = json.loads(summary.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    if meta.get("bench") != args.bench or meta.get("candidate") != args.candidate or meta.get("model") != args.model:
        return False
    if meta.get("flow") != args.flow or meta.get("repeats") != args.repeats:
        return False
    if args.bench == "sysengbench":
        return meta.get("subset") == ("all" if args.subset == "all" else str(SEB_IDS.relative_to(ROOT)))
    return meta.get("pure") == args.pure and meta.get("protocol") == _pure_protocol(args)


def _pure_protocol(args) -> str | None:
    """The task protocol of a full PURE run (from the build record), so a run of the copy protocol and a run of the
    demarcation protocol never share a folder. The two original excerpts have no protocol field."""
    if args.bench != "pure" or args.pure != "all":
        return None
    build = ROOT / "datasets" / "pure" / "tasks" / "BUILD.json"
    if build.is_file():
        return json.loads(build.read_text(encoding="utf-8")).get("protocol")
    return "copy-v1"


def _latest_folder(args) -> Path | None:
    matches = [path for path in (ROOT / "analysis").glob(f"side-{args.bench}-{_slug(args)}-{args.model}-*") if _run_matches(path, args)]
    return max(matches, key=lambda path: path.name) if matches else None


def _kept(record: dict, bench: str) -> bool:
    """A row that can stand as this item's score. An empty reply is not a zero."""
    if record.get("error") or record.get("scored") is False:
        return False
    if not str(record.get("answer") or "").strip():
        return False
    if bench == "sysengbench":
        return int(record.get("n") or 0) > 0
    return record.get("status") not in (None, "ERROR")


def _kept_rows(folder: Path, bench: str) -> list[dict]:
    path = folder / "results.jsonl"
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if _kept(record, bench):
            rows.append(record)
    return rows


def _read_holder(claim: Path) -> int:
    if not claim.is_file():
        return 0
    token = claim.read_text(encoding="utf-8").split()
    try:
        return int(token[0]) if token else 0
    except ValueError:
        return 0


def _take_queue(args, jobs: list, meta: dict) -> tuple[Path, list]:
    """One run per bench, candidate, subset and flow.

    A later launch waits for the live process, then uses that folder if every item already has a real score.
    It continues the same folder when the first process stopped short. It does not start a second copy, and it
    does not treat "someone is running" as finished.
    """
    claim = _claim_path(args)
    claim.parent.mkdir(parents=True, exist_ok=True)
    lock_path = Path(str(claim) + ".lock")
    while True:
        holder = 0
        with lock_path.open("a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            holder = _read_holder(claim)
            folder = _latest_folder(args)
            fresh = folder / "results.jsonl" if folder is not None else None
            busy = bool(holder and holder != os.getpid() and _pid_alive(holder))
            if not busy and fresh is not None and fresh.is_file() and time.time() - fresh.stat().st_mtime < 90:
                busy = True
                holder = holder or -1
            if not busy:
                if folder is None:
                    folder = ROOT / "analysis" / f"side-{args.bench}-{_slug(args)}-{args.model}-{meta['started']}"
                    folder.mkdir(parents=True)
                    (folder / "summary.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
                    pending = list(jobs)
                else:
                    kept = _kept_rows(folder, args.bench)
                    (folder / "results.jsonl").write_text(
                        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in kept), encoding="utf-8")
                    done = {(row.get("repeat"), row.get("item")) for row in kept}
                    pending = [job for job in jobs if (job[0], job[1]) not in done]
                    if pending and done:
                        print(f"resume {folder} ({len(done)} already scored, {len(pending)} left)", flush=True)
                    elif pending:
                        print(f"redo {folder} (no scored rows kept; empty replies are not zeros)", flush=True)
                if not pending:
                    print(f"already finished in {folder}", flush=True)
                    claim.unlink(missing_ok=True)
                    return folder, []
                claim.write_text(f"{os.getpid()} {folder.relative_to(ROOT)}\n", encoding="utf-8")
                return folder, pending
        print(f"queued behind pid {holder}; waiting, not starting a second copy", flush=True)
        if holder > 0:
            while _pid_alive(holder):
                time.sleep(15)
        else:
            time.sleep(15)


def _release_queue(args) -> None:
    claim = _claim_path(args)
    if claim.is_file() and claim.read_text(encoding="utf-8").split()[:1] == [str(os.getpid())]:
        claim.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", choices=["sysengbench", "pure"], required=True)
    parser.add_argument("--candidate", required=True,
                        help="direct, direct-p0 … direct-p3 (the four direct chat flows), opencode, claude, or langflow")
    parser.add_argument("--flow", default=None, help="Langflow flow name when --candidate langflow")
    parser.add_argument("--subset", choices=["100", "all"], default="100",
                        help="SysEngBench only: the published 100-question draw, or every question in test.csv")
    parser.add_argument("--pure", choices=["excerpts", "all"], default="excerpts",
                        help="excerpts: the two original sentences. all: every <req> in the PURE XML subset, in passages of five")
    parser.add_argument("--model", default="qwen3.8-flash")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    if args.candidate == "langflow" and not args.flow:
        raise SystemExit("--candidate langflow needs --flow")
    if args.candidate.startswith("direct-") and args.candidate.split("-", 1)[1].upper() not in {"P0", "P1", "P2", "P3"}:
        raise SystemExit("--candidate direct-p0, direct-p1, direct-p2 or direct-p3")
    if args.flow:
        os.environ["RTRC_SIDE_FLOW"] = args.flow
    load_env()
    os.environ["MVP_LLM_MODEL"] = args.model
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    meta = {"bench": args.bench, "candidate": args.candidate, "flow": args.flow, "model": args.model, "repeats": args.repeats, "started": stamp}
    if args.bench == "sysengbench":
        rows = seb_rows()
        ids = seb_subset(rows, args.subset)
        prompts = seb_prompts(rows, ids)
        meta.update({"dataset": "rabell/SysEngBench test.csv", "sha256": hashlib.sha256(SEB_CSV.read_bytes()).hexdigest(),
                     "subset": "all" if args.subset == "all" else str(SEB_IDS.relative_to(ROOT)), "seed": SEED, "questions": len(ids), "per_prompt": BATCH,
                     "always_B_on_subset": sum(rows[q]["answer"] == "B" for q in ids)})
        system = "Answer the multiple-choice questions. One JSON object, no prose."
        jobs = [(repeat, pid, text, chunk) for repeat in range(1, args.repeats + 1) for pid, text, chunk in prompts]
    else:
        pure_root = ROOT / "datasets" / "pure" / "tasks" if args.pure == "all" else PURE
        names = sorted(p.name for p in pure_root.iterdir() if (p / "input" / "excerpt.md").is_file()) if args.pure == "all" else list(PURE_TASKS)
        if args.pure == "all" and not names:
            raise SystemExit("No PURE tasks in datasets/pure/tasks. Run: python3 bench/build_pure_tasks.py")
        jobs = []
        for name in names:
            excerpt = (pure_root / name / "input" / "excerpt.md").read_text(encoding="utf-8")
            jobs += [(repeat, name, excerpt, pure_root / name) for repeat in range(1, args.repeats + 1)]
        rows = None
        meta["pure"] = args.pure
        meta["documents"] = len(names)
        meta["protocol"] = _pure_protocol(args)
        if meta["protocol"] == "sysml-v2":
            system = ("You write SysML v2 textual notation. Reply with the complete package in one fenced code block tagged sysml "
                      "and nothing else. Never invent a number.")
        else:
            system = "Reply with one JSON object and no prose, using the field names required by the task."
        build = ROOT / "datasets" / "pure" / "tasks" / "BUILD.json"
        if args.pure == "all" and build.is_file():
            meta["tasks_sha256"] = json.loads(build.read_text(encoding="utf-8")).get("tasks_sha256")
    out, jobs = _take_queue(args, jobs, meta)
    if not jobs:
        print(out)
        return
    scratch = ROOT / "mvp" / "exam-inbox" / f"side-{args.bench}-{args.candidate}-{stamp}"

    def run(job):
        repeat, pid, text, chunk = job
        record = {"bench": args.bench, "candidate": args.candidate, "model": args.model, "repeat": repeat, "item": pid}
        try:
            reply = ask(args.candidate, args.model, f"{pid}-r{repeat}", text, system, scratch)
            if not str(reply.get("text") or "").strip():
                raise RuntimeError("empty reply")
            record["usage"] = reply.get("usage")
            record["answer"] = reply["text"][:4000]
            if args.bench == "sysengbench":
                graded = seb_score(reply["text"], chunk, rows)
                record.update({"questions": graded, "correct": sum(item["correct"] for item in graded), "n": len(graded)})
            else:
                scored = pure_score(chunk if isinstance(chunk, Path) else PURE / pid, reply["text"],
                                    workspace=out / "graded" / f"{pid}-r{repeat}")
                record.update({key: scored[key] for key in ("status", "expected", "actual", "tp", "fp", "fn", "total", "covered", "missing", "extra",
                                                            "prose_inside", "invented", "pilot", "package", "run_dir", "diagnostics", "reason") if key in scored})
        except Exception as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"
            record["scored"] = False
            if args.bench == "sysengbench":
                record.update({"correct": 0, "n": 0})
            else:
                record["status"] = "ERROR"
        with LOCK:
            with (out / "results.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            if record.get("scored") is False:
                line = f"r{repeat} {pid} ERROR"
            elif args.bench == "sysengbench":
                line = f"r{repeat} {pid} {record.get('correct')}/{record.get('n')}"
            else:
                line = f"r{repeat} {pid} {record.get('status', '?')}"
            print(line, flush=True)

    try:
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
            list(pool.map(run, jobs))
    finally:
        _release_queue(args)
        shutil.rmtree(scratch, ignore_errors=True)
    _write_totals(out, args.bench)
    print(out)


def _write_totals(out: Path, bench: str) -> None:
    """Totals over the kept rows, into summary.json: SysEngBench correct/n; PURE PASS count and, for the demarcation
    protocol, precision, recall and F1 over all items."""
    rows = _kept_rows(out, bench)
    summary_path = out / "summary.json"
    meta = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.is_file() else {}
    if bench == "sysengbench":
        totals = {"rows": len(rows), "correct": sum(int(r.get("correct") or 0) for r in rows), "n": sum(int(r.get("n") or 0) for r in rows)}
    else:
        tp = sum(int(r.get("tp") or 0) for r in rows)
        fp = sum(int(r.get("fp") or 0) for r in rows)
        fn = sum(int(r.get("fn") or 0) for r in rows)
        precision = tp / (tp + fp) if tp + fp else None
        recall = tp / (tp + fn) if tp + fn else None
        totals = {"rows": len(rows), "pass": sum(1 for r in rows if r.get("status") == "PASS"),
                  "pilot_pass": sum(1 for r in rows if r.get("pilot") == "PASS"),
                  "requirements_covered": tp, "requirements_total": tp + fn, "extra_requirement_defs": fp,
                  "precision": precision, "recall": recall,
                  "f1": (2 * precision * recall / (precision + recall)) if precision and recall else None}
    meta["totals"] = totals
    summary_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
