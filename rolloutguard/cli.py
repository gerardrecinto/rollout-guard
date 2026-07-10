"""rollout-guard CLI: check a deployment's post-release health window and act."""

import argparse
import json
import sys

from . import __version__, llm, remediate, rules as rules_mod, signals


def build_parser():
    p = argparse.ArgumentParser(
        prog="rollout-guard",
        description="Verify a release's health window and auto-remediate known failures.")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="evaluate one health window")
    check.add_argument("--metrics", required=True, help="JSON array of metric samples")
    check.add_argument("--logs", help="optional log file for the window")
    check.add_argument("--rules", required=True, help="JSON rule definitions")
    check.add_argument("--deployment", default="app")
    check.add_argument("--namespace", default="default")
    check.add_argument("--audit", default="rollout-guard-audit.jsonl")
    check.add_argument("--execute", action="store_true",
                       help="actually run kubectl (default: dry run)")
    check.add_argument("--llm-fallback", action="store_true",
                       help="classify unknown degraded signatures with Claude")

    report = sub.add_parser("report", help="summarize the audit trail")
    report.add_argument("--audit", default="rollout-guard-audit.jsonl")
    return p


def cmd_check(args):
    samples = signals.load_metrics(args.metrics)
    logs = signals.load_logs(args.logs) if args.logs else []
    window = signals.Window(samples, logs)
    ruleset = rules_mod.load_rules(args.rules)
    verdict, findings = rules_mod.evaluate(window, ruleset)

    print("verdict: %s (%d finding%s)" % (verdict, len(findings),
                                          "" if len(findings) == 1 else "s"))
    if verdict == rules_mod.VERDICT_HEALTHY:
        if args.llm_fallback and window.max("error_rate") > 0:
            print("no rule matched; LLM fallback not needed while healthy")
        return 0

    results = remediate.remediate(findings, args.deployment, args.namespace,
                                  args.audit, dry_run=not args.execute)
    for r in results:
        outcome = r["outcome"]
        mode = "ran" if outcome.get("executed") else "dry-run"
        print("  [%s] %s -> %s: %s" % (mode, r["finding"]["rule"],
                                       r["finding"]["action"],
                                       outcome.get("cmd", "escalate to on-call")))

    if args.llm_fallback and verdict == rules_mod.VERDICT_DEGRADED:
        guess = llm.classify(window, args.deployment)
        remediate.audit(args.audit, {"deployment": args.deployment,
                                     "llm_classification": guess})
        print("  [llm] cause: %s | suggested: %s (%s confidence)"
              % (guess["cause"], guess["action"], guess["confidence"]))
    return 1 if verdict == rules_mod.VERDICT_FAILING else 0


def cmd_report(args):
    counts = {}
    try:
        with open(args.audit) as f:
            for line in f:
                rec = json.loads(line)
                key = rec.get("finding", {}).get("rule") or "llm_classification"
                counts[key] = counts.get(key, 0) + 1
    except FileNotFoundError:
        print("no audit trail at %s" % args.audit)
        return 1
    for rule, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print("%4d  %s" % (n, rule))
    return 0


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.command == "check":
        return cmd_check(args)
    return cmd_report(args)


if __name__ == "__main__":
    sys.exit(main())
