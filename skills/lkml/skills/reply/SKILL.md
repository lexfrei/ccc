---
name: reply
description: Compose and send an in-thread reply on a Linux kernel mailing list — answering review comments, asking a clarifying question, or reporting test results. TRIGGER — invoke when the task is to respond inside an existing kernel thread with prose (no patches attached). DO NOT TRIGGER for posting a new version of a series — that is a new thread, use lkml:submit — or for reading the thread (use lkml:lore).
argument-hint: "[lore URL or Message-ID of the mail to answer]"
---

A review reply is prose sent into a public, permanently archived thread. The mechanics are three commands; the failure modes are all in the content, so the content gates come first.

## Gate: is a reply the right vehicle?

- Review comments are answered **in-thread**. Fixed code is **not** — a new version of the series goes out as a new thread (lkml:submit). Never attach or inline corrected patches in a reply.
- Answer the review before reposting: do not send a new version while the discussion about the current one is still ongoing, unless a reviewer directly asks for it.
- Every reviewer comment gets a response — agreed-and-will-fix, a reasoned pushback, or a clarifying question. Silently dropping a point reads as ignoring the reviewer, and ignoring reviewers is how submissions start being ignored.

## Build the reply

Fetch the thread mbox (lkml:lore) and take from the mail being answered: its exact `Message-ID:`, its exact `Subject:`, its `From:`, and the full recipient set. Never guess or reconstruct a Message-ID.

Write the reply to a file with a header block:

```text
Subject: Re: [PATCH net-next 2/3] net: dsa: mt7530: example subject copied exactly

> quoted fragment of the reviewer's point, trimmed to what is answered
> only

Response to that point.

> next quoted point

Response.
```

Formatting rules for the body:

- **Interleaved replies only.** Quote a fragment with `> `, answer under it, repeat. Top-posting (answer above full quote) marks the mail as not worth reading.
- **Trim quotes.** Keep only the lines being answered; delete the rest of the quoted mail, including the signature and the diff, unless a specific hunk is discussed.
- **Hard-wrap body text at about 72 columns.** Kernel mail is plain-text with real line breaks — the opposite of markdown-renderer habits. No HTML, no attachments, no links where text will do.
- Answer in the order the points were raised; one mail per parent mail being answered, not one mail per point.

## Tone that works on kernel lists

- When the reviewer is right, say so plainly and state what v-next will do: "Right, will drop the lock here in v3." No apology theater.
- When the reviewer is wrong, disagree with a mechanism: a code path, a measurement, a spec section, a test result. Never with seniority, effort spent, or urgency.
- When a reviewer supplies the actual fix or the idea for it, credit it — say so in the reply and carry `Suggested-by:` in the next version.
- Thank briefly, once. English only. No emoji, no corporate signature blocks or legal footers.
- Claims about sets ("all callers hold the lock", "this is only reached once") are the easiest thing for a reviewer to falsify — grep before asserting, or phrase as mechanism instead of quantity.

## Send

```bash
git send-email --confirm=never \
    --to "<author of the mail being answered>" \
    --cc "<every other participant and list from the thread>" \
    --in-reply-to="<message-id of the mail being answered>" \
    reply.eml
```

To is the person being answered; Cc is everyone already on the thread plus the lists — the full reply-all set. Removing anyone who was on Cc is bad form, even people who have not spoken.

Show the user the complete reply text and recipient list and get an explicit OK before running git send-email — this is public, archived, and unretractable.
