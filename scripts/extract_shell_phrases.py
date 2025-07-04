#!/usr/bin/env python3
"""
Extract topical phrases and geography phrases from ACS table shells.

Usage
-----
python scripts/extract_shell_phrases.py \
       --shell-path data/acs_table_shells/2023            # a directory *or* a TSV
       --out-topical data/topical_phrases.txt \
       --out-geo    data/geo_phrases.txt
"""

import argparse, re, sys, textwrap
from pathlib import Path
import pandas as pd

# ---------- simple helpers ---------------------------------------------------

GEO_PATTERNS = [
    r'\bstate(?:s)?\b', r'\bcounty(?:ies)?\b', r'\btracts?\b', r'\bblock groups?\b',
    r'\bmsa\b', r'\bcbsa\b', r'\bpuma\b', r'\burban\b', r'\brural\b',
    r'\bmetropolitan\b', r'\bmicropolitan\b',
    r'\bresidence\b', r'\bworkplace\b', r'\bhousehold\b'
]
geo_re = re.compile('|'.join(GEO_PATTERNS), flags=re.I)

def split_phrases(cell: str):
    """Return plausible phrase tokens from shell stub / column text."""
    if not isinstance(cell, str) or not cell.strip():
        return []
    # Common separators: colon, comma, slash, + line breaks.
    parts = re.split(r'[:;/\n]+', cell)
    return [p.strip() for p in parts if p.strip()]

def classify_phrase(phrase: str):
    """Return 'geo' if phrase matches GEO_PATTERNS else 'topical'."""
    return 'geo' if geo_re.search(phrase) else 'topical'

# ---------- extractor --------------------------------------------------------

def extract_from_xlsx(xlsx_path: Path):
    """Yield phrases from every sheet of a single XLSX shell file."""
    try:
        xls = pd.ExcelFile(xlsx_path)
    except Exception as e:
        print(f"⚠️  Skipping {xlsx_path.name}: {e}", file=sys.stderr)
        return

    for sheet in xls.sheet_names:
        df = xls.parse(sheet, dtype=str, header=None)
        for cell in df.values.flatten():
            for phrase in split_phrases(str(cell)):
                yield phrase

def extract_from_tsv(tsv_path: Path):
    """Yield phrases from the big Census‐supplied TSV list."""
    df = pd.read_csv(tsv_path, sep='\t', dtype=str)
    for col in df.columns:
        for cell in df[col].dropna().unique():
            for phrase in split_phrases(cell):
                yield phrase

def main():
    p = argparse.ArgumentParser(
        description="Extract topical & geography phrases from ACS table shells"
    )
    p.add_argument("--shell-path", required=True,
                   help="Directory of .xlsx shells or a single TSV file")
    p.add_argument("--out-topical", required=True, help="Path to write topical phrases")
    p.add_argument("--out-geo",     required=True, help="Path to write geography phrases")
    args = p.parse_args()

    shell_path = Path(args.shell_path)
    topical, geo = set(), set()

    if shell_path.is_dir():
        files = list(shell_path.rglob("*.xlsx"))
        if not files:
            print("❌ No .xlsx shells found in directory", file=sys.stderr)
            sys.exit(1)
        for f in files:
            for phrase in extract_from_xlsx(f):
                (geo if classify_phrase(phrase) == 'geo' else topical).add(phrase)
    else:
        # Assume TSV
        for phrase in extract_from_tsv(shell_path):
            (geo if classify_phrase(phrase) == 'geo' else topical).add(phrase)

    # --- write output --------------------------------------------------------
    def write_out(path, phrases):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            for p in sorted(phrases):
                fh.write(p + '\n')
        print(f"✅ Wrote {len(phrases):,} phrases → {path}")

    write_out(args.out_topical, topical)
    write_out(args.out_geo,    geo)

if __name__ == "__main__":
    main()
