---
name: qa-only
description: Run the same real-flow validation as QA but stop at reporting instead of changing code.
---

# qa-only

## purpose

Provide an independent QA report without mixing testing and implementation in the same pass.

## when to use

- Inside `check` when an independent QA report is needed
- When a pure test report is preferred
- When code changes are blocked or should be separated from validation

## inputs

- Current change and release candidate context
- `.ai/EVALS/smoke-checklist.md`
- `.ai/EVALS/exception-checklist.md`
- Relevant review notes

## procedure

1. Select the highest-value flows for the release.
2. Build a narrow exception-path matrix for those flows: happy path, highest-risk failure path, and recovery path at minimum.
3. Execute them and collect evidence.
4. Report bugs, inconsistencies, risk areas, and untested exception paths in `.ai/PLANS/current-sprint.md`.
5. Update score or readiness notes if the report changes release confidence.
6. If the same blocked validation path repeats, run `scripts/record-retry.sh <signature>`. If it opens the circuit breaker, hand off to `learn`.

## outputs

- QA report without code changes
- Bug list and risk list
- Exception-path report

## escalation rules

- Escalate if high-severity issues are found and no owner is assigned.
- Escalate if the release cannot be judged without missing credentials, environments, or fixtures.

## handoff rules

- Hand off to `fix-bug`, `implement-feature`, or `ship` depending on the report outcome.
