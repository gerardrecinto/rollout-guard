"""Claude fallback for unknown failure signatures.

Only consulted when the window is unhealthy but no rule explains why. The
model classifies the signature and suggests one action from the same allowed
set the rule engine uses. The suggestion is written to the audit trail for
the on-call and is never executed automatically; there is no flag that
turns it into a live action. The path from "LLM guess" to "automated
response" is a human promoting a repeated correct guess to a rule (see
docs/adr-001-safety-boundaries.md). Requires ANTHROPIC_API_KEY; without it
the tool degrades to plain escalation.
"""

import json
import os
import urllib.request

from .rules import ALLOWED_ACTIONS

API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-5"

PROMPT = """A deployment just shipped and its health window is degraded, but no known
failure signature matched. Classify the likely cause and pick exactly one
action from: %s.

Metrics (max over window): %s
Log excerpt:
%s

Reply as JSON: {"cause": "...", "action": "...", "confidence": "high|medium|low"}"""


def classify(window, deployment):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return {"cause": "unknown (no ANTHROPIC_API_KEY, LLM fallback disabled)",
                "action": "escalate", "confidence": "low"}
    metrics = {f: window.max(f) for f in
               ("error_rate", "p99_latency_ms", "cpu_pct", "mem_pct")}
    body = json.dumps({
        "model": MODEL,
        "max_tokens": 300,
        "messages": [{"role": "user", "content": PROMPT % (
            ", ".join(ALLOWED_ACTIONS), json.dumps(metrics),
            "\n".join(window.log_lines[-20:]) or "(none)")}],
    }).encode()
    req = urllib.request.Request(API_URL, data=body, headers={
        "x-api-key": key, "anthropic-version": "2023-06-01",
        "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            text = json.load(resp)["content"][0]["text"]
        verdict = json.loads(text[text.index("{"):text.rindex("}") + 1])
    except Exception as exc:
        return {"cause": "LLM fallback failed: %s" % exc,
                "action": "escalate", "confidence": "low"}
    if verdict.get("action") not in ALLOWED_ACTIONS:
        verdict["action"] = "escalate"
    return verdict
