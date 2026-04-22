---
name: qa
description: Test real user flows as the QA step inside `check`, or produce a narrow QA report when used directly.
---

# qa

## purpose

Validate that the implemented change works in the way a user experiences it, not only in isolated tests.

## when to use

- Inside `check` as the default user-flow check
- Before shipping when a separate QA pass is intentionally needed
- When the team needs a realistic flow-level confidence check without a broader validation report

## inputs

- Current change and plan context
- `.ai/EVALS/smoke-checklist.md`
- `.ai/EVALS/exception-checklist.md`
- Review findings and open risks

## procedure

1. Identify the real flows most likely to matter for the release.
2. Build a compact QA matrix for those flows: happy path, empty or missing state, invalid input, permission or auth failure, dependency failure, conflict or retry, and recovery path as applicable.
3. Execute the matrix and note failures, confusing states, incorrect exception handling, and hidden operational risks.
4. Produce a bug and risk report in `.ai/PLANS/current-sprint.md`, including which exception paths were tested and which remain unverified.
5. Update `.ai/EVALS/scorecard.md` if the test outcome changes release readiness.
6. Feed repeatable gaps into `.ai/EVALS/failure-patterns.md` or memory files.
7. If validation is stuck in the same failing path, run `scripts/record-retry.sh <signature>`. If it opens the circuit breaker, stop the loop and hand off to `learn`.

## outputs

- Flow-based QA report
- Bug list
- Risk list
- Tested exception-path matrix
- Updated readiness notes

## escalation rules

- Escalate if the release depends on flows that cannot be tested credibly.
- Escalate if high-severity bugs remain unresolved.

## handoff rules

- Hand off to `ship` only after critical findings are addressed or explicitly deferred.
- Hand off to `check` when QA is one part of a broader validation pass.
- Hand off to `learn` or `retro` if QA exposed a recurring failure pattern.
