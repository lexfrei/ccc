---
name: shrink
description: Find the guilty few among many boolean suspects with group testing (split-half, delta debugging) instead of toggling one thing at a time. TRIGGER — invoke when 8+ independently toggleable suspects (feature flags, config lines, env-var deltas, patches, plugins, extensions, imports) hide an expected single culprit or small set and each run is expensive; the moment the plan looks like "disable them one by one" this replaces it. DO NOT TRIGGER for ranking several contributing factors (use the taguchi skill), for ordered history (git bisect does this natively), for suspects that cannot be toggled independently, or for cheap runs.
argument-hint: "[list of suspects]"
---

When one culprit hides among n toggles, testing halves finds it in log2 n to 2·log2 n runs instead of n — the upper end pays for testing the second half after a pass: 32 flags → 5-10 runs, 1000 config lines → 10-20. The method is group testing; delta debugging is its generalization to multiple culprits.

Vocabulary: each suspect has a **suspect** value (as in the failing config) and an **innocent** value (as in the known-good one). "Test a subset" means: subset at suspect values, everything else innocent, run, record fail/pass.

## Step 0 — baselines, always first

Two runs before any search:

- **All-innocent must pass.** If it fails, the difference between good and bad is not in the suspect list — stop and widen the list.
- **All-suspect must fail.** If it passes, the culprit interacts with something outside the list (environment, timing, data) — stop, the search space is wrong.

Skipping these two runs is how a whole binary search gets spent chasing a phantom.

## Step 1 — split-half for a single culprit

Split the suspects in half, test one half. Fails → culprit inside, recurse into it. Passes → test the other half; fails → recurse there. Repeat to one suspect.

Both halves passing is a finding, not an error: the failure needs suspects from both halves at once. Re-split along a different boundary first (group by subsystem instead of by list order); if every split shows the same pattern, it is a genuine interaction — take the surviving suspects to the taguchi skill and rank them as factors.

## Step 2 — delta debugging for multiple culprits

When more than one culprit is plausible, split-half alone can chase the first one and lose the rest. The ddmin scheme:

1. Partition the current suspect set into k subsets (start k=2).
2. Test each subset alone, and each complement (everything except that subset).
3. A failing subset → it becomes the new suspect set, back to k=2.
4. A failing complement → the removed subset was irrelevant, drop it, keep k.
5. Nothing fails → double k (finer granularity); k above the set size means every remaining suspect is needed — that set is the answer.

## Step 3 — flaky bugs: pass and fail are not symmetric

A failure is certain — the bug fired. A pass is probabilistic — the bug may just not have fired this time. A false pass sends the search into the wrong half and the error compounds silently. So repeat only the passing verdicts: before trusting a pass, rerun it N times, N ≥ ln(0.05)/ln(1−p) for repro probability p observed on the all-suspect baseline (p=0.5 → 5, p=0.3 → 9, p=0.1 → 29). A run that fails once anywhere in the repeats is a fail.

## Step 4 — confirm

Same discipline as the taguchi skill: culprit alone at suspect value must fail; everything-but-culprit at suspect values must pass. If the second run fails, there is another culprit still in the dropped remainder — resume step 2 on it.
