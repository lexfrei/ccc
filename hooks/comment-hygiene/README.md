# comment-hygiene

SessionStart hook that injects code-comment discipline into every Claude Code session. The injected rules apply to every comment, docstring, and doc comment the session writes, in any language.

Bloated comments are the loudest textual tell of AI-generated code: narration of the next line, tutorial flow, changelog comments, reviewer asides, docstrings that restate the signature. Anthropic already marks AI-generated content invisibly at the model level ([how Claude marks AI-generated content](https://support.claude.com/en/articles/16266773-how-claude-marks-ai-generated-content)), so none of that noise serves disclosure — it is just bad code. This hook makes every session start from the opposite default: a comment must say what the code cannot.

## How it works

A `SessionStart` hook (fires on startup, resume, and post-compact) cats [`rules/COMMENTS.md`](rules/COMMENTS.md) to stdout, which Claude Code adds to the session context. There is no enforcement script and nothing to configure — the rules ride along in context where the model cannot miss them, the same delivery mechanism as a persona plugin.

The rules in one line each:

- **The one rule** — a comment must say what the code cannot.
- **The deletion test** — before writing a comment: would deleting it lose information not in the code? Could it become a name, type, or assertion instead? Is it about the change process rather than the code?
- **Never write** — narration, tutorial flow, section banners, changelog comments, reviewer asides, signature restatement, docstrings on trivial helpers, ownerless TODOs, dead code as comments, emphasis inflation.
- **Worth writing** — why-not-what, constraints the code cannot show, external anchors (RFC/spec/upstream bug), traps, rejected alternatives, conventional public-API doc comments.
- **Density** — a diff must not be visibly denser in comments than the file around it.
- **Attribution** — never in source files; commit trailers only.

## Installation

```bash
/plugin marketplace add lexfrei/ccc
/plugin install comment-hygiene@claude-code-companions
```

## Extending

Edit [`rules/COMMENTS.md`](rules/COMMENTS.md) — whatever it contains is what gets injected verbatim. Keep it short: it lands in every session's context, so every line costs tokens on every startup.

## Related

- `doc-curator` agent (this marketplace) — the after-the-fact counterpart: sweeps a codebase and removes AI-generated comment noise that already landed. `comment-hygiene` prevents; `doc-curator` cleans up.
