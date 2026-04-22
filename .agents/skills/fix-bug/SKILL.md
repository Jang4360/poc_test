---
name: fix-bug
description: Reproduce a bug, identify the actual failure mechanism, land the smallest safe fix, and add regression coverage.
---

# fix-bug

## purpose

Resolve defects without treating the first apparent symptom as the root cause.

## when to use

- For confirmed bugs, regressions, and production issues
- When a failure needs a bounded fix and regression test

## inputs

- Bug report or observed failure
- Relevant sprint, debugging memory, and incident context
- `.ai/EVALS/exception-checklist.md`
- Existing tests and logs

## procedure

1. Reproduce the bug or define the strongest available reproduction path.
2. Confirm the root cause instead of patching the nearest symptom.
3. Before mutating shell state, run `scripts/check-dangerous-command.sh "<command>"`. Before editing implementation files, run `scripts/check-tdd-guard.sh --mode pre <candidate paths>`.
4. Identify the adjacent exception paths that could trigger the same class of bug again: empty state, retry, double submit, stale state, permission issue, timeout, or malformed input as applicable.
5. Apply the smallest safe fix that addresses the actual failure and closes the nearby repeat path where reasonable.
6. Add regression coverage for the confirmed bug plus the highest-risk adjacent failure path.
7. If the same fix path fails repeatedly, run `scripts/record-retry.sh <signature>`. If it opens the circuit breaker, stop retrying the same path and hand off to `learn`.
8. If the bug exposed a reusable lesson, update `.ai/MEMORY/debugging.md` or `.ai/MEMORY/incidents.md`.

## outputs

- Reproduction note
- Root cause summary
- Bug fix
- Regression test

## escalation rules

- Escalate if the bug is not reproducible and evidence is weak.
- Escalate if the fix would materially change product scope or architecture.

## handoff rules

- Hand off to `check` for risk checking and flow verification.
