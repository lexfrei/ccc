# COMMENT DISCIPLINE ACTIVE

Applies to every code comment, docstring, and doc comment you write this session, in every language. No drift until the session ends.

Bloated comments are the watermark. Nothing marks code as machine-generated faster than commentary the reader could have generated themselves, and maintainers of large open-source projects reject it on sight. Every comment must earn its place: it complements the code or it does not exist.

## The one rule

A comment must say what the code cannot. Everything else is noise.

## The deletion test — run before writing any comment

1. Delete the comment mentally. Does the reader lose information not recoverable from the code itself? If no — the comment stays deleted.
2. Could the information become a better name, a type, a constant, or an assertion? Then move it there instead of writing the comment.
3. Is it about the process that produced the code rather than the code at rest? That belongs to git history, not source.

## Never write

- **Narration** — restating the next line: `// increment counter`, `// call the API`.
- **Tutorial flow** — `// First, we...`, `// Next...`, `// Finally...`. Code is not a lesson.
- **Section banners** — `// ===== Helpers =====`. Structure comes from functions and files.
- **Changelog comments** — `// changed X to Y`, `// now handles null`. That is `git log`'s job.
- **Reviewer asides** — `// this is safe because we validated above`, `// as requested`. Talking to the PR, not the next reader; noise the moment it merges.
- **Provenance** — `// see the PR description`, ticket IDs, review-round references. A comment must survive without access to the thread that produced it.
- **Signature restatement** — `@param name - the name`, `Returns: the result`. Worse than no docstring.
- **Docstrings on trivial private helpers** — the name is the documentation.
- **Ownerless TODOs** — a TODO without an issue reference or a concrete trigger does not exist.
- **Dead code as comments** — delete it; git remembers.
- **Emphasis inflation** — `// IMPORTANT:`, `// NOTE:` on things that are neither.

## Worth writing

- **Why, not what** — why this way and not the obvious way: `// linear scan: n<=8 in practice, beats the map alloc`.
- **Constraints the code cannot show** — units, ordering, locking, invariants: `// caller must hold mu`, `// timeout is ms, not s`.
- **External anchors** — the RFC section, spec clause, or upstream bug that forces odd behavior, with a link.
- **Traps** — `// this write looks dead; removing it breaks resume on darwin`.
- **Rejected alternatives** — `// don't "simplify" to a single regex: catastrophic backtracking on long inputs`. Saves the next refactorer from re-learning it.
- **Public API doc comments** — per the ecosystem convention (godoc, rustdoc, javadoc, docstring): full sentences, contract not implementation, only where the convention expects them.

## Write the invariant, not the derivation

Every sentence in a comment is a checkable claim; the more prose, the more of it will be false. An invariant survives and a test can pin it; a derivation rots at the first change in a neighboring subsystem and nothing checks it.

- **No counts about sets** — `// all four callers`, `// 11 files still do X`: true on your tree, false after the next merge. Write "every caller"; if the number matters, compute it in code or pin it with a test.
- **Quantifiers are numbers in disguise** — "most", "nearly all" assert arithmetic precise enough to be wrong and vague enough that nothing can pin them. Same fix.
- **No lists of neighbors** — a comment enumerating sibling files or checks is a table of contents that decays on the next edit to those files. Point at where they live instead.
- **Facts about other components rot fastest** — a default, a timeout, a behavior belonging to another subsystem is where comments go to be wrong. If the sentence under your fingers is about another file, open that file now and write from it, not from memory.
- **Ordering claims need tests** — "must run before", "takes priority" asserts an invariant; pin it with a test in the same sitting or delete the sentence.
- **Maintenance instructions must name every site** — "lifting this = removing this check" is false when the rule also lives in a schema, a validation layer, or a second copy. Name all of them or write nothing.
- **One claim, one place** — a second copy of the same statement is a scheduled divergence. Fix duplicates by deleting the copy, never by syncing it.

## Density

Match the file you are editing. Count comment density in the surrounding code before adding yours; your diff must not be visibly denser than its neighborhood. A patch several times denser in comments reads as machine output regardless of content.

## No leaks

Comments ship with the code and are public. Never: internal tool names, private infrastructure details (cluster names, client names, internal namespaces), ticket-tracker IDs, review-workflow references. English only.

## Attribution

Never in source files. No "AI-generated", no model names, no tool names in code or comments. Attribution, when the project wants it, lives in commit trailers — nowhere else.
