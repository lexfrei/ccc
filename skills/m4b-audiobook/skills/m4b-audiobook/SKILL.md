---
name: m4b-audiobook
description: Assemble m4b audiobook from audio files with chapters, metadata, and cover art.
argument-hint: "[directory]"
allowed-tools: Bash, Read, Glob, Grep, Write, AskUserQuestion
---

Assemble a single `.m4b` audiobook from a directory of audio files. Adds chapter markers, metadata, and cover art.

## Prerequisites

- `ffmpeg` and `ffprobe` must be installed

## Arguments

- `directory` — path to the directory with audio files. If omitted, use the current working directory.

## Process

### 1. Inventory

List all audio files in the directory. Supported formats: `.m4a`, `.mp3`, `.aac`, `.ogg`, `.opus`, `.flac`, `.wav`.

Also look for a cover image: `.jpg`, `.jpeg`, `.png` files with names suggesting cover art (e.g., `cover`, `folder`, `front`, or any single image file present).

### 2. Determine file order

Analyze filenames to determine the correct playback order. Common patterns:

- Numeric prefixes: `01 - Title.m4a`, `1.1. Title.m4a`
- Chapter/part indicators: `Chapter 1`, `Part 1`, `Глава 1`, `Часть 1`
- Structured names: `Week 1. 1.1. Title`, `Неделя 1. 1.1. Title`

Sort rules:

- Group by logical sections (introduction, parts/chapters/weeks, ending/epilogue)
- Within each group, sort by numeric indicators
- Files without clear numbering: sort alphabetically within their group

Present the proposed order to the user. Ask for confirmation before proceeding.

### 3. Determine metadata

Try to extract metadata from:

- Directory name
- Existing tags in audio files (`ffprobe` output)
- File naming patterns

Required metadata fields:

- **title** — book title
- **artist** / **album_artist** — author name
- **album** — same as title (convention for audiobooks)
- **genre** — set to `Audiobook`
- **date** — year if determinable from file metadata
- **language** — detected from content/filenames (e.g., `rus`, `eng`)

Present proposed metadata to user. Ask for confirmation or corrections.

### 4. Probe audio formats

Run `ffprobe` on each file to determine:

- Codec (aac, mp3, flac, etc.)
- Sample rate
- Channels
- Bitrate

If all files share the same codec and parameters: use `-c:a copy` (no re-encoding — fast and lossless).

If formats differ: re-encode to AAC-LC. Choose parameters:

- Sample rate: use the most common value across files
- Bitrate: `64k` for mono, `128k` for stereo (or match source if higher)
- Channels: preserve original (mono/stereo)

### 5. Generate chapter names

Create clean chapter titles from filenames:

- Strip file extensions
- Strip leading numeric prefixes (e.g., `01 - `, `1.1. `)
- Keep meaningful structure (e.g., `Неделя 1.` prefix for week-based books)
- Fix obvious truncation from long filenames (e.g., `Задани` → `Задания` if context is clear)
- Use em-dash `—` instead of hyphen `-` in Russian text where appropriate

### 6. Build concat list

Create `filelist.txt` for ffmpeg concat demuxer:

```text
file '/path/to/first file.m4a'
file '/path/to/second file.m4a'
```

Escape single quotes in filenames: replace `'` with `'\''`.

### 7. Build chapter metadata

Get exact duration of each file in milliseconds:

```bash
ffprobe -v quiet -show_entries format=duration -of csv=p=0 "file.m4a"
```

Generate `chapters.txt` in FFMETADATA1 format:

```text
;FFMETADATA1
title=Book Title
artist=Author Name
album=Book Title
album_artist=Author Name
genre=Audiobook
date=2024
language=eng

[CHAPTER]
TIMEBASE=1/1000
START=0
END=473590
title=Chapter Title

[CHAPTER]
TIMEBASE=1/1000
START=473590
END=960000
title=Next Chapter
```

Each chapter START equals the previous chapter END. Calculate from cumulative durations.

### 8. Assemble m4b

Run ffmpeg:

```bash
ffmpeg -y \
  -f concat -safe 0 -i filelist.txt \
  -i chapters.txt \
  -i cover.jpg \
  -map 0:a -map 2:v \
  -c:a copy \
  -c:v copy \
  -disposition:v:0 attached_pic \
  -map_metadata 1 \
  -map_chapters 1 \
  -movflags +faststart \
  "Author - Title.m4b"
```

Adjust flags:

- If re-encoding needed: replace `-c:a copy` with `-c:a aac -b:a 128k` (or appropriate bitrate)
- If no cover image: remove `-i cover.jpg`, `-map 2:v`, `-c:v copy`, `-disposition:v:0 attached_pic`
- Output filename: `Author - Title.m4b` (from metadata)

### 9. Verify

After assembly, verify the output:

```bash
ffprobe -v quiet -show_format -show_chapters output.m4b
```

Confirm:

- All chapters present with correct titles
- Metadata fields populated
- Cover art stream present (if provided)
- Total duration matches sum of source files

Report results to user: filename, size, duration, chapter count.

### 10. Cleanup

Remove temporary files (`filelist.txt`, `chapters.txt`).

## Error handling

- If `ffmpeg` is not installed: suggest `brew install ffmpeg`
- If no audio files found: report and stop
- If ffmpeg fails: show the error output, suggest possible fixes
- If concat produces audio glitches (different sample rates): fall back to re-encoding
