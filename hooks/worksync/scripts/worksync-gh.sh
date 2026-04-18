#!/usr/bin/env bash
# PostToolUse hook: detect GitHub-facing gh commands and append them to
# today's work-sync note via the companion worksync-append.sh helper.
#
# Matches:
#   gh pr create      → type=pr,     msg = "<title> — <url>"
#   gh issue create   → type=issue,  msg = "<title> — <url>"
#   gh pr merge       → type=merge,  msg = "<pr url>"
#   gh issue close    → type=issue,  msg = "closed: <issue ref>"
#
# Silent on unrelated commands. Never blocks the tool call.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APPEND="$HERE/worksync-append.sh"
[[ -x "$APPEND" ]] || exit 0

INPUT="$(cat)"

TOOL_NAME="$(jq --raw-output '.tool_name // empty' <<<"$INPUT")"
[[ "$TOOL_NAME" == "Bash" ]] || exit 0

CMD="$(jq --raw-output '.tool_input.command // empty' <<<"$INPUT")"
STDOUT="$(jq --raw-output '.tool_response.stdout // .tool_response.output // empty' <<<"$INPUT")"
STDERR="$(jq --raw-output '.tool_response.stderr // empty' <<<"$INPUT")"

# Combine stdout+stderr; gh prints PR/issue URLs to stdout normally, but
# some flows go through stderr (e.g. "Creating pull request for ...").
OUTPUT="${STDOUT}"$'\n'"${STDERR}"

# Extract the first github.com URL from output (PR or issue).
URL="$(grep --extended-regexp --only-matching --max-count=1 \
    'https://github\.com/[^[:space:]]+/(pull|issues)/[0-9]+' \
    <<<"$OUTPUT" || true)"

extract_title() {
    # Pull --title/-t value out of the command line, tolerating single or
    # double quotes. Falls back to empty string.
    local c="$1"
    local t
    t="$(grep --extended-regexp --only-matching --max-count=1 \
        -- "--title[= ]\"[^\"]+\"|--title[= ]'[^']+'|--title[= ][^[:space:]]+" \
        <<<"$c" | sed -E "s/^--title[= ]//; s/^['\"]//; s/['\"]\$//" || true)"
    printf '%s' "$t"
}

dispatch() {
    local type="$1" msg="$2"
    [[ -n "$msg" ]] || return 0
    "$APPEND" "$type" "$msg" || true
}

case "$CMD" in
    *"gh pr create"*)
        TITLE="$(extract_title "$CMD")"
        if [[ -n "$TITLE" && -n "$URL" ]]; then
            dispatch pr "$TITLE — $URL"
        elif [[ -n "$URL" ]]; then
            dispatch pr "$URL"
        fi
        ;;
    *"gh issue create"*)
        TITLE="$(extract_title "$CMD")"
        if [[ -n "$TITLE" && -n "$URL" ]]; then
            dispatch issue "$TITLE — $URL"
        elif [[ -n "$URL" ]]; then
            dispatch issue "$URL"
        fi
        ;;
    *"gh pr merge"*)
        if [[ -n "$URL" ]]; then
            dispatch merge "$URL"
        else
            REF="$(grep --extended-regexp --only-matching --max-count=1 \
                -- 'gh pr merge[[:space:]]+[^[:space:]]+' <<<"$CMD" \
                | awk '{print $NF}' || true)"
            [[ -n "$REF" ]] && dispatch merge "$REF"
        fi
        ;;
    *"gh issue close"*)
        REF="$(grep --extended-regexp --only-matching --max-count=1 \
            -- 'gh issue close[[:space:]]+[^[:space:]]+' <<<"$CMD" \
            | awk '{print $NF}' || true)"
        [[ -n "$REF" ]] && dispatch issue "closed: $REF"
        ;;
esac

exit 0
