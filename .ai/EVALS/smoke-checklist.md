# Smoke Checklist

Use this as the minimum real-flow checklist before release.

- Can a user start the primary flow without hidden setup?
- Can the user recover from a common failure or empty state?
- Do the highest-risk invalid input, timeout, not-found, and permission paths fail safely?
- Do key error states present actionable guidance?
- Do authentication, permissions, and trust boundaries behave as intended?
- Do logging, monitoring, or diagnostics capture the likely failure points?
- Did a human or agent verify the actual flow rather than only unit tests?
