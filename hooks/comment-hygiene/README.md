# comment-hygiene

SessionStart hook that injects code-comment discipline into every Claude Code session. The injected rules apply to every comment, docstring, and doc comment the session writes, in any language.

Bloated comments are the watermark. Narration of the next line, tutorial flow, changelog comments, reviewer asides, docstrings that restate the signature — nothing marks code as machine-generated faster, and maintainers of large open-source projects reject it on sight precisely because the reader could have generated it themselves. This hook makes every session start from the opposite default: every comment must earn its place — complement the code, never duplicate it.

## How it works

A `SessionStart` hook (no matcher, so it fires on every source: startup, resume, clear, compact, and fork) cats [`rules/COMMENTS.md`](rules/COMMENTS.md) to stdout, which Claude Code adds to the session context. There is no enforcement script and nothing to configure — the rules ride along in context where the model cannot miss them, the same delivery mechanism as a persona plugin.

The rules in one line each:

- **The one rule** — a comment must say what the code cannot.
- **The deletion test** — before writing a comment: would deleting it lose information not in the code? Could it become a name, type, or assertion instead? Is it about the change process rather than the code?
- **Never write** — narration, tutorial flow, section banners, changelog comments, reviewer asides, provenance, signature restatement, docstrings on trivial helpers, ownerless TODOs, dead code as comments, emphasis inflation.
- **Worth writing** — why-not-what, constraints the code cannot show, external anchors (RFC/spec/upstream bug), traps, rejected alternatives, conventional public-API doc comments.
- **Invariant, not derivation** — no counts about sets, no quantifiers in disguise, no lists of neighbors, no facts about other components written from memory, no untested ordering claims, no maintenance instructions that name only one of the rule's homes, one claim in one place.
- **Density** — a diff must not be visibly denser in comments than the file around it.
- **No leaks** — comments are public: no internal tool names, no private infrastructure, no tracker IDs, no review-workflow references.
- **Attribution** — never in source files; commit trailers only.

## Installation

```bash
/plugin marketplace add lexfrei/ccc
/plugin install comment-hygiene@claude-code-companions
```

## Extending

Edit [`rules/COMMENTS.md`](rules/COMMENTS.md) — whatever it contains is what gets injected verbatim. Keep it short: it lands in every session's context, so every line costs tokens on every startup.

## Related

- `become:hygiene` agent (this marketplace) — the after-the-fact counterpart: sweeps a codebase and removes AI-generated comment noise that already landed. `comment-hygiene` prevents; `become:hygiene` cleans up.
