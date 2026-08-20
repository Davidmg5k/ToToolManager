"""Pluggable metrics collection (Bloque 2 -- Observabilidad).

Deliberately does NOT bundle a specific metrics backend (Prometheus,
StatsD, OpenTelemetry Metrics, ...) as a dependency. `MetricsCollector`
is a minimal `Protocol` any of those can satisfy with a thin adapter
written by the consuming application; `InMemoryMetricsCollector` here is
a real, usable default (handy for tests and for apps that just want to
inspect counters directly) rather than a stub.

Scope note on what's measurable at this layer: `MetricsMiddleware` (see
`metrics_middleware.py`) wraps `Service`/`Module` dispatch -- it has no
visibility into LLM token usage, which is a property of the *Agent*
completion, not of an individual tool call. Token metrics belong at the
adapter layer (e.g. pydantic-ai's own `result.usage()`), not here; this
module covers latency and error-rate per dispatch, which IS visible at
this layer.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Mapping, Protocol


class MetricsCollector(Protocol):
    """Minimal interface any metrics backend adapter must satisfy.

    Both methods take `tags` (e.g. `{"service": "Orders", "outcome":
    "success"}`) so a real backend adapter can attach them as labels
    (Prometheus), dimensions (StatsD/Datadog), or span attributes
    (OpenTelemetry) -- this module stays agnostic about which.
    """

    def record_duration(self, name: str, seconds: float, tags: Mapping[str, str]) -> None: ...

    def increment(self, name: str, tags: Mapping[str, str], value: int = 1) -> None: ...


@dataclass
class InMemoryMetricsCollector:
    """Thread-safe in-memory `MetricsCollector`.

    Useful directly for tests and small/single-process deployments, and
    as a reference implementation of the `MetricsCollector` protocol for
    anyone writing a real backend adapter.
    """

    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False, compare=False)
    _durations: dict[tuple[str, tuple[tuple[str, str], ...]], list[float]] = field(
        default_factory=dict, init=False, repr=False
    )
    _counters: dict[tuple[str, tuple[tuple[str, str], ...]], int] = field(
        default_factory=dict, init=False, repr=False
    )

    @staticmethod
    def _key(name: str, tags: Mapping[str, str]) -> tuple[str, tuple[tuple[str, str], ...]]:
        return (name, tuple(sorted(tags.items())))

    def record_duration(self, name: str, seconds: float, tags: Mapping[str, str]) -> None:
        key = self._key(name, tags)
        with self._lock:
            self._durations.setdefault(key, []).append(seconds)

    def increment(self, name: str, tags: Mapping[str, str], value: int = 1) -> None:
        key = self._key(name, tags)
        with self._lock:
            self._counters[key] = self._counters.get(key, 0) + value

    def get_durations(self, name: str, tags: Mapping[str, str] | None = None) -> list[float]:
        """Returns the recorded durations for `name`. If `tags` is
        given, only the exact-match series; otherwise every series
        recorded under that name across all tag combinations,
        concatenated."""
        with self._lock:
            if tags is not None:
                return list(self._durations.get(self._key(name, tags), []))
            return [v for (n, _), values in self._durations.items() if n == name for v in values]

    def get_count(self, name: str, tags: Mapping[str, str] | None = None) -> int:
        with self._lock:
            if tags is not None:
                return self._counters.get(self._key(name, tags), 0)
            return sum(v for (n, _), v in self._counters.items() if n == name)
