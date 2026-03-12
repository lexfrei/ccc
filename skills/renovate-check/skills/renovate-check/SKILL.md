---
name: renovate-check
description: Run Renovate locally in dry-run mode to get a list of available dependency updates for the current working directory, then offer to apply them
disable-model-invocation: true
allowed-tools: Bash, Read, Glob, Grep, Edit, Write, AskUserQuestion, WebSearch, WebFetch
---

# Renovate Dependency Update Checker

Run Renovate in `--platform=local` mode to discover available dependency updates by analyzing the **local** files in the current working directory. No PRs or branches are created. The `--platform=local` mode automatically implies `dryRun=lookup`.

## Execution Steps

### 1. Detect existing Renovate configuration

Before running Renovate, check if the project has a Renovate config file. Search these standard locations (in order):

- `renovate.json`
- `renovate.json5`
- `.renovaterc`
- `.renovaterc.json`
- `.github/renovate.json`
- `.github/renovate.json5`

Also check if `package.json` exists and contains a `"renovate"` key.

If a config file is found:
- Use `--require-config=optional` so Renovate reads it but does not fail if it's missing
- Do NOT pass `--require-config=ignored` — this would skip the config entirely

If NO config file is found:
- Use `--require-config=ignored` as fallback

### 2. Run Renovate against local files

Use npx to run Renovate in local platform mode. This analyzes the current directory without cloning anything from GitHub.

A `GITHUB_COM_TOKEN` is still needed for changelog lookups and to avoid rate limiting against package registries.

**When config exists:**

```bash
GITHUB_COM_TOKEN="$(gh auth token)" \
RENOVATE_LOG_FILE=/tmp/renovate-output.ndjson \
RENOVATE_LOG_FILE_LEVEL=debug \
LOG_LEVEL=info \
npx --yes --package renovate -- renovate \
  --platform=local \
  --onboarding=false \
  --require-config=optional
```

**When no config exists:**

```bash
GITHUB_COM_TOKEN="$(gh auth token)" \
RENOVATE_LOG_FILE=/tmp/renovate-output.ndjson \
RENOVATE_LOG_FILE_LEVEL=debug \
LOG_LEVEL=info \
npx --yes --package renovate -- renovate \
  --platform=local \
  --onboarding=false \
  --require-config=ignored
```

Run this command from the project's working directory (use `cd` if needed).

IMPORTANT: Always use full flag names (e.g. `--yes`, `--package`). Never use short flags.

### 3. Extract updates from the log

After Renovate finishes, parse the NDJSON log file with `jq` to extract a clean list of available updates:

```bash
jq --raw-output '
  select(.msg == "packageFiles with updates") |
  .config | to_entries[] |
  .key as $manager |
  .value[] |
  .packageFile as $file |
  .deps[]? |
  select(.updates | length > 0) |
  "\($manager) | \($file) | \(.depName) | \(.currentValue // .currentDigest // "n/a") -> \(.updates[0].newVersion // .updates[0].newValue // .updates[0].newDigest // "n/a") (\(.updates[0].updateType))"
' /tmp/renovate-output.ndjson
```

### 4. Present results

Format the extracted updates as a clear, readable markdown table for the user:

| Manager | File | Dependency | Current | Available | Type |
| --- | --- | --- | --- | --- | --- |

Group by manager for readability. If no updates are found, report that all dependencies are up to date and skip to clean up (step 8).

### 5. Research migration guides for major updates

If ANY of the found updates have `updateType` equal to `major`, research migration guides for each one **before** asking the user what to apply.

For each major update:

1. Use WebSearch to search for a migration guide. Use queries like:
   - `"<depName>" migrate v<currentMajor> to v<newMajor>`
   - `"<depName>" upgrade guide v<newMajor>`
   - `"<depName>" breaking changes v<newMajor>`
   - For GitHub Actions: `"<depName>" v<newMajor> changelog`
   - For Helm charts: `"<chartName>" changelog v<newVersion>`

2. If a migration guide / changelog / upgrade guide is found, use WebFetch to read it and extract a concise summary of breaking changes.

3. Present the migration summary to the user alongside the updates table. Format:

```
### Major update: <depName> <currentVersion> -> <newVersion>

**Breaking changes:**
- <bullet point summary of key breaking changes>
- ...

**Migration guide:** <URL>
```

If no migration guide is found, note that explicitly: "No migration guide found for <depName> v<currentVersion> -> v<newVersion>. Review the release notes manually before upgrading."

This step is critical — major version bumps can break builds and deployments. The user needs this information to make an informed decision.

### 6. Ask user which updates to apply

If major updates were found, present the migration summaries first, then ask.

Use AskUserQuestion to ask the user which updates they want to apply. Offer these options:

- "All updates" — apply everything found
- "Only patch/minor" — skip major version bumps (potentially breaking)
- "Pick specific" — let the user specify which ones
- (The user can also decline via "Other")

### 7. Apply selected updates

For each update the user approved, apply changes using the appropriate method for the manager type:

#### gomod (Go modules)

```bash
go get dependency@vX.Y.Z
```

After all `go get` commands, run:

```bash
go mod tidy
```

#### github-actions (GitHub Actions)

Edit the workflow YAML files directly — replace the old version tag with the new one in `uses:` lines. Use the Edit tool for this.

#### dockerfile / containerfile

Edit the Containerfile/Dockerfile directly — replace the old image tag with the new one. Use the Edit tool.

#### helm-values (Helm)

Edit the `values.yaml` file directly — replace the old image tag/version with the new one. Use the Edit tool.

#### argocd (ArgoCD Application manifests)

Edit the ArgoCD Application YAML files directly — replace the old `targetRevision` value with the new version. Use the Edit tool.

#### npm / pip / cargo / other managers

Use the native package manager CLI to update (e.g. `npm install package@version`, `pip install package==version`, `cargo update --package name`).

After applying updates:

- Run project linters if available (e.g. `golangci-lint run` for Go projects)
- Run tests if available (e.g. `go test ./...` for Go projects)
- Report results to the user

Do NOT commit changes automatically — leave that to the user.

### 8. Clean up

Remove the temporary log file after parsing:

```bash
rm -f /tmp/renovate-output.ndjson
```

## Notes

- `--platform=local` analyzes the LOCAL files in the current directory, not the remote repository
- `--platform=local` automatically sets `dryRun=lookup` — do NOT pass `--dry-run` separately
- `--onboarding=false` is REQUIRED — without it Renovate crashes trying to create an onboarding branch in local mode
- Renovate config detection is critical: the `argocd` manager has NO default fileMatch pattern and requires explicit configuration in the project's renovate.json (e.g. `"argocd": {"fileMatch": ["argocd/.+\\.yaml$"]}`)
- `GITHUB_COM_TOKEN` is needed even locally for changelog lookups and registry rate limits
- `gh auth token` provides the token from GitHub CLI
- macOS `rm` does not support `--force`, use `-f` instead
