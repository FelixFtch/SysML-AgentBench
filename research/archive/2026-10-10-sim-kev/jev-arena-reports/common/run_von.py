"""In-process Von runner (CPU/OpenVINO). Usage: run_von.py OUT.jsonl [chunk]"""
import json, os, resource, sys, time
os.environ.setdefault("VON_NOUL_DECISION", "raw")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from systemone_client import load_texts, chunks, state_for, noul_question

def main(out, chunk=40):
    import von
    t0 = time.time()
    ok_criteria = True
    qs_test = {"t": {"type": "noul", "instructions": "test",
                     "criteria": {"true": "yes it is", "false": "no it is not"}}}
    try:
        von.system_one(state="The system shall log errors.", questions=qs_test)
    except Exception:
        ok_criteria = False
    print(f"load {time.time()-t0:.1f}s criteria={ok_criteria}", flush=True)
    rows = load_texts()
    by_doc = {}
    for r in rows:
        by_doc.setdefault(r["doc"], []).append(r)
    fh = open(out, "w")
    total = 0.0; nc = 0
    wt0 = time.time()
    for doc in sorted(by_doc):
        for ch in chunks(by_doc[doc], chunk):
            qs = {str(r["uid"]): noul_question(r["uid"] % 10000, r["text"], with_criteria=ok_criteria) for r in ch}
            t1 = time.time()
            try:
                res = von.system_one(state=state_for(ch), questions=qs)
                lat = time.time() - t1
                ans = res.answers
                for r in ch:
                    a = ans.get(str(r["uid"]))
                    v = getattr(a, "noul", None) if a is not None else None
                    ok = isinstance(v, (int, float))
                    fh.write(json.dumps({"uid": r["uid"], "doc": r["doc"], "judge": "von",
                                         "prob": float(v) if ok else None, "ok": ok,
                                         "err": None if ok else "unparseable"},
                                        ensure_ascii=False) + "\n")
            except Exception as e:
                lat = time.time() - t1
                for r in ch:
                    fh.write(json.dumps({"uid": r["uid"], "doc": r["doc"], "judge": "von",
                                         "prob": None, "ok": False,
                                         "err": f"{type(e).__name__}: {e}"[:200]}, ensure_ascii=False) + "\n")
            total += lat; nc += 1; fh.flush()
            print(f"doc={doc[:20]} n={len(ch)} lat={lat:.2f}s", flush=True)
    wall = time.time() - wt0
    meta = {"judge": "von", "calls": nc, "wall_s": round(wall, 1),
            "sum_call_latency_s": round(total, 1),
            "peak_rss_gb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6, 2)}
    fh.close()
    json.dump(meta, open(out + ".meta", "w"), indent=1)
    print(json.dumps(meta))

if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 40)
