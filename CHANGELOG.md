# Changelog

## v1.0.0 - 2026-07-10

### Added
- Rule engine for known failure signatures: metric thresholds (error rate, p99 latency, restart deltas, CPU/mem) and log patterns, each mapped to a closed action set.
- Remediation planner and executor: rollback, restart, scale via kubectl; dry-run by default; duplicate actions collapsed; worst severity first.
- Append-only JSONL audit trail covering dry runs, executions, escalations, and LLM classifications, plus a `report` summary command.
- Claude fallback classifier for degraded windows with no matching rule; suggestion-only, validated against the allowed action set.
- CLI (`rollout-guard check | report`) with CI-gate exit codes; 14 pytest tests; stdlib-only runtime.
