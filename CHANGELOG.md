# Changelog

## v1.1.0 - 2026-08-20

### Fixed
- `scale` action always constructed `kubectl scale --replicas=2` regardless of the actual failure; the one code path meant to set a real target (rule `metric: "replicas"`) crashed `evaluate()` before it could ever be reached, since `replicas` isn't a metric sample field. Replaced with an explicit `scale_to` field on the rule that never goes through metric evaluation.
- `llm.py`'s docstring described an `--allow-llm-actions` opt-in that was never implemented; the LLM path has never had an execution flag. Reworded to match actual (and ADR-001's documented) behavior: the suggestion is audited, never executed.

### Added
- `rollout-guard validate --rules rules.json`: checks rule definitions for an unknown metric name, a metric with no threshold, or a duplicate rule name, without needing a live metrics window. Catches the class of bug above before a real check run.

## v1.0.0 - 2026-07-10

### Added
- Rule engine for known failure signatures: metric thresholds (error rate, p99 latency, restart deltas, CPU/mem) and log patterns, each mapped to a closed action set.
- Remediation planner and executor: rollback, restart, scale via kubectl; dry-run by default; duplicate actions collapsed; worst severity first.
- Append-only JSONL audit trail covering dry runs, executions, escalations, and LLM classifications, plus a `report` summary command.
- Claude fallback classifier for degraded windows with no matching rule; suggestion-only, validated against the allowed action set.
- CLI (`rollout-guard check | report`) with CI-gate exit codes; 14 pytest tests; stdlib-only runtime.
