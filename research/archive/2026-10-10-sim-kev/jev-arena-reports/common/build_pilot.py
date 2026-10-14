"""Parse PURE requirements-xml into per-doc sentence lists with gold labels.
Protocol: gold=1 iff sentence text comes from inside a <req> element (recursive).
Text sources: <title>, <text_body> (incl. <item> inside itemize), <meaning>, <description>.
Sentence split: deterministic regex, abbreviation-guarded.
Output: pilot_sentences.jsonl  (one row per sentence) + docs summary.
"""
import glob, json, os, random, re, sys
import xml.etree.ElementTree as ET

XML_DIR = "/tmp/pure_xml/XMLZIPFile"
OUT_DIR = "/data/robotics/RTRC/tools/jev-arena/common"

ABBR = {"e.g","i.e","etc","vs","cf","approx","fig","no","mr","mrs","ms","dr","sr","jr","st","inc","ltd","co","corp","u.s","a.m","p.m","sec","min","max","ref","vol","pp","al"}
NUM_ABBR = re.compile(r"^\d")

def sentences(text):
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    out, cur = [], ""
    tokens = re.split(r"(\s+)", text)
    for tok in tokens:
        cur += tok
        m = re.match(r"^(.*?)([.!?])[\"')\]]*$", tok, re.S)
        if m and m.group(2) in ".!?":
            head = m.group(1)
            last = head.split(".")[-1].lower() if "." in head else ""
            # guard: digit.digit decimals, single letters, known abbreviations
            if m.group(2) == ".":
                if head and re.search(r"\d$", head) and False: pass
                if re.search(r"\d\.$", tok) or re.search(r"\.\d", tok): continue  # decimal-ish
                if last in ABBR: continue
                if len(last) == 1: continue  # initials like "J."
            cur = cur.strip()
            if cur: out.append(cur); cur = ""
    cur = cur.strip()
    if cur: out.append(cur)
    return [s for s in out if len(s) > 1]

def strip_ns(tag):
    return tag.split("}")[-1]

def walk(el, in_req, doc_rows, path):
    tag = strip_ns(el.tag)
    in_req_child = in_req or tag == "req"
    if tag in ("title", "meaning", "description", "item", "text_body"):
        # direct text of this element, excluding nested structural elements (item handled separately)
        parts = [t for t in el.itertext()]
        # for text_body with nested <item>, itertext includes items; handle by splitting:
        if tag == "text_body":
            # accumulate non-item text only
            def collect(e):
                buf = ""
                for child in e:
                    ct = strip_ns(child.tag)
                    if ct in ("itemize", "enum", "figure"):
                        if buf.strip(): buf += " "
                        return buf, child  # stop at first block structure marker
                    buf += child.text or ""
                    sub, stop = collect(child)
                    buf += sub
                    if stop is not None: return buf, stop
                    buf += child.tail or ""
                return buf, None
            buf, stopchild = collect(el)
            # leading text before itemize
            lead = (el.text or "") + buf
            for s in sentences(lead):
                doc_rows.append({"text": s, "gold": 1 if in_req_child else 0, "src": tag})
            # recurse into itemize/enum items via normal walk
            for child in el:
                walk(child, in_req_child, doc_rows, path)
        else:
            txt = "".join(parts)
            for s in sentences(txt):
                doc_rows.append({"text": s, "gold": 1 if in_req_child else 0, "src": tag})
        return
    for child in el:
        walk(child, in_req_child, doc_rows, path)

def main():
    files = sorted(glob.glob(os.path.join(XML_DIR, "*.xml")))
    docs = []
    for f in files:
        name = os.path.basename(f)[:-4]
        try:
            tree = ET.parse(f)
        except Exception as e:
            print("PARSE FAIL", name, e); continue
        rows = []
        walk(tree.getroot(), False, rows, [])
        if not rows: continue
        docs.append({"doc": name, "n": len(rows), "pos": sum(r["gold"] for r in rows), "rows": rows})
    print(f"parsed {len(docs)} docs, total sentences {sum(d['n'] for d in docs)}")
    # Only docs with <req> annotation carry gold labels (12 of 18 are unannotated;
    # treating them as all-negative would poison gold). Deterministic: take ALL annotated.
    docs_sorted = sorted([d for d in docs if d["pos"] > 0], key=lambda d: d["n"])
    sel = docs_sorted
    print(f"annotated docs: {len(sel)} (of {len(docs)} parsed)")
    with open(os.path.join(OUT_DIR, "pilot_sentences.jsonl"), "w") as fh:
        for d in sel:
            for r in d["rows"]:
                fh.write(json.dumps({"doc": d["doc"], "text": r["text"], "gold": r["gold"], "src": r["src"]}, ensure_ascii=False) + "\n")
    meta = [{"doc": d["doc"], "n": d["n"], "pos": d["pos"]} for d in sel]
    with open(os.path.join(OUT_DIR, "pilot_docs.json"), "w") as fh:
        json.dump(meta, fh, indent=1)
    print(json.dumps(meta, indent=1))
    tot = sum(d["n"] for d in sel); pos = sum(d["pos"] for d in sel)
    print(f"pilot: 20 docs, {tot} sentences, {pos} pos ({pos/tot:.1%})")

if __name__ == "__main__":
    main()
