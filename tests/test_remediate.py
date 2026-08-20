import json

from rolloutguard.remediate import plan, remediate
from rolloutguard.rules import Rule, Finding


def finding(name, action, **kw):
    return Finding(Rule(name, action, metric="error_rate", threshold=0.05, **kw),
                   {"error_rate": 0.2})


def test_plan_rollback_command():
    cmd = plan(finding("error-spike", "rollback"), "api", "prod")
    assert cmd == ["kubectl", "-n", "prod", "rollout", "undo", "deployment/api"]


def test_escalate_has_no_command():
    assert plan(finding("weird", "escalate"), "api", "prod") is None


def test_dry_run_never_executes_and_audits(tmp_path):
    audit = tmp_path / "audit.jsonl"
    results = remediate([finding("error-spike", "rollback")], "api", "prod",
                        str(audit), dry_run=True)
    assert results[0]["outcome"]["executed"] is False
    rec = json.loads(audit.read_text().splitlines()[0])
    assert rec["finding"]["rule"] == "error-spike"
    assert "ts" in rec


def test_duplicate_actions_collapse_to_one(tmp_path):
    audit = tmp_path / "audit.jsonl"
    results = remediate([finding("error-spike", "rollback"),
                         finding("crash-loop", "rollback")],
                        "api", "prod", str(audit), dry_run=True)
    assert len(results) == 1


def test_failing_findings_ordered_before_degraded(tmp_path):
    audit = tmp_path / "audit.jsonl"
    degraded = finding("latency", "restart", severity="degraded")
    failing = finding("error-spike", "rollback")
    results = remediate([degraded, failing], "api", "prod", str(audit), dry_run=True)
    assert results[0]["finding"]["rule"] == "error-spike"


def test_plan_scale_uses_rule_scale_to():
    f = finding("oom-kill", "scale", scale_to=6)
    cmd = plan(f, "api", "prod")
    assert cmd == ["kubectl", "-n", "prod", "scale", "deployment/api", "--replicas=6"]


def test_plan_scale_defaults_to_two_replicas_when_unset():
    f = finding("oom-kill", "scale")
    cmd = plan(f, "api", "prod")
    assert cmd == ["kubectl", "-n", "prod", "scale", "deployment/api", "--replicas=2"]
