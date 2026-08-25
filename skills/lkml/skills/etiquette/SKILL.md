---
name: etiquette
description: Reference for the communication rules of Linux kernel mailing lists — who to write to, what goes where, timing, tags, and tone. TRIGGER — invoke when deciding where or to whom a kernel question, bug report, or patch should go, when unsure whether a planned action (ping, resend, off-list mail, tag) is acceptable, or before drafting any list-bound text outside the lkml:reply / lkml:submit workflows. DO NOT TRIGGER for the mechanics already covered there: sending is lkml:submit or lkml:reply, reading is lkml:lore, state is lkml:patch-status.
---

Kernel lists are a public workspace with strong, mostly unwritten-until-violated norms. This skill is the reference: consult the relevant section, apply it, and when a rule here conflicts with a subsystem's own `Documentation/process/maintainer-*.rst`, the subsystem wins.

## The medium

Everything sent to a list is public, archived on lore.kernel.org forever, quoted in commit messages, and indexed by search engines. English only. Plain text only — no HTML, no attachments, no images; hard-wrapped at about 72 columns. Nothing confidential, no internal infrastructure details, no employer boilerplate footers. Write every mail knowing it may be read ten years later by someone with no context but the thread.

## Who to write to

The MAINTAINERS file is the routing table; `scripts/get_maintainer.pl` reads it for you (feed it patch files, or a file path with `--file`). When reading an entry directly:

- `M:` — maintainers: the people who take the patch; they go in To
- `R:` — designated reviewers: Cc them
- `L:` — the subsystem list: Cc, mandatory — this is where review actually happens
- `S:` — status: `Maintained`/`Supported` will answer; `Odd Fixes`/`Orphan` explains silence in advance
- `T:` — the git tree patches land in; base your work on it, not on Linus' tree
- `P:` — subsystem profile document with local rules (tree prefixes, timing); read it before first contact
- `B:` — where bugs go, when it is not the list

Routing rules:

- Patches and review questions: maintainers in To, list plus reviewers in Cc, `linux-kernel@vger.kernel.org` as archive Cc. Review happens on the list; mailing a maintainer privately about an ordinary patch wastes the one reviewer it reaches and is quietly resented.
- Bug reports: the subsystem list plus its maintainers, same routing as a patch for the file that misbehaves. A regression (something that worked in a previous kernel) additionally Cc's `regressions@lists.linux.dev` and names the last good version — bisect first if at all possible.
- Security bugs: `security@kernel.org` privately, never the public list, never a public tracker.
- Usage questions ("how do I configure X") do not belong on development lists at all.
- A newcomer question is fine on the subsystem list if it shows the homework: what was read, what was tried, where it diverged from expectation.

## Threads

- One topic per thread. Answers to a thread stay in it; new code — including every reroll of a series — starts a new thread. Never bolt a new topic onto an existing thread because the right people are already on it.
- Reply-all is the default; the full Cc set of a thread is load-bearing. Removing participants mid-thread, or between versions of a series, reads as hiding the discussion from them.
- Interleaved quoting, trimmed to what is answered. Top-posting and full-quote-below signatures mark mail that gets skipped.

## Time

- Kernel review has no SLA. netdev answers in days, most subsystems in one to two weeks, some in a month. During a merge window (the two weeks after a release) everything slows and netdev's net-next closes to features entirely.
- Minimum 24 hours between versions of one series; minimum a week of silence before any nudge.
- A nudge is never the word "ping". It restates where things stand and asks one concrete answerable question. One nudge, then a resend (`[PATCH RESEND ...]`, unchanged, with a line saying why) after another silent stretch beats a second nudge.
- Do not vanish either: a series whose author stops responding for weeks is dropped from queues, and the context cost of resurrecting it lands on you.

## Tags

Tags are signed statements by real people, not decoration:

| tag | states | who may add it |
| --- | --- | --- |
| `Signed-off-by:` | DCO certification of origin | each human in the patch's path; never generated |
| `Reviewed-by:` | reviewed and found acceptable | you, only after the person offered it on-list |
| `Acked-by:` | maintainer of a touched area does not object | same — only if actually given |
| `Tested-by:` | ran it and it worked | same |
| `Suggested-by:` | the idea came from this person | you may add without asking; credit generously |
| `Reported-by:` + `Closes:` | who found the bug, link to the report | you may add without asking |
| `Fixes:` | which commit introduced the bug | you; 12+ char SHA plus quoted subject, one unwrapped line |
| `Cc:` | keep this person/list informed | you may add without asking |
| `Assisted-by:` | AI/tool assistance disclosure | you; kernel format `AGENT:MODEL [tools]` — see lkml:submit |

Offered tags on unchanged patches are carried into the next version by the author. Inventing a tag someone did not give is forgery of a public record.

## Tone

- Technical, brief, specific. State the problem, the mechanism, the question. No marketing adjectives, no enthusiasm padding, no apology theater.
- Disagreement is welcome when it carries a mechanism: a code path, a number, a spec clause, a failing test. "I spent a lot of time on this" and "we need this urgently" are not arguments and actively hurt.
- Concede plainly when wrong; credit reviewers whose ideas you take (in words and in `Suggested-by:`).
- Assertions about sets — "all drivers", "the only caller", "never reached" — are the claims reviewers falsify for sport. Verify with grep or phrase as mechanism.
- Terse maintainer replies are the norm, not hostility. Read exactly what was written; do not answer implied tone.
- Verbose, essay-shaped mail now draws "Is it AI generated?" as a review response. Length is not diligence; the prose gates in lkml:submit exist because of a real changes-requested for exactly this.

## Worked examples

Live threads showing the full cycle, useful as format references: a v1 → review → v2 series with an architectural maintainer reply (https://lore.kernel.org/netdev/20260822155259.87146-1-f@lex.la/), its v2 as a new thread with the changelog under the scissors (https://lore.kernel.org/netdev/20260824024029.41310-1-f@lex.la/), and a series reworked after an "is it AI generated" review with a second reviewer's fix credited (https://lore.kernel.org/netdev/20260824024117.46154-1-f@lex.la/).
