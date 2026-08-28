#!/bin/bash
# duration_report.sh — total audio duration per subdirectory

parent="${1:-.}"

for dir in "$parent"/*/; do
  dirname=$(basename "$dir")
  total_seconds=0

  while IFS= read -r -d '' file; do
    dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$file" 2>/dev/null)
    if [[ -n "$dur" ]]; then
      total_seconds=$(echo "$total_seconds + $dur" | bc)
    fi
  done < <(find "$dir" -type f \( -iname "*.opus" -o -iname "*.mp3" -o -iname "*.m4a" -o -iname "*.flac" \) -print0)

  hours=$(echo "$total_seconds / 3600" | bc)
  minutes=$(echo "($total_seconds % 3600) / 60" | bc)
  seconds=$(echo "$total_seconds % 60" | bc | cut -d. -f1)

  printf "%-55s %02dh %02dm %02ds\n" "$dirname" "$hours" "$minutes" "$seconds"
done
