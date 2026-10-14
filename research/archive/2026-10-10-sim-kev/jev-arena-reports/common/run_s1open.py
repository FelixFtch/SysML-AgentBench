"""system-one-open runner against the author's public Modal demo endpoint.
Question format: list of {id,type,instructions,criteria{true,false}}. Answer: noul prob.
Usage: run_s1open.py OUT.jsonl [chunk]"""
import json, os, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from systemone_client import load_texts, chunks, state_for, CRIT_TRUE, CRIT_FALSE

URL = "https://mithalouni--jev-serve-e2b-full-server-web.modal.run/decide"

def main(out, chunk=32):
    rows = load_texts()
    by_doc = {}
    for r in rows:
        by_doc.setdefault(r["doc"], []).append(r)
    fh = open(out, "w")
    total = 0.0; nc = 0; cold = True
    wt0 = time.time()
    for doc in sorted(by_doc):
        for ch in chunks(by_doc[doc], chunk):
            body = {"state": state_for(ch),
                    "questions": [{"id": str(r["uid"]), "type": "noul",
                                   "instructions": f'Is sentence [{r["uid"] % 10000}] a software requirement statement? Sentence [{r["uid"] % 10000}]: "{r["text"]}"',
                                   "criteria": {"true": CRIT_TRUE, "false": CRIT_FALSE}}
                                  for r in ch],
                    "max_state_tokens": 12000}
            data = json.dumps(body).encode()
            t1 = time.time()
            for attempt in range(3):
                try:
                    req = urllib.request.Request(URL, data=data, headers={"content-type": "application/json"}, method="POST")
                    with urllib.request.urlopen(req, timeout=600) as resp:
                        res = json.loads(resp.read())
                    break
                except Exception as e:
                    res = None; err = f"{type(e).__name__}: {e}"[:200]
                    time.sleep(10 * (attempt + 1))
            lat = time.time() - t1
            if res is None:
                for r in ch:
                    fh.write(json.dumps({"uid": r["uid"], "doc": r["doc"], "judge": "system-one-open",
                                         "prob": None, "ok": False, "err": err}, ensure_ascii=False) + "\n")
            else:
                ans = {str(a.get("id")): a.get("noul") for a in res.get("answers", [])}
                for r in ch:
                    v = ans.get(str(r["uid"]))
                    ok = isinstance(v, (int, float))
                    fh.write(json.dumps({"uid": r["uid"], "doc": r["doc"], "judge": "system-one-open",
                                         "prob": float(v) if ok else None, "ok": ok,
                                         "err": None if ok else "unparseable"}, ensure_ascii=False) + "\n")
            total += lat; nc += 1; fh.flush()
            print(f"call {nc} doc={doc[:20]} n={len(ch)} lat={lat:.2f}s", flush=True)
            time.sleep(0.4)
    meta = {"judge": "system-one-open", "calls": nc, "wall_s": round(time.time() - wt0, 1),
            "sum_call_latency_s": round(total, 1), "hosted": True}
    fh.close()
    json.dump(meta, open(out + ".meta", "w"), indent=1)
    print(json.dumps(meta))

if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 32)
