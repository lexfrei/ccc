# become

Session role switches for Claude Code. Each skill in this plugin turns the current session into a specific role that holds for the rest of the session. Roles are invoked as `/become:<role>`, and new roles are added as sibling skills under `skills/`.

## Installation

```bash
/plugin marketplace add lexfrei/ccc
/plugin install become@claude-code-companions
```

## Skills

### `/become:manager`

Turns the session into the manager of a subagent fleet instead of an executor: it briefs teammates, delegates whole loops, approves their output inside the delegated scope, integrates results by ground truth, and reports upward in short digests.

What the role enforces:

- **Entry gates** — first, whether the task needs a team at all (a fleet costs several times a single session and pays off only for context isolation, real parallelism, or specialization); second, that the manager seat runs on the strongest available model while teammates get an explicit cost-scaled model per task.
- **Decomposition** — split at context boundaries rather than work types, disjoint file ownership per teammate, tasks sized to self-contained deliverables.
- **Team topology** — one standing investigator per session, fix-review loops owned end-to-end by the implementing teammate (one gate at a time), one-shot workers killed after their work is saved, teammates retired at the first opportunity rather than reused (a "finished" report is about the task, not the agent's exit — only a verified stop frees the seat), capped concurrency.
- **Briefing** — success criteria, essential context only, an explicit verification requirement (for code: a clean Codex review plus two consecutive `/branch-review` LGTMs on the same commit, reset only by a false claim or a code defect), a bounded report format, a comms contract that treats the channel as lossy in both directions, hard boundaries; plan approval for risky workstreams.
- **Integration** — frozen SHAs pushed at freeze time, push only an explicitly stated final SHA, run the session's own quality gate on the assembled result, verify by ground truth rather than notifications, add an adversarial blackbox verifier when stakes warrant it.
- **Findings bookkeeping** — every out-of-scope finding gets a home (an issue, a registry entry, or a written disposition) before its gate closes; a defect-class registry the manager reads before approving techniques.
- **Approval boundary** — agent output inside the delegated scope is approved by the manager; anything leaving it (messages to people, other repositories, external services) waits for the user.

## Extending

Add a new role as `skills/<role>/SKILL.md` inside this plugin and list it in the plugin description. It becomes available as `/become:<role>` with no other changes.
