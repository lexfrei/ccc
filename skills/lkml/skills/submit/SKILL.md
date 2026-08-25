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
- **The reroll changelog lives under the `---` scissors** — in the cover letter for a series, under the `---` of the single patch otherwise — so git drops it on apply. One bullet per change, each attributed to the reviewer who asked for it, plus a link to the previous posting: `v1: https://lore.kernel.org/r/<message-id>/`. A reroll resends the entire series, not just the changed patches.
- **Carry received tags forward:** `Reviewed-by:`, `Acked-by:`, `Tested-by:` given on the list for unchanged patches are added by you to the next version. Tags other than `Cc:`, `Reported-by:`, and `Suggested-by:` are never invented — they require the named person to have actually offered them.

## 4. Mechanical checks

```bash
./scripts/checkpatch.pl --strict /tmp/series/*.patch
```

Zero warnings on every patch. checkpatch is nearly a no-op on the cover letter ("0 lines checked") — its prose is reviewed by hand against the content gates above. Build-test the series before sending; a patch that was not built or tested must say so explicitly.

Last check before send: grep every outgoing file for leftover placeholders — a TESTED stub, an unfilled changelog bullet, a TODO in the cover letter. A literal placeholder in a public posting is unrecallable.

## 5. Timing

- At least 24 hours between versions of the same series — reviewers span time zones. But not weeks either: context evaporates.
- Sends go out in batches, not a trickle: prepare everything first, send in one window. Pending replies (lkml:reply) ride the same window; they do not reset the 24-hour clock.
- netdev closes net-next during the merge window; feature patches wait for it to reopen (status page is linked from `Documentation/process/maintainer-netdev.rst`).

## 6. Send

```bash
git send-email --confirm=never \
    --to "maintainer1@example.com,maintainer2@example.com" \
    --cc "netdev@vger.kernel.org,linux-kernel@vger.kernel.org,reviewer@example.com" \
    /tmp/series/*.patch
```

No `--in-reply-to` — a version threads to itself via the cover letter, never to the previous version or any other thread.

Show the user the full cover letter, one representative patch mail, and the recipient list, and get an explicit OK before sending — the list is public and archived forever.

After the send, in the same session:

- Confirm delivery, not just submission: SMTP 250 per mail in the send output, then the thread appears at `https://lore.kernel.org/<list>/<message-id>/` within minutes.
- Record the new thread's Message-ID in the project's thread-tracking file (see lkml:lore) — lkml:patch-status queries start from it.
- If the project carries downstream copies of the mailed patches (distro backports and similar), the send is not finished until those copies are resynced to what was actually mailed and their reference links point at the new posting. How exactly is a per-project procedure — look for it in the project's own docs before improvising.
