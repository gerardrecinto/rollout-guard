from rolloutguard.rules import (Rule, evaluate, validate_rules,
                                VERDICT_HEALTHY, VERDICT_DEGRADED, VERDICT_FAILING)
from rolloutguard.signals import MetricSample, Window

RULES = [
    Rule("error-spike", "rollback", metric="error_rate", threshold=0.05),
    Rule("latency-regression", "restart", metric="p99_latency_ms",
         threshold=800, severity=VERDICT_DEGRADED),
    Rule("crash-loop", "rollback", metric="restarts", threshold=3),
    Rule("oom", "scale", log_pattern="OOMKilled"),
]


def window(samples, logs=None):
    return Window(samples, logs)


def test_healthy_window_has_no_findings():
    w = window([MetricSample(1, error_rate=0.01, p99_latency_ms=200)])
    verdict, findings = evaluate(w, RULES)
    assert verdict == VERDICT_HEALTHY and findings == []


def test_error_spike_triggers_failing_rollback():
    w = window([MetricSample(1, error_rate=0.02), MetricSample(2, error_rate=0.12)])
    verdict, findings = evaluate(w, RULES)
    assert verdict == VERDICT_FAILING
    assert findings[0].rule.action == "rollback"
    assert findings[0].evidence["error_rate"] == 0.12


def test_latency_only_is_degraded_not_failing():
    w = window([MetricSample(1, p99_latency_ms=950)])
    verdict, findings = evaluate(w, RULES)
    assert verdict == VERDICT_DEGRADED
    assert findings[0].rule.name == "latency-regression"


def test_restarts_use_window_delta_not_absolute():
    # counter starts at 10; only 2 new restarts in window, below threshold 3
    w = window([MetricSample(1, restarts=10), MetricSample(2, restarts=12)])
    verdict, _ = evaluate(w, RULES)
    assert verdict == VERDICT_HEALTHY


def test_log_pattern_rule_fires():
    w = window([MetricSample(1)], ["pod api-7f9 OOMKilled exit 137"])
    verdict, findings = evaluate(w, RULES)
    assert verdict == VERDICT_FAILING
    assert findings[0].evidence["matches"] == 1


def test_rule_rejects_unknown_action():
    import pytest
    with pytest.raises(ValueError):
        Rule("bad", "delete-namespace", metric="error_rate", threshold=1)


def test_validate_rules_clean_set_has_no_problems():
    assert validate_rules(RULES) == []


def test_validate_rules_flags_unknown_metric():
    bad = [Rule("typo", "restart", metric="replicas", threshold=2)]
    problems = validate_rules(bad)
    assert len(problems) == 1
    assert "unknown metric" in problems[0]


def test_validate_rules_flags_duplicate_names():
    dup = [Rule("dup", "restart", metric="cpu_pct", threshold=90),
           Rule("dup", "rollback", metric="mem_pct", threshold=90)]
    problems = validate_rules(dup)
    assert any("duplicate rule name" in p for p in problems)


def test_validate_rules_flags_metric_without_threshold():
    no_threshold = [Rule("weird", "restart", metric="cpu_pct")]
    problems = validate_rules(no_threshold)
    assert any("no threshold" in p for p in problems)
