"""Health/readiness checks (Bloque 7 -- Preparacion operativa).

`to_tool_manager` is a library, not an HTTP server -- it has no opinion
about web frameworks, so it doesn't expose `/healthz`/`/readyz` routes
itself. What it CAN do, and does here, is give the consuming app a
cheap, real thing to call from its own health endpoint (FastAPI,
Flask, aiohttp, ...).

Scope, honestly stated: `check_manager_health()` verifies that every
registered `Service`/`Module` can build its `ToolSpec` -- which, for a
`Service`, means its `get_instance()` succeeds. Since
`ToToolManager.tool_specs` is built once and cached (see
`ToToolManager.tool_specs` / `Service.singleton`'s docstring), this is
closer to a LIVENESS check ("did construction succeed") than a live
READINESS probe ("is the downstream dependency reachable right now") --
a `Service` whose `__init__` opened a DB connection successfully at
startup and is now checked again post-startup will report healthy even
if that connection has since dropped, because `get_instance()` doesn't
re-run for an already-built singleton. For genuine point-in-time
readiness (e.g. "can I still reach the DB"), pass `readiness_probes` --
this module doesn't invent its own DB/network-probing mechanism, since
that's inherently application-specific.
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Mapping

from to_tool_manager.core.manager import ToToolManager


@dataclass(frozen=True)
class ServiceHealth:
    name: str
    healthy: bool
    error: str | None = None


@dataclass(frozen=True)
class ProbeHealth:
    name: str
    healthy: bool
    error: str | None = None


@dataclass(frozen=True)
class HealthReport:
    healthy: bool
    services: tuple[ServiceHealth, ...] = field(default_factory=tuple)
    probes: tuple[ProbeHealth, ...] = field(default_factory=tuple)


async def check_manager_health(
    manager: ToToolManager,
    readiness_probes: Mapping[str, Callable[[], bool | Awaitable[bool]]] | None = None,
) -> HealthReport:
    """Checks that every `Service`/`Module` registered on `manager` can
    build successfully (i.e. `get_instance()` / `_get_sub_manager()`
    succeeds), plus any application-supplied `readiness_probes`.

    Never raises: a failing service or probe is reported in the
    returned `HealthReport`, not propagated as an exception -- a health
    endpoint calling this should always get a report back to serialize,
    even when the underlying manager is broken.

    Checks each registered `Service`/`Module` independently (rather than
    just accessing `manager.tool_specs` as a whole) so one broken
    service doesn't obscure whether its siblings are healthy.

    Args:
        manager: The `ToToolManager` to check.
        readiness_probes: Optional `{name: callable}` mapping for
            application-specific liveness checks this library can't
            know how to perform itself (DB ping, downstream API check,
            ...). Each callable may be sync or async, and must return a
            bool (or raise, which is caught and reported as unhealthy).
    """
    services: list[ServiceHealth] = []
    for name, service in {**manager.services, **manager.modules}.items():
        try:
            if hasattr(service, "get_instance"):
                service.get_instance()
            else:
                service.sub_manager  # Module: exercises the same lazy-build path as get_instance
            services.append(ServiceHealth(name=name, healthy=True))
        except Exception as exc:
            services.append(ServiceHealth(name=name, healthy=False, error=f"{type(exc).__name__}: {exc}"))

    probes: list[ProbeHealth] = []
    for probe_name, probe in (readiness_probes or {}).items():
        try:
            result = probe()
            if inspect.isawaitable(result):
                result = await result
            probes.append(ProbeHealth(name=probe_name, healthy=bool(result)))
        except Exception as exc:
            probes.append(ProbeHealth(name=probe_name, healthy=False, error=f"{type(exc).__name__}: {exc}"))

    overall_healthy = all(s.healthy for s in services) and all(p.healthy for p in probes)
    return HealthReport(healthy=overall_healthy, services=tuple(services), probes=tuple(probes))
