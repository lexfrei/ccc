# Subsystem theory note

A theory note is half a page kept in the project's repository as `THEORY.md` in the subsystem's directory; for a changed file, the note is the `THEORY.md` in the file's own directory or the nearest parent that has one, or the document the project already keeps for that purpose, and with neither there is no note. Read it at the base branch: a note the PR adds or changes is part of the diff, not evidence. A human owner approves it; a reviewer of the same changes does not. It records why the subsystem is the way it is, so that a reviewer who meets the code for the first time can tell a change that extends it from one that bends it. `pr-review` quotes it as an item the project wrote down; `series-review` compares a series against it.

A note records what a subsystem is for and what it must not know; it does not restate decisions the project keeps elsewhere (decision records, design documents, agent docs), but links them, so that two copies cannot disagree. Where the project already has a home for this per subsystem, that document is the note and no `THEORY.md` is added beside it.

Sections, in this order:

1. **Purpose**: one or two sentences.
2. **Agreed with**: the external contracts and tools the subsystem relies on.
3. **Decisions**: at most seven, each as decision, reason, rejected alternative.
4. **Does not know**: what must never appear inside it.
5. **Known debts**: places that already break the note, so they are not mistaken for precedent.
6. **Owner and date.**

## Sample, not an approved note

An invented subsystem, for the shape only.

> **ownership/ (THEORY.md).** Purpose: for any object a tenant can see, find the installed plugin it belongs to. Agreed with: the platform's owner references and the `plugin.example/instance` label every plugin chart sets. Decisions: (1) walk owner references first, then the label, because both are contracts plugins already keep; a registry of links maintained by the core was rejected, since every plugin would have to write to it. (2) An object without an owner reference gets its owner from the plugin that creates it, through the same label; a branch in the walker for that plugin's kinds was rejected, since the core would then have to change with each plugin. Does not know: any kind, API group or label key of a particular plugin. Its tests do not read plugin files. Debts: one walker branch still special-cases a storage plugin's snapshot kind. Owner and date: not set.
