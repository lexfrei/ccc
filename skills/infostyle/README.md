# infostyle

Two skills for Russian text, built on информационный стиль — the editing method of Maxim Ilyahov and Lyudmila Sarycheva («Пиши, сокращай 2025», «Ясно, понятно», «Новые правила деловой переписки»).

The instructions are in English, the rules and examples are in Russian: stop-words, case government and bureaucratese are properties of the language being edited, not of the language the skill is written in. English prose is out of scope — that is what a separate humanize-style skill is for.

## Installation

```bash
/plugin marketplace add lexfrei/ccc
/plugin install infostyle@claude-code-companions
```

## Skills

### `infostyle` — edit prose

Articles, landing copy, product descriptions, internal docs, announcements, reports, résumés, posts.

Runs a fixed order of passes instead of a single vague "make it better":

1. **Task** — audience and useful action ("why would the reader read this at all"). Everything that does not serve it becomes a deletion candidate.
2. **Structure** — substance first, one structure per text, contract with the reader, no second-level nesting.
3. **Paragraph** — one topic, self-contained opening sentence, first-sentences-only readability check.
4. **Sentence** — people and actions instead of processes, main parts close together, no overload.
5. **Word** — the five stop-word groups: вводные, неопределённое, заумь, навязанные оценки, штампы.
6. **Presentation** — headings, subheadings, lists, a cheat-sheet box for long documents.

Two modes: rewrite (default, ends with a change report) and `--разбор` — findings only, no rewriting.

Reference files next to the skill carry the detail: `references/stop-words.md` (the five groups with replacement tables), `references/syntax.md` (sentence, paragraph, lists, the six bureaucratese fixes), `references/structure.md` (useful action, text structures, examples and counter-examples, tone, presentation).

The rule that matters most: **the skill never invents facts.** Replacing "качественный сервис" with a number requires a number. When there is none, the text gets an explicit `[нужен факт: …]` marker and the report says so.

### `infostyle-letter` — business correspondence

Letters to colleagues, clients, contractors and officials; replies to complaints; cold emails; job applications; work messages in chat.

Starts with the question the book puts first: should this be a letter at all? Emotions, a complaint about a colleague, a ten-person planning thread and an actual fire all belong on the phone, not in the inbox. Then it checks the subject line, the structure (substance right after the greeting, one letter — one matter, a question that is comfortable to answer), the work done on the reader's behalf, and boundaries: no "как у тебя со временем", no "ты же профессионал", no ironic quotation marks, no "заранее спасибо".

Separate sections cover cold emails (assume nothing about the reader, ask for a small next step) and replies to public calls for applications (answer point by point, in the requester's own format).

Same two modes: rewrite or `--разбор`.

## Extending

Both skills are plain markdown. The natural extension points:

- new entries in the stop-word tables — put them in `references/stop-words.md`, not in `SKILL.md`, so the main file stays a process description;
- new genres for the letter skill (претензия подрядчику, письмо в поддержку, ответ на отзыв) — a new section under "Жанры";
- a project-specific tone of voice — a `references/voice.md` next to `infostyle/SKILL.md` and one line in the hard rules pointing at it.

Version bump on any content change, and keep the description identical in `plugin.json` and `.claude-plugin/marketplace.json` at the repo root.
