import json

from rolloutguard.cli import main


def write(path, obj):
    path.write_text(json.dumps(obj))
    return str(path)


RULES = [{"name": "error-spike", "action": "rollback",
          "metric": "error_rate", "threshold": 0.05}]


def test_check_healthy_exits_zero(tmp_path, capsys):
    metrics = write(tmp_path / "m.json", [{"ts": 1, "error_rate": 0.01}])
    rules = write(tmp_path / "r.json", RULES)
    rc = main(["check", "--metrics", metrics, "--rules", rules,
               "--audit", str(tmp_path / "a.jsonl")])
    assert rc == 0
    assert "verdict: healthy" in capsys.readouterr().out


def test_check_failing_dry_runs_rollback_and_exits_nonzero(tmp_path, capsys):
    metrics = write(tmp_path / "m.json", [{"ts": 1, "error_rate": 0.5}])
    rules = write(tmp_path / "r.json", RULES)
    audit = tmp_path / "a.jsonl"
    rc = main(["check", "--metrics", metrics, "--rules", rules,
               "--deployment", "api", "--namespace", "prod",
               "--audit", str(audit)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "[dry-run] error-spike -> rollback" in out
    assert "kubectl -n prod rollout undo deployment/api" in out
    assert audit.exists()


def test_report_summarizes_audit(tmp_path, capsys):
    audit = tmp_path / "a.jsonl"
    audit.write_text(json.dumps({"finding": {"rule": "error-spike"}}) + "\n")
    rc = main(["report", "--audit", str(audit)])
    assert rc == 0
    assert "error-spike" in capsys.readouterr().out


def test_validate_clean_rules_exits_zero(tmp_path, capsys):
    rules = write(tmp_path / "r.json", RULES)
    rc = main(["validate", "--rules", rules])
    assert rc == 0
    assert "1 rule(s) OK" in capsys.readouterr().out


def test_validate_bad_rules_exits_nonzero(tmp_path, capsys):
    bad = [{"name": "typo", "action": "restart", "metric": "repllicas", "threshold": 2}]
    rules = write(tmp_path / "r.json", bad)
    rc = main(["validate", "--rules", rules])
    assert rc == 1
    assert "unknown metric" in capsys.readouterr().out
