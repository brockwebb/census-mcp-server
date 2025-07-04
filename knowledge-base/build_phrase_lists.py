#!/usr/bin/env python3
"""
0-C – Harvest topical and geographic key-phrases from the mini-corpus.

Outputs
-------
data/topical_phrases.txt   one phrase per line (deduped, sorted)
data/geo_phrases.txt       subset of geo-centric phrases
"""

import re, json, string, random
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CORPUS_DIR   = ROOT / "data" / "mini_corpus"
MANIFEST     = ROOT / "data" / "mini_manifest.json"
TOPICAL_OUT  = ROOT / "data" / "topical_phrases.txt"
GEO_OUT      = ROOT / "data" / "geo_phrases.txt"

# ---------- helpers ----------------------------------------------------------

punct_table = str.maketrans("", "", string.punctuation.replace("-", ""))
STOP = {
    "the","and","of","in","to","for","on","with","by","per","a","an",
    "or","as","at","be","from","this","that","pdf","acs","american","community","survey"
}

GEO_KEYS = {
    "tract","block","county","state","msa","cbsa","puma","zip","zcta",
    "urban","rural","metro","micropolitan","place","geography","geographies",
    "region","division","csa","town","city","township"
}

def tokenize(text: str):
    text = text.translate(punct_table).lower()
    return [t for t in text.split() if t and not t.isdigit() and t not in STOP]

def ngrams(tokens, n):
    return [" ".join(tokens[i:i+n]) for i in range(len(tokens)-n+1)]

# ---------- harvest ----------------------------------------------------------

def collect_phrases():
    phrase_counts = Counter()

    for txt_path in CORPUS_DIR.iterdir():
        text = txt_path.read_text(errors="ignore")
        toks = tokenize(text)[:2000]     # keep it cheap
        for n in (2,3,4):                # bi-, tri-, quad-grams
            phrase_counts.update(ngrams(toks, n))

    # remove obvious numeric range / dollar stubs
    cleaner = re.compile(r"^\$?\d+[k0-9,]*( to |–|-)")
    phrases = [p for p,c in phrase_counts.items()
               if c >= 2 and               # appears at least twice
               not cleaner.match(p) and
               not re.fullmatch(r"[a-z_]+\d+", p)]   # skip raw table ids

    topical = sorted(phrases)
    geo     = sorted(p for p in phrases if any(g in p for g in GEO_KEYS))

    TOPICAL_OUT.write_text("\n".join(topical))
    GEO_OUT.write_text("\n".join(geo))

    print(f"✅ Wrote {len(topical):,} topical phrases  → {TOPICAL_OUT}")
    print(f"✅ Wrote {len(geo):,} geo phrases      → {GEO_OUT}")

# ---------- main -------------------------------------------------------------

if __name__ == "__main__":
    if not CORPUS_DIR.exists():
        raise SystemExit("❌ Run step 0-B first – mini_corpus not found.")
    collect_phrases()

