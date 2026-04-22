---
name: plan-eng
description: Force architecture, data flow, failure modes, trust boundaries, and test strategy into the open before implementation.
---

# plan-eng

## purpose

Turn product intent into an execution plan that engineers and QA can actually follow.

## when to use

- After the product wedge and scope are understood
- Before large implementation work
- When a change touches architecture, external systems, state, or security boundaries

## inputs

- `.ai/PLANS/current-sprint.md`
- Latest relevant files under `docs/PRD/`, `docs/ERD/`, and `docs/API/` when they exist
- `.ai/ARCHITECTURE.md`
- `.ai/DECISIONS/`
- `.ai/EVALS/failure-patterns.md`
- Relevant ADRs or incidents if they exist

## procedure

1. Read the latest relevant files in `docs/PRD/`, `docs/ERD/`, and `docs/API/` first and treat them as the primary source for interfaces, data contracts, and domain boundaries.
2. Map the proposed flow: trigger, data movement, state changes, and external boundaries.
3. Split the work into executable workstreams, preferably by domain, API surface, UI slice, job, or operational boundary.
4. Define success criteria and a verification strategy for each workstream, not just for the request as a whole.
5. Identify failure modes, race conditions, stale state risks, and trust boundaries.
6. Read `.ai/DECISIONS/` and keep the plan aligned with any architecture or product decisions already recorded there.
7. Detect whether the repository already has a usable app framework; if it does not, force a separate setup workstream before feature work.
8. For spec-driven work, keep subplans anchored to cited docs; for change-driven work, restate the requested behavior and derive workstreams from impacted boundaries instead of inventing one giant plan.
9. Document implementation constraints, subplan boundaries, and open questions in `.ai/PLANS/current-sprint.md` and the relevant subplan files.
10. Update `.ai/ARCHITECTURE.md` or draft an ADR when the system shape changes.

## outputs

- Engineering review notes
- Data flow and failure mode summary
- Trust boundary notes
- Test strategy
- Workstream split with per-workstream success criteria

## escalation rules

- Escalate if the architecture depends on assumptions that are not yet validated.
- Escalate if production risk is high and no rollback or monitoring path exists.

## handoff rules

- Hand off to `plan-design` if UX states still need clarification.
- Hand off to build skills once architecture and test strategy are explicit enough to execute.
