"""Health signal ingestion: metric samples and log lines for a deployment window."""

import json


class MetricSample:
    def __init__(self, ts, error_rate=0.0, p99_latency_ms=0.0, restarts=0,
                 cpu_pct=0.0, mem_pct=0.0):
        self.ts = ts
        self.error_rate = float(error_rate)
        self.p99_latency_ms = float(p99_latency_ms)
        self.restarts = int(restarts)
        self.cpu_pct = float(cpu_pct)
        self.mem_pct = float(mem_pct)


class Window:
    """Aggregates samples over the post-deploy observation window."""

    def __init__(self, samples, log_lines=None):
        if not samples:
            raise ValueError("window requires at least one sample")
        self.samples = samples
        self.log_lines = log_lines or []

    def _values(self, field):
        return [getattr(s, field) for s in self.samples]

    def max(self, field):
        return max(self._values(field))

    def avg(self, field):
        vals = self._values(field)
        return sum(vals) / len(vals)

    def total_restarts(self):
        # restarts is a counter per sample snapshot; delta across the window
        return self.samples[-1].restarts - self.samples[0].restarts

    def log_matches(self, pattern):
        return [ln for ln in self.log_lines if pattern in ln]


def load_metrics(path):
    """Load samples from a JSON array (Prometheus/CloudWatch export shape)."""
    with open(path) as f:
        raw = json.load(f)
    return [MetricSample(**row) for row in raw]


def load_logs(path):
    with open(path) as f:
        return [ln.rstrip("\n") for ln in f]
