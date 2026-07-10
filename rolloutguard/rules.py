"""Rule engine: known failure signatures mapped to verdicts and remediation actions.

A rule fires when its metric threshold is crossed or its log pattern appears
in the window. Anything degraded that no rule explains is an unknown
signature and gets escalated (optionally to the LLM classifier) instead of
auto-remediated.
"""

import json

VERDICT_HEALTHY = "healthy"
VERDICT_DEGRADED = "degraded"
VERDICT_FAILING = "failing"

ALLOWED_ACTIONS = ("rollback", "restart", "scale", "escalate")


class Rule:
    def __init__(self, name, action, metric=None, op="gt", threshold=None,
                 log_pattern=None, severity=VERDICT_FAILING):
        if action not in ALLOWED_ACTIONS:
            raise ValueError("unknown action: %s" % action)
        if metric is None and log_pattern is None:
            raise ValueError("rule %s needs a metric or log_pattern" % name)
        self.name = name
        self.action = action
        self.metric = metric
        self.op = op
        self.threshold = threshold
        self.log_pattern = log_pattern
        self.severity = severity


class Finding:
    def __init__(self, rule, evidence):
        self.rule = rule
        self.evidence = evidence

    def as_dict(self):
        return {"rule": self.rule.name, "action": self.rule.action,
                "severity": self.rule.severity, "evidence": self.evidence}


def load_rules(path):
    with open(path) as f:
        return [Rule(**row) for row in json.load(f)]


def _metric_value(window, rule):
    if rule.metric == "restarts":
        return window.total_restarts()
    return window.max(rule.metric)


def evaluate(window, rules):
    """Return (verdict, findings) for a window against known signatures."""
    findings = []
    for rule in rules:
        if rule.metric is not None:
            value = _metric_value(window, rule)
            crossed = value > rule.threshold if rule.op == "gt" else value < rule.threshold
            if crossed:
                findings.append(Finding(rule, {rule.metric: value, "threshold": rule.threshold}))
        if rule.log_pattern is not None:
            hits = window.log_matches(rule.log_pattern)
            if hits:
                findings.append(Finding(rule, {"log_pattern": rule.log_pattern,
                                               "matches": len(hits), "sample": hits[0]}))
    if any(f.rule.severity == VERDICT_FAILING for f in findings):
        return VERDICT_FAILING, findings
    if findings:
        return VERDICT_DEGRADED, findings
    return VERDICT_HEALTHY, findings
