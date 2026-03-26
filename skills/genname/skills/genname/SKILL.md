---
name: genname
description: Generate a /rename command from arguments. No git or gh calls — pure string formatting.
argument-hint: "<type> <title> [PR number]"
---

Generate a `/rename` command from arguments. No git or gh calls — pure string formatting.

## Arguments

Parse arguments for:

- **type** (required): commit type (`fix`, `feat`, `refactor`, `chore`, `ci`, `docs`, `test`, `perf`, `build`, `style`)
- **title** (required): branch-style name with dashes/underscores (e.g., `e2e-kubernetes-flaky-retry`)
- **PR number** (optional): bare number or `#N`

### Inferring from context

If arguments are not provided (or partially provided), infer them from conversation context:

- **type**: extract from branch name prefix (e.g., `feat/...` → `feat`, `fix/...` → `fix`)
- **title**: extract from branch name after the prefix (e.g., `feat/vnc-transport-abstraction` → `vnc-transport-abstraction`)
- **PR number**: extract from conversation context (PR URL, `gh pr view` output, etc.)

Never ask the user for arguments that can be inferred. If nothing can be inferred and no arguments provided, then ask.

## Formatting

1. Take the type as-is
2. Convert the title to human-readable: replace `-` and `_` with spaces, capitalize first letter only
3. If PR number provided, append `(PR #N)`

## Output

Output the rename command as a single copyable line:

```text
/rename <type>: <Title> (PR #<number>)
```

Or without PR:

```text
/rename <type>: <Title>
```

## Examples

- `/genname fix e2e-kubernetes-flaky-retry 2062` → `/rename fix: E2E kubernetes flaky retry (PR #2062)`
- `/genname feat app-harbor #2055` → `/rename feat: App harbor (PR #2055)`
- `/genname refactor e2e-helm-install` → `/rename refactor: E2E helm install`
- `/genname ci optimize-build-pipeline 100` → `/rename ci: Optimize build pipeline (PR #100)`
