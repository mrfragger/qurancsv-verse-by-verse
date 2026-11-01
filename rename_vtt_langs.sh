#!/usr/bin/env bash
# rename_vtt_langs.sh
# Usage: ./rename_vtt_langs.sh [directory]
# Renames files matching *.<code>.vtt to *.<Language>.vtt
# Skips files that are already named with the language name.
# At the end, reports which languages in the map had no matching file,
# grouped by section, listing the language name.

set -euo pipefail

DIR="${1:-.}"

# ---------------------------------------------------------------------------
# Section -> ordered list of "code=Language" entries
# Keep the order you want the report to appear in.
# ---------------------------------------------------------------------------
declare -A SECTIONS=(
  [Common]="en=English zh=Chinese(Simplified) zh-hant=Chinese(Traditional) es=Spanish fr=French de=German ja=Japanese ko=Korean hi=Hindi ar=Arabic ru=Russian pt-br=Portuguese(Brazil) pt-pt=Portuguese(Portugal) id=Indonesian vi=Vietnamese it=Italian yue=Cantonese"
  [Europe]="ro=Romanian el=Greek hu=Hungarian sv=Swedish cs=Czech ca=Catalan sr=Serbian bg=Bulgarian hy=Armenian da=Danish sq=Albanian fi=Finnish nb=Norwegian sk=Slovak hr=Croatian be=Belarusian scn=Sicilian ka=Georgian lmo=Lombard lt=Lithuanian gl=Galician bs=Bosnian sl=Slovenian mk=Macedonian lv=Latvian et=Estonian is=Icelandic mt=Maltese cy=Welsh ga=Irish br=Breton eu=Basque yi=Yiddish lb=Luxembourgish oc=Occitan la=Latin eo=Esperanto uk=Ukrainian pl=Polish nl=Dutch"
  [Middle_East]="tr=Turkish he=Hebrew fa=Persian ur=Urdu ps=Pashto prs=Dari ckb=Kurdish(Central) kmr=Kurdish(Northern)"
  [Central_Asia]="uz=Uzbek kk=Kazakh ky=Kyrgyz tk=Turkmen az=Azerbaijani tg=Tajik mn=Mongolian ba=Bashkir tt=Tatar ug=Uyghur"
  [South_Asia]="bn=Bengali mr=Marathi te=Telugu ta=Tamil gu=Gujarati kn=Kannada pa=Punjabi ml=Malayalam bho=Bhojpuri mai=Maithili ne=Nepali si=Sinhala as=Assamese gom=Konkani sa=Sanskrit"
  [Southeast_Asia]="th=Thai lo=Lao my=Burmese km=Khmer ms=Malay fil=Filipino jv=Javanese su=Sundanese ace=Acehnese pag=Pangasinan pam=Kapampangan ceb=Cebuano"
  [Africa]="sw=Swahili ha=Hausa am=Amharic ig=Igbo wo=Wolof xh=Xhosa zu=Zulu af=Afrikaans om=Oromo st=Southern_Sotho tn=Tswana ts=Tsonga mg=Malagasy ln=Lingala"
  [Americas_Oceania]="ht=Haitian_Creole qu=Quechua ay=Aymara gn=Guarani mi=Maori"
)

# Fixed display order for sections
SECTION_ORDER=(Common Europe Middle_East Central_Asia South_Asia Southeast_Asia Africa Americas_Oceania)

# Human-readable section labels
declare -A SECTION_LABEL=(
  [Common]="Common"
  [Europe]="Europe"
  [Middle_East]="Middle East"
  [Central_Asia]="Central Asia"
  [South_Asia]="South Asia"
  [Southeast_Asia]="Southeast Asia"
  [Africa]="Africa"
  [Americas_Oceania]="Americas & Oceania"
)

# ---------------------------------------------------------------------------
# Expand sections into:
#   LANGS[code]       = Language name
#   CODE_SECTION[code]= section key
#   SECTION_CODES[section] = ordered list of codes in that section
# (Names with spaces were stored using underscores in the map above;
#  we convert them back here.)
# ---------------------------------------------------------------------------
declare -A LANGS=()
declare -A CODE_SECTION=()
declare -A SECTION_CODES=()

for section in "${SECTION_ORDER[@]}"; do
  read -r -a entries <<< "${SECTIONS[$section]}"
  codes_for_section=()
  for entry in "${entries[@]}"; do
    code="${entry%%=*}"
    name="${entry#*=}"
    name="${name//_/ }"          # underscores -> spaces
    LANGS["$code"]="$name"
    CODE_SECTION["$code"]="$section"
    codes_for_section+=("$code")
  done
  SECTION_CODES["$section"]="$(printf '%s\n' "${codes_for_section[@]}")"
done

# Build a lookup set of all language *names* (to skip already-renamed files)
declare -A NAMES_SET=()
for name in "${LANGS[@]}"; do
  NAMES_SET["$name"]=1
done

# Track which codes we saw so we can report which we didn't
declare -A SEEN=()

# ---------------------------------------------------------------------------
# Process files
# ---------------------------------------------------------------------------
shopt -s nullglob nocaseglob
count=0
skipped=0
unknown=0

for f in "$DIR"/*.vtt; do
  base="${f%.vtt}"
  ext="${f##*.}"

  prefix="${base%.*}"
  code="${base##*.}"

  # Already renamed to a language name? Skip.
  if [[ -n "${NAMES_SET[$code]:-}" ]]; then
    ((skipped++)) || true
    continue
  fi

  # Look up (case-insensitive) the language name for this code
  key=$(printf '%s' "$code" | tr '[:upper:]' '[:lower:]')
  lang="${LANGS[$key]:-}"

  if [[ -z "$lang" ]]; then
    echo "WARN: unknown code '$code' in: $f" >&2
    ((unknown++)) || true
    continue
  fi

  SEEN["$key"]=1

  newfile="${prefix}.${lang}.${ext}"
  if [[ -e "$newfile" ]]; then
    echo "SKIP: target exists: $newfile" >&2
    continue
  fi

  echo "RENAME: $(basename "$f") -> $(basename "$newfile")"
  mv -v -- "$f" "$newfile"
  ((count++)) || true
done

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo
echo "Done. Renamed: $count  |  Already-renamed skipped: $skipped  |  Unknown codes: $unknown"

# ---------------------------------------------------------------------------
# Missing report, grouped by section, listing language names
# ---------------------------------------------------------------------------
total_missing=0
declare -A MISSING_BY_SECTION=()

for section in "${SECTION_ORDER[@]}"; do
  mapfile -t codes < <(printf '%s\n' "${SECTION_CODES[$section]}")
  section_missing=()
  for code in "${codes[@]}"; do
    if [[ -z "${SEEN[$code]:-}" ]]; then
      section_missing+=("${LANGS[$code]}")
    fi
  done
  if (( ${#section_missing[@]} > 0 )); then
    MISSING_BY_SECTION["$section"]="$(printf '%s\n' "${section_missing[@]}")"
    (( total_missing += ${#section_missing[@]} )) || true
  fi
done

echo
if (( total_missing == 0 )); then
  echo "Not found: 0 — every language in the map had a matching file."
else
  echo "Not found (no file for these languages): $total_missing"
  for section in "${SECTION_ORDER[@]}"; do
    if [[ -z "${MISSING_BY_SECTION[$section]:-}" ]]; then
      continue
    fi
    echo
    echo "  ${SECTION_LABEL[$section]}:"
    mapfile -t names < <(printf '%s\n' "${MISSING_BY_SECTION[$section]}")
    for name in "${names[@]}"; do
      echo "    - $name"
    done
  done
fi
