---
name: refactor-module
description: Improve module structure, boundaries, or readability while preserving behavior and making architectural intent clearer.
---

# refactor-module

## purpose

Make a code area easier to maintain without changing product behavior.

## when to use

- When a module is too large, repetitive, or hard to reason about
- When architecture drift is slowing feature or bug work

## inputs

- Target module or boundary
- `.ai/ARCHITECTURE.md`
- Relevant tests and current failure patterns

## procedure

1. State what pain the refactor is addressing.
2. Identify the safe behavioral boundary that must not change.
3. Before mutating shell state, run `scripts/check-dangerous-command.sh "<command>"`. Before editing implementation files, run `scripts/check-tdd-guard.sh --mode pre <candidate paths>`.
4. Refactor incrementally with tests guarding expected behavior.
5. If the same refactor path fails repeatedly, run `scripts/record-retry.sh <signature>`. If it opens the circuit breaker, stop retrying the same path and hand off to `learn`.
6. Update architecture notes if the resulting boundaries become clearer or different.
7. Record notable patterns in `.ai/MEMORY/conventions.md` if reusable.

## outputs

- Refactored module
- Preserved or improved tests
- Updated architecture notes when relevant

## escalation rules

- Escalate if the refactor requires behavior changes disguised as cleanup.
- Escalate if test coverage is too weak to preserve confidence.

## handoff rules

- Hand off to `check` for maintainability and regression risk inspection.
