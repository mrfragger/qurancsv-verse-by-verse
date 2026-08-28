#!/usr/bin/env python3

import csv
import glob
import io
import os
import platform
import re
import shutil
import subprocess

try:
    import jieba
    jieba.setLogLevel(20)
    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False

try:
    from sudachipy import Dictionary as SudachiDictionary
    _test_tokenizer = SudachiDictionary().create()
    _test_tokenizer.tokenize("テスト")
    SUDACHI_AVAILABLE = True
    del _test_tokenizer
except (ImportError, ModuleNotFoundError, Exception):
    SUDACHI_AVAILABLE = False

try:
    from pythainlp.tokenize import word_tokenize as thai_word_tokenize
    PYTHAINLP_AVAILABLE = True
except ImportError:
    PYTHAINLP_AVAILABLE = False

try:
    from khmer_segmenter import Tokenizer as KhmerTokenizer
    _khmer_tokenizer = KhmerTokenizer(seg_type="com")
    _khmer_tokenizer.tokenize("សួស្ដី")
    KHMER_AVAILABLE = True
except (ImportError, Exception):
    KHMER_AVAILABLE = False

RANGES = [
    "001-006", "007-015", "016-024", "025-036", "037-049", "050-069", "070-114",
]

RANGE_BOUNDS = [
    (1, 6), (7, 15), (16, 24), (25, 36), (37, 49), (50, 69), (70, 114),
]

REPLACEMENTS = {
    "Qur\u2019an": "Quran",
    "Qur'an": "Quran",
    "Qur\u2019ân": "Quran",
    "Qur'ân": "Quran",
    "Allâh": "Allah",
    "Allāh": "Allah",
    "صلى الله عليه وسلم": "﵇",
    "\u0101": "a",
    "\u0100": "A",
    "\u012B": "i",
    "\u012A": "I",
    "\u016B": "u",
    "\u016A": "U",
    "\u1E63": "s",
    "\u1E62": "S",
    "\u1E0D": "d",
    "\u1E0C": "D",
    "\u1E6D": "t",
    "\u1E6C": "T",
    "\u1E93": "z",
    "\u1E92": "Z",
    "\u1E25": "h",
    "\u1E24": "H",
    "\u1E0F": "dh",
    "\u1E0E": "Dh",
    "\u1E6F": "th",
    "\u1E6E": "Th",
    "\u0121": "gh",
    "\u0120": "Gh",
    "\u1E2B": "kh",
    "\u1E2A": "Kh",
    "\u02BF": "'",
    "\u02BE": "'",
    "\u00E2": "a",
    "\u00C2": "A",
    "\u00EE": "i",
    "\u00CE": "I",
    "\u00FB": "u",
    "\u00DB": "U",
}

CJK_THRESHOLDS = {6: 160, 5: 133, 4: 107, 3: 80, 2: 53}
LATIN_THRESHOLDS = {6: 480, 5: 400, 4: 320, 3: 240, 2: 160}
THAI_THRESHOLDS = {6: 400, 5: 320, 4: 260, 3: 200, 2: 130}
KHMER_THRESHOLDS = {6: 400, 5: 320, 4: 260, 3: 200, 2: 130}


def detect_prefix(filename):
    base = os.path.splitext(os.path.basename(filename))[0]
    return re.sub(r'_v[\d].*$', '', base)


def prefix_to_label(prefix):
    return " ".join(word.capitalize() for word in prefix.split("_"))


def detect_script(text):
    total = len(text.strip())
    if total == 0:
        return "latin"
    chinese = len(re.findall(r'[\u4E00-\u9FFF]', text))
    japanese = len(re.findall(r'[\u3040-\u309F\u30A0-\u30FF]', text))
    korean = len(re.findall(r'[\uAC00-\uD7AF\u1100-\u11FF]', text))
    arabic = len(re.findall(r'[\u0600-\u06FF]', text))
    thai = len(re.findall(r'[\u0E00-\u0E7F]', text))
    khmer = len(re.findall(r'[\u1780-\u17FF]', text))
    if japanese > 0:
        return "japanese"
    if chinese > 10 and chinese / total > 0.2:
        return "chinese"
    if korean > 10 and korean / total > 0.2:
        return "korean"
    if thai > 10 and thai / total > 0.2:
        return "thai"
    if khmer > 10 and khmer / total > 0.2:
        return "khmer"
    if arabic > 10 and arabic / total > 0.2:
        return "arabic"
    return "latin"


def find_all_language_dirs():
    dirs = []
    for entry in sorted(os.listdir(".")):
        if os.path.isdir(entry) and not entry.startswith(".") and entry not in ("zsplit", "z_bismillah"):
            if glob.glob(os.path.join(entry, "*.csv")):
                dirs.append(entry)
    return dirs


def find_all_vtt_dirs():
    dirs = []
    for entry in sorted(os.listdir(".")):
        if os.path.isdir(entry) and not entry.startswith(".") and entry not in ("zsplit", "z_bismillah"):
            if glob.glob(os.path.join(entry, "*.vtt")):
                dirs.append(entry)
    return dirs


def step_clean_csv(filepath):
    print("\n  === Step 0: Clean CSV (remove header info, id, footnotes) ===")
    with open(filepath, "r", encoding="utf-8") as f:
        raw_lines = f.readlines()

    data_lines = []
    found_header = False
    in_quotes = False

    for line in raw_lines:
        starts_outside_quotes = not in_quotes
        if line.count('"') % 2 == 1:
            in_quotes = not in_quotes

        if starts_outside_quotes:
            stripped = line.strip().strip('"')
            if stripped.startswith("#") or stripped.lower().startswith("translation info"):
                continue
            if stripped.replace(",", "").strip() == "":
                continue
            if not found_header and stripped.lower().startswith("id,"):
                found_header = True
                continue

        if found_header:
            data_lines.append(line)

    if not data_lines:
        print("    ERROR: No data rows found after removing header info")
        return
    reader = csv.reader(io.StringIO("".join(data_lines)))
    output_rows = [["sura", "aya", "translation"]]
    for row in reader:
        if not row or len(row) < 4:
            continue
        sura = row[1].strip()
        aya = row[2].strip()
        translation = row[3].strip() if len(row) > 3 else ""
        output_rows.append([sura, aya, translation])
    with open(filepath, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        writer.writerows(output_rows)
    print(f"    Removed translation info, id column, and footnotes column")
    print(f"    Data rows: {len(output_rows) - 1}")
    print(f"    Updated: {filepath}")


def normalize_text(text):
    for src, dst in REPLACEMENTS.items():
        text = text.replace(src, dst)
    return text


def remove_reference_numbers(text):
    text = re.sub(r' \[\d+\]', '', text)
    text = re.sub(r'\[\d+\]', '', text)
    return text


def strip_leading_verse_number(translation, aya):
    m = re.match(r'^(\d+)[\.\,:]?\s*(.*)$', translation, re.DOTALL)
    if not m:
        return translation
    num, rest = m.group(1), m.group(2)
    try:
        if aya and int(num) == int(aya):
            return rest
    except ValueError:
        pass
    return translation


def step_normalize_and_clean(filepath):
    print("\n  === Step 1: Normalize, remove reference numbers & verse numbers ===")
    with open(filepath, "r", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    if not rows:
        print("    ERROR: CSV is empty")
        return
    header = rows[0]
    data_rows = rows[1:]
    found_chars = set()
    out_rows = [header]
    for row in data_rows:
        if len(row) < 3:
            out_rows.append(row)
            continue
        sura, aya, translation = row[0], row[1], row[2]
        rest = row[3:]
        for src in REPLACEMENTS:
            if src in translation:
                found_chars.add(src)
        translation = normalize_text(translation)
        translation = remove_reference_numbers(translation)
        translation = strip_leading_verse_number(translation, aya)
        out_rows.append([sura, aya, translation] + rest)
    with open(filepath, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        writer.writerows(out_rows)
    if found_chars:
        print(f"    Replaced: {sorted(found_chars)}")
    else:
        print("    No Arabic transliteration characters found")
    print(f"    Reference numbers and verse numbers removed")
    print(f"    Updated: {filepath}")

def step_duplicate_and_split(filepath, subdir, prefix):
    print("\n  === Step 2: Split into 7 range files ===")
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    rows = list(csv.reader(io.StringIO(content)))
    if not rows:
        print("    ERROR: CSV is empty")
        return []
    header = None
    data_rows = rows
    if rows[0][0].strip().lower() in ("sura", "surah", "chapter"):
        header = rows[0]
        data_rows = rows[1:]
    created_files = []
    for i, (range_label, (start, end)) in enumerate(zip(RANGES, RANGE_BOUNDS)):
        out_name = f"{prefix}{range_label}.csv"
        out_path = os.path.join(subdir, out_name)
        filtered = []
        if header:
            filtered.append(header)
        for row in data_rows:
            if not row:
                continue
            try:
                sura_num = int(row[0].strip().lstrip("\ufeff"))
            except ValueError:
                continue
            if start <= sura_num <= end:
                filtered.append(row)
        with open(out_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
            writer.writerows(filtered)
        data_count = len(filtered) - (1 if header else 0)
        print(f"    Created: {out_path} (surahs {start}-{end}, {data_count} rows)")
        created_files.append(out_path)
    return created_files


def step_add_arabic_audio(subdir, prefix):
    print("\n  === Step 3: Add Arabic text & audio ===")
    for suffix in RANGES:
        source_file = f"quran_saheeh{suffix}.csv"
        if not os.path.exists(source_file):
            print(f"    WARNING: Source file not found: {source_file} — skipping")
            continue
        target_files = glob.glob(os.path.join(subdir, f"{prefix}{suffix}.csv"))
        if not target_files:
            print(f"    WARNING: No target file matching {prefix}{suffix}.csv — skipping")
            continue
        target_file = target_files[0]
        arabic_audio = {}
        with open(source_file, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = (row["sura"].strip(), row["aya"].strip())
                arabic_audio[key] = (row["arabic"], row["audio"])
        target_rows = []
        with open(target_file, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                target_rows.append(row)
        with open(target_file, "w", newline="", encoding="utf-8") as f:
            fieldnames = ["sura", "aya", "translation", "arabic", "audio"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in target_rows:
                key = (row["sura"].strip().lstrip("\ufeff"), row["aya"].strip())
                arabic, audio = arabic_audio.get(key, ("", ""))
                translation = row.get("translation") or row.get("text", "")
                writer.writerow({
                    "sura": row["sura"],
                    "aya": row["aya"],
                    "translation": translation,
                    "arabic": arabic,
                    "audio": audio,
                })
        print(f"    Updated: {target_file} (merged from {source_file})")


def load_translations_from_csv(csv_path):
    translations = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            translations.append({
                "sura": row.get("sura", "").strip(),
                "aya": row.get("aya", "").strip(),
                "translation": row.get("translation", "").strip(),
            })
    return translations


def parse_vtt_blocks(vtt_path):
    with open(vtt_path, "r", encoding="utf-8") as f:
        content = f.read()
    lines = content.split("\n")
    header_lines = []
    i = 0
    timecode_re = re.compile(r'^\d{2}:\d{2}:\d{2}\.\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}\.\d{3}')
    while i < len(lines):
        if timecode_re.match(lines[i].strip()):
            break
        header_lines.append(lines[i])
        i += 1
    blocks = []
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if timecode_re.match(line):
            timecode = line
            i += 1
            text_lines = []
            while i < len(lines) and lines[i].strip():
                text_lines.append(lines[i].strip())
                i += 1
            blocks.append((timecode, text_lines))
        else:
            i += 1
    return header_lines, blocks


def build_vtt(header_lines, blocks):
    parts = []
    for line in header_lines:
        parts.append(line)
    if header_lines and header_lines[-1].strip() != "":
        parts.append("")
    for timecode, text_lines in blocks:
        parts.append(timecode)
        for tl in text_lines:
            parts.append(tl)
        parts.append("")
    return "\n".join(parts)


def step_translate_vtt(subdir, prefix, reciter, target_label):
    print("\n  === Step 4: Generate translated VTT files ===")
    created_vtts = []
    vtt_found = False

    sample_text = ""
    try:
        with open(os.path.join(subdir, f"{prefix}.csv"), newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                sample_text = row.get("translation", "").strip()
                break
    except FileNotFoundError:
        pass
    lang_script = detect_script(sample_text) if sample_text else "latin"
    cjk_no_separator = lang_script in ("chinese", "japanese", "korean")

    for suffix in RANGES:
        vtt_pattern = f"*{suffix}*{reciter}*.vtt"
        vtt_matches = glob.glob(vtt_pattern)
        if not vtt_matches:
            vtt_matches = glob.glob(f"*{suffix}*.vtt")
        if not vtt_matches:
            continue
        vtt_found = True
        source_vtt = vtt_matches[0]
        csv_path = os.path.join(subdir, f"{prefix}{suffix}.csv")
        if not os.path.exists(csv_path):
            print(f"    WARNING: CSV not found: {csv_path} — skipping")
            continue
        print(f"    Processing range {suffix}:")
        print(f"      Source VTT: {source_vtt}")
        print(f"      CSV:        {csv_path}")
        translations = load_translations_from_csv(csv_path)
        header_lines, blocks = parse_vtt_blocks(source_vtt)
        if len(translations) != len(blocks):
            print(f"      WARNING: Translation count ({len(translations)}) != VTT block count ({len(blocks)})")
            print(f"      Will process min({len(translations)}, {len(blocks)}) entries")
        count = min(len(translations), len(blocks))
        new_blocks = []
        for i in range(len(blocks)):
            timecode, old_text = blocks[i]
            if i < len(translations):
                t = translations[i]
                if cjk_no_separator:
                    label = f"{t['sura']}{t['aya']}"
                else:
                    label = f"{t['sura']},{t['aya']}"
                text = f"{label} {t['translation']}".strip()
                new_blocks.append((timecode, [text]))
            else:
                new_blocks.append((timecode, old_text))
        new_vtt_content = build_vtt(header_lines, new_blocks)
        out_name = os.path.basename(source_vtt)
        out_path = os.path.join(subdir, out_name)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(new_vtt_content)
        print(f"      Created: {out_path} ({count} cues replaced)")
        created_vtts.append(out_path)
    if not vtt_found:
        print("    No source VTT files found — skipping VTT generation.")
    return created_vtts


def parse_timestamp_ms(ts):
    ts = ts.strip()
    parts = ts.split(":")
    h = int(parts[0])
    m = int(parts[1])
    s_parts = parts[2].split(".")
    s = int(s_parts[0])
    ms = int(s_parts[1])
    return h * 3600000 + m * 60000 + s * 1000 + ms


def format_timestamp_ms(ms):
    h = ms // 3600000
    ms %= 3600000
    m = ms // 60000
    ms %= 60000
    s = ms // 1000
    ms %= 1000
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def find_word_boundary(text, pos):
    for j in range(50):
        if pos + j < len(text) and text[pos + j] == " ":
            return pos + j
        if pos - j >= 0 and text[pos - j] == " ":
            return pos - j
    return pos


def tokenize_chinese(text):
    if not JIEBA_AVAILABLE:
        return list(text)
    return list(jieba.cut(text))


def tokenize_japanese(text):
    if not SUDACHI_AVAILABLE:
        return list(text)
    tokenizer = SudachiDictionary().create()
    morphemes = tokenizer.tokenize(text)
    return [m.surface() for m in morphemes]


def tokenize_korean(text):
    return text.split(" ")


def tokenize_thai(text):
    if not PYTHAINLP_AVAILABLE:
        return list(text)
    return thai_word_tokenize(text, engine="attacut")


def tokenize_khmer(text):
    if not KHMER_AVAILABLE:
        return list(text)
    return _khmer_tokenizer.tokenize(text)


def find_token_boundary(tokens, target_char_pos):
    cumulative = 0
    best_pos = 0
    best_diff = abs(target_char_pos)
    for i, token in enumerate(tokens):
        cumulative += len(token)
        diff = abs(cumulative - target_char_pos)
        if diff < best_diff:
            best_diff = diff
            best_pos = cumulative
    return best_pos


def split_cjk_text(text, num_parts, script):
    if script == "chinese":
        tokens = tokenize_chinese(text)
    elif script == "japanese":
        tokens = tokenize_japanese(text)
    elif script == "korean":
        tokens = tokenize_korean(text)
    elif script == "thai":
        tokens = tokenize_thai(text)
    elif script == "khmer":
        tokens = tokenize_khmer(text)
    else:
        return [text]
    total_len = len(text)
    boundaries = [0]
    for k in range(1, num_parts):
        target = total_len * k // num_parts
        boundary = find_token_boundary(tokens, target)
        if boundary > boundaries[-1]:
            boundaries.append(boundary)
    boundaries.append(total_len)
    parts = []
    for i in range(len(boundaries) - 1):
        part = text[boundaries[i]:boundaries[i + 1]].strip()
        if part:
            parts.append(part)
    while len(parts) < num_parts:
        parts.append("")
    return parts[:num_parts]


def split_vtt_long_subs(vtt_path, output_path):
    with open(vtt_path, "r", encoding="utf-8") as f:
        content = f.read()
    lines = content.split("\n")
    output = []
    split_count = 0
    i = 0
    timecode_re = re.compile(r'^\d{2}:\d{2}:\d{2}\.\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}\.\d{3}')
    tag_re = re.compile(r'<[^>]+>')
    verse_num_re = re.compile(r'^\d+\.\s+')

    while i < len(lines):
        line = lines[i]
        if timecode_re.match(line.strip()):
            parts = line.split("-->")
            start_ms = parse_timestamp_ms(parts[0])
            end_ms = parse_timestamp_ms(parts[1])
            text_lines = []
            i += 1
            while i < len(lines) and lines[i].strip():
                text_lines.append(lines[i])
                i += 1

            original_text = " ".join(t.strip() for t in text_lines)
            clean = tag_re.sub("", original_text)
            clean = verse_num_re.sub("", clean)
            script = detect_script(clean)

            if script == "arabic":
                text_to_split = original_text
                thresholds = LATIN_THRESHOLDS
                num_parts = 0
                for n_parts in [6, 5, 4, 3, 2]:
                    if len(clean) > thresholds[n_parts]:
                        num_parts = n_parts
                        break
                if num_parts > 0:
                    boundaries = [0]
                    for k in range(1, num_parts):
                        target = len(text_to_split) * k // num_parts
                        pos = find_word_boundary(text_to_split, target)
                        if pos > boundaries[-1]:
                            boundaries.append(pos)
                    boundaries.append(len(text_to_split))
                    text_parts = []
                    for b in range(len(boundaries) - 1):
                        part = text_to_split[boundaries[b]:boundaries[b+1]].strip()
                        if part:
                            text_parts.append(part)
                    while len(text_parts) < num_parts:
                        text_parts.append("")
                    dur = end_ms - start_ms
                    for idx in range(num_parts):
                        t_start = start_ms + dur * idx // num_parts
                        t_end = start_ms + dur * (idx + 1) // num_parts
                        output.append(f"{format_timestamp_ms(t_start)} --> {format_timestamp_ms(t_end)}")
                        output.append(text_parts[idx])
                        output.append("")
                    split_count += 1
                else:
                    output.append(line.strip())
                    output.append(original_text)
                    output.append("")

            elif script in ("chinese", "japanese", "korean"):
                thresholds = CJK_THRESHOLDS
                num_parts = 0
                for n_parts in [6, 5, 4, 3, 2]:
                    if len(clean) > thresholds[n_parts]:
                        num_parts = n_parts
                        break
                if num_parts > 0:
                    text_parts = split_cjk_text(clean, num_parts, script)
                    dur = end_ms - start_ms
                    for idx in range(num_parts):
                        t_start = start_ms + dur * idx // num_parts
                        t_end = start_ms + dur * (idx + 1) // num_parts
                        output.append(f"{format_timestamp_ms(t_start)} --> {format_timestamp_ms(t_end)}")
                        output.append(text_parts[idx] if idx < len(text_parts) else "")
                        output.append("")
                    split_count += 1
                else:
                    output.append(line.strip())
                    output.append(clean)
                    output.append("")

            elif script == "thai":
                thresholds = THAI_THRESHOLDS
                num_parts = 0
                for n_parts in [6, 5, 4, 3, 2]:
                    if len(clean) > thresholds[n_parts]:
                        num_parts = n_parts
                        break
                if num_parts > 0:
                    text_parts = split_cjk_text(clean, num_parts, script)
                    dur = end_ms - start_ms
                    for idx in range(num_parts):
                        t_start = start_ms + dur * idx // num_parts
                        t_end = start_ms + dur * (idx + 1) // num_parts
                        output.append(f"{format_timestamp_ms(t_start)} --> {format_timestamp_ms(t_end)}")
                        output.append(text_parts[idx] if idx < len(text_parts) else "")
                        output.append("")
                    split_count += 1
                else:
                    output.append(line.strip())
                    output.append(clean)
                    output.append("")

            elif script == "khmer":
                thresholds = KHMER_THRESHOLDS
                num_parts = 0
                for n_parts in [6, 5, 4, 3, 2]:
                    if len(clean) > thresholds[n_parts]:
                        num_parts = n_parts
                        break
                if num_parts > 0:
                    text_parts = split_cjk_text(clean, num_parts, script)
                    dur = end_ms - start_ms
                    for idx in range(num_parts):
                        t_start = start_ms + dur * idx // num_parts
                        t_end = start_ms + dur * (idx + 1) // num_parts
                        output.append(f"{format_timestamp_ms(t_start)} --> {format_timestamp_ms(t_end)}")
                        output.append(text_parts[idx] if idx < len(text_parts) else "")
                        output.append("")
                    split_count += 1
                else:
                    output.append(line.strip())
                    output.append(clean)
                    output.append("")

            else:
                thresholds = LATIN_THRESHOLDS
                num_parts = 0
                for n_parts in [6, 5, 4, 3, 2]:
                    if len(clean) > thresholds[n_parts]:
                        num_parts = n_parts
                        break

                if num_parts == 6:
                    sixth = len(clean) // 6
                    s1 = find_word_boundary(clean, sixth)
                    s2 = find_word_boundary(clean, sixth * 2)
                    s3 = find_word_boundary(clean, sixth * 3)
                    s4 = find_word_boundary(clean, sixth * 4)
                    s5 = find_word_boundary(clean, sixth * 5)
                    text_parts = [
                        clean[:s1].strip(), clean[s1:s2].strip(), clean[s2:s3].strip(),
                        clean[s3:s4].strip(), clean[s4:s5].strip(), clean[s5:].strip(),
                    ]
                    dur = end_ms - start_ms
                    times = [start_ms + dur * k // 6 for k in range(1, 6)] + [end_ms]
                    starts = [start_ms] + times[:-1]
                    for idx in range(6):
                        output.append(f"{format_timestamp_ms(starts[idx])} --> {format_timestamp_ms(times[idx])}")
                        output.append(text_parts[idx])
                        output.append("")
                    split_count += 1

                elif num_parts == 5:
                    fifth = len(clean) // 5
                    s1 = find_word_boundary(clean, fifth)
                    s2 = find_word_boundary(clean, fifth * 2)
                    s3 = find_word_boundary(clean, fifth * 3)
                    s4 = find_word_boundary(clean, fifth * 4)
                    text_parts = [
                        clean[:s1].strip(), clean[s1:s2].strip(), clean[s2:s3].strip(),
                        clean[s3:s4].strip(), clean[s4:].strip(),
                    ]
                    dur = end_ms - start_ms
                    times = [start_ms + dur * k // 5 for k in range(1, 5)] + [end_ms]
                    starts = [start_ms] + times[:-1]
                    for idx in range(5):
                        output.append(f"{format_timestamp_ms(starts[idx])} --> {format_timestamp_ms(times[idx])}")
                        output.append(text_parts[idx])
                        output.append("")
                    split_count += 1

                elif num_parts == 4:
                    quarter = len(clean) // 4
                    s1 = find_word_boundary(clean, quarter)
                    s2 = find_word_boundary(clean, len(clean) // 2)
                    s3 = find_word_boundary(clean, quarter * 3)
                    text_parts = [
                        clean[:s1].strip(), clean[s1:s2].strip(),
                        clean[s2:s3].strip(), clean[s3:].strip(),
                    ]
                    dur = end_ms - start_ms
                    m1 = start_ms + dur // 4
                    m2 = start_ms + dur // 2
                    m3 = start_ms + dur * 3 // 4
                    starts = [start_ms, m1, m2, m3]
                    times = [m1, m2, m3, end_ms]
                    for idx in range(4):
                        output.append(f"{format_timestamp_ms(starts[idx])} --> {format_timestamp_ms(times[idx])}")
                        output.append(text_parts[idx])
                        output.append("")
                    split_count += 1

                elif num_parts == 3:
                    s1 = find_word_boundary(clean, len(clean) // 3)
                    s2 = find_word_boundary(clean, len(clean) * 2 // 3)
                    text_parts = [
                        clean[:s1].strip(), clean[s1:s2].strip(), clean[s2:].strip(),
                    ]
                    dur = end_ms - start_ms
                    m1 = start_ms + dur // 3
                    m2 = start_ms + dur * 2 // 3
                    starts = [start_ms, m1, m2]
                    times = [m1, m2, end_ms]
                    for idx in range(3):
                        output.append(f"{format_timestamp_ms(starts[idx])} --> {format_timestamp_ms(times[idx])}")
                        output.append(text_parts[idx])
                        output.append("")
                    split_count += 1

                elif num_parts == 2:
                    s1 = find_word_boundary(clean, len(clean) // 2)
                    p1 = clean[:s1].strip()
                    p2 = clean[s1:].strip()
                    mid_ms = start_ms + (end_ms - start_ms) // 2
                    output.append(f"{format_timestamp_ms(start_ms)} --> {format_timestamp_ms(mid_ms)}")
                    output.append(p1)
                    output.append("")
                    output.append(f"{format_timestamp_ms(mid_ms)} --> {format_timestamp_ms(end_ms)}")
                    output.append(p2)
                    output.append("")
                    split_count += 1

                else:
                    output.append(line.strip())
                    output.append(clean)
                    output.append("")
        else:
            output.append(line)
            i += 1

    result = "\n".join(output)
    result = re.sub(r'\n{3,}', '\n\n', result)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(result)
    return split_count


def halve_arabic_durations(vtt_path, output_path):
    with open(vtt_path, "r", encoding="utf-8") as f:
        content = f.read()
    lines = content.split("\n")
    output = []
    i = 0
    timecode_re = re.compile(r'^\d{2}:\d{2}:\d{2}\.\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}\.\d{3}')

    while i < len(lines):
        line = lines[i]
        if timecode_re.match(line.strip()):
            parts = line.split("-->")
            start_ms = parse_timestamp_ms(parts[0])
            end_ms = parse_timestamp_ms(parts[1])
            text_lines = []
            i += 1
            while i < len(lines) and lines[i].strip():
                text_lines.append(lines[i])
                i += 1
            original_text = " ".join(t.strip() for t in text_lines)
            script = detect_script(original_text)
            if script == "arabic":
                mid_ms = start_ms + (end_ms - start_ms) // 2
                output.append(f"{format_timestamp_ms(start_ms)} --> {format_timestamp_ms(mid_ms)}")
                for t in text_lines:
                    output.append(t)
                output.append("")
                output.append(f"{format_timestamp_ms(mid_ms)} --> {format_timestamp_ms(end_ms)}")
                for t in text_lines:
                    output.append(t)
                output.append("")
            else:
                output.append(f"{format_timestamp_ms(start_ms)} --> {format_timestamp_ms(end_ms)}")
                for t in text_lines:
                    output.append(t)
                output.append("")
        else:
            output.append(line)
            i += 1

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(output))


def step_split_long_subs(subdir, created_vtts):
    print("\n  === Step 4b: Split long subtitles ===")
    if not created_vtts:
        print("    No VTT files to split — skipping.")
        return
    lang_name = os.path.basename(subdir).capitalize()
    split_dir = os.path.join("zsplit", lang_name)
    os.makedirs(split_dir, exist_ok=True)
    for vtt_path in created_vtts:
        filename = os.path.basename(vtt_path)
        output_path = os.path.join(split_dir, filename)
        split_count = split_vtt_long_subs(vtt_path, output_path)
        print(f"    {filename}: split {split_count} long cues → zsplit/{lang_name}/{filename}")
    print(f"    Split files saved to: zsplit/{lang_name}/")


def split_vtts_only(subdir, use_3x=False):
    lang_name = os.path.basename(subdir).capitalize()
    vtt_files = sorted(glob.glob(os.path.join(subdir, "*.vtt")))
    if not vtt_files:
        print(f"  No VTT files found in '{subdir}/' — skipping.")
        return
    print(f"\n{'='*60}")
    print(f"  Splitting VTTs: {lang_name} ({len(vtt_files)} files){' [3x repeat mode]' if use_3x else ''}")
    print(f"{'='*60}")
    split_dir = os.path.join("zsplit", lang_name)
    os.makedirs(split_dir, exist_ok=True)
    for vtt_path in vtt_files:
        filename = os.path.basename(vtt_path)
        output_path = os.path.join(split_dir, filename)
        if use_3x:
            temp_path = output_path + ".tmp"
            halve_arabic_durations(vtt_path, temp_path)
            split_count = split_vtt_long_subs(temp_path, output_path)
            os.remove(temp_path)
        else:
            split_count = split_vtt_long_subs(vtt_path, output_path)
        print(f"    {filename}: split {split_count} long cues → zsplit/{lang_name}/{filename}")
    print(f"    Split files saved to: zsplit/{lang_name}/")


def step_copy_and_split_source_vtts(reciter):
    print("\n=== Splitting source English VTT files ===")
    folder_name = "a English saheeh"
    source_dir = os.path.join("zsplit", folder_name)
    os.makedirs(source_dir, exist_ok=True)
    processed = 0
    for suffix in RANGES:
        vtt_pattern = f"*{suffix}*{reciter}*.vtt"
        vtt_matches = glob.glob(vtt_pattern)
        if not vtt_matches:
            vtt_matches = glob.glob(f"*{suffix}*.vtt")
        if not vtt_matches:
            continue
        src = vtt_matches[0]
        dst = os.path.join(source_dir, os.path.basename(src))
        split_count = split_vtt_long_subs(src, dst)
        print(f"    {os.path.basename(src)}: split {split_count} long cues → zsplit/{folder_name}/")
        processed += 1
    if processed:
        print(f"  Split {processed} source VTT files to zsplit/{folder_name}/")
    else:
        print("  No source VTT files found to process.")

def step_deploy_split_source_vtts():
    print("\n=== Deploying split source VTT files to root ===")
    folder_name = "a English saheeh"
    split_source_dir = os.path.join("zsplit", folder_name)
    if not os.path.isdir(split_source_dir):
        print(f"    WARNING: '{split_source_dir}' not found — skipping deploy")
        return
    split_files = glob.glob(os.path.join(split_source_dir, "*.vtt"))
    if not split_files:
        print(f"    WARNING: No split VTT files found in '{split_source_dir}' — skipping deploy")
        return
    deployed = 0
    for src in split_files:
        dst = os.path.basename(src)
        shutil.copy2(src, dst)
        print(f"    Deployed: {dst}")
        deployed += 1
    print(f"  Deployed {deployed} split VTT files to root directory.")


def step_zip_zsplit(reciter="Alafasy Verse by Verse"):
    if not os.path.isdir("zsplit"):
        return
    print("\n--- Zip Output (Optional) ---")
    do_zip = input("Zip the zsplit folder? [y/N]: ").strip().lower() == "y"
    if not do_zip:
        return
    default_zip = f"Quran Arabic - {reciter}_vtt"
    zip_name = input(f"Enter zip filename [{default_zip}]: ").strip() or default_zip
    if zip_name != "zsplit":
        if os.path.exists(zip_name):
            shutil.rmtree(zip_name)
        os.rename("zsplit", zip_name)
        folder_to_zip = zip_name
    else:
        folder_to_zip = "zsplit"
    zip_filename = f"{zip_name}.zip"
    system = platform.system()
    try:
        if system == "Darwin":
            subprocess.run([
                "zip", "-r", zip_filename, folder_to_zip,
                "-x", "*.DS_Store", "-x", "*__MACOSX*"
            ], check=True)
        else:
            shutil.make_archive(zip_name, 'zip', '.', folder_to_zip)
        print(f"    Created: {zip_filename}")
    except Exception as e:
        print(f"    ERROR creating zip: {e}")
        print("    You can manually zip the folder.")
    if folder_to_zip != "zsplit":
        os.rename(folder_to_zip, "zsplit")


def process_language(subdir, do_vtt=False, reciter=None):
    csv_files = glob.glob(os.path.join(subdir, "*_v*.csv"))
    if not csv_files:
        csv_files = glob.glob(os.path.join(subdir, "*.csv"))
    if not csv_files:
        print(f"  ERROR: No CSV files found in '{subdir}'")
        return
    source_csv = csv_files[0]
    prefix = detect_prefix(source_csv)
    label = prefix_to_label(prefix)
    print(f"\n{'='*60}")
    print(f"  Processing: {label}")
    print(f"  Source: {source_csv}")
    print(f"  Prefix: {prefix}")
    print(f"{'='*60}")
    working_csv = os.path.join(subdir, f"{prefix}.csv")
    shutil.copy2(source_csv, working_csv)
    print(f"  Working copy: {working_csv}")
    step_clean_csv(working_csv)
    step_normalize_and_clean(working_csv)
    created = step_duplicate_and_split(working_csv, subdir, prefix)
    step_add_arabic_audio(subdir, prefix)
    created_vtts = []
    if do_vtt and reciter:
        target_label = label
        created_vtts = step_translate_vtt(subdir, prefix, reciter, target_label)
        if created_vtts:
            step_split_long_subs(subdir, created_vtts)
    return created, created_vtts

def step_backup_source_vtts(reciter):
    print("\n=== Backing up original source VTT files ===")
    backup_dir = os.path.join("zsplit", "zsourcevtt")
    os.makedirs(backup_dir, exist_ok=True)
    backed_up = 0
    for suffix in RANGES:
        vtt_pattern = f"*{suffix}*{reciter}*.vtt"
        vtt_matches = glob.glob(vtt_pattern)
        if not vtt_matches:
            vtt_matches = glob.glob(f"*{suffix}*.vtt")
        if not vtt_matches:
            print(f"    WARNING: No source VTT found for range {suffix} — skipping backup")
            continue
        src = vtt_matches[0]
        dst = os.path.join(backup_dir, os.path.basename(src))
        shutil.copy2(src, dst)
        print(f"    Backed up: {os.path.basename(src)} → zsplit/zsourcevtt/")
        backed_up += 1
    if backed_up:
        print(f"  Backed up {backed_up} original VTT files to zsplit/zsourcevtt/")
    else:
        print("  No source VTT files found to back up.")

def step_organize_media(source_dir="quranversebyverse"):
    print("\n=== Organize MP3 media files into range subdirectories ===")
    if not os.path.isdir(source_dir):
        print(f"  ERROR: '{source_dir}' directory not found.")
        return
    mp3_files = glob.glob(os.path.join(source_dir, "*.mp3"))
    if not mp3_files:
        print(f"  ERROR: No mp3 files found in '{source_dir}'.")
        return

    target_dirs = {}
    for range_label in RANGES:
        target_dir = f"quran_saheeh{range_label}_media"
        os.makedirs(target_dir, exist_ok=True)
        target_dirs[range_label] = target_dir

    bismillah_dir = "z_bismillah"

    name_re = re.compile(r'^(\d{3})(\d{3})\.mp3$', re.IGNORECASE)
    moved = 0
    skipped = 0
    bismillah_moved = 0
    for filepath in sorted(mp3_files):
        filename = os.path.basename(filepath)
        m = name_re.match(filename)
        if not m:
            print(f"    WARNING: Skipping unrecognized filename: {filename}")
            skipped += 1
            continue
        sura_num = int(m.group(1))
        aya_part = m.group(2)
        if aya_part == "000":
            os.makedirs(bismillah_dir, exist_ok=True)
            dest_path = os.path.join(bismillah_dir, filename)
            shutil.move(filepath, dest_path)
            bismillah_moved += 1
            continue
        target_range = None
        for range_label, (start, end) in zip(RANGES, RANGE_BOUNDS):
            if start <= sura_num <= end:
                target_range = range_label
                break
        if target_range is None:
            print(f"    WARNING: Sura {sura_num} out of range 1-114, skipping: {filename}")
            skipped += 1
            continue
        dest_path = os.path.join(target_dirs[target_range], filename)
        shutil.move(filepath, dest_path)
        moved += 1

    print(f"\n  Moved {moved} mp3 files into range subdirectories.")
    if bismillah_moved:
        print(f"  Moved {bismillah_moved} bismillah file(s) (ayah 000) to '{bismillah_dir}/'.")
    if skipped:
        print(f"  Skipped {skipped} file(s) — see warnings above.")
    for range_label in RANGES:
        count = len(glob.glob(os.path.join(target_dirs[range_label], "*.mp3")))
        print(f"    quran_saheeh{range_label}_media/: {count} files")

    remaining = os.listdir(source_dir)
    if remaining:
        print(f"\n  WARNING: '{source_dir}' still contains {len(remaining)} item(s) — not deleting.")
        for item in remaining:
            print(f"    {item}")
    else:
        shutil.rmtree(source_dir)
        print(f"\n  Deleted empty source directory: {source_dir}")


def print_banner():
    print("""
╔══════════════════════════════════════════════════════════════╗
║                    zqurancsv.py                               ║
║          Combined Quran CSV Processing Pipeline              ║
╚══════════════════════════════════════════════════════════════╝

Steps:
  A. Organize mp3 media into range subdirectories like so:
      quran_saheeh001-006_media
      quran_saheeh007-015_media
      quran_saheeh016-024_media
      quran_saheeh025-036_media
      quran_saheeh037-049_media
      quran_saheeh050-069_media
      quran_saheeh070-114_media
      This can be done automatically by putting all mp3 into a subdir named quranversebyverse then choosing 3. Organize mp3 media into range subdirectories

      === Organize MP3 media files into range subdirectories ===

        Moved 6236 mp3 files into range subdirectories.
        Left 112 bismillah file(s) (ayah 000) in place, not moved.
          quran_saheeh001-006_media/: 954 files
          quran_saheeh007-015_media/: 947 files
          quran_saheeh016-024_media/: 954 files
          quran_saheeh025-036_media/: 933 files
          quran_saheeh037-049_media/: 842 files
          quran_saheeh050-069_media/: 745 files
          quran_saheeh070-114_media/: 861 files
          (which totals 6236 ayahs)

      Once that's done use SubSticher to make opus chaptered audiobooks with csv (Anki convert to audiobook and choose csv)

      Language put Quran Arabic or Quran English
      Title should automatically fill with 001-006 depending on which csv is chosen and put reciters name after 001-006
      example: Quran Arabic - 007-015 Ghamadi Verse by Verse

      Audio Repetitions 1x (2x, 3x, 4x are for anki audiobooks)
      Bitrate 32 kpbs (since recitations aren't purely speak)

      check 'Use filename as chaptername' so surah 2 ayah 5 is 002005 rather 4 digits
      uncheck Sample Mode (50 entries)
      check Prepend Sura/Aya to subtitles
      check Match media by range (this automatically change 001-006 to 070-114 corresponding to selected  csv)

      Front column translation (this is the chapter name)
      Back Column (arabic, doesn't matter though only for 2x, 3x, 4x repetitions)
      Audio Column audio (this is the mp3)
      Sura Column sura (adds surah number before each verse in the vtt subs)
      Aya Column aya (adds ayah number before each verse in the vtt subs)

      Subsequent audiobooks just choose the next csv and it autofills the surah numbers and then in Column Selection section click Use Last (3,4,5, Sura 1, Aya 2) so needn't manually fill in again

  B. Remove translation info header, id column, footnotes column
  C. Normalize Arabic transliteration characters, remove reference & verse numbers
  D. Split into 7 range-based files (001-006, 007-015, etc.)
  E. Add Arabic text and audio from quran_saheeh source files
  F. (Optional) Generate translated VTT files from existing English VTT source files
     (long subtitle cues are automatically split into shorter ones → zsplit/Language/)
  G. (Optional) Zip zsplit folder for distribution

For Japanese, Chinese, Thai, and Khmer tokenization, install:
  pip3 install jieba sudachipy SudachiDict-core pythainlp[attacut] khmer-segmenter

Make sure to have in the root dir (reciter subs generated with SubStitcher):
  qurancsv.py
  Quran Arabic - 001-006 Abu Bakr Ash-Shaatree Verse by Verse.opus
  Quran Arabic - 001-006 Abu Bakr Ash-Shaatree Verse by Verse.vtt
  Quran Arabic - 007-015 Abu Bakr Ash-Shaatree Verse by Verse.opus
  Quran Arabic - 007-015 Abu Bakr Ash-Shaatree Verse by Verse.vtt
  Quran Arabic - 016-024 Abu Bakr Ash-Shaatree Verse by Verse.opus
  Quran Arabic - 016-024 Abu Bakr Ash-Shaatree Verse by Verse.vtt
  Quran Arabic - 025-036 Abu Bakr Ash-Shaatree Verse by Verse.opus
  Quran Arabic - 025-036 Abu Bakr Ash-Shaatree Verse by Verse.vtt
  Quran Arabic - 037-049 Abu Bakr Ash-Shaatree Verse by Verse.opus
  Quran Arabic - 037-049 Abu Bakr Ash-Shaatree Verse by Verse.vtt
  Quran Arabic - 050-069 Abu Bakr Ash-Shaatree Verse by Verse.opus
  Quran Arabic - 050-069 Abu Bakr Ash-Shaatree Verse by Verse.vtt
  Quran Arabic - 070-114 Abu Bakr Ash-Shaatree Verse by Verse.opus
  Quran Arabic - 070-114 Abu Bakr Ash-Shaatree Verse by Verse.vtt
  quran_saheeh001-006.csv
  quran_saheeh007-015.csv
  quran_saheeh016-024.csv
  quran_saheeh025-036.csv
  quran_saheeh037-049.csv
  quran_saheeh050-069.csv
  quran_saheeh070-114.csv

And all translation CSV files in their respective subdirs:
  french/french_montada_v1.0.0-csv.1.csv
  german/german_bubenheim_v1.1.4-csv.1.csv
  etc.""")
    if JIEBA_AVAILABLE:
        print("\n  ✓ jieba (Chinese tokenizer) is installed")
    else:
        print("\n  ✗ jieba not installed — Chinese splitting will use character-level fallback")
    if SUDACHI_AVAILABLE:
        print("  ✓ sudachipy + SudachiDict-core (Japanese tokenizer) is installed")
    else:
        print("  ✗ sudachipy/SudachiDict-core not installed — Japanese splitting will use character-level fallback")
    if PYTHAINLP_AVAILABLE:
        print("  ✓ pythainlp + attacut (Thai tokenizer) is installed")
    else:
        print("  ✗ pythainlp not installed — Thai splitting will use character-level fallback")
    if KHMER_AVAILABLE:
        print("  ✓ khmer-segmenter (Khmer tokenizer) is installed")
    else:
        print("  ✗ khmer-segmenter not installed — Khmer splitting will use character-level fallback")



def main():
    print_banner()

    print("\nMode:")
    print("  1. Single language (full pipeline)")
    print("  2. Batch all languages (full pipeline)")
    print("  3. Organize mp3 media into range subdirectories")
    print("  after 3. make opus Quran Verse by Verse audiobooks")
    mode = input("Choose mode (1/2/3): ").strip()

    if mode in ("1", "2"):
        all_dirs = find_all_language_dirs()
        if not all_dirs:
            print("ERROR: No subdirectories with CSV files found.")
            return
        print(f"\nFound {len(all_dirs)} language directories:")
        for d in all_dirs:
            csv_files = glob.glob(os.path.join(d, "*_v*.csv"))
            if csv_files:
                p = detect_prefix(csv_files[0])
                print(f"  {d}/ → {prefix_to_label(p)}")
            else:
                print(f"  {d}/")

    if mode == "1":
        language = input("Enter language (subdirectory name): ").strip()
        if language not in all_dirs:
            print(f"ERROR: Directory '{language}' not found or has no CSV files.")
            return
        print("\n--- VTT Translation (Optional) ---")
        print("Requires English VTT source files in this directory.")
        do_vtt = input("Also generate translated VTT files? [Y/n]: ").strip().lower() != "n"
        reciter = None
        if do_vtt:
            reciter = input("Enter reciter name in VTT filenames [Alafasy Verse by Verse]: ").strip() or "Alafasy Verse by Verse"
            step_backup_source_vtts(reciter)
        process_language(language, do_vtt, reciter)
        if do_vtt and reciter:
            step_copy_and_split_source_vtts(reciter)
            step_deploy_split_source_vtts()
        step_zip_zsplit(reciter or "Alafasy Verse by Verse")

    elif mode == "2":
        print("\n--- VTT Translation (Optional) ---")
        print("Requires English VTT source files in this directory.")
        print("If enabled, all languages will use the same reciter/source settings.")
        do_vtt = input("Also generate translated VTT files? [Y/n]: ").strip().lower() != "n"
        reciter = None
        if do_vtt:
            reciter = input("Enter reciter name in VTT filenames [Alafasy Verse by Verse]: ").strip() or "Alafasy Verse by Verse"
            step_backup_source_vtts(reciter)
        print(f"\nProcessing {len(all_dirs)} languages...")
        for i, lang_dir in enumerate(all_dirs, 1):
            print(f"\n[{i}/{len(all_dirs)}]")
            try:
                process_language(lang_dir, do_vtt, reciter)
            except Exception as e:
                print(f"  ERROR processing {lang_dir}: {e}")
                print("  Continuing with next language...")
        if do_vtt and reciter:
            step_copy_and_split_source_vtts(reciter)
            step_deploy_split_source_vtts()
        step_zip_zsplit(reciter or "Alafasy")


    elif mode == "3":
        source_dir = input("Enter mp3 source directory [quranversebyverse]: ").strip() or "quranversebyverse"
        step_organize_media(source_dir)

    else:
        print("Invalid choice.")
        return

    print("\n" + "=" * 60)
    print("  ALL DONE!")
    print("=" * 60)


if __name__ == "__main__":
    main()
