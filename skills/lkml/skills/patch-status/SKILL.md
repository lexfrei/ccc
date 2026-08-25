---
name: patch-status
description: Check the acceptance state of a Linux kernel patch in patchwork and decide the correct next action — wait, repost, or ask. TRIGGER — invoke when the task is to find out whether a submitted kernel patch or series was accepted, rejected, or needs changes, or whether it is time to ping the maintainers. DO NOT TRIGGER for reading the review discussion itself (use lkml:lore) or for sending anything (use lkml:reply or lkml:submit).
argument-hint: "[Message-ID | patchwork URL]"
---

Patchwork tracks what maintainers will do with a patch; the mailing list tracks what people said about it. Check both before concluding anything: a thread with zero replies can still be `accepted`, and a thread full of praise can sit at `changes-requested`.

## Query by Message-ID

```bash
curl --silent "https://patchwork.kernel.org/api/1.2/patches/?project=netdevbpf&msgid=<message-id>" | jq '.[0] | {state, delegate: .delegate.username, web: .web_url}'
```

- `<message-id>` is bare, without angle brackets — the ID of a **patch mail** (`1/N`, `2/N`, ...). Cover letters are not patches; querying a `0/N` ID returns an empty list.
- `project=netdevbpf` covers netdev and bpf. Other kernel subsystems have their own project slugs on the same instance — list them via `https://patchwork.kernel.org/api/1.2/projects/` and match by `list_email`. Some subsystems do not use patchwork at all; an empty result for every patch of a series means look at the thread and the maintainer's git tree instead.
- Other projects run their own instances with the same API (U-Boot lives on `patchwork.ozlabs.org`, `project=uboot`).

## What the states mean

| state | meaning | your move |
| --- | --- | --- |
| `new` | in the queue, nobody triaged it | wait |
| `under-review` | a maintainer is looking | wait |
| `changes-requested` | review asked for changes | answer every comment in-thread, then new version as a new thread |
| `superseded` | a newer version of the series replaced it | check the newest version instead |
| `accepted` / `queued` | applied to the maintainer tree | done; netdev also sends an "applied" mail to the thread |
| `rejected` / `not-applicable` | will not be taken as-is | read the thread for the reason before doing anything |
| `deferred` / `awaiting-upstream` | parked on something external | find what it waits for in the thread |

`delegate` set to a maintainer (e.g. `netdev`) means the series is in that queue — a good sign, not a request for action.

A reply in the thread reading `pw-bot: cr` (or `pw-bot: changes-requested`) is a bot command that moved the series to `changes-requested`. Treat it exactly like the state: the next posting is a new version in a new thread, never a reply with fixed patches.

## When silence means "wait" and when it means "act"

Kernel review runs on timers, and pinging early reads as pressure:

- netdev moves in days; most other subsystems in one to two weeks; anything overlapping a merge window slows down further.
- Wait at least one week of silence before nudging anywhere, and longer around a merge window. For slower trees (staging, individual driver maintainers), two to three weeks of silence is normal.
- A bare "ping" or "bump" reply is explicitly called rude in the netdev process docs. A nudge must carry content: state your understanding of where things stand and ask one concrete question — "X asked for A in v2 and that discussion stalled; should I go with B and repost?".
- If the state is `changes-requested`, silence is on your side of the net: nothing will happen until a new version is posted.

Report findings to the user as: state, who (if anyone) replied since the last check, and the single recommended next action.
