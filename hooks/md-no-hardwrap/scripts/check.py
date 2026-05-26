#!/usr/bin/env python3
"""PreToolUse hook: refuse Write/Edit/MultiEdit on .md files when prose paragraphs span >1 line.

Reads the Claude Code hook protocol JSON from stdin:

    {
      "tool_name": "Write" | "Edit" | "MultiEdit",
      "tool_input": {
        "file_path": "/abs/path/to/file.md",
        "content"  : "..."                          # Write
        "new_string": "..."                         # Edit
        "edits": [{"new_string": "..."}, ...]       # MultiEdit
        ...
      },
      ...
    }

Exit codes per the Claude Code hook contract:

    0  -> allow tool call to proceed
    2  -> block tool call; stderr is shown to the model

We only care about Write/Edit/MultiEdit targeting markdown files. For Edit /
MultiEdit the body we check is the `new_string` (per-hunk) -- a single hunk on
its own. A hunk that ends mid-sentence is fine if the surrounding file makes
the paragraph whole; we detect a violation only when the hunk itself contains
a >1-line paragraph (so the EDIT introduces the wrap). That keeps the
false-positive rate low on small in-place edits while still catching the
dominant failure mode -- a Claude reflex hardwrapping a fresh paragraph at
~72-80 chars.

Lines that are NOT prose-paragraph and therefore don't count toward the
"paragraph span" tally:

    * blank lines (separators)
    * fenced code blocks (```...``` or ~~~...~~~)
    * indented code blocks (>=4 spaces at start when not inside a list/admonition)
    * headings (^#+ )
    * list items (^[-*+] or ^\\d+\\. -- one bullet per line is fine)
    * tables (lines starting with `|` or hr-style separators)
    * blockquotes (^> )
    * admonition openers (^!!! or ^??? -- MkDocs Material syntax)
    * horizontal rules (---, ***, ___ on a line)
    * HTML block tags
    * YAML/TOML front-matter (--- ... --- or +++ ... +++ at the top)

Everything else is treated as prose: consecutive prose lines form one paragraph,
and any paragraph longer than ONE LINE is a violation. The renderer collapses
soft breaks to spaces anyway -- the hardwrap is purely a readability hazard on
narrow viewports and a friction source for diff review.

Special-case exemption: a paragraph whose every line is a badge (`[![...]...`)
or bare image (`![...]...`) row passes through unflagged. The canonical
GitHub README shields stack puts one shield per line as a column; collapsing
them would be wrong. A MIXED paragraph (some badges, some prose) is still a
violation -- that's almost always a wrapped-prose bug.
"""

from __future__ import annotations

import json
import re
import sys
from typing import NamedTuple


class Violation(NamedTuple):
    start_line: int  # 1-based, first line of the offending paragraph
    end_line: int    # 1-based, last line of the offending paragraph
    text: str        # paragraph contents joined with " | " for the error msg


# Compiled regexes for line classification. All anchored at the start of the
# (left-stripped) line because indentation is handled separately for code-block
# detection.
_RE_HEADING = re.compile(r"^#{1,6}\s")
_RE_UNORDERED_LIST = re.compile(r"^\s*[-*+]\s")
_RE_ORDERED_LIST = re.compile(r"^\s*\d+\.\s")
_RE_BLOCKQUOTE = re.compile(r"^\s*>")
_RE_TABLE_ROW = re.compile(r"^\s*\|")
# Setext underlines: ===== or ----- (treat as non-paragraph so the preceding
# title line still gets paired with its underline without triggering)
_RE_SETEXT_UNDERLINE = re.compile(r"^\s*(=+|-+)\s*$")
_RE_ADMONITION_OPENER = re.compile(r"^\s*(\?\?\?|!!!)")
_RE_HTML_BLOCK = re.compile(r"^\s*</?[a-zA-Z][^>]*>?\s*$")
_RE_HTML_COMMENT_OPEN = re.compile(r"^\s*<!--")
_RE_HTML_COMMENT_CLOSE = re.compile(r"-->\s*$")
_RE_FENCE = re.compile(r"^\s*(```|~~~)")
_RE_HR = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$")
_RE_FRONT_MATTER = re.compile(r"^\s*(---|\+\+\+)\s*$")
# Badge / image-link rows: canonical GitHub README layout puts one shield or
# image per line as a column. The lines collectively look like a "paragraph"
# (no blank lines between, no list-marker prefix), so they would otherwise
# trip the multi-line-paragraph rule. A paragraph composed ENTIRELY of these
# rows is exempted -- a single per-line shield is the conventional shape and
# collapsing them onto one line would be wrong. A MIXED paragraph (some
# badges, some prose) still triggers, because that's almost certainly a
# wrapped-prose bug rather than an intentional layout.
_RE_BADGE_ROW = re.compile(r"^\s*\[!\[")  # [![alt](img)](href)
_RE_IMAGE_ROW = re.compile(r"^\s*!\[")    # ![alt](img) without surrounding link
# Admonition CONTENT is indented under the opener. We treat 4-space-indented
# continuation lines as still inside the admonition -- they ARE prose and
# multi-line indented prose is still a hardwrap. So indent does NOT escape the
# check; we just need to recognise the opener so we don't pair an admonition
# title with the next prose line.


def is_blank(line: str) -> bool:
    return line.strip() == ""


def is_badge_or_image_row(line: str) -> bool:
    """Return True iff line is a badge (`[![…`) or bare image (`![…`) row.

    Used by the close-paragraph step to exempt a paragraph whose every line
    is one of these shapes -- canonical README badge stacks.
    """
    return bool(_RE_BADGE_ROW.match(line) or _RE_IMAGE_ROW.match(line))


def classify_non_paragraph(line: str) -> bool:
    """Return True iff this line is something that breaks paragraph continuity."""
    if _RE_HEADING.match(line):
        return True
    if _RE_UNORDERED_LIST.match(line):
        return True
    if _RE_ORDERED_LIST.match(line):
        return True
    if _RE_BLOCKQUOTE.match(line):
        return True
    if _RE_TABLE_ROW.match(line):
        return True
    if _RE_SETEXT_UNDERLINE.match(line):
        return True
    if _RE_ADMONITION_OPENER.match(line):
        return True
    if _RE_HTML_BLOCK.match(line):
        return True
    if _RE_HR.match(line):
        return True
    return False


def find_violations(content: str) -> list[Violation]:
    """Scan content; return list of multi-line prose paragraphs (1-based line numbers)."""
    violations: list[Violation] = []

    lines = content.split("\n")

    in_fence = False
    fence_marker = ""  # "```" or "~~~"
    in_html_comment = False
    in_front_matter = False
    front_matter_marker = ""

    para_start: int | None = None
    para_lines: list[str] = []

    # Detect leading front matter
    if lines and _RE_FRONT_MATTER.match(lines[0]):
        in_front_matter = True
        front_matter_marker = lines[0].strip()

    def close_paragraph(end_line_inclusive: int) -> None:
        nonlocal para_start, para_lines
        if para_start is not None and len(para_lines) > 1:
            # Exempt paragraphs whose every line is a badge / image row -- the
            # canonical README shields stack is one-per-line by convention,
            # not a hardwrap. A mixed paragraph (some badges, some prose) is
            # still a violation; that's almost always wrapped prose.
            if not all(is_badge_or_image_row(line) for line in para_lines):
                violations.append(
                    Violation(
                        start_line=para_start,
                        end_line=end_line_inclusive,
                        text=" | ".join(s.strip() for s in para_lines),
                    )
                )
        para_start = None
        para_lines = []

    for idx, raw in enumerate(lines, start=1):
        # Front-matter handling: skip until closing delimiter
        if in_front_matter and idx > 1:
            if raw.strip() == front_matter_marker:
                in_front_matter = False
            continue
        if in_front_matter:
            # First-line delimiter; nothing else to do
            continue

        # HTML-comment block handling. A `<!--` opens; `-->` closes. While
        # inside, every line is non-paragraph (multi-line HTML comments are
        # routine in docs corpora and obviously not prose).
        if in_html_comment:
            if _RE_HTML_COMMENT_CLOSE.search(raw):
                in_html_comment = False
            continue
        if _RE_HTML_COMMENT_OPEN.match(raw):
            close_paragraph(idx - 1)
            # Single-line `<!-- foo -->` closes immediately; multi-line opens.
            if not _RE_HTML_COMMENT_CLOSE.search(raw):
                in_html_comment = True
            continue

        # Fence handling next (fences are recognised regardless of indentation
        # to keep things simple; misses cases with weird nested indent but those
        # are rare in practice).
        fence_match = _RE_FENCE.match(raw)
        if fence_match:
            close_paragraph(idx - 1)
            if not in_fence:
                in_fence = True
                fence_marker = fence_match.group(1)
            else:
                # Only close on a matching marker
                if fence_marker in raw:
                    in_fence = False
                    fence_marker = ""
            continue

        if in_fence:
            # Inside code fence: everything is non-paragraph and untouched
            continue

        if is_blank(raw):
            close_paragraph(idx - 1)
            continue

        if classify_non_paragraph(raw):
            close_paragraph(idx - 1)
            continue

        # Prose line
        if para_start is None:
            para_start = idx
        para_lines.append(raw)

    # Flush trailing paragraph
    close_paragraph(len(lines))

    return violations


def truncate(text: str, limit: int = 160) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        # If we can't parse the hook payload, don't block -- let Claude proceed
        # and surface the issue elsewhere.
        return 0

    # Defensive: stdin parsed but isn't a JSON object (`null`, `42`, `[...]`,
    # `"string"`). The hook protocol always sends an object, but a corrupt or
    # mock payload shouldn't crash the script with AttributeError -- it should
    # quietly allow the tool through, same as a JSONDecodeError.
    if not isinstance(data, dict):
        return 0

    tool_name = data.get("tool_name", "")
    if tool_name not in ("Write", "Edit", "MultiEdit"):
        return 0

    tool_input = data.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return 0

    file_path = tool_input.get("file_path") or ""
    if not isinstance(file_path, str):
        return 0

    if not file_path.lower().endswith((".md", ".markdown", ".mdx", ".md.gotmpl")):
        return 0

    # Write supplies "content"; Edit supplies "new_string"; MultiEdit supplies
    # "edits" with per-hunk "new_string". All three are matched by the
    # PreToolUse matcher in hooks.json, so all three branches are live code.
    candidates: list[str] = []

    if "content" in tool_input and isinstance(tool_input["content"], str):
        candidates.append(tool_input["content"])

    if "new_string" in tool_input and isinstance(tool_input["new_string"], str):
        candidates.append(tool_input["new_string"])

    edits = tool_input.get("edits")
    if isinstance(edits, list):
        for edit in edits:
            if isinstance(edit, dict):
                ns = edit.get("new_string")
                if isinstance(ns, str):
                    candidates.append(ns)

    all_violations: list[Violation] = []

    for cand in candidates:
        all_violations.extend(find_violations(cand))

    if not all_violations:
        return 0

    # Build the block message
    lines_out: list[str] = []
    lines_out.append(
        "BLOCKED: markdown content contains a paragraph that spans more than one line."
    )
    lines_out.append(
        "CLAUDE.md rule: ONE continuous line per paragraph. The renderer wraps to viewer width."
    )
    lines_out.append("Reflow each multi-line paragraph onto a single line, then retry.")
    lines_out.append("")
    lines_out.append(f"File: {file_path}")
    lines_out.append("Offending paragraphs (line ranges relative to the supplied content):")
    for v in all_violations[:5]:
        lines_out.append(f"  - lines {v.start_line}-{v.end_line}: {truncate(v.text)}")

    if len(all_violations) > 5:
        lines_out.append(f"  - … and {len(all_violations) - 5} more")

    print("\n".join(lines_out), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
