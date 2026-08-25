---
name: lore
description: Read, search, and monitor Linux kernel mailing-list threads on lore.kernel.org. TRIGGER — invoke when a task involves fetching a kernel thread, checking whether reviewers replied to a submission, finding prior discussion of a topic, or extracting a Message-ID for a follow-up. DO NOT TRIGGER for checking whether a patch was accepted (use lkml:patch-status) or for composing outgoing mail (use lkml:reply or lkml:submit).
argument-hint: "[lore URL | Message-ID | search query]"
---

lore.kernel.org is the public-inbox archive of the kernel lists. Everything below works with plain curl, no subscription and no local mail setup, but the archive sits behind bot protection that keys on the User-Agent.

## User-Agent: the one thing that breaks everything

Default curl gets HTTP 403; browser-style agents (`Mozilla/5.0 ...`) get an Anubis JavaScript challenge page instead of content. Send `--user-agent "lei/1.0"` on every request — it works for mbox, atom, and search endpoints alike.

If a response starts with `<!doctype html>` and mentions "not a bot", you hit the challenge: fix the User-Agent, do not try to solve or bypass the challenge.

## Fetch a whole thread

```bash
curl --silent --user-agent "lei/1.0" "https://lore.kernel.org/<list>/<message-id>/t.mbox.gz" | gunzip
```

`<message-id>` is bare, without angle brackets. Any message's ID pulls its entire thread — cover letter, patches, and every reply. This mbox is the source of truth for reply headers: take `Message-ID:`, `From:`, `Cc:`, and exact `Subject:` values from it, never reconstruct them from memory.

The list name in the URL scopes the archive (`netdev`, `linux-kernel`, `linux-mm`, ...); when the list is unknown, `https://lore.kernel.org/all/<message-id>/` resolves from the cross-list index and `https://lore.kernel.org/r/<message-id>/` is the canonical short form for citing a message in changelogs and `Link:` tags.

If the `b4` tool is installed, `b4 mbox <message-id>` does the same fetch with retries; the curl form needs no tooling.

## Check for new replies without refetching

```bash
curl --silent --user-agent "lei/1.0" "https://lore.kernel.org/<list>/<message-id>/t.atom" | grep -oE "<name>[^<]+</name>|<updated>[^<]+</updated>"
```

Read it as author/timestamp pairs. A new author entry with a fresh timestamp is a new message — fetch the mbox. A bumped `<updated>` with the same set of authors is lore reindexing the thread, not new mail; do not report it as a reply.

## Search

```bash
curl --silent --user-agent "lei/1.0" "https://lore.kernel.org/<list>/?q=<url-encoded-query>&x=A"
```

`x=A` returns results as an Atom feed, which is the machine-readable option; drop it for the HTML view. The query is public-inbox / Xapian syntax:

- `f:linus` — by author (name or address substring)
- `s:phylink` — in subject
- `d:20260101..` / `d:..20260201` / `d:20260101..20260201` — date ranges
- `"exact phrase"` — quoted phrases
- `nq:pw-bot` — quoted text only (finds replies quoting a phrase)
- Terms AND by default; `OR` must be uppercase

Search one list when the list is known — `/all/` works but ranks noisier.

## Reading a series

Read the cover letter (`0/N`) first for intent, then patch replies for review comments. Separate humans from machinery before summarizing a thread: `pw-bot` replies are patchwork state changes (see lkml:patch-status), `kernel test robot <lkp@intel.com>` and netdev CI mails are automated build/test results. A maintainer's one-line reply outweighs any bot output.
