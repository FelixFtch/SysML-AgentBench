"""Run one systemone-wire judge (official TypeSafe API, kev server, mojev server).

Usage: run_http_judge.py --name jev-api --base-url https://api.typesafe.ai/v1/systemone \
         [--key-env TYPESAFE_API_KEY] [--chunk 40] [--per-doc 120] [--sleep 2] OUT.jsonl
"""
import argparse, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from systemone_client import (load_texts, chunks, state_for, noul_question,
                              post_json, parse_noul, sample_doc)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--key-env")
    ap.add_argument("--model", default="jev-latest")
    ap.add_argument("--chunk", type=int, default=40)
    ap.add_argument("--per-doc", type=int, default=0, help="0 = all sentences")
    ap.add_argument("--sleep", type=float, default=0.0)
    ap.add_argument("--max-calls", type=int, default=10**9)
    ap.add_argument("--timeout", type=float, default=240)
    ap.add_argument("out")
    a = ap.parse_args()

    headers = {}
    if a.key_env:
        key = os.environ.get(a.key_env, "")
        assert key, f"missing env {a.key_env}"
        headers["authorization"] = f"Bearer {key}"

    rows = load_texts()
    if a.per_doc:
        by_doc = {}
        for r in rows:
            by_doc.setdefault(r["doc"], []).append(r)
        rows = sample_doc(by_doc, a.per_doc)
        # group sampled rows back into per-doc contiguous chunks
        groups = []
        for doc in sorted({r["doc"] for r in rows}):
            groups.append([r for r in rows if r["doc"] == doc])
    else:
        by_doc = {}
        for r in rows:
            by_doc.setdefault(r["doc"], []).append(r)
        groups = [by_doc[d] for d in sorted(by_doc)]

    fh = open(a.out, "w")
    n_calls = 0
    t_start = time.time()
    total_lat = 0.0
    for g in groups:
        for ch in chunks(g, a.chunk):
            if n_calls >= a.max_calls:
                break
            body = {"model": a.model, "state": state_for(ch),
                    "questions": {str(r["uid"]): noul_question(r["uid"] % 10000, r["text"]) for r in ch}}
            ans, lat, err = None, 0.0, None
            for attempt in range(4):
                ans, lat, err = post_json(a.base_url, body, headers, a.timeout)
                if err and ("429" in err or "529" in err) and attempt < 3:
                    time.sleep(5 * (attempt + 1)); continue
                break
            n_calls += 1; total_lat += lat
            if ans is None:
                for r in ch:
                    fh.write(json.dumps({"uid": r["uid"], "doc": r["doc"], "judge": a.name,
                                         "prob": None, "ok": False, "err": err}, ensure_ascii=False) + "\n")
            else:
                answers = ans.get("answers", {})
                for r in ch:
                    p = parse_noul(answers.get(str(r["uid"])))
                    fh.write(json.dumps({"uid": r["uid"], "doc": r["doc"], "judge": a.name,
                                         "prob": p, "ok": p is not None,
                                         "err": None if p is not None else "unparseable"},
                                        ensure_ascii=False) + "\n")
            fh.flush()
            print(f"call {n_calls} doc={ch[0]['doc'][:24]} n={len(ch)} lat={lat:.2f}s err={err}", flush=True)
            if a.sleep:
                time.sleep(a.sleep)
        if n_calls >= a.max_calls:
            break
    dt = time.time() - t_start
    meta = {"judge": a.name, "calls": n_calls, "wall_s": round(dt, 1),
            "sum_call_latency_s": round(total_lat, 1)}
    json.dump(meta, open(a.out + ".meta", "w"), indent=1)
    print(json.dumps(meta))

if __name__ == "__main__":
    main()
