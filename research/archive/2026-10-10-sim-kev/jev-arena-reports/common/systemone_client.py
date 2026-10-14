"""Shared pieces for the Jev-arena PURE pilot.

Judges only ever see sentence TEXTS (pilot_texts.jsonl). Gold labels live in
pilot_sentences.jsonl and are read exclusively by score.py (scoring stage).
"""
import json, os, time, random, urllib.request, urllib.error

COMMON = os.path.dirname(os.path.abspath(__file__))
TEXTS = os.path.join(COMMON, "pilot_texts.jsonl")

CRIT_TRUE = "A testable statement of what the software system shall, must, should, or will do, or a constraint on its quality or environment"
CRIT_FALSE = "Headings, background, explanation, rationale, definitions, plans, or any other non-requirement sentence"

def load_texts():
    return [json.loads(l) for l in open(TEXTS)]

def noul_question(idx, text, with_criteria=True):
    q = {"type": "noul",
         "instructions": f'Is sentence [{idx}] a software requirement statement? Sentence [{idx}]: "{text}"'}
    if with_criteria:
        q["criteria"] = {"true": CRIT_TRUE, "false": CRIT_FALSE}
    return q

def chunks(rows, size):
    for i in range(0, len(rows), size):
        yield rows[i:i+size]

def state_for(rows):
    body = "\n".join(f'[{r["uid"] % 10000}] {r["text"]}' for r in rows)
    return ("Excerpt of a software requirements specification document. "
            "Each line is one sentence with its identifier in brackets:\n" + body)

def sample_doc(rows_by_doc, per_doc, seed=42):
    """Deterministic even spread of <=per_doc uids per doc."""
    rng = random.Random(seed)
    out = []
    for doc in sorted(rows_by_doc):
        rows = rows_by_doc[doc]
        if len(rows) <= per_doc:
            out.extend(rows)
        else:
            step = len(rows) / per_doc
            out.extend(rows[int(i * step)] for i in range(per_doc))
    return out

def post_json(url, body, headers=None, timeout=180):
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={"content-type": "application/json", **(headers or {})}, method="POST")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read()), time.time() - t0, None
    except urllib.error.HTTPError as e:
        return None, time.time() - t0, f"HTTP {e.code}: {e.read()[:300].decode('utf-8', 'replace')}"
    except Exception as e:
        return None, time.time() - t0, f"{type(e).__name__}: {e}"

def parse_noul(ans):
    """Return probability or None if unparseable."""
    if not isinstance(ans, dict):
        return None
    v = ans.get("noul", ans.get("probability", ans.get("p")))
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return float(v)
    return None
