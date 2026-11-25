# Cases

Maintenance: at most five cases; a new incident replaces a case and never becomes a rule. Any addition to `SKILL.md` or to these cases names a deletion of at least the same size in the same commit.

## 1. Dependency knowledge in a core component

- **In the PR.** A generic ownership walker learned one provider's kinds and labels, so that virtual machines created without an ownerReference resolved to their application.
- **Why it was accepted.** The missing ownerReference was upstream behaviour and the bridge was small; the reviewer asked for tests on its guard, which made the provider branch permanent.
- **What it was.** Provider knowledge in a package meant to know none. The alternative, a label from the chart that creates the machines, changes the node template: every worker pool rolls and existing machines need a migration. On cost, the original choice was defensible.
- **How it ended.** A later rework moved ownership to the chart label and paid that price.

## 2. A test over other components' files

- **In the PR.** A new API field with declarations for several applications, and a unit test that globbed other components' charts, matched templates by regexp and compared about seventy hand-typed values.
- **Why it was accepted.** The author's claims were true, the test was green, and an accepted design, approved by the same reviewer, prescribed it.
- **What it was.** A copy of other charts' defaults with no consumer yet, guarded by a test that detects change, not defects, and couples one package to the sources of others.
- **How it ended.** It was approved and merged; the maintainer later judged it the wrong thing fixed by the wrong mechanism.

## 3. The backup series

- **In the PR.** Each change in a backup driver added a wait, a refusal or an uncached read: hold the first backup until the rollout the driver itself triggered, key the archive prefix by instance, re-read the cluster after a restore.
- **Why it was accepted.** Each was small, tested, fixed a real failure, and was reasonable given the one before.
- **What it was.** From one PR, only one thing was visible: the change repaired the project's own previous step. The questionable decisions were two early ones, which none of the later diffs contained.
- **How it ended.** The pattern surfaced only when the series was read together, as a series review.

## 4. Simplification breaks too

- **In the PR.** Three cleanups in one day: removing a rule that looked dead; switching logic to key on a new label; replacing a regexp with template execution.
- **Why it looked right.** Each removed code or made it more uniform, and each looked like the proportionate change.
- **What it was.** The removal left an empty list that its consumer rejects. The label logic forgot objects created before the label existed. The template execution would have run tenant-supplied values in the management cluster.
- **How it ended.** All three were caught by tracing the sources to the wrong result or by running the change, not by asking what it was for.

## 5. The doubt that was wrong

- **In the PR.** A restore controller refused to proceed when it found an `-orig` volume left by an earlier restore job of the same name.
- **Why the reviewer doubted it.** The refusal looked like machinery guarding a collision the controller itself created; keying the suffix on the job's UID seemed to make it unnecessary.
- **What it was.** The suffix hash is 16 bits and `-orig` volumes accumulate; without the refusal, a collision deletes a live disk.
- **How it ended.** The rework that tried the simpler version found this, and the refusal stayed. The doubt was reproducible across runs and wrong; only execution refuted it.
