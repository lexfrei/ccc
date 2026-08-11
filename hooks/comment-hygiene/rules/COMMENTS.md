# COMMENT DISCIPLINE ACTIVE

Applies to every code comment, docstring, and doc comment you write this session. No drift: the rules below hold for every file edit, in every language, until the session ends.

Context: Anthropic marks AI-generated content invisibly at the model level (EU AI Act transparency). Nothing about disclosure requires noise in the source. A bloated comment is not compliance and not documentation — it is the loudest textual tell that nobody senior reviewed this code.

## The one rule

A comment must say what the code cannot. Everything else is noise.

## The deletion test — run before writing any comment

1. Delete the comment mentally. Does the reader lose information not recoverable from the code itself? If no — the comment stays deleted.
2. Could the information become a better name, a type, a constant, or an assertion? Then move it there instead of writing the comment.
3. Is it about the process that produced the code (review round, request, iteration, fix) rather than the code at rest? That belongs to git history, not source.

## Never write

- **Narration** — restating the next line: `// increment counter`, `// call the API`, `// return the result`.
- **Tutorial flow** — `// First, we...`, `// Next...`, `// Finally...`. Code is not a lesson.
- **Section banners** — `// ===== Helpers =====`, `// --- Validation ---`. Structure comes from functions and files.
- **Changelog comments** — `// changed X to Y`, `// new implementation`, `// now handles null`. That is `git log`'s job.
- **Reviewer asides** — `// this is safe because we validated above`, `// as requested`, `// per review`. That is talking to the PR, not to the next reader; it is noise the moment the PR merges.
- **Signature restatement** — `@param name - the name`, `Returns: the result`. A docstring that adds nothing below the signature is worse than none.
- **Docstrings on trivial private helpers** — the name is the documentation.
- **Ownerless TODOs** — `// TODO: improve later`. A TODO without an issue reference or a concrete trigger does not exist.
- **Dead code as comments** — delete it; git remembers.
- **Emphasis inflation** — `// IMPORTANT:`, `// NOTE:` on things that are neither.

## Worth writing

- **Why, not what** — why this way and not the obvious way: `// linear scan: n<=8 in practice, beats the map alloc`.
- **Constraints the code cannot show** — units, ordering, locking, invariants: `// caller must hold mu`, `// timeout is ms, not s`.
- **External anchors** — the RFC section, spec clause, or upstream bug that forces odd behavior, with a link.
- **Traps** — `// this write looks dead; removing it breaks resume on darwin`.
- **Rejected alternatives** — `// don't "simplify" to a single regex: catastrophic backtracking on long inputs`. Saves the next refactorer from re-learning it.
- **Public API doc comments** — per the ecosystem convention (godoc, rustdoc, javadoc, docstring): full sentences, contract not implementation, only where the convention expects them.

## Density

Match the file you are editing. Count comment density in the surrounding code before adding yours; your diff must not be visibly denser than its neighborhood. A patch with five times the ambient comment density reads as machine output regardless of content.

## Attribution

Never in source files. No "AI-generated", no model names, no tool names in code or comments. Attribution, when the project wants it, lives in commit trailers — nowhere else.
