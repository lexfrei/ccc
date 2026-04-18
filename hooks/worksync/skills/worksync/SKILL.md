---
name: worksync
description: >
  Append a sync-worthy entry to today's work-sync note. The note lives under
  $WORKSYNC_VAULT_DIR/YYYY-MM-DD.md (default ~/worksync) so it can be picked
  up by Obsidian, Logseq, or any markdown tool the user prefers.
  TRIGGER: invoke when (a) the user types /worksync with a message, (b) a research task just finished
  and produced a conclusion worth mentioning at a work sync, (c) an operational task (deploy, rollout,
  migration, infrastructure change) just finished, (d) the user says "checkpoint this" / "log this" / similar.
  DO NOT TRIGGER: for trivial read-only lookups, for unfinished work, more than once per distinct event.
  Explicit PR/issue creation, merges, and closes are already captured automatically by the companion
  PostToolUse hook — do not re-log those here.
---

# worksync — log a sync-worthy entry

Appends a single timestamped bullet to today's note at
`${WORKSYNC_VAULT_DIR:-$HOME/worksync}/YYYY-MM-DD.md` via the bundled helper
script `${CLAUDE_PLUGIN_ROOT}/scripts/worksync-append.sh`.

The file's purpose: a low-friction daily log of things the user will want to
mention at a work sync, standup, or weekly review. Phrase entries for a
technical peer audience.

## Arguments

The skill accepts a free-form argument from `$ARGUMENTS`:

- If non-empty: treat it as the message, with optional leading type hint.
- If empty: derive message from recent session activity (see "Inferring content" below).

Supported types (passed as first arg to the helper):

| Type         | When to use                                                              |
|--------------|--------------------------------------------------------------------------|
| `research`   | A question was investigated and produced a concrete finding or decision. |
| `ops`        | A deploy, rollout, migration, or infrastructure operation finished.      |
| `checkpoint` | User-requested mid-task marker ("log this", "checkpoint").               |
| `note`       | Anything else worth mentioning that doesn't fit the above.               |

Types `pr`, `issue`, `merge` are **reserved for the automatic hook** — do not
emit them from the skill. If the user explicitly asks to log one manually, use
`note` and include the URL in the message.

## Inferring content (no arguments case)

When invoked with no arguments, scan the most recent turns of the current
session and produce ONE entry summarizing the most recent sync-worthy event.
Do not produce multiple entries in one invocation — call the skill again if
more is needed.

Selection priority (pick the most recent qualifying item):

1. An `ops` action that visibly succeeded (deploy, apply, rollout, migration,
   infrastructure reconfiguration, provisioning run against real hosts).
2. A `research` conclusion — user asked a question, you investigated, you
   reached a definite answer or recommendation.
3. A `checkpoint` the user explicitly requested.

Skip if the most recent activity was just reading/exploring without producing
a decision or action — nothing to log yet.

## Message format

Keep the message to one line, English, technical-peer tone.

Good examples:

- `research` — `confirmed HTTP/2 keepalive is the right fix for the connection-reset issue; ADR pending`
- `ops`      — `rolled out v1.42.3 to staging, all replicas healthy inside 90s`
- `ops`      — `ran db migration 0042 on production, 0 rows skipped, 12s runtime`
- `research` — `decided to drop Redis cluster mode — single-primary + replica covers our load`

Bad examples (do not emit):

- `checked pod status` (not sync-worthy)
- `discussed architecture` (no outcome)
- anything with customer names, credentials, or internal-only identifiers

## Execution

Run the helper script. Do not write to the file directly — the helper handles
directory creation, date-based filenames, and deduplication.

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/worksync-append.sh" <type> "<message>"
```

Exit on failure is fine — surface the error to the user. On success, reply
with one short line: which file was updated and what was logged.

## Redaction rules

Before appending, strip or rewrite:

- Customer, client, or project names → generic labels ("production cluster",
  "test environment", "a customer request").
- Internal hostnames or cluster identifiers that reveal topology → generic.
- Credentials, tokens, private IP addresses, internal URLs.

If the event cannot be described without private details, log a vague version
("reviewed an internal auth change") rather than skipping — the user still
wants a timestamp marker they can expand on verbally at the sync.

## Configuration

Users can point the note directory at any location by exporting
`WORKSYNC_VAULT_DIR` in their shell, Claude `settings.json` `env` block, or a
project `.env`. Common targets:

- `~/Documents/Obsidian/MyVault/worksync` — Obsidian vault subfolder
- `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/<vault>/worksync` — macOS iCloud-synced Obsidian vault
- `~/logseq/journals/worksync` — Logseq graph
- `~/worksync` — the default, plain folder

Daily files are plain markdown, so any editor will do.
