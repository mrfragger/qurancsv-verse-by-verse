import requests
import json
import os
import time

TRANSLATION_KEY = "georgian_rwwad"
DART_VAR_NAME = "rwwadGeorgian"
DART_FUNC_NAME = "getTranslationRwwadGeorgian"
OUT_DIR = "rwwad"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; QuranResearch/1.0)"}
DELAY = 0.4
MAX_RETRIES = 3
RETRY_BACKOFF = 5

SURAH_AYAHS = [
    7, 286, 200, 176, 120, 165, 206, 75, 129, 109,
    123, 111, 43, 52, 99, 128, 111, 110, 98, 135,
    112, 78, 118, 64, 77, 227, 93, 88, 69, 60,
    34, 30, 73, 54, 45, 83, 182, 88, 75, 85,
    54, 53, 89, 59, 37, 35, 38, 29, 18, 45,
    60, 49, 62, 55, 78, 96, 29, 22, 24, 13,
    14, 11, 11, 18, 12, 12, 30, 52, 52, 44,
    28, 28, 20, 56, 40, 31, 50, 40, 46, 42,
    29, 19, 36, 25, 22, 17, 19, 26, 30, 20,
    15, 21, 11, 8, 8, 19, 5, 8, 8, 11,
    11, 8, 4, 5, 7, 3, 6, 3, 5, 4,
    5, 4, 5, 6,
]


def fetch_sura(sura: int) -> list | None:
    url = f"https://quranenc.com/api/v1/translation/sura/{TRANSLATION_KEY}/{sura}"
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code == 200:
                return resp.json().get("result", [])
            elif resp.status_code == 404:
                print(f"  404 — sura {sura} not found")
                return None
            else:
                print(f"  HTTP {resp.status_code} on attempt {attempt}/{MAX_RETRIES}")
        except requests.exceptions.RequestException as e:
            print(f"  Error (attempt {attempt}/{MAX_RETRIES}): {e}")
        if attempt < MAX_RETRIES:
            wait = RETRY_BACKOFF * attempt
            print(f"  Retrying in {wait}s...")
            time.sleep(wait)
    return None


def process_text(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\r", "")
    )


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    # --- Step 1: fetch all JSON and save ---
    all_ayahs = {}  # (sura, aya) -> {translation, footnotes}

    for sura in range(1, 115):
        print(f"Fetching sura {sura}...")
        ayahs = fetch_sura(sura)
        if not ayahs:
            print(f"  Sura {sura} — NO DATA")
            time.sleep(DELAY)
            continue
        for entry in ayahs:
            key = (int(entry.get("sura", sura)), int(entry.get("aya")))
            all_ayahs[key] = {
                "translation": (entry.get("translation") or "").strip(),
                "footnotes":   (entry.get("footnotes") or "").strip(),
            }
        print(f"  Sura {sura} — {len(ayahs)} ayat")
        time.sleep(DELAY)

    # save raw JSON snapshot
    json_path = os.path.join(OUT_DIR, f"{TRANSLATION_KEY}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {f"{k[0]}:{k[1]}": v for k, v in all_ayahs.items()},
            f, ensure_ascii=False, indent=2
        )
    print(f"\n✓ JSON saved: {json_path}")

    # --- Step 2: convert to Dart ---
    lines = [f"const Map<int, String> _{DART_VAR_NAME} = {{"]

    for surah, ayah_count in enumerate(SURAH_AYAHS, start=1):
        for ayah in range(1, ayah_count + 1):
            entry = all_ayahs.get((surah, ayah))
            if not entry:
                continue
            translation = entry["translation"]
            footnotes   = entry["footnotes"]
            if footnotes:
                text = f"{translation}\\n\\nFootnotes: {footnotes}"
            else:
                text = translation
            text = process_text(text)
            lines.append(f'  {surah * 1000 + ayah}: "{text}",')

    lines.append("};")
    lines.append("")
    lines.append(f"String? {DART_FUNC_NAME}(int surah, int ayah) => _{DART_VAR_NAME}[surah * 1000 + ayah];")

    dart_path = os.path.join(OUT_DIR, f"{TRANSLATION_KEY}.dart")
    with open(dart_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"✓ Dart saved: {dart_path}")
    print(f"\nTotal ayat written: {len(all_ayahs)}")


if __name__ == "__main__":
    main()
