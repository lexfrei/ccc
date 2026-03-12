---
name: learn
description: Analyze the current session and extract key learnings worth preserving.
disable-model-invocation: true
---

Analyze the current session and extract key takeaways worth preserving.

## Classification

Separate findings into three categories:

**Personal** (~/CLAUDE.md):

- General patterns and approaches that work across projects
- Tool/language insights not specific to this codebase
- Workflow preferences discovered
- Errors caused by misunderstanding that were corrected during the session

**Project** (CLAUDE.md):

- Architecture decisions specific to this codebase
- Project-specific conventions and patterns
- Codebase quirks and gotchas
- Integration details with project's stack
- Errors and mistakes fixed during test implementation and runs
- Insights from code review if available

**Memory** (auto memory system):

- User preferences and feedback specific to this project (type: user, feedback)
- Project status, ongoing initiatives, deadlines (type: project)
- References to external systems: boards, channels, dashboards (type: reference)
- Gotchas and lessons learned that are personal experience, not codebase conventions
- Anything that is project-scoped but should NOT be committed to the repo

## Fallback: no project CLAUDE.md

If the project has no CLAUDE.md (or user has no write access to repo):

- Everything from **Project** category goes to **Memory** instead
- Use memory types: `project` for architecture/conventions, `feedback` for gotchas/corrections
- Do NOT create CLAUDE.md without explicit user request

## Process

1. Read target files before proposing changes (~/CLAUDE.md, CLAUDE.md, MEMORY.md)
2. Check MEMORY.md line count — if at or above 180 lines, propose cleanup of stale/outdated entries before adding new ones
3. Check for duplicates or overlapping content across ALL targets — skip if already covered
4. Skip findings if found in another file (e.g. project item already in ~/CLAUDE.md globally)
5. Decide where each item fits best within existing structure (don't create new sections unless nothing fits)
6. Formulate concisely, matching the style of existing content

## MEMORY.md Size Management

MEMORY.md is truncated after 200 lines — anything beyond line 200 is invisible to future conversations.

- **NEVER allow MEMORY.md to exceed 200 lines** — this is a hard limit
- After reading MEMORY.md, count its lines. If above 150: proactively suggest compacting
- Compacting strategies (propose to user, apply only after approval):
  - Merge related memories into a single entry
  - Remove entries for completed/abandoned projects
  - Remove entries that are now covered by CLAUDE.md or code itself
  - Shorten verbose descriptions to one-liners
- When proposing cleanup, show which entries to remove/merge and why
- **NEVER delete or modify memory entries without explicit user approval**

## Output

Show proposed additions grouped by target:

```text
~/CLAUDE.md:
  - [where in file] addition text

CLAUDE.md:
  - [where in file] addition text

Memory:
  - [type: feedback] description of memory
  - [type: project] description of memory
```

Ask for confirmation. Accept: "y", "yes", or selective like "only project" / "skip personal" / "only memory".

After confirmation, apply changes.
