"""Offline cascade simulation + scoring for the Kev-0.8B -> qwen3.8-max confidence cascade.

No API calls. Reads the max baseline preds (run_max_baseline.py), the Kev-0.8B probs of the arena
pilot, and the gold labels (read HERE ONLY, at scoring time, per arena discipline).

Cascade definition (symmetric confidence band around 0.5, because Kev's probabilities sit low and
compressed): threshold t lets Kev self-answer when |prob - 0.5| >= 1 - t, i.e.
  prob >= 1-(t-0.5) = 1.5-t  -> Kev says "requirement" (prob is on the high side of 0.5)
  prob <= t-0.5              -> Kev says "not a requirement"
Every other sentence is escalated to the max zero-shot answer. A sentence escalated but with no max
answer (double parse failure) falls back to Kev at threshold 0.5 and is counted as such, never hidden.

Cost at list price (bench/board_facts.PRICES, qwen3.8-max): the baseline's measured tokens give an
amortized USD per sentence (batch of 20, same shape a deployed cascade would use), so a cascade
point costs escalation_rate x that per-sentence price; Kev is local and billed at 0 (electricity
counted as 0 by experiment decree).

Usage: python3 cascade_metrics.py <analysis/jev-arena-cascade-folder> [--kev <preds-kev.jsonl>]
Writes <folder>/metrics.json and prints the comparison table.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

GOLD_PATH = os.path.join(HERE, "pilot_sentences.jsonl")
KEV_DEFAULT = os.path.join(ROOT, "analysis", "jev-arena-pilot-20261010-105531", "preds-kev-0.8b.jsonl")
THRESHOLDS = [0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90]


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return round(p, 4), round(r, 4), round(f, 4)


def confusion(pairs):
    tp = fp = fn = tn = 0
    for pred, gold in pairs:
        if pred and gold:
            tp += 1
        elif pred and not gold:
            fp += 1
        elif not pred and gold:
            fn += 1
        else:
            tn += 1
    acc = round((tp + tn) / len(pairs), 4) if pairs else None
    p, r, f = prf(tp, fp, fn)
    return {"n": len(pairs), "P": p, "R": r, "F1": f, "acc": acc, "tp": tp, "fp": fp, "fn": fn, "tn": tn}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("folder")
    ap.add_argument("--kev", default=KEV_DEFAULT)
    args = ap.parse_args()

    gold = {i: row["gold"] for i, row in enumerate(json.loads(l) for l in open(GOLD_PATH, encoding="utf-8"))}
    kev = {row["uid"]: row["prob"] for row in (json.loads(l) for l in open(args.kev, encoding="utf-8"))
           if row.get("prob") is not None}
    max_rows = [json.loads(l) for l in open(os.path.join(args.folder, "preds-max-qwen3.8-max.jsonl"),
                                            encoding="utf-8")]
    max_ans = {row["uid"]: row.get("ans") for row in max_rows}
    meta = json.load(open(os.path.join(args.folder, "preds-max-qwen3.8-max.jsonl.meta"), encoding="utf-8"))
    uids = sorted(gold)
    assert all(u in kev for u in uids), "Kev preds must cover every gold uid"

    no_max = [u for u in uids if max_ans.get(u) is None]
    usd_total = meta.get("usd_list_price") or 0.0
    usd_per_sentence = usd_total / len(uids)

    # ---- channels on their own --------------------------------------------------
    kev05_pairs = [(kev[u] >= 0.5, bool(gold[u])) for u in uids]
    kev_alone = {"threshold": 0.5, **confusion(kev05_pairs), "usd_per_1k": 0.0}
    best = max(((round(th, 2), confusion([(kev[u] >= th, bool(gold[u])) for u in uids]))
                for th in [i / 200 for i in range(10, 200)]), key=lambda item: item[1]["F1"])
    kev_alone_best = {"threshold": best[0], **best[1], "usd_per_1k": 0.0}

    max_answered_pairs = [(bool(max_ans[u]), bool(gold[u])) for u in uids if max_ans.get(u) is not None]
    max_full_pairs = [(bool(max_ans[u]) if max_ans.get(u) is not None else kev[u] >= 0.5, bool(gold[u]))
                      for u in uids]
    max_alone = {
        "answered_only": {**confusion(max_answered_pairs)},
        "full_fallback_kev05": {**confusion(max_full_pairs), "no_answer_fallback": len(no_max)},
        "usd_per_1k": round(usd_per_sentence * 1000, 4),
    }

    # ---- cascade sweep ----------------------------------------------------------
    cascade = {}
    for t in THRESHOLDS:
        hi, lo = 1.5 - t, t - 0.5
        covered = {u for u in uids if kev[u] >= hi or kev[u] <= lo}
        pairs, esc_fallback, cov_err, esc_err = [], 0, 0, 0
        for u in uids:
            g = bool(gold[u])
            if u in covered:
                pred = kev[u] >= hi
                cov_err += pred != g
            else:
                if max_ans.get(u) is not None:
                    pred = bool(max_ans[u])
                else:
                    pred = kev[u] >= 0.5
                    esc_fallback += 1
                esc_err += pred != g
            pairs.append((pred, g))
        escalation = len(uids) - len(covered)
        cascade[str(t)] = {
            "band": {"hi": round(hi, 2), "lo": round(lo, 2)},
            "kev_covered": len(covered), "kev_coverage_pct": round(100 * len(covered) / len(uids), 2),
            "escalated": escalation, "escalation_pct": round(100 * escalation / len(uids), 2),
            "escalated_no_max_fallback": esc_fallback,
            "errors_covered": cov_err, "errors_escalated": esc_err,
            **confusion(pairs),
            "usd_per_1k": round(usd_per_sentence * escalation / len(uids) * 1000, 4),
        }

    # ---- failure overlap: the pessimistic bound ---------------------------------
    max_wrong = {u for u in uids if max_ans.get(u) is not None and bool(max_ans[u]) != bool(gold[u])}
    kev_wrong = {u for u in uids if (kev[u] >= 0.5) != bool(gold[u])}
    kev_wrong_best = {u for u in uids if (kev[u] >= best[0]) != bool(gold[u])}
    # oracle: per sentence pick whichever of (kev@0.5, max) is right, if either is
    oracle_pairs = []
    for u in uids:
        g = bool(gold[u])
        kx = kev[u] >= 0.5
        mx = bool(max_ans[u]) if max_ans.get(u) is not None else kx
        oracle_pairs.append((g if (kx == g or mx == g) else kx, g))
    overlap = {
        "max_wrong_n": len(max_wrong), "kev05_wrong_n": len(kev_wrong),
        "both_wrong_n": len(max_wrong & kev_wrong),
        "both_wrong_pct": round(100 * len(max_wrong & kev_wrong) / len(uids), 2),
        "jaccard": round(len(max_wrong & kev_wrong) / len(max_wrong | kev_wrong), 4),
        "kev_alone_best_wrong_n": len(kev_wrong_best),
        "max_and_kevbest_both_wrong_n": len(max_wrong & kev_wrong_best),
        "oracle_either_right": confusion(oracle_pairs),
        "note": "both_wrong = sentences no kev/max cascade can ever get right; "
                "oracle = per-sentence best of the two channels (upper bound)",
    }

    out = {"n": len(uids), "positives": sum(gold.values()),
           "kev_alone": kev_alone, "kev_alone_best": kev_alone_best,
           "max_alone": max_alone, "cascade": cascade, "overlap": overlap,
           "cost_basis": {"usd_total_measured": usd_total, "usd_per_sentence": round(usd_per_sentence, 6),
                          "max_calls": meta.get("calls"), "note": "Kev local cost billed as 0 (decree)"}}

    # ---- optional solo (unbatched) spot check, when its file exists --------------------
    solo_path = os.path.join(args.folder, "solo-check-85.jsonl")
    if os.path.exists(solo_path):
        solo = {row["uid"]: row["ans"] for row in (json.loads(l) for l in open(solo_path, encoding="utf-8"))
                if row.get("ans") is not None}
        uids_s = list(solo)
        out["solo_check"] = {
            "n": len(uids_s),
            "solo": confusion([(bool(solo[u]), bool(gold[u])) for u in uids_s]),
            "batched_same_items": confusion([(bool(max_ans[u]), bool(gold[u])) for u in uids_s]),
            "agree_pct": round(100 * sum(solo[u] == max_ans[u] for u in uids_s) / len(uids_s), 2),
            "note": "same items, one sentence per call: measures the batching penalty of the baseline",
        }
    path = os.path.join(args.folder, "metrics.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)

    print(f"n={len(uids)} pos={sum(gold.values())} max_no_answer={len(no_max)} usd_total={usd_total}")
    print(f"{'channel':>14s} {'F1':>7s} {'acc':>7s} {'P':>7s} {'R':>7s} {'cov%':>6s} {'esc%':>6s} {'$/1k':>8s}")
    def show(name, m, cov=None, esc=None):
        print(f"{name:>14s} {m['F1']:7.4f} {m['acc']:7.4f} {m['P']:7.4f} {m['R']:7.4f} "
              f"{cov if cov is not None else '-':>6} {esc if esc is not None else '-':>6} "
              f"{m.get('usd_per_1k', 0):8.4f}")
    show("kev@0.5", kev_alone, 100, 0)
    show(f"kev@{best[0]:.2f}", kev_alone_best, 100, 0)
    show("max(ans-only)", {**max_alone["answered_only"], "usd_per_1k": max_alone["usd_per_1k"]}, 0, 100)
    show("max(full)", {**max_alone["full_fallback_kev05"], "usd_per_1k": max_alone["usd_per_1k"]}, 0, 100)
    for t in THRESHOLDS:
        c = cascade[str(t)]
        show(f"t={t:.2f}", c, c["kev_coverage_pct"], c["escalation_pct"])
    print(f"both_wrong={overlap['both_wrong_n']} ({overlap['both_wrong_pct']}%) "
          f"oracle F1={overlap['oracle_either_right']['F1']:.4f}")
    print(path)


if __name__ == "__main__":
    main()
