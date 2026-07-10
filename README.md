# rollout-guard

Watches a deployment's health window right after a release, auto-remediates known failure signatures (rollback, restart, scale), and hands unknown ones to Claude for classification. Dry-run by default, every decision audited.

## Why

Most release failures repeat. Error-rate spike after deploy, crash loop, OOM kill: the on-call runs the same three kubectl commands every time, 20 minutes after the page. rollout-guard encodes those responses as rules so the fix lands in seconds, and keeps a JSONL audit trail so you can prove what it did and why. Signatures no rule explains are escalated, optionally with an LLM classification attached to the page, instead of guessed at.

## Quickstart

```bash
pip install git+https://github.com/gerardrecinto/rollout-guard
rollout-guard check --metrics examples/metrics_failing.json --rules examples/rules.json --deployment api --namespace prod
rollout-guard report
```

Output:

```
verdict: failing (3 findings)
  [dry-run] error-spike -> rollback: kubectl -n prod rollout undo deployment/api
  [dry-run] latency-regression -> restart: kubectl -n prod rollout restart deployment/api
```

Three findings, two actions: `crash-loop` also demanded a rollback and was collapsed into the first one.

Nothing runs until you pass `--execute`. Add `--llm-fallback` (with `ANTHROPIC_API_KEY` set) to classify degraded windows no rule explains.

## How it works

```
 metrics.json ──┐
                ├─► Window ──► rule engine ──► verdict ──► remediation planner ──► kubectl
 pod logs ──────┘                  │                              │
                                   │ no rule matched              ├─► audit trail (JSONL)
                                   ▼                              │
                             Claude classifier ───────────────────┘
                             (suggests, never executes)
```

- **signals.py** ingests metric samples (Prometheus/CloudWatch export shape) and log lines into a window.
- **rules.py** evaluates known failure signatures: metric thresholds and log patterns, each mapped to one action from a closed set (`rollback`, `restart`, `scale`, `escalate`).
- **remediate.py** plans one command per action, collapses duplicates, executes worst-severity first, and appends every decision to the audit trail. Restart counters are compared as deltas across the window, not absolutes, so a pod with old restarts doesn't trigger a false rollback.
- **llm.py** is the fallback for unknown signatures. Its suggestion is constrained to the same closed action set, audited, and never executed automatically.

## Rules

```json
{"name": "error-spike", "action": "rollback", "metric": "error_rate", "threshold": 0.05}
{"name": "oom-kill", "action": "scale", "log_pattern": "OOMKilled"}
```

`severity` defaults to `failing` (exit code 1, remediation planned). Set `"severity": "degraded"` for symptoms that warrant a restart but not a page.

## Safety model

1. Dry-run is the default. `--execute` is an explicit opt-in per invocation.
2. Actions are a closed set. There is no path from a rule file or an LLM response to an arbitrary shell command.
3. The LLM only ever suggests. Its output is validated against the allowed action set and written to the audit trail for the on-call.
4. One action per type per window. Two rules both demanding rollback produce one rollback.
5. Everything is audited, including dry runs and escalations, as replayable JSONL.

Design reasoning in [docs/adr-001-safety-boundaries.md](docs/adr-001-safety-boundaries.md).

## Development

```bash
pip install pytest && pytest -q   # 14 tests, stdlib-only runtime, no dependencies
```
