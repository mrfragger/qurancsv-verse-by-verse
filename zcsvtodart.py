import csv
import os
import re

SURAH_AYAHS = [
    7,286,200,176,120,165,206,75,129,109,123,111,43,52,99,128,111,110,98,135,
    112,78,118,64,77,227,93,88,69,60,34,30,73,54,45,83,182,88,75,85,
    54,53,89,59,37,35,38,29,18,45,60,49,62,55,78,96,29,22,24,13,
    14,11,11,18,12,12,30,52,52,44,28,28,20,56,40,31,50,40,46,42,
    29,19,36,25,22,17,19,26,30,20,15,21,11,8,8,19,5,8,8,11,
    11,8,4,5,7,3,6,3,5,4,5,4,5,6,
]

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
        content = f.read()

    # Strip a leading "Translation Info:" comment block if present — it's
    # one big quoted CSV cell that spans multiple lines and sits before the
    # real header row ("sura,aya,translation" or "id,sura,aya,translation,footnotes").
    header_match = re.search(r'^(?:id,)?sura,aya,translation', content, re.MULTILINE)
    if header_match:
        content = content[header_match.start():]

    reader = csv.DictReader(content.splitlines())
    rows = {}
    for r in reader:
        try:
            key = (int(r["sura"]), int(r["aya"]))
        except (KeyError, ValueError, TypeError):
            continue
        rows[key] = r

    lines = [f"const Map<int, String> {dart_var} = {{"]
    for surah, ayah_count in enumerate(SURAH_AYAHS, start=1):
        for ayah in range(1, ayah_count + 1):
            row = rows.get((surah, ayah))
            if not row:
                continue
            translation = (row.get("translation") or "").strip()
            footnotes = (row.get("footnotes") or "").strip()
            text = f"{translation}\\n\\nFootnotes: {footnotes}" if footnotes else translation
            text = process_text(text)
            lines.append(f'  {surah * 1000 + ayah}: "{text}",')
    lines.append("};")
    lines.append("")
    lines.append(f"String? {dart_func}(int surah, int ayah) => {dart_var}[surah * 1000 + ayah];")

    with open(dart_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Done — {dart_path} written")


# Map each CSV filename -> (Dart variable, Dart function, source file name)
LANGUAGES = {
    "Belarusian":   "belarusian_krivtsov_v1.0.0.csv",
    "Cebuano":      "bisayan_rwwad_v1.1.3-csv.1.csv",
    "Bulgarian":    "bulgarian_translation_v1.0.0.csv",
    "Chichewa":     "chichewa_betala_v1.0.0.csv",
    "Croatian":     "croatian_rwwad_v1.0.1-csv.1.csv",
    "Dagbani":      "dagbani_ghatubo_v1.0.0.csv",
    "Dari":         "dari_badkhashani_v1.0.0.csv",
    "Dutch":        "dutch_center_v2.0.10-csv.1.csv",
    "Greek":        "greek_rwwad_v1.0.0.csv",
    "Gujarati":     "gujarati_omari_v1.1.3-csv.1.csv",
    "Hebrew":       "hebrew_darussalam_v1.0.0.csv",
    "Kirundi":      "ikirundi_gehiti_v1.0.4-csv.1.csv",
    "Iranun":       "iranun_sarro_v1.0.0.csv",
    "Kannada":      "kannada_hamza_v1.0.3-csv.1.csv",
    "Kazakh":       "kazakh_altai_v1.0.0.csv",
    "Kinyarwanda":  "kinyarwanda_assoc_v1.0.5-csv.1.csv",
    "Lingala":      "lingala_zakaria_v1.0.2-csv.1.csv",
    "Lithuanian":   "lithuanian_rwwad_v1.0.8-csv.1.csv",
    "Luganda":      "luganda_foundation_v1.0.0.csv",
    "Luhya":        "luhya_center_v1.0.0.csv",
    "Macedonian":   "macedonian_group_v1.0.1-csv.1.csv",
    "Maguindanaon": "maguindanao_rwwad_v1.0.4-csv.1.csv",
    "Malay":        "malay_basumayyah_v1.0.0.csv",
    "Marathi":      "marathi_ansari_v1.0.0.csv",
    "Moore":        "moore_rwwad_v1.0.1-csv.1.csv",
    "Punjabi":      "punjabi_arif_v1.0.1-csv.1.csv",
    "Romanian":     "romanian_project_v1.0.4-csv.1.csv",
    "Somali":       "somali_yacob_v1.0.26-csv.1.csv",
    "Swedish":      "swedish_rwwad_v1.0.0.csv",
    "Ukrainian":    "ukrainian_yakubovych_v1.0.0.csv",
    "Yao":          "yaw_silika_v1.0.0.csv",
    "Yoruba":       "yoruba_mikail_v1.0.9-csv.1.csv",
}

for lang, csv_file in LANGUAGES.items():
    convert(
        csv_file,
        f"translation_various_{lang.lower()}.dart",
        f"_various{lang}",
        f"getVariousTranslation{lang}",
    )

for lang, csv_file in LANGUAGES.items():
    convert(
        csv_file,
        f"translation_various_{lang.lower()}.dart",
        f"_various{lang}",
        f"getVariousTranslation{lang}",
    )
