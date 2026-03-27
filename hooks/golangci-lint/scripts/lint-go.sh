#!/bin/bash
INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# Only .go files
[[ -z "$FILE" || "$FILE" != *.go ]] && exit 0

# Find repo root
ROOT=$(git -C "$(dirname "$FILE")" rev-parse --show-toplevel 2>/dev/null) || exit 0

# Skip if no golangci-lint config
[[ -f "$ROOT/.golangci.yml" || -f "$ROOT/.golangci.yaml" || -f "$ROOT/.golangci.toml" || -f "$ROOT/.golangci.json" ]] || exit 0

# Lint the package containing the file, JSON output for machine-readable parsing
PKG="./$(dirname "${FILE#$ROOT/}")/..."
LINT_JSON=$(cd "$ROOT" && golangci-lint run --issues-exit-code 0 --output.json.path stdout "$PKG" 2>/dev/null)

# Extract issues only, format as "file:line:col linter: message"
ISSUES=$(echo "$LINT_JSON" | jq -r '.Issues[]? | "\(.Pos.Filename):\(.Pos.Line):\(.Pos.Column) \(.FromLinter): \(.Text)"')

if [[ -n "$ISSUES" ]]; then
  jq -n --arg issues "$ISSUES" '{
    hookSpecificOutput: {
      hookEventName: "PostToolUse",
      additionalContext: ("golangci-lint found issues:\n" + $issues)
    }
  }'
fi

exit 0
