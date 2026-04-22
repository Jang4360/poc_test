---
name: start
description: Build a change against the approved plan and carry it through validation before calling it ready.
---

# start

## purpose

Provide a single delivery entrypoint that does not stop at implementation when the user expects a validated result.

## when to use

- When the request should include implementation plus validation in one pass
- When the team wants the default build path to continue automatically into review and QA
- When same-host or cross-host validation should be explicit instead of ad hoc

## inputs

- Approved plan in `.ai/PLANS/current-sprint.md`
- `.ai/ARCHITECTURE.md`
- `.ai/EVALS/exception-checklist.md`
- Relevant tests, runbooks, and validation expectations

## procedure

1. Choose the build skill that fits the work: `implement-feature`, `fix-bug`, `refactor-module`, or `write-test`.
2. Before implementation closes, identify the highest-risk failure paths for this change using `.ai/EVALS/exception-checklist.md` and the current workstream plan.
3. Execute the build work against the approved plan and update tests as required, including meaningful failure-path coverage for the change.
4. As soon as the change is coherent, run the intent of `check` instead of stopping at a raw diff. Do not treat implementation alone as a completed result.
5. If validation finds actionable issues, apply the smallest credible fix and re-run `check`.
6. If the same delivery path keeps failing, run `scripts/record-retry.sh <signature>`. If it opens the circuit breaker, immediately run the intent of `learn` with the failure signature and current evidence instead of leaving the escalation as a manual next step.
7. Record the final validation status, blockers, accepted risks, tested exception paths, and any promoted learning in the sprint artifact.

## outputs

- Implemented change
- Validation evidence
- Explicit ready, blocked, or learn-next status
- Promoted learning when repeated failures forced a strategy change

## escalation rules

- Escalate if the approved plan is no longer valid enough to implement safely.
- Escalate if the delivery path depends on missing infrastructure, environments, or ownership.

## handoff rules

- Hand off to `ship` when the change is implemented and validated.
- Run the intent of `learn` immediately in the same pass when the circuit breaker opens; this is not a deferred handoff but an inline continuation.
- Hand off back to planning when validation reveals a scope or architecture mismatch.
