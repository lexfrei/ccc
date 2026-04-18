#!/usr/bin/env bash
# Append an entry to today's work-sync note.
#
# Usage:
#   worksync-append.sh <type> <message>
#
# <type>: one of pr | issue | merge | research | ops | checkpoint | note
# <message>: free-form text, may contain markdown
#
# Output file: ${WORKSYNC_VAULT_DIR}/YYYY-MM-DD.md (default: ~/worksync/YYYY-MM-DD.md).
# Point WORKSYNC_VAULT_DIR at your Obsidian vault subdirectory, iCloud path,
# or anywhere else.
#
# Designed to be called from:
#   - PostToolUse hooks (deterministic events: PR/issue create/merge/close)
#   - the worksync skill (Claude-driven checkpoints, research, ops events)

set -euo pipefail

# Precedence: shell/settings.json override > plugin userConfig > default.
VAULT_DIR="${WORKSYNC_VAULT_DIR:-${CLAUDE_PLUGIN_OPTION_VAULT_DIR:-$HOME/worksync}}"
# Expand leading tilde — userConfig values arrive as literal strings, so a
# tilde-prefixed path would otherwise create a directory named literally ~.
VAULT_DIR="${VAULT_DIR/#\~/$HOME}"

TYPE="${1:?type required (pr|issue|merge|research|ops|checkpoint|note)}"
MSG="${2:?message required}"

mkdir -p "$VAULT_DIR"

DATE="$(date +%Y-%m-%d)"
TIME="$(date +%H:%M)"
FILE="$VAULT_DIR/$DATE.md"

if [[ ! -f "$FILE" ]]; then
    {
        echo "# Work sync — $DATE"
        echo ""
        echo "## Log"
        echo ""
    } > "$FILE"
fi

# Dedup guard #1: exact (type + message) already logged today.
if grep --fixed-strings --quiet "**$TYPE** — $MSG" "$FILE"; then
    exit 0
fi

# Dedup guard #2: any github.com URL (PR/issue) in the message that
# already appears in the day file, regardless of type. Catches the case
# where the hook logs `pr` and the skill later tries to log the same PR
# as `note` or `research`.
URLS="$(grep --extended-regexp --only-matching \
    'https://github\.com/[^[:space:]]+/(pull|issues)/[0-9]+' \
    <<<"$MSG" || true)"
if [[ -n "$URLS" ]]; then
    while IFS= read -r u; do
        [[ -z "$u" ]] && continue
        if grep --fixed-strings --quiet "$u" "$FILE"; then
            exit 0
        fi
    done <<<"$URLS"
fi

printf -- '- `%s` **%s** — %s\n' "$TIME" "$TYPE" "$MSG" >> "$FILE"
