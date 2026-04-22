# Guards

## Purpose

Define harness-level safeguards that should run before risky automation proceeds.

## TDD guard

- If production implementation files change, check whether meaningful related tests changed too.
- Default policy in this template: block production edits before execution when no related test work exists yet, then warn again after edits if needed.
- Exceptions should be explicit and rare.
- Entry point: `scripts/check-tdd-guard.sh`

## Dangerous command guard

- Block obviously destructive commands before execution whenever possible.
- Default deny examples: `rm -rf`, `git reset --hard`, force push, destructive bulk deletes, irreversible environment mutations.
- Keep the rule set short and conservative.
- Entry point: `scripts/check-dangerous-command.sh`

## Circuit breaker

- If the same or effectively equivalent failure repeats several times in a short window, stop retrying and require a strategy change.
- Default threshold: 3 equivalent failures in 30 minutes.
- Record retries in `.ai/EVALS/retry-log.jsonl`.
- `scripts/record-retry.sh` is the default entrypoint because it logs the failure and checks the breaker immediately. Use `scripts/check-circuit-breaker.sh` directly only when a workflow needs a read-only preflight.
- Entry point: `scripts/check-circuit-breaker.sh`

## Operating rule

Guards should remain deterministic, fast, and easy to wire into host-specific hooks later. They are enforcement helpers, not the canonical source of policy by themselves. Policy remains documented in `.ai/`.
