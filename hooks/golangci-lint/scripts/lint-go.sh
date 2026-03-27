#!/bin/bash
FILE=$(cat | jq -r '.tool_input.file_path // empty')

# Only .go files
[[ -z "$FILE" || "$FILE" != *.go ]] && exit 0

# Find repo root
ROOT=$(git -C "$(dirname "$FILE")" rev-parse --show-toplevel 2>/dev/null) || exit 0

# Skip if no golangci-lint config
[[ -f "$ROOT/.golangci.yml" || -f "$ROOT/.golangci.yaml" || -f "$ROOT/.golangci.toml" || -f "$ROOT/.golangci.json" ]] || exit 0

# Lint the package containing the file
PKG="./$(dirname "${FILE#$ROOT/}")/..."
cd "$ROOT" && golangci-lint run "$PKG" 2>&1
