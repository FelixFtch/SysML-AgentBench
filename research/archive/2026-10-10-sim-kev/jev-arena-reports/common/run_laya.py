"""In-process Laya runner (CPU). Usage: run_laya.py OUT.jsonl [chunk]"""
import json, os, resource, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from systemone_client import load_texts, chunks, state_for, noul_question, CRIT_TRUE, CRIT_FALSE

def main(out, chunk=16):
    from laya import Router
    t0 = time.time()
    router = Router()
    print(f"load {time.time()-t0:.1f}s", flush=True)
    rows = load_texts()
    by_doc = {}
    for r in rows:
        by_doc.setdefault(r["doc"], []).append(r)
    fh = open(out, "w")
    total = 0.0; nc = 0
    wt0 = time.time()
    for doc in sorted(by_doc):
        for ch in chunks(by_doc[doc], chunk):
            qs = {str(r["uid"]): noul_question(r["uid"] % 10000, r["text"], with_criteria=False) for r in ch}
            t1 = time.time()
            try:
                res = router.predict(state_for(ch), qs)
                lat = time.time() - t1
                ans = res.get("answers", {})
                for r in ch:
                    a = ans.get(str(r["uid"])) or {}
                    v = a.get("noul")
                    ok = isinstance(v, (int, float))
                    fh.write(json.dumps({"uid": r["uid"], "doc": r["doc"], "judge": "laya",
                                         "prob": float(v) if ok else None, "ok": ok,
                                         "err": None if ok else json.dumps(a)[:120],
                                         "model": res.get("routing", {}).get("model")},
                                        ensure_ascii=False) + "\n")
            except Exception as e:
                lat = time.time() - t1
                for r in ch:
                    fh.write(json.dumps({"uid": r["uid"], "doc": r["doc"], "judge": "laya",
                                         "prob": None, "ok": False, "err": f"{type(e).__name__}: {e}"[:200]},
                                        ensure_ascii=False) + "\n")
            total += lat; nc += 1; fh.flush()
            print(f"doc={doc[:20]} n={len(ch)} lat={lat:.2f}s", flush=True)
    wall = time.time() - wt0
    meta = {"judge": "laya", "calls": nc, "wall_s": round(wall, 1),
            "sum_call_latency_s": round(total, 1),
            "peak_rss_gb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6, 2)}
    fh.close()
    json.dump(meta, open(out + ".meta", "w"), indent=1)
    print(json.dumps(meta))

if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 16)
