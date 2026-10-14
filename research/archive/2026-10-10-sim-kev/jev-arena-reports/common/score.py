"""Score prediction jsonl files against gold. Gold is read HERE ONLY.

Precision/Recall/F1 at threshold 0.5, requirement = positive class.
Also reports metrics restricted to the official-API subsample uids for
apples-to-apples comparison with the budget-limited official judge.
"""
import json, sys, glob, os

def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return round(p, 4), round(r, 4), round(f, 4)

def main(pred_files, gold_path, out_path):
    gold = {i: json.loads(l)["gold"] for i, l in enumerate(open(gold_path))}
    # subsample = uids present in the official judge file (if any)
    sub_uids = None
    for f in pred_files:
        if os.path.basename(f).startswith("preds-jev-api"):
            sub_uids = {json.loads(l)["uid"] for l in open(f) if json.loads(l).get("ok")}
    results = {}
    for f in pred_files:
        name = os.path.basename(f)[len("preds-"):-len(".jsonl")]
        rows = [json.loads(l) for l in open(f)]
        tp = fp = fn = tn = fail = 0
        lats = []
        for r in rows:
            if not r.get("ok"):
                fail += 1; continue
            pred = r["prob"] >= 0.5
            g = gold[r["uid"]]
            if pred and g: tp += 1
            elif pred and not g: fp += 1
            elif not pred and g: fn += 1
            else: tn += 1
        entry = {"n": len(rows), "fail": fail,
                 "P": prf(tp, fp, fn)[0], "R": prf(tp, fp, fn)[1], "F1": prf(tp, fp, fn)[2],
                 "tp": tp, "fp": fp, "fn": fn, "tn": tn}
        meta_f = f + ".meta"
        if os.path.exists(meta_f):
            entry.update(json.load(open(meta_f)))
        if sub_uids is not None:
            tp2 = fp2 = fn2 = 0; n2 = 0
            for r in rows:
                if r.get("ok") and r["uid"] in sub_uids:
                    n2 += 1
                    pred = r["prob"] >= 0.5; g = gold[r["uid"]]
                    if pred and g: tp2 += 1
                    elif pred and not g: fp2 += 1
                    elif not pred and g: fn2 += 1
            if n2:
                p2, r2, f2 = prf(tp2, fp2, fn2)
                entry["subsample"] = {"n": n2, "P": p2, "R": r2, "F1": f2}
        results[name] = entry
    json.dump(results, open(out_path, "w"), indent=1)
    for k, v in sorted(results.items(), key=lambda kv: -kv[1]["F1"]):
        sub = v.get("subsample")
        print(f'{k:18s} F1={v["F1"]:.4f} P={v["P"]:.4f} R={v["R"]:.4f} n={v["n"]} fail={v["fail"]}'
              + (f' | subsample F1={sub["F1"]}' if sub else ''))

if __name__ == "__main__":
    ts = sys.argv[1]
    d = f"/data/robotics/RTRC/analysis/jev-arena-pilot-{ts}"
    main(sorted(glob.glob(d + "/preds-*.jsonl")),
         "/data/robotics/RTRC/tools/jev-arena/common/pilot_sentences.jsonl",
         d + "/metrics.json")
