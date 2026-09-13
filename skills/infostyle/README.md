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

1. **Task and context** — audience, useful action ("why would the reader read this at all"), and where the text lands: a text whose context is broken is not fixed by editing words. Everything that does not serve the useful action becomes a deletion candidate.
2. **Structure** — substance first, one structure per text, contract with the reader, no second-level nesting.
3. **Paragraph** — one topic, self-contained opening sentence, first-sentences-only readability check.
4. **Sentence** — people and actions instead of processes, main parts close together, no overload.
5. **Word** — the five stop-word groups: вводные, неопределённое, заумь, навязанные оценки, штампы.
6. **Presentation** — headings, subheadings, lists, a cheat-sheet box for long documents.

Three modes: rewrite (default, ends with a change report), `--разбор` — findings only, no rewriting, and `--раскладка` — re-layout without changing a single word, for documents whose wording is fixed by lawyers or a regulation: paragraphs cut to 5–7 lines, key points duplicated as a list at the top, blocks reordered from substance to background, run-in subheadings added.

Reference files next to the skill carry the detail: `references/stop-words.md` (the five groups with replacement tables), `references/syntax.md` (sentence, paragraph, lists, the six bureaucratese fixes), `references/structure.md` (context, useful action, text structures, examples and counter-examples, tone, presentation), `references/genres.md` (writing about yourself, about a company, work reports, press releases, slide decks, promo pages).

The rule that matters most: **the skill never invents facts.** Replacing "качественный сервис" with a number requires a number. When there is none, the text gets an explicit `[нужен факт: …]` marker and the report says so.

### `infostyle-letter` — business correspondence

Letters to colleagues, clients, contractors and officials; replies to complaints; cold emails; job applications; work messages in chat.

Starts with the question the book puts first: should this be a letter at all? Emotions, a complaint about a colleague, a five-person planning thread, an actual fire and a complex high-stakes proposal all belong on the phone or in a meeting, not in the inbox. Then it checks the subject line, the structure (substance right after the greeting, one letter — one matter, a question that is comfortable to answer), how new participants are brought into a thread, the work done on the reader's behalf, and boundaries: no "как у тебя со временем", no "ты же профессионал", no ironic quotation marks, no "заранее спасибо".

Separate sections cover the genres: cold emails, replies to job ads, complaint responses (both when the customer is right and when they are not), letters that are pure venting, reminders to a colleague, hiring conversations and fee negotiation, commercial proposals, and asking someone to do work outside their obligations.

Same modes: rewrite or `--разбор`.

## Extending

Both skills are plain markdown. The natural extension points:

- new entries in the stop-word tables — put them in `references/stop-words.md`, not in `SKILL.md`, so the main file stays a process description;
- new genres for the letter skill (претензия подрядчику, письмо в поддержку, ответ на отзыв) — a new section under "Жанры";
- a project-specific tone of voice — a `references/voice.md` next to `infostyle/SKILL.md` and one line in the hard rules pointing at it.

Version bump on any content change, and keep the description identical in `plugin.json` and `.claude-plugin/marketplace.json` at the repo root.
