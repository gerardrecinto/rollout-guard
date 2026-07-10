# ADR 001: Safety boundaries for auto-remediation

Status: accepted

## Context

An auto-remediation tool that can run kubectl against production has a worst case of making an incident worse, faster. The blast radius question drives the design more than any feature.

## Decision

1. **Dry-run by default.** The tool must be safe to point at production on day one. Execution is opt-in per invocation (`--execute`), never a config-file default that survives copy-paste.

2. **Closed action set.** Rules map to `rollback | restart | scale | escalate` only. Rule files are data, not code: a compromised or fat-fingered rules.json cannot produce `kubectl delete namespace`.

3. **LLM suggests, never executes.** The fallback classifier handles the long tail of unknown signatures, but its output is a labeled suggestion on the audit record. Two reasons: LLM output is not deterministic enough to gate production actions on, and an unknown signature is by definition one we have no tested runbook for. When a suggestion proves right repeatedly, the human promotes it to a rule; that is the path from "LLM guess" to "automated response".

4. **Deltas over absolutes for counters.** Restart counts are compared across the observation window, not read as absolutes, so pre-existing restarts from last week's incident don't trigger a rollback of a healthy release.

5. **Audit everything.** Dry runs, executions, escalations, and LLM classifications all land in append-only JSONL. MTTR improvements are only trustworthy if you can replay what the tool saw and did.

## Consequences

- New remediation types require a code change, not just a rule edit. Accepted: that is the review gate working as intended.
- The LLM path adds latency (one API round trip) only on the unknown-signature path, where the alternative is a human context-switching for 20 minutes anyway.
- Exit codes make it composable as a CI/CD release gate: 0 = healthy or remediated-degraded, 1 = failing.
