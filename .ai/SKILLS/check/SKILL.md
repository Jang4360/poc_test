---
name: check
description: Run review and user-flow validation as one explicit gate after implementation, in the same host or by handoff.
---

# check

## purpose

Make validation a first-class stage output instead of an optional follow-up after coding.

## when to use

- After `implement-feature`, `fix-bug`, `refactor-module`, or `write-test`
- When the same AI host should review and QA its own change under an explicit gate
- When implementation and validation happen in different hosts and a durable handoff is needed
- When code review and verification should stay in one combined gate instead of being split into separate top-level commands

## inputs

- Current diff or changed files
- `.ai/PLANS/current-sprint.md`
- `.ai/EVALS/exception-checklist.md`
- Relevant tests, runbooks, and acceptance criteria
- Optional handoff brief such as `scripts/review-brief.sh`

## procedure

1. Decide the validation route: same-host validation or cross-host handoff. If validation will move across hosts, generate the brief with `scripts/review-brief.sh` as part of this step instead of expecting the user to remember the script manually.
2. Derive a small validation matrix from the plan and `.ai/EVALS/exception-checklist.md`: happy path, highest-risk edge case, highest-risk failure path, and recovery behavior.
3. Run the intent of `review` and capture correctness, maintainability, exception-handling, and missing-test findings as one part of this combined validation pass.
4. Run `design-review`, `security-review`, or `benchmark` when the change shape requires them.
5. Run `qa` or `qa-only` for the highest-value real user flows and the failure or recovery paths that matter for release confidence.
6. Consolidate findings, accepted risks, tested exception paths, and release readiness in `.ai/PLANS/current-sprint.md`.
7. If validation loops through the same failing path, run `scripts/record-retry.sh <signature>`. If it opens the circuit breaker, immediately run the intent of `learn` instead of leaving the escalation as a manual reminder.

## outputs

- Consolidated validation summary
- Review findings and QA evidence
- Tested exception-path summary
- Ship-readiness note with explicit open risks
- Cross-host handoff brief when validation must move to another runtime

## escalation rules

- Escalate if no credible validation path exists in the current host or across available hosts.
- Escalate if unresolved high-severity findings remain and no owner is assigned.

## handoff rules

- Hand off to `ship` when validation is green or accepted-risk status is explicit.
- Hand off to `implement-feature`, `fix-bug`, or `refactor-module` when validation fails with actionable fixes.
- Run the intent of `learn` immediately in the same pass when the circuit breaker opens; this is not a deferred handoff but an inline continuation.
