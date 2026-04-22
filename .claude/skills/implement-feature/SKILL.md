---
name: implement-feature
description: Build an approved feature against the recorded plan instead of improvising from the latest prompt.
---

# implement-feature

## purpose

Execute planned feature work while keeping implementation tied to durable artifacts.

## when to use

- After the relevant planning reviews are complete
- When the work is a net-new feature or capability

## inputs

- Approved plan in `.ai/PLANS/current-sprint.md`
- `.ai/ARCHITECTURE.md`
- `.ai/EVALS/exception-checklist.md`
- Relevant tests and runbooks

## procedure

1. Restate the approved feature scope and non-goals.
2. Before mutating shell state, run `scripts/check-dangerous-command.sh "<command>"`. Before editing implementation files, run `scripts/check-tdd-guard.sh --mode pre <candidate paths>`.
3. Identify the failure assumptions that matter for the slice: invalid input, empty state, missing dependency, conflict, permission problem, timeout, stale state, and recovery path as applicable.
4. Implement the smallest coherent slice that satisfies the plan and handles the applicable failure assumptions explicitly instead of falling back to generic crashes or silent failure.
5. Add or update tests as the feature is built. Cover the intended path plus the highest-risk edge and failure paths for the slice.
6. If a failure path is intentionally deferred, record it as explicit risk or accepted gap in `.ai/PLANS/current-sprint.md` instead of leaving it implicit.
7. If the same implementation attempt fails repeatedly, run `scripts/record-retry.sh <signature>`. If it opens the circuit breaker, stop retrying the same path and hand off to `learn`.
8. Record any material plan deviation in `.ai/PLANS/current-sprint.md`.
9. Update architecture or runbooks if the change alters system behavior, error contracts, or operator recovery steps.

## outputs

- Feature implementation
- Tests for intended behavior
- Explicit failure-path handling or recorded accepted gap
- Updated sprint artifact if the build revealed meaningful changes

## escalation rules

- Escalate if implementation requires changing the approved wedge, trust boundary, or release plan.
- Escalate if missing infrastructure or unclear ownership blocks progress.

## handoff rules

- Hand off to `check` once the implementation is coherent.
