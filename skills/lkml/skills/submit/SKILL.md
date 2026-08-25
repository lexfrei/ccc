---
name: submit
description: Prepare and send a Linux kernel patch series with git send-email — a first version or a reroll (v2, v3, ...). TRIGGER — invoke when the task is to post kernel patches to a mailing list, including new versions after review. DO NOT TRIGGER for prose-only replies inside an existing thread (use lkml:reply) or for checking what happened to an already-sent series (use lkml:patch-status).
argument-hint: "[branch or commit range] [v2|v3 ...]"
---

Every posting of a series — v1 and every reroll — is a **new thread**. Review feedback is answered in the old thread (lkml:reply); fixed code is posted fresh. The workflow below is ordered as gates: content, recipients, format, timing, send. A failed gate stops the send.

## 1. Content gates (before formatting anything)

**Commit message = WHY.** The subject is `subsystem: imperative summary` at 70-75 characters; the body says why the change is needed and why this way, hard-wrapped at 75 columns. Mechanism walkthroughs, rejected-alternative essays, and reachability analyses do not belong in the commit body — put them under the `---` scissors or in the cover letter. A verbose commit body draws "This is very verbose. Is it AI generated?" and a changes-requested; there is a public precedent of exactly that: https://lore.kernel.org/netdev/20260822195252.2934-1-f@lex.la/

**Verify claims about sets.** Any sentence of the form "all drivers do X", "this lock is only taken once", "no caller passes NULL" is an invitation for a reviewer to find the counterexample. Grep the tree for each such claim before sending, or rewrite it as a statement about the mechanism.

**Bug fixes carry a `Fixes:` tag** — 12+ character SHA plus the quoted subject of the broken commit, one line, never wrapped. Reports from other people carry `Reported-by:` plus a `Closes:` link to the report on lore.

**AI assistance is disclosed** per Documentation/process/coding-assistants.rst with the kernel's own tag format, which checkpatch validates:

```text
Assisted-by: Claude:claude-fable-5
```

Format is `Assisted-by: AGENT:MODEL [tool1] [tool2]`, the optional brackets naming analysis tools like coccinelle or smatch. The `Assisted-By: Name <email>` form used in other projects is formally invalid here. `Signed-off-by:` is the human's DCO certification — the author adds it themselves (`git commit --signoff`); never generate or alter it.

**Rerolls answer everything first.** A new version goes out only after every comment on the previous one has a reply in the old thread, and never while that discussion is still live.

## 2. Recipients

```bash
git format-patch --output-directory /tmp/series -v2 --cover-letter <base>..HEAD
scripts/get_maintainer.pl /tmp/series/*.patch
```

- **To:** the maintainers get_maintainer.pl lists for the touched files. **Cc:** the lists it names (the subsystem list is mandatory; `linux-kernel@vger.kernel.org` as archive Cc), plus the named reviewers (`R:` entries).
- **On a reroll, Cc additionally includes every person who commented on any previous version.** Dropping someone from Cc between versions is bad form and gets noticed.
- Review happens on the list — never mail a maintainer privately about an ordinary patch. The exceptions are security@kernel.org for embargoed vulnerabilities and `Cc: stable@vger.kernel.org` **as a tag line in the sign-off area** (not a mail header) for fixes that should reach stable kernels.

## 3. Format

- Subject prefix names the target tree where the subsystem requires it: netdev uses `[PATCH net]` for fixes and `[PATCH net-next]` for features, lowercase (`git format-patch --subject-prefix="PATCH net-next"`). Other subsystems: check `Documentation/process/maintainer-*.rst` and the `P:` entry in MAINTAINERS before inventing a prefix. Unready work is `[RFC ...]`.
- Multi-patch series get a cover letter; keep a series at 15 patches or fewer and one logical change per patch.
- **The reroll changelog lives under the `---` scissors** — in the cover letter for a series, under the `---` of the single patch otherwise — so git drops it on apply. It lists what changed per version and links the previous posting: `v1: https://lore.kernel.org/r/<message-id>/`. A reroll resends the entire series, not just the changed patches.
- **Carry received tags forward:** `Reviewed-by:`, `Acked-by:`, `Tested-by:` given on the list for unchanged patches are added by you to the next version. Tags other than `Cc:`, `Reported-by:`, and `Suggested-by:` are never invented — they require the named person to have actually offered them.

## 4. Mechanical checks

```bash
./scripts/checkpatch.pl --strict /tmp/series/*.patch
```

Zero warnings on every patch. checkpatch is nearly a no-op on the cover letter ("0 lines checked") — its prose is reviewed by hand against the content gates above. Build-test the series before sending; a patch that was not built or tested must say so explicitly.

## 5. Timing

- At least 24 hours between versions of the same series — reviewers span time zones. But not weeks either: context evaporates.
- netdev closes net-next during the merge window; feature patches wait for it to reopen (status page is linked from `Documentation/process/maintainer-netdev.rst`).

## 6. Send

```bash
git send-email --confirm=never \
    --to "maintainer1@example.com,maintainer2@example.com" \
    --cc "netdev@vger.kernel.org,linux-kernel@vger.kernel.org,reviewer@example.com" \
    /tmp/series/*.patch
```

No `--in-reply-to` — a version threads to itself via the cover letter, never to the previous version or any other thread.

Show the user the full cover letter, one representative patch mail, and the recipient list, and get an explicit OK before sending — the list is public and archived forever. After sending, note the new thread's Message-ID for lkml:patch-status.
