# Failure Patterns

## Purpose

Capture repeatable ways AI-assisted delivery can fail so planning, review, QA, and release skills can counter them.

## Starter patterns

- Shipping the first requested feature instead of the real product wedge
- Missing trust boundaries, data ownership, or failure modes in the plan
- Passing tests while real user flows still fail
- Shipping happy-path code while invalid input, empty state, timeout, stale state, or recovery paths still break
- Generic UI that technically works but weakens product clarity
- Skipping rollback preparation because the change looked small
- Editing production code without updating relevant tests
- Returning raw exceptions or silent failure instead of a user-safe or operator-safe error contract
- Brute-force retrying the same failing strategy instead of changing approach
- Hiding progress or risk state inside transient chat output instead of canonical artifacts
- Hard-coding one AI host as the only valid reviewer or validator and losing portability when the tooling mix changes
