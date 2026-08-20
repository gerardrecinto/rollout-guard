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


KNOWN_METRICS = ("error_rate", "p99_latency_ms", "restarts", "cpu_pct", "mem_pct")


class Rule:
    def __init__(self, name, action, metric=None, op="gt", threshold=None,
                 log_pattern=None, severity=VERDICT_FAILING, scale_to=None):
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
        # Target replica count for a "scale" action. Kept separate from
        # metric/threshold: those two drive window evaluation against a
        # MetricSample field, and "replicas" is not one (see remediate.py).
        self.scale_to = scale_to


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


def validate_rules(ruleset):
    """Check rule definitions for structural mistakes evaluate() can't catch
    on its own: unknown metric names, duplicate rule names, and a metric set
    with no threshold to compare it against. Returns a list of problem
    strings; an empty list means the rules are safe to run.
    """
    problems = []
    seen = set()
    for rule in ruleset:
        if rule.name in seen:
            problems.append("duplicate rule name: %s" % rule.name)
        seen.add(rule.name)
        if rule.metric is not None and rule.metric not in KNOWN_METRICS:
            problems.append("rule %s: unknown metric %r (known: %s)"
                            % (rule.name, rule.metric, ", ".join(KNOWN_METRICS)))
        if rule.metric is not None and rule.threshold is None:
            problems.append("rule %s: metric %r set but no threshold"
                            % (rule.name, rule.metric))
    return problems


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
