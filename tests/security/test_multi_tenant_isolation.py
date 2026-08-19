"""Dedicated security test for multi-tenant isolation (Bloque 4, D2).

Distinct from the generic concurrency tests in `tests/core/test_service.py`
/ `test_module.py` / `test_manager.py` (which confirm thread-safety of
*construction* -- exactly one instance ever gets built under a race).
This file asks a different, security-relevant question: given the SAFE
usage pattern this project documents and its own `example/` app follows
(`example/app/router/api/chat.py::_get_manager()` -- a fresh `Service`/
`ToToolManager` per request), can one tenant's request ever observe
another tenant's data?

It also locks in, with an actual assertion rather than only a docstring,
the one documented case where isolation is intentionally NOT provided:
reusing the same `Service` object (not just the same service *class*)
across tenants with `singleton=True` does share state -- by design, per
`Service.singleton`'s own docstring. A security test suite that only
covers the safe path and never asserts the unsafe one risks a future
change silently altering that documented contract without anything
catching it.
"""
import threading

import pytest

from to_tool_manager.core.manager import ToToolManager
from to_tool_manager.core.service import Service

from tests.concurrency_harness import run_concurrently_threads


class TenantScopedCounter:
    """Stateful service standing in for anything a real tenant's
    request might mutate (a DB session, an in-memory cache, request
    context, ...). Each call increments and records who called it."""

    def __init__(self):
        self.calls: list[str] = []

    def touch(self, tenant_id: str) -> int:
        """Records a call from `tenant_id` and returns the call count."""
        self.calls.append(tenant_id)
        return len(self.calls)


def _build_fresh_manager_for_tenant() -> ToToolManager:
    """Mirrors example/app/router/api/chat.py::_get_manager()'s pattern:
    a brand-new `Service` (and therefore a brand-new singleton instance)
    constructed fresh for this call, not reused across calls."""
    svc = Service(name="Counter", service=TenantScopedCounter, singleton=True)
    return ToToolManager([svc])


class TestSafePatternIsolatesTenants:
    """The pattern this project actually documents and uses in
    example/ -- fresh Service/ToToolManager per request -- must never
    let one tenant observe another's state, including under real
    concurrent access."""

    @pytest.mark.anyio
    async def test_two_sequential_tenants_do_not_share_state(self):
        manager_a = _build_fresh_manager_for_tenant()
        manager_b = _build_fresh_manager_for_tenant()

        spec_a = manager_a.tool_specs[0]
        spec_b = manager_b.tool_specs[0]

        result_a = await spec_a.call(operations=[{"method": "touch", "args": {"tenant_id": "tenant-a"}}])
        result_b = await spec_b.call(operations=[{"method": "touch", "args": {"tenant_id": "tenant-b"}}])

        # If state leaked between tenants, tenant B would see call count 2
        # (having "inherited" tenant A's prior call) instead of 1.
        assert result_a.content[0]["result"] == 1
        assert result_b.content[0]["result"] == 1

    def test_concurrent_tenants_never_observe_each_others_calls(self):
        """Real OS threads (matching concurrency_harness's own guidance
        for racing sync code), each simulating a fully independent
        tenant request -- fresh manager, fresh singleton instance, one
        call, check only its own data came back."""

        def one_tenant_request(i: int) -> tuple[str, int]:
            tenant_id = f"tenant-{i}"
            manager = _build_fresh_manager_for_tenant()
            counter = manager.tool_specs[0]

            import asyncio
            result = asyncio.run(counter.call(operations=[{"method": "touch", "args": {"tenant_id": tenant_id}}]))
            return tenant_id, result.content[0]["result"]

        results = run_concurrently_threads(lambda i: one_tenant_request(i), n=32)

        assert results.ok, f"unexpected errors during concurrent tenant requests: {results.errors}"

        # Every tenant must see exactly ITS OWN first call (count == 1).
        # Any leakage across tenants (shared counter) would surface as
        # some tenant observing a count > 1.
        for tenant_id, count in results.results:
            assert count == 1, (
                f"{tenant_id} observed call count {count} -- expected 1. "
                "A count > 1 means this tenant's fresh Service somehow "
                "shared state with another tenant's."
            )


class TestDocumentedUnsafeSharingActuallyShares:
    """The flip side, asserted rather than left as prose: reusing the
    SAME Service object (not just the same class) across tenants with
    singleton=True does share state, exactly as Service.singleton's
    docstring warns. If a future change to Service/ToToolManager quietly
    made singleton=True always request-scoped (removing the documented
    footgun) or, worse, made singleton=False also leak across managers,
    this test would need to be updated -- which is the point: the
    contract stays explicit and test-enforced in both directions, not
    just described.

    Also locks in the real scope `singleton` operates at (discovered
    while writing this test, and clarified in `Service.singleton`'s
    docstring as a result): `get_instance()` is called exactly once per
    `ToToolManager`, at that manager's `tool_specs` build time -- not
    once per dispatch call. `singleton=False`'s isolation boundary is
    therefore "different manager instance", not "different call within
    an already-built manager". Conflating the two was an actual mistake
    caught while writing this file (see git history) -- both tests below
    guard against reintroducing it.
    """

    @pytest.mark.anyio
    async def test_reusing_the_same_service_object_shares_state_across_tenants(self):
        # Built ONCE, then (mis)used as if it were shared setup across
        # two different tenant requests -- the anti-pattern the
        # docstring warns against, e.g. building ToToolManager once at
        # startup instead of per request.
        shared_svc = Service(name="Counter", service=TenantScopedCounter, singleton=True)
        shared_manager = ToToolManager([shared_svc])
        spec = shared_manager.tool_specs[0]

        result_tenant_a = await spec.call(operations=[{"method": "touch", "args": {"tenant_id": "tenant-a"}}])
        result_tenant_b = await spec.call(operations=[{"method": "touch", "args": {"tenant_id": "tenant-b"}}])

        # Tenant B's call count is 2, not 1: it inherited tenant A's
        # prior call because both went through the same Service object's
        # singleton instance. This IS the documented, intentional
        # behavior of singleton=True -- not a bug -- but it must stay
        # asserted, not just described in a comment.
        assert result_tenant_a.content[0]["result"] == 1
        assert result_tenant_b.content[0]["result"] == 2

    @pytest.mark.anyio
    async def test_singleton_false_isolates_separate_managers_sharing_the_same_service_object(self):
        """The real scope `singleton` applies at: `Service.get_instance()`
        is called exactly once per `ToToolManager` (at that manager's
        `tool_specs` build time -- see `ToToolManager.tool_specs`), not
        once per dispatch call. So `singleton=False`'s isolation
        boundary is "different manager" -- not "different call within
        the same manager" (see the test below for that distinction).
        Here: the SAME Service object feeds two DIFFERENT managers
        (e.g. a service registry module reused to build one manager per
        tenant) -- singleton=False must give each manager its own
        instance."""
        shared_svc = Service(name="Counter", service=TenantScopedCounter, singleton=False)
        manager_a = ToToolManager([shared_svc])
        manager_b = ToToolManager([shared_svc])

        result_tenant_a = await manager_a.tool_specs[0].call(
            operations=[{"method": "touch", "args": {"tenant_id": "tenant-a"}}]
        )
        result_tenant_b = await manager_b.tool_specs[0].call(
            operations=[{"method": "touch", "args": {"tenant_id": "tenant-b"}}]
        )

        assert result_tenant_a.content[0]["result"] == 1
        assert result_tenant_b.content[0]["result"] == 1

    @pytest.mark.anyio
    async def test_singleton_has_no_effect_within_a_single_already_built_manager(self):
        """The subtle, non-obvious corollary of the scope documented
        above: within ONE already-built manager, repeated dispatch
        calls always reuse the same instance regardless of `singleton`
        -- because `get_instance()` was already called (and its result
        cached inside the manager's `tool_specs`) before either of these
        calls happened. `singleton=False` is not "fresh instance per
        call"; conflating the two is the exact mistake this test guards
        against reintroducing."""
        svc = Service(name="Counter", service=TenantScopedCounter, singleton=False)
        manager = ToToolManager([svc])
        spec = manager.tool_specs[0]

        result_first_call = await spec.call(operations=[{"method": "touch", "args": {"tenant_id": "first"}}])
        result_second_call = await spec.call(operations=[{"method": "touch", "args": {"tenant_id": "second"}}])

        assert result_first_call.content[0]["result"] == 1
        # Second call observes count 2, NOT a fresh count of 1 --
        # confirming singleton=False does not, by itself, isolate
        # separate calls within the same manager. Isolation at that
        # granularity requires rebuilding the manager/Service per
        # request, as example/app/router/api/chat.py::_get_manager()
        # does.
        assert result_second_call.content[0]["result"] == 2
