#!/usr/bin/env python3
"""
build_mini_corpus.py
--------------------
* Scans   knowledge-base/source-docs/OtherACS/
          knowledge-base/source-docs/acs_table_shells/
* Builds  knowledge-base/data/mini_manifest.json
* Saves   plain-text for every file under
          knowledge-base/data/mini_corpus/<sha1>.txt

Extraction strategy (PDF):
  1. pdfminer.six                 – super-fast if text embedded
  2. poppler `pdftotext` fallback – better with odd encodings
  3. OCR (pdf2image + pytesseract)– last-resort for scanned / “print-to-PDF”

All failures are logged; the script never crashes on a bad file.

© 2025 – tweak / reuse freely
"""
import json, hashlib, logging, subprocess, tempfile, shutil, re, html
from pathlib import Path
from datetime import datetime

import pdfminer.high_level as pdfminer

from pdf2image import convert_from_path
import pytesseract

import logging, warnings
# ------------------------------------------------------------------
# QUIET DOWN pdfminer + pillow font warnings
logging.getLogger("pdfminer").setLevel(logging.ERROR)
warnings.filterwarnings(
    "ignore",
    message=r"Could get FontBBox from font descriptor",
    module="pdfminer",
)
# pdf2image / pillow sometimes shout about DPI; silence those too
logging.getLogger("PIL").setLevel(logging.ERROR)
# ------------------------------------------------------------------


# --------------------------------------------------------------------------- #
# CONFIG – adjust only if your paths differ
ROOT = Path(__file__).resolve().parent           # knowledge-base/
SRC_DIRS = [
    ROOT / "source-docs" / "OtherACS",
    ROOT / "source-docs" / "acs_table_shells",
]
OUT_DIR   = ROOT / "data"
TEXT_DIR  = OUT_DIR / "mini_corpus"
MANIFEST  = OUT_DIR / "mini_manifest.json"
MIN_SIZE  = 200  # bytes – ignore truly empty extractions
# --------------------------------------------------------------------------- #

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("mini-corpus")

# --------------------------------------------------------------------------- #
# Helper – robust PDF→text
def pdf_to_text(file: Path) -> str:
    """Return extracted text or '' . 3-stage fallback."""
    # 1) pdfminer
    try:
        text = pdfminer.extract_text(str(file)) or ""
        if text.strip():
            return text
    except Exception as e:
        log.debug(f"pdfminer failed on {file.name}: {e}")

    # 2) pdftotext
    if shutil.which("pdftotext"):
        try:
            with tempfile.NamedTemporaryFile(suffix=".txt") as tmp:
                subprocess.run(
                    ["pdftotext", "-layout", "-enc", "UTF-8", str(file), tmp.name],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                text = Path(tmp.name).read_text(encoding="utf-8", errors="ignore")
                if text.strip():
                    return text
        except Exception as e:
            log.debug(f"pdftotext failed on {file.name}: {e}")
    else:
        log.warning("pdftotext not found – skipping stage-2 fallback")

    # 3) OCR
    try:
        pages = convert_from_path(str(file), dpi=300, fmt="png")
        ocr_chunks = []
        for img in pages:
            ocr_chunks.append(pytesseract.image_to_string(img, lang="eng"))
        text = "\n".join(ocr_chunks).strip()
        if text:
            log.info(f"OCR succeeded on {file.name}")
            return text
    except Exception as e:
        log.debug(f"OCR failed on {file.name}: {e}")

    return ""


# --------------------------------------------------------------------------- #
def plain_text(file: Path) -> str:
    """Dispatcher: pick extractor based on extension."""
    ext = file.suffix.lower()
    if ext == ".pdf":
        return pdf_to_text(file)
    elif ext in {".txt", ".md"}:
        return file.read_text("utf-8", errors="ignore")
    elif ext in {".html", ".htm"}:
        raw = file.read_text("utf-8", errors="ignore")
        return html.unescape(re.sub("<[^>]+>", " ", raw))
    else:
        # Leave xlsx/csv/tsv etc. alone – store empty text, still list in manifest
        return ""


# --------------------------------------------------------------------------- #
def sha1_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def save_text(text: str) -> str:
    """Write deduplicated text file => returns sha1."""
    h = sha1_bytes(text.encode("utf-8"))
    out_path = TEXT_DIR / f"{h}.txt"
    if not out_path.exists():
        out_path.write_text(text, "utf-8")
    return h


# --------------------------------------------------------------------------- #
def main() -> None:
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    manifest = []
    processed = 0

    for src_root in SRC_DIRS:
        for path in sorted(src_root.rglob("*")):
            if path.is_dir():
                continue

            processed += 1
            rel = path.relative_to(ROOT)

            # hash of file bytes for manifest
            file_bytes = path.read_bytes()
            file_sha1  = sha1_bytes(file_bytes)

            text = plain_text(path)
            text_sha1 = save_text(text) if len(text.encode()) > MIN_SIZE else None

            manifest.append(
                {
                    "path"       : str(rel),
                    "bytes"      : len(file_bytes),
                    "file_sha1"  : file_sha1,
                    "text_sha1"  : text_sha1,
                    "ext"        : path.suffix.lower(),
                    "timestamp"  : datetime.utcnow().isoformat(timespec="seconds")+"Z",
                }
            )

            if processed % 50 == 0:
                log.info(f"…{processed} files processed")

    MANIFEST.write_text(json.dumps(manifest, indent=2))
    log.info(f"✅ Wrote {len(manifest):,} entries → {MANIFEST.relative_to(ROOT)}")
    log.info(f"✅ Text corpus saved in {TEXT_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
