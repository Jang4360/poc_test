# Exception Checklist

Use this file to force implementation and validation to cover failure behavior, not only the happy path.

## Minimum failure-path lenses

- Input validation: malformed payload, unsupported format, missing required field
- Empty state: no data, first-run state, optional relation missing
- Not found and stale reference: deleted resource, stale ID, expired link
- Auth and permission: unauthenticated, unauthorized, downgraded role, revoked access
- Conflict and idempotency: duplicate request, double submit, retry after partial success
- External dependency failure: timeout, network error, upstream 5xx, partial downstream success
- Concurrency and stale state: race condition, optimistic update mismatch, overlapping edits
- Rate, quota, or limit: throttling, capacity ceiling, maximum size/count exceeded
- Recovery path: retry guidance, fallback state, rollback, resumable action
- Observability: actionable error message, log signal, metric, trace, or alertability

## Operating rule

- Planning should mention the highest-risk failure paths for each workstream.
- Implementation should handle or explicitly defer the applicable failure paths.
- Review should check whether the code actually enforces the intended failure behavior.
- QA should test the real user or operator experience for the applicable failure paths.
- Done means the highest-risk exception paths are either validated or recorded as explicit accepted risk.
