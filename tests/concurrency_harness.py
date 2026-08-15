"""Fase 1.3 (Bloque 1): reusable concurrency test harness.

Formalizes the pattern already used ad-hoc in Fase 0.1-0.3's tests
(`Service.get_instance`, `Module._get_sub_manager`, `ToToolManager.tool_specs`
-- see `tests/core/test_service.py`, `tests/core/test_module.py`,
`tests/core/test_manager.py`): spawn N concurrent callers racing on the
same first call, confirm exactly one "winner" (single instance/build), and
confirm no errors leaked out of any caller.

Two flavors, matching the two concurrency models this project actually
runs under (see the note in `Service.get_instance`'s docstring):

- `run_concurrently_threads`: real OS threads. The right model whenever
  the call under test has no internal `await` -- pure sync code is
  otherwise atomic under a single-threaded asyncio event loop, so real
  threads are what's needed to genuinely race a sync method.
- `run_concurrently_async`: asyncio tasks via `asyncio.gather` (with
  `asyncio.to_thread` for sync callables) -- the right model for
  confirming the same guarantee holds from the async call sites that
  actually invoke this code in production (tool dispatch).

Both accept a configurable `n` (volume), per Fase 1.3's requirement.
"""
from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar

T = TypeVar("T")

DEFAULT_CONCURRENCY = 32


@dataclass
class ConcurrencyResult:
    """Outcome of racing `n` concurrent callers against one callable.

    `results` and `errors` are aligned by caller index where applicable
    (results[i] is None if that caller raised; the exception goes into
    `errors` instead, tagged with its caller index).
    """

    results: list[Any]
    errors: list[tuple[int, BaseException]]

    @property
    def ok(self) -> bool:
        """True if every caller completed without raising."""
        return not self.errors

    @property
    def unique_result_count(self) -> int:
        """Number of distinct objects (by identity) among `results`.
        The go-to assertion for "exactly one instance was constructed":
        `assert result.unique_result_count == 1`."""
        return len({id(r) for r in self.results if r is not None})


def run_concurrently_threads(
    fn: Callable[[int], T],
    n: int = DEFAULT_CONCURRENCY,
) -> ConcurrencyResult:
    """Calls `fn(i)` from `n` real OS threads, started together and
    joined before returning. `fn` receives its own caller index (0..n-1)
    -- ignore it if not needed (e.g. `lambda _: svc.get_instance()`).

    Use this for racing sync, no-await code (e.g. `Service.get_instance`,
    `Module._get_sub_manager`, `ToToolManager.tool_specs`) -- real threads
    are required to genuinely interleave pure sync execution; asyncio's
    single-threaded cooperative scheduling would not (see module docstring).
    """
    results: list[Any] = [None] * n
    errors: list[tuple[int, BaseException]] = []
    errors_lock = threading.Lock()

    def worker(i: int) -> None:
        try:
            results[i] = fn(i)
        except BaseException as e:  # pragma: no cover - failure path only
            with errors_lock:
                errors.append((i, e))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    return ConcurrencyResult(results=results, errors=errors)


def run_concurrently_async(
    fn: Callable[[int], T],
    n: int = DEFAULT_CONCURRENCY,
) -> ConcurrencyResult:
    """Calls `fn(i)` from `n` concurrent asyncio tasks (via
    `asyncio.gather` + `asyncio.to_thread`, since `fn` is a sync
    callable), started together. Matches how a real tool-call dispatch
    would invoke this kind of sync method under concurrent load, from
    the async side.

    Must be called from sync test code (creates and runs its own event
    loop via `asyncio.run`) -- keeps call sites identical to
    `run_concurrently_threads`, no `await`/`pytest.mark.asyncio` needed.
    """
    results: list[Any] = [None] * n
    errors: list[tuple[int, BaseException]] = []

    async def worker(i: int) -> None:
        try:
            results[i] = await asyncio.to_thread(fn, i)
        except BaseException as e:  # pragma: no cover - failure path only
            errors.append((i, e))

    async def run_all() -> None:
        await asyncio.gather(*[worker(i) for i in range(n)])

    asyncio.run(run_all())

    return ConcurrencyResult(results=results, errors=errors)
