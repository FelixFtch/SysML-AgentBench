"""Zero-shot qwen3.8-max baseline over all 4217 pilot sentences ("is this a requirement sentence?").

Batched to save budget: every call carries 20 consecutive sentences (kept in document order so the
"excerpt of a requirements specification" framing of the arena holds), each line numbered by uid,
and the model must answer yes/no per sentence as one JSON object (agents.llm.chat, the direct shape
of bench/run_sim_side.ask_direct; temperature 0 for a deterministic classification run).

Sentences whose id is missing or unparseable in a batch reply are re-asked once, alone; a sentence
that fails again is recorded with ans=null (honest no-answer count, never silently imputed here).
Budget red line: hard cap on total calls (default 400 = ceil(4217/20)=211 batches + retry margin).

Output: analysis/jev-arena-cascade-<stamp>/
  preds-max-qwen3.8-max.jsonl       one row per sentence: uid, ans (0/1/null), src (batch/retry/none)
  calls-max-qwen3.8-max.jsonl       one row per API call: kind, uids, reply head, usage, error
  preds-max-qwen3.8-max.jsonl.meta  calls, wall time, token usage, USD at list price
Gold labels are never read by this script (scoring happens in cascade_metrics.py).
"""
import argparse
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from agents.llm import USAGE_LOG, chat, extract_json, usage_summary  # noqa: E402
from bench.experiment import load_env  # noqa: E402
from systemone_client import load_texts, CRIT_TRUE, CRIT_FALSE  # noqa: E402

MODEL = "qwen3.8-max"
SYSTEM = ("You are a careful requirements engineer. Reply with one JSON object and no prose.")
LOCK = threading.Lock()


def batch_prompt(rows):
    body = "\n".join(f'[{r["uid"]}] {r["text"]}' for r in rows)
    return (
        "Excerpt of a software requirements specification document. "
        "Each line is one sentence with its identifier in brackets:\n" + body + "\n\n"
        "For each sentence, decide: is it a software requirement statement?\n"
        f"- yes: {CRIT_TRUE}\n"
        f"- no: {CRIT_FALSE}\n\n"
        "Reply with one JSON object only, exactly one entry per sentence id above:\n"
        '{"answers": [{"id": 0, "a": "yes"}, {"id": 1, "a": "no"}, ...]}'
    )


def single_prompt(row):
    return (
        f'Is sentence [{row["uid"]}] a software requirement statement? '
        f'Sentence [{row["uid"]}]: "{row["text"]}"\n\n'
        f"- yes: {CRIT_TRUE}\n"
        f"- no: {CRIT_FALSE}\n"
        "Reply with one JSON object only: "
        f'{{"id": {row["uid"]}, "a": "yes"}} or {{"id": {row["uid"]}, "a": "no"}}'
    )


def norm_answer(value):
    """yes/no in the common spellings -> 1/0; anything else is a parse failure."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)) and value in (0, 1):
        return int(value)
    if isinstance(value, str):
        low = value.strip().lower()
        if low in {"yes", "y", "true"}:
            return 1
        if low in {"no", "n", "false"}:
            return 0
    return None


def parse_answers(text, wanted_ids):
    """{uid: 0/1} for the wanted ids the reply answered cleanly; the rest come back missing."""
    try:
        data = extract_json(text)
    except (ValueError, json.JSONDecodeError):
        return {}
    items = data.get("answers") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return {}
    out = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        uid, ans = item.get("id"), norm_answer(item.get("a"))
        if isinstance(uid, int) and ans is not None and uid in wanted_ids:
            out[uid] = ans
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--chunk", type=int, default=20)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--max-calls", type=int, default=400, help="budget red line, batch + retry calls")
    ap.add_argument("--folder", default="", help="analysis/jev-arena-cascade-<stamp>/; default: create new")
    args = ap.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    folder = args.folder or os.path.join(ROOT, "analysis", f"jev-arena-cascade-{stamp}")
    os.makedirs(folder, exist_ok=True)
    preds_path = os.path.join(folder, "preds-max-qwen3.8-max.jsonl")
    calls_path = os.path.join(folder, "calls-max-qwen3.8-max.jsonl")

    rows = load_texts()  # uid + text only; gold lives in pilot_sentences.jsonl and is never read here

    # ---- resume: calls already on disk are kept, their answers are final for those sentences
    done_batches, resolved = set(), {}
    if os.path.exists(calls_path):
        for line in open(calls_path, encoding="utf-8"):
            if not line.strip():
                continue
            try:
                call = json.loads(line)
            except json.JSONDecodeError:
                continue
            done_batches.add(call["batch_start"])
            for uid, ans in (call.get("answers") or {}).items():
                if ans is not None:
                    resolved[int(uid)] = ans
        print(f"resume {os.path.basename(folder)}: {len(done_batches)} calls, "
              f"{len(resolved)} sentences already answered", flush=True)

    batches = [rows[i:i + args.chunk] for i in range(0, len(rows), args.chunk)]
    todo = [b for b in batches if b[0]["uid"] not in done_batches]
    n_calls = len(done_batches)
    t0 = time.time()
    usage_rows = []

    def one_call(kind, batch_start, prompt, wanted_ids):
        nonlocal n_calls
        with LOCK:  # reserve the call slot before dialing, so the cap is a real red line
            if n_calls >= args.max_calls:
                return None
            n_calls += 1
        calls, reply, err = [], None, None
        USAGE_LOG.set(calls)
        os.environ["MVP_LLM_MODEL"] = MODEL
        try:
            reply = chat([{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
                         max_tokens=1500, temperature=0.0)
        except Exception as exc:  # network/API failure after llm.py's own retries
            err = f"{type(exc).__name__}: {exc}"
        record = {"kind": kind, "batch_start": batch_start, "uids": sorted(wanted_ids),
                  "answers": parse_answers(reply["text"], wanted_ids) if reply else {},
                  "reply_head": (reply.get("text") or "")[:600] if reply else None,
                  "error": err}
        with LOCK:
            usage_rows.extend(calls)
            with open(calls_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            for uid, ans in record["answers"].items():
                resolved[int(uid)] = ans
            print(f"call {n_calls} {kind} start={batch_start} answered={len(record['answers'])}"
                  f"/{len(wanted_ids)}" + (f" err={err}" if err else ""), flush=True)
        return record

    load_env()
    retry_jobs = []

    def run_batch(batch):
        record = one_call("batch", batch[0]["uid"], batch_prompt(batch), {r["uid"] for r in batch})
        if record is None:
            return
        missing = [r for r in batch if r["uid"] not in record["answers"]]
        if missing:  # every unresolved sentence gets exactly one solo re-ask
            with LOCK:
                retry_jobs.extend(missing)

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        list(pool.map(run_batch, todo))
        for row in list(retry_jobs):  # one retry per still-missing sentence, budget permitting
            if n_calls >= args.max_calls or row["uid"] in resolved:
                continue
            one_call("retry", row["uid"], single_prompt(row), {row["uid"]})

    # ---- per-sentence preds: src says where the answer came from; null = no max answer
    src_of = {}
    if os.path.exists(calls_path):
        for line in open(calls_path, encoding="utf-8"):
            if line.strip():
                call = json.loads(line)
                for uid in call.get("answers") or {}:
                    src_of[int(uid)] = call["kind"]
    with open(preds_path, "w", encoding="utf-8") as fh:
        for row in rows:
            uid = row["uid"]
            fh.write(json.dumps({"uid": uid, "doc": row["doc"], "judge": "qwen3.8-max",
                                 "ans": resolved.get(uid), "src": src_of.get(uid, "none")},
                                ensure_ascii=False) + "\n")

    usage = usage_summary(usage_rows)
    from bench.board_facts import PRICES
    usd = None
    if usage.get("by_model"):
        price = PRICES["models"].get(MODEL)
        if price:
            total, fresh = 0.0, 0
            for slot in usage["by_model"].values():
                fresh = slot.get("prompt_tokens", 0) - slot.get("cached_tokens", 0)
                total += (fresh * price["input"] + slot.get("cached_tokens", 0) * price["cache"]
                          + slot.get("completion_tokens", 0) * price["output"]) / 1e6
            usd = round(total, 4)
    meta = {"judge": "qwen3.8-max", "calls": n_calls, "batches": len(batches),
            "no_answer": sum(1 for r in rows if r["uid"] not in resolved),
            "wall_s": round(time.time() - t0, 1), "usage": usage, "usd_list_price": usd,
            "temperature": 0.0, "chunk": args.chunk}
    with open(preds_path + ".meta", "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=1)
    print(json.dumps(meta, indent=1))
    print(folder)


if __name__ == "__main__":
    main()
