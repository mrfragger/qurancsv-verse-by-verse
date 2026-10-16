#!/usr/bin/env python3
"""Rebuild verse_timestamps.json.gz + catalog.json for reciters from the
QUD-Technologies/quranic-universal-ayahs Hugging Face dataset, so that
download_audio.py --format ayah works without the GitHub release.

Only metadata columns are read (never the audio column).

    pip install duckdb huggingface_hub pyarrow

    python hf_to_release.py --list                   # slug, reciter name, (style, channel, year), Arabic name
    python hf_to_release.py --list --slugs-only > slugs.txt   # pure slugs, one per line
    python hf_to_release.py mukhtar_al_haj_mp3quran  # one or more slugs
    python hf_to_release.py --all                    # every reciter (skips finished ones)
    python hf_to_release.py --all --match qdc        # only slugs containing "qdc"
    python hf_to_release.py --all --skip-missing     # don't build reciters with gaps

While a reciter is processed it is checked for missing ayahs / surahs and a
WARNING is printed. 1:1 (the basmalah) is reported as informational only, since
it is missing from most recordings. Warned reciters are still built unless
--skip-missing is given.

Output goes to out/<slug>/{catalog.json,verse_timestamps.json.gz}; then:

    python download_audio.py out/<slug>/catalog.json --reciter <slug> --format ayah
"""
import argparse
import gzip
import json
import sys
from pathlib import Path

REPO = "QUD-Technologies/quranic-universal-ayahs"
COLS = "surah, ayah, duration_ms, source_url, source_offset_ms"
NON_RECITER = {"mushafs"}
OK_MISSING = {"1:1"}

# Verses per surah, Hafs / Kufan numbering (6,236 total, basmalah of surah 1 = 1:1).
SURAH_COUNTS = [
    7, 286, 200, 176, 120, 165, 206, 75, 129, 109, 123, 111, 43, 52, 99, 128, 111, 110,
    98, 135, 112, 78, 118, 64, 77, 227, 93, 88, 69, 60, 34, 30, 73, 54, 45, 83, 182, 88,
    75, 85, 54, 53, 89, 59, 37, 35, 38, 29, 18, 45, 60, 49, 62, 55, 78, 96, 29, 22, 24,
    13, 14, 11, 11, 18, 12, 12, 30, 52, 52, 44, 28, 28, 20, 56, 40, 31, 50, 40, 46, 42,
    29, 19, 36, 25, 22, 17, 19, 26, 30, 20, 15, 21, 11, 8, 8, 19, 5, 8, 8, 11, 11, 8, 3,
    9, 5, 4, 7, 3, 6, 3, 5, 4, 5, 6,
]
assert len(SURAH_COUNTS) == 114 and sum(SURAH_COUNTS) == 6236
# Riwayat that share this numbering. Warsh/Qalon number verses differently, so for
# those we can only detect gaps and missing surahs, not a truncated tail.
KUFAN = {"hafs_an_asim", "shubah_an_asim"}


def parse_configs(configs: list) -> dict:
    """{slug: riwayah_dir} from the dataset card's `configs` list."""
    out = {}
    for c in configs or []:
        name = c.get("config_name")
        files = c.get("data_files")
        if isinstance(files, list) and files:
            first = files[0]
            path = first.get("path") if isinstance(first, dict) else first
        else:
            path = files
        if not name or not path or "/" not in path:
            continue
        folder = path.split("/")[0]
        if name in NON_RECITER or folder in NON_RECITER:
            continue
        out[name] = folder
    return out


def list_reciters() -> dict:
    from huggingface_hub import HfApi

    info = HfApi().dataset_info(REPO)
    cd = info.card_data
    configs = cd.to_dict().get("configs") if hasattr(cd, "to_dict") else cd.get("configs")
    return parse_configs(configs)


def fetch_catalog(url: str = f"hf://datasets/{REPO}/mushafs/all-*.parquet") -> dict:
    """{slug: catalog row} from the dataset's `mushafs` catalog (reciter names,
    style, channel, year...). It is one small parquet. Never fatal: on any
    failure it returns {} so listing and building still work, just without names."""
    rows = None
    try:
        import duckdb

        cur = duckdb.connect().execute(f"SELECT * FROM '{url}'")
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    except Exception:
        try:
            from huggingface_hub import HfFileSystem
            import pyarrow.parquet as pq

            fs = HfFileSystem()
            rows = []
            for p in sorted(fs.glob(url.replace("hf://", ""))):
                with fs.open(p, "rb") as fh:
                    rows += pq.read_table(fh).to_pylist()
        except Exception as exc:
            print(f"(could not load reciter names: {exc})", file=sys.stderr)
            return {}
    return {r["slug"]: r for r in rows if r.get("slug")}


def describe(row) -> str:
    """'Name EN  (style, channel, year)  Name AR' for one catalog row.

    The parenthesised bit tells variants of the same reciter apart (Murattal vs
    Mujawwad, YouTube vs QuranicAudio, 2025 vs 2026). Arabic goes last so the
    right-to-left text can't scramble the rest of the line."""
    if not row:
        return ""
    bits = []
    riwayah = row.get("riwayah") or ""
    if riwayah and not riwayah.lower().startswith("hafs"):  # Hafs is the default; flag the rest
        bits.append(riwayah)
    for key in ("style", "channel", "recording_year", "recording_context"):
        val = row.get(key)
        if val not in (None, ""):
            bits.append(str(val))
    tag = f"  ({', '.join(bits)})" if bits else ""
    ar = row.get("name_ar")
    return f"{row.get('name_en') or ''}{tag}" + (f"  {ar}" if ar else "")


def fetch_rows(slug: str, folder: str, cols: str = COLS):
    """Rows for one reciter, selecting only the named (small) columns."""
    try:
        import duckdb

        con = duckdb.connect()
        pattern = f"hf://datasets/{REPO}/{folder}/{slug}-*.parquet"
        return con.execute(
            f"SELECT {cols} FROM '{pattern}' ORDER BY surah, ayah"
        ).fetchall()
    except Exception as exc:  # hf:// unsupported in this duckdb build
        print(f"  duckdb hf:// failed ({exc}); using HfFileSystem", file=sys.stderr)
    from huggingface_hub import HfFileSystem
    import pyarrow.parquet as pq

    fs = HfFileSystem()
    paths = sorted(fs.glob(f"datasets/{REPO}/{folder}/{slug}-*.parquet"))
    if not paths:
        raise RuntimeError(f"no parquet shards found for {slug} in {folder}")
    names = [c.strip() for c in cols.split(",")]
    rows = []
    for p in paths:
        with fs.open(p, "rb") as fh:  # column projection -> ranged reads, no audio
            t = pq.read_table(fh, columns=names)
        rows += list(zip(*[t.column(n).to_pylist() for n in names]))
    rows.sort(key=lambda r: (r[0], r[1]))
    return rows


def compute_missing(pairs, folder: str):
    """-> (missing, tail_checked). missing is e.g. ['1:1', '26:21', 'surah 39']."""
    by = {}
    for s, a in pairs:
        by.setdefault(int(s), set()).add(int(a))
    kufan = folder in KUFAN
    missing = []
    for s in range(1, 115):
        got = by.get(s)
        if not got:
            missing.append(f"surah {s}")
            continue
        n = SURAH_COUNTS[s - 1] if kufan else max(got)
        missing += [f"{s}:{a}" for a in range(1, n + 1) if a not in got]
        if kufan:  # numbering mismatch shows up as ayahs past the end
            missing += [f"{s}:{a}(extra)" for a in sorted(got) if a > n]
    return missing, kufan


def unexpected(missing) -> list:
    """Everything missing except the (common, harmless) 1:1."""
    return [m for m in missing if m not in OK_MISSING]


def warn_lines(missing, tail_checked: bool) -> list:
    """Human-readable warnings for one reciter (empty list = nothing to warn about)."""
    lines = []
    surahs = [m[len("surah "):] for m in missing if m.startswith("surah ")]
    ayahs = [m for m in unexpected(missing) if not m.startswith("surah ")]
    if surahs:
        lines.append(f"WARNING: missing surahs: {', '.join(surahs)}")
    if ayahs:
        shown = ", ".join(ayahs[:20]) + (f" (+{len(ayahs) - 20} more)" if len(ayahs) > 20 else "")
        lines.append(f"WARNING: missing ayahs: {shown}")
    if lines and not tail_checked:
        lines.append("(note: numbering differs from Hafs, so only gaps/missing surahs "
                     "were checked, not a cut-off last verse)")
    if "1:1" in missing and not lines:
        lines.append("note: 1:1 not present (normal)")
    return lines


def build(slug: str, rows, out: Path, missing) -> None:
    out.mkdir(parents=True, exist_ok=True)
    verse_rows, urls = [], {}
    for i, (su, ay, dur, url, off) in enumerate(rows):
        start, end = int(off), int(off) + int(dur)
        nxt = rows[i + 1] if i + 1 < len(rows) else None
        gap = int(nxt[4]) - end if nxt and nxt[0] == su else 0
        verse_rows.append([f"{su}:{ay}", start, end, True, max(gap, 0)])
        if not url.startswith("http"):
            url = "https://" + url
        urls.setdefault(str(su), url)
    vt = {
        "_meta": {
            "slug": slug, "units": "ms", "tier": "verse",
            "verse_count": len(verse_rows), "occurrence_count": len(verse_rows),
            "layout": "rows=[[ref,start,end,canonical,silence_after],...]",
        },
        "rows": verse_rows,
    }
    with gzip.open(out / "verse_timestamps.json.gz", "wt", encoding="utf-8") as f:
        json.dump(vt, f, ensure_ascii=False, separators=(",", ":"))
    catalog = {
        "slug": slug,
        "audio_category": "by_surah",
        "coverage": {"ayahs": len(verse_rows), "surahs": len(urls),
                     "missing_verses": ", ".join(missing) or None},
        "audio": {"chapter_urls": urls, "bitrate_mode": "cbr",
                  "bitrate_kbps_nominal": 192, "sample_rate_hz": 44100},
    }
    (out / "catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=1), encoding="utf-8")
    shared = len(urls) - len(set(urls.values()))
    bad = sum(1 for r in verse_rows if r[2] <= r[1])
    print(f"  {len(verse_rows)} verses, {len(urls)} surahs, "
          f"{shared} surahs share a source file, {bad} rows with end<=start -> {out}/")
    if shared:
        print("  NOTE: shared source files - offsets may be relative to the whole "
              "video; chapter_offsets_ms is NOT written. Check before using.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slugs", nargs="*", help="reciter slug(s)")
    ap.add_argument("--list", action="store_true", help="print the live reciter list and exit")
    ap.add_argument("--slugs-only", action="store_true", help="with --list: slugs only")
    ap.add_argument("--all", action="store_true", help="process every reciter")
    ap.add_argument("--match", help="only slugs containing this substring")
    ap.add_argument("--skip-missing", action="store_true",
                    help="don't build reciters missing ayahs/surahs other than 1:1")
    ap.add_argument("--force", action="store_true", help="redo reciters already in --out")
    ap.add_argument("--out", type=Path, default=Path("out"))
    args = ap.parse_args()

    reciters = list_reciters()
    if args.match:
        reciters = {s: d for s, d in reciters.items() if args.match in s}

    if args.list:
        if args.slugs_only:  # pure slugs, safe to feed to a loop
            for slug in sorted(reciters):
                print(slug)
        else:
            catalog = fetch_catalog()
            width = max((len(s) for s in reciters), default=0)
            for slug in sorted(reciters):
                print(f"{slug:<{width}}  {describe(catalog.get(slug))}".rstrip())
        print(f"# {len(reciters)} reciters", file=sys.stderr)
        return 0

    todo = sorted(reciters) if args.all else args.slugs
    if not todo:
        ap.error("give slug(s), or use --all / --list")

    failed, warned, skipped = [], [], []
    catalog = fetch_catalog()
    for n, slug in enumerate(todo, 1):
        dest = args.out / slug
        if (not args.force and (dest / "catalog.json").exists()
                and (dest / "verse_timestamps.json.gz").exists()):
            print(f"[{n}/{len(todo)}] {slug}: already done, skipping")
            continue
        folder = reciters.get(slug)
        if not folder:
            print(f"[{n}/{len(todo)}] {slug}: not in the dataset's config list")
            failed.append(slug)
            continue
        name = (catalog.get(slug) or {}).get("name_en")
        print(f"[{n}/{len(todo)}] {slug}{' - ' + name if name else ''} ({folder})")
        try:
            rows = fetch_rows(slug, folder)
            if not rows:
                raise RuntimeError("no rows")
            missing, checked = compute_missing([(r[0], r[1]) for r in rows], folder)
            for line in warn_lines(missing, checked):
                print(f"  {line}")
            if unexpected(missing):
                warned.append(slug)
                if args.skip_missing:
                    print("  SKIPPED (--skip-missing)")
                    skipped.append(slug)
                    continue
            build(slug, rows, dest, missing)
        except Exception as exc:
            print(f"  FAILED: {exc}")
            failed.append(slug)
    if warned:
        print("\nreciters with missing ayahs/surahs:", ", ".join(warned))
    if skipped:
        print("not built (--skip-missing):", ", ".join(skipped))
    if failed:
        print("failed:", ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
