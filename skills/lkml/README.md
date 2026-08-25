# lkml

Skills for working with Linux kernel mailing lists end to end: reading and monitoring threads on lore.kernel.org, checking patch state in patchwork, replying to review, and posting patch series with git send-email — plus the communication rules that decide whether a submission survives contact with maintainers. The mechanics are curl- and git-based, no list subscription or local mail setup required; the rules are distilled from `Documentation/process/` and from live review cycles on netdev.

## Installation

```bash
/plugin marketplace add lexfrei/ccc
/plugin install lkml@claude-code-companions
```

## Skills

### lore

Read, search, and monitor threads on lore.kernel.org with plain curl. Covers the User-Agent gate (default curl gets 403, browser agents get an Anubis challenge, `lei/1.0` passes on every endpoint), whole-thread mbox fetch, cheap new-reply polling via atom feeds — including how to tell a real reply from a lore reindex — public-inbox search syntax, and how to separate maintainer replies from bot traffic when reading a series. Invoked when a task needs a kernel thread fetched, prior discussion found, or a Message-ID extracted; also `/lkml:lore`.

### patch-status

Check what patchwork says will happen to a patch: the api/1.2 query by patch-mail Message-ID, the state table (`new` through `accepted`/`changes-requested`/`superseded`) mapped to a concrete next action, `pw-bot` commands in threads, and the timing rules for pinging — including why a bare "ping" is explicitly rude and what a useful nudge contains. Invoked when the question is "was it accepted" or "is it time to ping"; also `/lkml:patch-status`.

### reply

Compose and send an in-thread review reply: the reply-vs-new-version gate, building the mail from real thread headers, interleaved trimmed quoting at 72 columns, the answer-every-comment rule, and disagreement carried by mechanism rather than seniority. Sends with `git send-email --in-reply-to` only after showing the user the full text and recipient set. Invoked for any prose response inside an existing kernel thread; also `/lkml:reply`.

### submit

Post a patch series — v1 or any reroll, always as a new thread. Ordered gates before the send: content (WHY-only commit bodies, grep-verified set claims, `Fixes:`/`Closes:` tags, the kernel's `Assisted-by:` disclosure format from coding-assistants.rst), recipients (get_maintainer.pl plus everyone from prior discussion, nobody dropped), format (tree subject prefixes, changelog under the `---` scissors, carrying received tags forward), `checkpatch.pl --strict`, and timing (24 hours between versions, merge-window closures). Invoked when kernel patches need to go out; also `/lkml:submit`.

### etiquette

The standing-rules reference the other skills lean on: routing via the MAINTAINERS entry types and get_maintainer.pl, where bug reports, regressions, and security issues go, thread and Cc discipline, review timing norms, the tag permission matrix (which tags need the named person's consent), and the tone rules that keep threads productive. Invoked when deciding where or to whom something should go, or whether a planned action is acceptable; also `/lkml:etiquette`.

## Extending

Subsystem-specific rules belong in the skill they gate, sourced from that subsystem's `Documentation/process/maintainer-*.rst`, not from memory — the netdev rules here (tree prefixes, 24-hour rule, net-next closure) are the template. Endpoint mechanics (User-Agent strings, API shapes) drift; when a command in these skills stops working, re-verify against the live service before editing the prompt.
