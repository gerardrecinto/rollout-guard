"""Remediation planner and executor.

Dry-run is the default: commands are printed and audited, never executed,
unless --execute is passed. Every decision (including dry runs and
escalations) is appended to a JSONL audit trail so the on-call can replay
exactly what the tool saw and did.
"""

import json
import subprocess
import time


def plan(finding, deployment, namespace):
    action = finding.rule.action
    base = ["kubectl", "-n", namespace]
    if action == "rollback":
        return base + ["rollout", "undo", "deployment/%s" % deployment]
    if action == "restart":
        return base + ["rollout", "restart", "deployment/%s" % deployment]
    if action == "scale":
        replicas = finding.rule.threshold if finding.rule.metric == "replicas" else 2
        return base + ["scale", "deployment/%s" % deployment,
                       "--replicas=%d" % int(replicas)]
    return None  # escalate: no command, page a human


def execute(cmd, dry_run=True):
    if dry_run:
        return {"executed": False, "cmd": " ".join(cmd)}
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return {"executed": True, "cmd": " ".join(cmd),
            "returncode": proc.returncode, "stderr": proc.stderr.strip()}


def audit(path, record):
    record["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    with open(path, "a") as f:
        f.write(json.dumps(record) + "\n")


def remediate(findings, deployment, namespace, audit_path, dry_run=True):
    """Plan and (optionally) run one action per finding, worst first."""
    results = []
    seen_actions = set()
    for finding in sorted(findings, key=lambda f: f.rule.severity != "failing"):
        action = finding.rule.action
        if action in seen_actions:
            continue  # one rollback is enough, however many rules asked for it
        seen_actions.add(action)
        cmd = plan(finding, deployment, namespace)
        outcome = execute(cmd, dry_run) if cmd else {"executed": False, "escalated": True}
        record = {"deployment": deployment, "namespace": namespace,
                  "finding": finding.as_dict(), "outcome": outcome}
        audit(audit_path, record)
        results.append(record)
    return results
