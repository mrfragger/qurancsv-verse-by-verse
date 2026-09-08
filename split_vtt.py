#!/usr/bin/env python3
"""
Split long VTT subtitle cues into segments of at most MAX_CHARS characters each.

Usage:
    python split_vtt.py input.vtt [output.vtt] [--max-chars 80]
    python split_vtt.py *.vtt --max-chars 80   # processes all .vtt files in current dir

The script parses each cue, joins multi‑line text with a space, and if the total
length exceeds MAX_CHARS, it splits the text into roughly equal parts using word
boundaries. Timestamps are adjusted proportionally to the original cue duration.
For languages without spaces (e.g., Chinese), splitting is done by characters.

Requires Python 3.6+.
"""

import argparse
import glob
import os
import re
import sys

# ----------------------------------------------------------------------
# Utility functions for VTT parsing & timestamp handling
# ----------------------------------------------------------------------

def parse_timestamp_ms(ts: str) -> int:
    """Convert VTT timestamp 'HH:MM:SS.mmm' to milliseconds."""
    ts = ts.strip()
    parts = ts.split(":")
    h = int(parts[0])
    m = int(parts[1])
    s_parts = parts[2].split(".")
    s = int(s_parts[0])
    ms = int(s_parts[1])
    return h * 3600000 + m * 60000 + s * 1000 + ms


def format_timestamp_ms(ms: int) -> str:
    """Convert milliseconds to VTT timestamp 'HH:MM:SS.mmm'."""
    h = ms // 3600000
    ms %= 3600000
    m = ms // 60000
    ms %= 60000
    s = ms // 1000
    ms %= 1000
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def parse_vtt_blocks(vtt_path: str):
    """
    Parse a VTT file and return (header_lines, blocks).
    blocks is a list of tuples: (timecode_line, list_of_text_lines).
    """
    with open(vtt_path, "r", encoding="utf-8") as f:
        content = f.read()
    lines = content.split("\n")
    header_lines = []
    i = 0
    timecode_re = re.compile(
        r"^\d{2}:\d{2}:\d{2}\.\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}\.\d{3}"
    )
    # Skip header (everything before first timecode)
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
            # Should not happen, but skip malformed lines
            i += 1
    return header_lines, blocks


def build_vtt(header_lines: list, blocks: list) -> str:
    """Reconstruct VTT content from header and blocks."""
    parts = []
    parts.extend(header_lines)
    if header_lines and header_lines[-1].strip() != "":
        parts.append("")
    for timecode, text_lines in blocks:
        parts.append(timecode)
        parts.extend(text_lines)
        parts.append("")  # blank line after each cue
    return "\n".join(parts)


def find_word_boundary(text: str, target_pos: int, search_radius: int = 50) -> int:
    """
    Find the nearest space to target_pos within search_radius characters.
    If no space found, return target_pos unchanged.
    """
    # Search forward first, then backward
    for offset in range(search_radius):
        pos = target_pos + offset
        if pos < len(text) and text[pos] == " ":
            return pos
        pos = target_pos - offset
        if pos >= 0 and text[pos] == " ":
            return pos
    return target_pos


def split_long_cue(text: str, max_chars: int) -> list:
    """
    Split a single text string into a list of segments, each <= max_chars.
    Uses word boundaries when possible; falls back to character splits if
    a single word is longer than max_chars.
    """
    text = text.strip()
    if len(text) <= max_chars:
        return [text]

    # Determine number of parts needed (at least 2)
    num_parts = (len(text) + max_chars - 1) // max_chars  # ceil division

    # If there are no spaces (e.g., CJK), just split by character count
    if " " not in text:
        # Split into roughly equal character chunks
        chunk_size = (len(text) + num_parts - 1) // num_parts
        parts = [text[i:i+chunk_size].strip() for i in range(0, len(text), chunk_size)]
        # Remove empty parts (if any)
        parts = [p for p in parts if p]
        # Ensure we have exactly num_parts, pad with empty if needed
        while len(parts) < num_parts:
            parts.append("")
        return parts

    # Use word boundary splitting
    boundaries = [0]
    for k in range(1, num_parts):
        target = len(text) * k // num_parts
        boundary = find_word_boundary(text, target)
        # Make sure boundary is after previous one and not at the end
        if boundary > boundaries[-1] and boundary < len(text):
            boundaries.append(boundary)
    boundaries.append(len(text))

    # Build parts from boundaries
    parts = []
    for i in range(len(boundaries) - 1):
        part = text[boundaries[i]:boundaries[i+1]].strip()
        if part:
            parts.append(part)

    # If any part still exceeds max_chars (due to long words), split those parts
    # by character as a last resort.
    final_parts = []
    for part in parts:
        if len(part) > max_chars:
            # Split mid‑word
            sub_parts = split_long_cue(part, max_chars)  # recursive, but part has no spaces, so char split
            final_parts.extend(sub_parts)
        else:
            final_parts.append(part)

    # Ensure we have at most num_parts (could be fewer if boundaries collapsed)
    # If more, we might need to merge? But unlikely; we'll just return as is.
    return final_parts


def split_vtt_file(input_path: str, output_path: str, max_chars: int = 80) -> int:
    """
    Process a VTT file: split long cues and write result to output_path.
    Returns the number of cues that were split.
    """
    header_lines, blocks = parse_vtt_blocks(input_path)
    new_blocks = []
    split_count = 0

    for timecode, text_lines in blocks:
        # Join lines with a space (VTT may have line breaks within a cue)
        original_text = " ".join(t.strip() for t in text_lines)

        if len(original_text) <= max_chars:
            # No split needed
            new_blocks.append((timecode, text_lines))
            continue

        # Parse start/end times
        parts = timecode.split("-->")
        start_ms = parse_timestamp_ms(parts[0])
        end_ms = parse_timestamp_ms(parts[1])
        duration = end_ms - start_ms

        # Split text into parts
        text_parts = split_long_cue(original_text, max_chars)
        num_parts = len(text_parts)

        if num_parts == 1:
            # Could happen if after stripping the text shrank? unlikely
            new_blocks.append((timecode, text_lines))
            continue

        split_count += 1

        # Create new blocks with proportional timing
        for idx, part in enumerate(text_parts):
            t_start = start_ms + duration * idx // num_parts
            t_end = start_ms + duration * (idx + 1) // num_parts
            new_timecode = f"{format_timestamp_ms(t_start)} --> {format_timestamp_ms(t_end)}"
            # Each part becomes a single‑line cue (but could preserve line breaks?)
            new_blocks.append((new_timecode, [part]))

    # Write output
    content = build_vtt(header_lines, new_blocks)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    return split_count


def main():
    parser = argparse.ArgumentParser(
        description="Split long VTT subtitle cues into segments of at most MAX_CHARS characters."
    )
    parser.add_argument(
        "input",
        nargs="+",
        help="Input VTT file(s). Accepts wildcards (e.g., *.vtt).",
    )
    parser.add_argument(
        "-o", "--output",
        help="Output file or directory. If not given, each input file gets a '.split' suffix.",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=80,
        help="Maximum characters per cue (default: 80).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite the original file instead of creating a new one.",
    )
    args = parser.parse_args()

    # Expand wildcards if any
    input_files = []
    for pattern in args.input:
        input_files.extend(glob.glob(pattern))
    if not input_files:
        print("No input files found.")
        sys.exit(1)

    # Determine output mode
    if args.overwrite:
        # Overwrite original files
        output_mode = "overwrite"
        print("Mode: overwrite original files")
    elif args.output and os.path.isdir(args.output):
        # Output directory specified
        os.makedirs(args.output, exist_ok=True)
        output_mode = "directory"
        out_dir = args.output
        print(f"Mode: output to directory '{out_dir}'")
    else:
        # Suffix mode: input.split.vtt
        output_mode = "suffix"
        print("Mode: create .split.vtt files")

    # Process each file
    total_split = 0
    for input_path in input_files:
        if not os.path.isfile(input_path):
            print(f"Warning: {input_path} is not a file, skipping.")
            continue

        if output_mode == "overwrite":
            output_path = input_path
        elif output_mode == "directory":
            base = os.path.basename(input_path)
            output_path = os.path.join(out_dir, base)
        else:  # suffix
            dir_name = os.path.dirname(input_path)
            base = os.path.basename(input_path)
            name, ext = os.path.splitext(base)
            output_path = os.path.join(dir_name, f"{name}.split{ext}")

        print(f"Processing: {input_path} → {output_path}")
        try:
            split_count = split_vtt_file(input_path, output_path, args.max_chars)
            total_split += split_count
            print(f"  Split {split_count} long cue(s).")
        except Exception as e:
            print(f"  ERROR: {e}")

    print(f"\nDone. Total cues split across all files: {total_split}")


if __name__ == "__main__":
    main()
