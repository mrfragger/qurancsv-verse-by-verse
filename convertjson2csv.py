import csv
import json
import sys

# Usage: python convert.py input.json output.csv
src = sys.argv[1] if len(sys.argv) > 1 else "quran.json"
dst = sys.argv[2] if len(sys.argv) > 2 else "quran.csv"

with open(src, encoding="utf-8") as f:
    data = json.load(f)

# Sort numerically by sura, then aya ("2:10" must come after "2:9")
def key(k):
    sura, aya = k.split(":")
    return int(sura), int(aya)

with open(dst, "w", encoding="utf-8", newline="") as f:
    header = csv.writer(f)  # unquoted header, like your sample
    rows = csv.writer(f, quoting=csv.QUOTE_NONNUMERIC)  # text quoted, numbers bare
    header.writerow(["id", "sura", "aya", "translation", "footnotes"])
    for i, k in enumerate(sorted(data, key=key), start=1):
        sura, aya = key(k)
        entry = data[k]
        rows.writerow([
            i,
            sura,
            aya,
            entry.get("translation", ""),
            entry.get("footnotes", ""),
        ])

print(f"Wrote {len(data)} rows to {dst}")
