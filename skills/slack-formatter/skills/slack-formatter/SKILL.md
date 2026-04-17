---
name: slack-formatter
description: Copy markdown text to macOS clipboard as rich HTML + plain-text fallback, ready for Cmd+V into Slack with formatting (bold, lists, code blocks, headings) preserved. Use when the user asks to prepare, format, copy, or paste text for Slack, or when a drafted message with markdown formatting needs to go into Slack without losing structure.
argument-hint: "[path-to-markdown-file]"
allowed-tools: Bash, Write, Read
---

Convert markdown to rich text and place it in the macOS clipboard so the user can `Cmd+V` it into Slack with formatting preserved.

## When to invoke this skill

Trigger automatically when the user:

- asks to prepare/format text for Slack (any language: "для Slack", "paste to Slack", "send to Slack", "для слака", "put into pbcopy for Slack")
- has a drafted reply in markdown in the conversation and wants it copied to the clipboard for pasting somewhere that supports rich text
- explicitly asks to "put into pbcopy with formatting" / "copy as rich text"

Do **not** invoke when the user asks for plain text only (`tldrpr` already covers that case).

## Input resolution

Parse `$ARGUMENTS`:

1. If a file path is passed — use that file.
2. Otherwise — use the most recent drafted markdown content from the conversation context (a reply, message, summary). Write it to a temp file first:

   ```bash
   TMPFILE=$(mktemp -t slackfmt).md
   # write conversation-drafted markdown here via Write tool
   ```

If no draft is available and no path given — ask the user what text to format.

## Execution

Require `pandoc` (install via Homebrew if missing: `brew install pandoc`). Swift is already shipped with macOS.

Run this block, substituting `$MDFILE` with the resolved input path:

```bash
MDFILE="${1:?markdown file required}"
HTMLFILE="${MDFILE%.md}.html"

command -v pandoc >/dev/null || { echo "pandoc not found — brew install pandoc" >&2; exit 1; }

pandoc -f gfm -t html "$MDFILE" -o "$HTMLFILE" || exit 1

SWIFT_SCRIPT=$(mktemp -t slackfmt).swift
cat > "$SWIFT_SCRIPT" <<'SWIFT'
import AppKit
import Foundation

guard CommandLine.arguments.count >= 3 else {
    FileHandle.standardError.write("usage: pbcopy_html <htmlfile> <plainfile>\n".data(using: .utf8)!)
    exit(2)
}

guard let html = try? String(contentsOfFile: CommandLine.arguments[1], encoding: .utf8),
      let plain = try? String(contentsOfFile: CommandLine.arguments[2], encoding: .utf8) else {
    FileHandle.standardError.write("cannot read input files\n".data(using: .utf8)!)
    exit(1)
}

let pb = NSPasteboard.general
pb.clearContents()
pb.setString(html, forType: .html)
pb.setString(plain, forType: .string)
print("OK: html=\(html.count) bytes, plain=\(plain.count) bytes")
SWIFT

swift "$SWIFT_SCRIPT" "$HTMLFILE" "$MDFILE"
rm -f "$SWIFT_SCRIPT" "$HTMLFILE"
```

## Output

After successful copy, confirm to the user with:

- byte sizes reported by the Swift script
- one-line reminder: **"Paste in Slack with `Cmd+V` — do NOT use `Cmd+Shift+V` (that pastes plain text and drops formatting)."**

## Notes

- `pbpaste` will only show the plain-text fallback — this is normal. The HTML part is in the clipboard under `«class HTML»`, which is what Slack reads.
- Verify with `osascript -e 'clipboard info'` if the user reports pasting issues. Expected output includes both `«class HTML»` and `«class utf8»`.
- Slack normalizes HTML on paste: `##` headings become bold text, nested lists flatten in predictable ways, fenced code blocks keep monospace font, tables become tab-separated plain text.
- GFM input flavor (`-f gfm`) handles GitHub-style fenced code blocks with language hints and task lists correctly.
