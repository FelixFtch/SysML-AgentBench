"""NanoJev runner via its /api/evaluate endpoint (boolean questions -> p_true).
Usage: run_nanojev.py OUT.jsonl [chunk]"""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from systemone_client import load_texts, chunks, state_for, CRIT_TRUE, CRIT_FALSE

URL = "http://127.0.0.1:8766/api/evaluate"

def find_ptrue(ans):
    if not isinstance(ans, dict):
        return None
    for k in ("p_true", "probability", "prob"):
        v = ans.get(k)
        if isinstance(v, (int, float)):
            return float(v)
    pr = ans.get("probabilities")
    if isinstance(pr, dict) and isinstance(pr.get("true"), (int, float)):
        return float(pr["true"])
    return None

def walk_answers(obj):
    """Yield (qid, answer-dict) wherever an answers mapping appears."""
    if isinstance(obj, dict):
        if isinstance(obj.get("answers"), dict):
            for qid, a in obj["answers"].items():
                yield qid, a
        for v in obj.values():
            yield from walk_answers(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk_answers(v)

def main(out, chunk=48):
    import urllib.request
    rows = load_texts()
    by_doc = {}
    for r in rows:
        by_doc.setdefault(r["doc"], []).append(r)
    fh = open(out, "w")
    total = 0.0; nc = 0
    wt0 = time.time()
    for doc in sorted(by_doc):
        for ch in chunks(by_doc[doc], chunk):
            payload = {"states": [{"id": f"{doc[:40]}-{ch[0]['uid']}", "state": state_for(ch),
                                   "questions": {str(r["uid"]): {
                                       "type": "boolean",
                                       "instructions": f'Is sentence [{r["uid"] % 10000}] a software requirement statement? Sentence [{r["uid"] % 10000}]: "{r["text"]}"',
                                       "criteria": {"true": CRIT_TRUE, "false": CRIT_FALSE}}
                                     for r in ch}}]}
            t1 = time.time()
            try:
                req = urllib.request.Request(URL, data=json.dumps(payload).encode(),
                                             headers={"content-type": "application/json"}, method="POST")
                with urllib.request.urlopen(req, timeout=600) as resp:
                    res = json.loads(resp.read())
                lat = time.time() - t1
                got = dict(walk_answers(res))
                for r in ch:
                    v = find_ptrue(got.get(str(r["uid"])))
                    ok = v is not None
                    fh.write(json.dumps({"uid": r["uid"], "doc": r["doc"], "judge": "nanojev",
                                         "prob": v, "ok": ok,
                                         "err": None if ok else "unparseable"}, ensure_ascii=False) + "\n")
            except Exception as e:
                lat = time.time() - t1
                for r in ch:
                    fh.write(json.dumps({"uid": r["uid"], "doc": r["doc"], "judge": "nanojev",
                                         "prob": None, "ok": False,
                                         "err": f"{type(e).__name__}: {e}"[:200]}, ensure_ascii=False) + "\n")
            total += lat; nc += 1; fh.flush()
            print(f"doc={doc[:20]} n={len(ch)} lat={lat:.2f}s", flush=True)
    meta = {"judge": "nanojev", "calls": nc, "wall_s": round(time.time() - wt0, 1),
            "sum_call_latency_s": round(total, 1)}
    fh.close()
    json.dump(meta, open(out + ".meta", "w"), indent=1)
    print(json.dumps(meta))

if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 48)
