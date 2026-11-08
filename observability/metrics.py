"""Prometheus-style counters/histograms, stdlib only.

Counters are monotonic. Histograms use cumulative buckets. Rendering is
Prometheus text exposition format (no client library required).
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field

DEFAULT_BUCKETS: tuple[float, ...] = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10)


def _escape_label(v: str) -> str:
    return v.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _fmt(v: float) -> str:
    if v == int(v):
        return str(int(v))
    return repr(float(v))


@dataclass
class Counter:
    name: str
    help: str
    _labels: dict[tuple[tuple[str, str], ...], float] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def inc(self, amount: float = 1.0, **labels: str) -> None:
        if amount < 0:
            raise ValueError("counters are monotonic; amount must be >= 0")
        key = tuple(sorted((k, str(v)) for k, v in labels.items()))
        with self._lock:
            self._labels[key] = self._labels.get(key, 0.0) + amount

    def value(self, **labels: str) -> float:
        key = tuple(sorted((k, str(v)) for k, v in labels.items()))
        with self._lock:
            return self._labels.get(key, 0.0)

    def render(self) -> list[str]:
        lines = [f"# HELP {self.name} {self.help}", f"# TYPE {self.name} counter"]
        with self._lock:
            items = sorted(self._labels.items())
        for key, v in items:
            lbl = ",".join(f'{k}="{_escape_label(val)}"' for k, val in key)
            lines.append(f"{self.name}{{{lbl}}} {_fmt(v)}" if lbl else f"{self.name} {_fmt(v)}")
        return lines


@dataclass
class Histogram:
    name: str
    help: str
    buckets: tuple[float, ...] = DEFAULT_BUCKETS
    _data: dict[tuple[tuple[str, str], ...], dict] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def observe(self, value: float, **labels: str) -> None:
        key = tuple(sorted((k, str(v)) for k, v in labels.items()))
        with self._lock:
            d = self._data.setdefault(key, {"counts": [0] * len(self.buckets), "sum": 0.0, "count": 0})
            for i, b in enumerate(self.buckets):
                if value <= b:
                    d["counts"][i] += 1
            d["sum"] += value
            d["count"] += 1

    def render(self) -> list[str]:
        lines = [f"# HELP {self.name} {self.help}", f"# TYPE {self.name} histogram"]
        with self._lock:
            items = sorted(self._data.items())
        for key, d in items:
            base = list(key)
            for i, b in enumerate(self.buckets):
                lbl = ",".join(f'{k}="{_escape_label(v)}"' for k, v in base + [("le", _fmt(b))])
                lines.append(f"{self.name}_bucket{{{lbl}}} {d['counts'][i]}")
            lbl = ",".join(f'{k}="{_escape_label(v)}"' for k, v in base + [("le", "+Inf")])
            lines.append(f"{self.name}_bucket{{{lbl}}} {d['count']}")
            lbl2 = ",".join(f'{k}="{_escape_label(v)}"' for k, v in base)
            lines.append(f"{self.name}_sum{{{lbl2}}} {_fmt(d['sum'])}" if lbl2 else f"{self.name}_sum {_fmt(d['sum'])}")
            lines.append(f"{self.name}_count{{{lbl2}}} {d['count']}" if lbl2 else f"{self.name}_count {d['count']}")
        return lines


class Registry:
    """Holds metrics; render() produces the full text exposition."""

    def __init__(self) -> None:
        self._metrics: list = []
        self._lock = threading.Lock()

    def counter(self, name: str, help: str) -> Counter:
        with self._lock:
            for m in self._metrics:
                if m.name == name:
                    return m  # type: ignore
            c = Counter(name, help)
            self._metrics.append(c)
            return c

    def histogram(self, name: str, help: str, buckets: tuple[float, ...] = DEFAULT_BUCKETS) -> Histogram:
        with self._lock:
            for m in self._metrics:
                if m.name == name:
                    return m  # type: ignore
            h = Histogram(name, help, tuple(sorted(buckets)))
            self._metrics.append(h)
            return h

    def render(self) -> str:
        with self._lock:
            ms = list(self._metrics)
        out: list[str] = []
        for m in ms:
            out.extend(m.render())
        return "\n".join(out) + ("\n" if out else "")


# Module-level default registry + helpers for app wiring.
registry = Registry()
http_requests_total = registry.counter("http_requests_total", "Total HTTP requests")
http_request_duration_seconds = registry.histogram(
    "http_request_duration_seconds", "HTTP request duration in seconds")
# LatencyLedger metric aliases (perf-spec §1.2): gate/ingest/health timings.
gate_evaluations_total = registry.counter("gate_evaluations_total", "CI gate evaluations")
gate_duration_seconds = registry.histogram("gate_duration_seconds", "Gate evaluation duration")
ingest_duration_seconds = registry.histogram("ingest_duration_seconds", "Sample ingest duration")
alerts_raised_total = registry.counter("alerts_raised_total", "Regression/down alerts raised")
alert_deliveries_total = registry.counter("alert_deliveries_total", "Alert deliveries attempted")


def observe_http(status: int, duration_s: float, endpoint: str = "unknown") -> None:
    http_requests_total.inc(1, status=str(status), endpoint=endpoint)
    http_request_duration_seconds.observe(duration_s, endpoint=endpoint)


def render_metrics() -> str:
    return registry.render()
