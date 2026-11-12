import csv

def process_text(text):
    return (
        text.replace("\\", "\\\\")
        .replace("$", "\\$")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "")
    )

def convert(csv_path, dart_path, dart_var, dart_func):
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = {}
        for r in reader:
            try:
                surah = int(r["surah_no"])
                ayah = int(r["ayah_no_surah"])
            except (KeyError, ValueError, TypeError):
                continue
            text = (r.get("ayah_ar") or "").strip()
            if not text:
                continue
            key = (surah, ayah)
            if key not in rows:          # keep only first occurrence
                rows[key] = text

    sorted_rows = sorted(rows.items())   # sorts by (surah, ayah)

    lines = [f"const Map<int, String> {dart_var} = {{"]
    for (surah, ayah), text in sorted_rows:
        text = process_text(text)
        lines.append(f'  {surah * 1000 + ayah}: "{text}",')
    lines.append("};")
    lines.append("")
    lines.append(f"String? {dart_func}(int surah, int ayah) => {dart_var}[surah * 1000 + ayah];")

    with open(dart_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Done — {dart_path} written ({len(sorted_rows)} unique ayahs)")


convert(
    "quran_dataset.csv",
    "quran_arabic.dart",
    "_quranArabic",
    "getQuranArabic",
)
