from __future__ import annotations

from typing import Awaitable, Callable, Generator, Sequence


MethodsType = frozenset[str]
AnyFunctionType = Sequence[Callable | Awaitable | Generator]


