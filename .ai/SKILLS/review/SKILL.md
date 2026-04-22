---
name: review
description: Produce a narrow code-review report or act as the code-review step inside `check`.
---

# review

## purpose

Inspect the branch like a strong human reviewer would, with emphasis on what happy-path implementation tends to miss.

## when to use

- Inside `check` as the code-review step
- When a narrow code-review-only report is intentionally preferred
- When a risky change needs a hard correctness pass without a full validation gate

## inputs

- Current diff or changed files
- Optional runtime-generated review handoff such as `scripts/review-brief.sh`
- `.ai/PLANS/current-sprint.md`
- `.ai/EVALS/exception-checklist.md`
- Relevant tests, architecture notes, and incidents

## procedure

1. Review the intended scope and compare it with the actual change.
2. Look for correctness issues, maintainability problems, missing tests, hidden risks, and weak exception handling.
3. Cross-check any runtime handoff summary against the actual diff instead of trusting it blindly.
4. Check whether the code handles the applicable failure paths credibly: invalid input, empty state, dependency failure, conflict, timeout, stale state, permission failure, and recovery behavior.
5. Record findings and open questions in the sprint artifact.
6. Make sure unresolved items are visible to QA and release stages.

## outputs

- Review findings
- Risk summary
- Missing-test or maintainability notes
- Exception-handling findings

## escalation rules

- Escalate if the implementation diverged materially from the approved plan.
- Escalate if unresolved correctness risks remain high.

## handoff rules

- Hand off to `check` when the change still needs the combined validation gate.
- Hand off to `ship` only after high-risk findings are resolved or explicitly accepted.
