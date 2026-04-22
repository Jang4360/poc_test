---
name: write-test
description: Add focused tests for behavior, edge cases, and failure modes that the current suite does not cover well enough.
---

# write-test

## purpose

Strengthen confidence around a behavior, regression, or boundary.

## when to use

- When implementation or review reveals missing coverage
- When a bug fix or refactor needs protection
- When a new plan includes critical edge cases

## inputs

- Target behavior or failure mode
- Existing test layout
- `.ai/EVALS/exception-checklist.md`
- Plan or review notes that describe what matters

## procedure

1. Define the exact behavior or risk the test must cover.
2. Prefer the smallest test that still exercises the real contract.
3. Cover the happy path plus the highest-risk edge and failure paths that apply to the contract.
4. Prefer explicit assertions for error contracts, retries, empty states, stale state, permission failure, or dependency failure when those are part of the risk.
5. Record important uncovered gaps in `.ai/PLANS/current-sprint.md` if they remain.

## outputs

- New or improved test coverage
- Explicit failure-path coverage where it matters
- Explicit note about what is still untested if applicable

## escalation rules

- Escalate if the code is too coupled to test without structural changes.
- Escalate if a test would be low-signal compared with a higher-level verification path.

## handoff rules

- Hand off to `check` when the test work is part of a broader change that still needs review or flow validation.
- Hand off to `review` or `qa` directly only when a narrower one-stage check is intentionally sufficient.
