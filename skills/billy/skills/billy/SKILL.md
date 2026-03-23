---
name: billy
description: "Where's the proof, Billy?" — stop and prove a claim with deep investigation.
argument-hint: "<claim to prove>"
---

Where's the proof, Billy? We need proof!

Someone made a claim. Stop everything and investigate. No proof — no trust.

## Input

The argument is a claim that needs verification. Examples:

- `/billy "the runner is dead"`
- `/billy "this endpoint returns 500 on empty body"`
- `/billy "the migration broke prod"`
- `/billy "node memory is leaking"`

## Rules

1. **Do NOT take the claim at face value.** Assume nothing. Verify everything.
2. **Do NOT stop at the first piece of evidence.** Keep digging until you have a conclusive answer.
3. **Do NOT suggest — investigate.** Run commands, read logs, check code, query APIs. Produce evidence.
4. **Do NOT fix anything.** This is investigation only. Report findings, never apply changes.

## Process

Launch an Agent (model: `opus`) to perform the investigation. The agent must:

### Phase 1: Understand the claim

Parse the assertion. Identify:

- **Subject**: what system/component/process is involved
- **Predicate**: what is being claimed about it (dead, broken, leaking, failing, etc.)
- **Implicit scope**: timeframe, environment, context from the current conversation

### Phase 2: Gather evidence

Use every available tool to collect evidence. Prioritize direct observation over inference:

- **Processes and services**: `ps`, `systemctl status`, `docker ps`, `kubectl get pods`, health endpoints
- **Logs**: application logs, system logs, journal, container logs, `dmesg`
- **Code and config**: read source code, check recent changes (`git log`, `git diff`), review config files
- **Network**: `curl` endpoints, check connectivity, DNS resolution, port availability
- **Resources**: disk space, memory, CPU, file descriptors, connection pools
- **External systems**: CI/CD status (`gh run list`), monitoring dashboards, database state
- **History**: git blame, recent deploys, recent config changes, cron jobs

Collect at least 3 independent pieces of evidence before forming a conclusion.

### Phase 3: Attempt to reproduce

If the claim describes a failure or behavior:

- Try to reproduce it directly
- Check if it is currently happening or happened in the past
- Determine if it is intermittent or permanent

### Phase 4: Verdict

Present findings structured as:

```text
## Claim: "<original assertion>"

## Verdict: CONFIRMED / REFUTED / INCONCLUSIVE

## Evidence

1. [source] finding
2. [source] finding
3. [source] finding
...

## Timeline (if applicable)

- HH:MM — event
- HH:MM — event

## Root cause (if confirmed)

What specifically caused or is causing the observed behavior.

## What was NOT checked (and why)

List anything you could not verify and the reason (no access, not applicable, etc.)
```

## Important

- **Maximum depth**: do not cut corners. Check everything that can be checked.
- **No assumptions**: if you cannot verify something, say so explicitly.
- **Read-only**: never modify, restart, delete, or fix anything. Observe only.
- **Time-bound**: if investigation exceeds 5 minutes of active work with no progress, report what you have and list what remains unchecked.
