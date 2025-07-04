#!/usr/bin/env bash
set -euo pipefail

BASE="https://www2.census.gov/programs-surveys/acs/tech_docs/table_shells/2023"
OUT="data/acs_table_shells/2023"
mkdir -p "$OUT"

echo "⏬  Fetching directory listing…"
curl -sL "$BASE/" > /tmp/acs_index.html

echo "🔎  Extracting XLSX / ZIP links…"
grep -oE 'href="[^"]+\.(xlsx|zip)"' /tmp/acs_index.html \
  | sed -E 's/^href="([^"]+)"/\1/' \
  | sort -u > /tmp/acs_files.txt

COUNT=$(wc -l < /tmp/acs_files.txt)
echo "📄  Found $COUNT files – downloading…"

cat /tmp/acs_files.txt \
 | xargs -n1 -P8 -I{} bash -c '
        url="'"$BASE"'/{}"
        file="'"$OUT"'"/$(basename "{}")
        if [[ ! -f "$file" ]]; then
            curl -sSL -o "$file" "$url"
            echo "✔  $(basename "$file")"
        fi
   '

echo "✅  Done. Files saved in $OUT"

