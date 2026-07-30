"""
ToToolManager: the single agnostic entry point.

Core design: ONE tool per Service. Give it a list of `Service` and get
back one `ToolSpec` per service — each accepting a list of operations
(method + args) to run in a single call. This is the whole point of
"to_tool_manager": a *service* becomes a *tool*, not a method.
"""
from __future__ import annotations

import json
from typing import Any, Sequence

from to_tool_manager.core.conditions import _evaluate_when
from to_tool_manager.core.discovery import class_summary, discover_methods
from to_tool_manager.core.executor import make_safe_caller
from to_tool_manager.core.module import Module
from to_tool_manager.core.planner import Planner, ServiceDependencyGraph
from to_tool_manager.core.service import Service
from to_tool_manager.core.types import OperationSpec, ParamSpec, ToolError, ToolResponse, ToolSpec
from to_tool_manager.security.middleware import Middleware, ToolMiddleware

_OPERATIONS_CONTRACT = (
    'Each item: {{"method": <name>, "args": {{...}}}}. Put every operation '
    "you need from this service into ONE call instead of calling this "
    'tool repeatedly. Optional per-item "id" (else referenced by '
    'position "op0", "op1", ...) plus a "when": {{"op": <id>, "outcome": '
    '"success"|"error", "category"?: <str|list>}} on a LATER item makes it '
    "run only depending on an earlier item's result in this same call — "
    "unmet conditions are skipped (reported, not executed), no extra "
    "request needed to decide.\n"
    "Example: {example}"
)


def _format_param(p: ParamSpec) -> str:
    type_name = getattr(p.annotation, "__name__", str(p.annotation))
    marker = "" if p.required else "?"
    return f"{p.name}{marker}: {type_name}"


def _example_placeholder(annotation: Any) -> Any:
    type_name = getattr(annotation, "__name__", "")
    return {"str": "...", "int": 0, "float": 0.0, "bool": True}.get(type_name, "...")


def _build_operations_contract(operations: Sequence[OperationSpec]) -> str:
    """
    Builds the operations-parameter contract text ONCE per tool, using
    that service's OWN first operation (and a second one, if it takes no
    required args) as the worked example — instead of a fixed, unrelated
    example copy-pasted into every tool's description (which both wastes
    tokens across many services and is confusing when e.g. the "Order"
    tool's description shows an example calling "create_user").
    """
    if not operations:
        return _OPERATIONS_CONTRACT.format(example='{"operations": [{"method": "<name>", "args": {}}]}')

    first = operations[0]
    first_args = {p.name: _example_placeholder(p.annotation) for p in first.parameters if p.required}
    example_ops: list[dict[str, Any]] = [{"id": "step1", "method": first.name, "args": first_args}]

    no_arg_op = next((op for op in operations[1:] if not any(p.required for p in op.parameters)), None)
    if no_arg_op is not None:
        example_ops.append(
            {
                "method": no_arg_op.name,
                "args": {},
                "when": {"op": "step1", "outcome": "error"},
            }
        )

    example = json.dumps({"operations": example_ops})
    return _OPERATIONS_CONTRACT.format(example=example)


def _build_tool_description(
    service: Service,
    operations: Sequence[OperationSpec],
    *,
    class_description: str | None = None,
    contract: str,
) -> str:
    parts: list[str] = []
    if service.description and service.description.strip():
        parts.append(service.description.strip())
    if class_description and class_description.strip():
        parts.append(class_description.strip())

    if parts:
        header = "\n\n".join(parts)
    else:
        header = (
            f"Service tool for managing '{service.name}' operations "
            f"— exposes the following capabilities:"
        )
    lines = [header, "", "Available operations (use as the `method` value):"]
    for op in operations:
        params = ", ".join(_format_param(p) for p in op.parameters) or "no arguments"
        lines.append(f"- {op.name}({params}): {op.description}")
    lines.append("")
    lines.append(contract)
    return "\n".join(lines)


class ToToolManager:
    def __init__(self, services: Sequence[Service | Module], middlewares: Sequence[Middleware] | None = None):
        names = [s.name for s in services]
        duplicates = {n for n in names if names.count(n) > 1}
        if duplicates:
            raise ValueError(f"Duplicate service/module name(s): {sorted(duplicates)}")

        self.__services: dict[str, Service] = {}
        self.__modules: dict[str, Module] = {}
        self.__middlewares: Sequence[Middleware] | None = middlewares

        for item in services:
            if isinstance(item, Module):
                self.__modules[item.name] = item
            elif isinstance(item, Service):
                self.__services[item.name] = item
            else:
                raise TypeError(
                    f"Expected Service or Module, got {type(item).__name__}"
                )

        self._specs: list[ToolSpec] | None = None

    @property
    def middlewares(self):
        if self.__middlewares is None:
            raise ValueError("The middelware isn't initialized")
        return self.__middlewares

    def get_service(self, name: str) -> Service | Module:
        if name in self.__services:
            return self.__services[name]
        if name in self.__modules:
            return self.__modules[name]
        all_names = list(self.__services.keys()) + list(self.__modules.keys())
        raise ValueError(
            f"Unknown service/module '{name}'. Registered: {sorted(all_names)}"
        )

    @property
    def services(self) -> dict[str, Service]:
        return dict(self.__services)

    @property
    def modules(self) -> dict[str, Module]:
        return dict(self.__modules)

    def _resolve_middlewares(self, service: Service) -> list[Middleware]:
        """Resolve which middlewares apply to a given service.

        Starts with global (ToToolManager-level) middlewares, removes
        any disabled by ``service.disable_middlewares``, then appends
        service-level middlewares.
        """
        global_mws: Sequence[Middleware] = self.__middlewares or ()
        service_disable = set(getattr(service, "disable_middlewares", ()))
        service_mws: Sequence[Middleware] = getattr(service, "middlewares", ())

        resolved: list[Middleware] = []
        for mw in global_mws:
            mw_name = getattr(mw, "name", type(mw).__name__)
            if mw_name in service_disable:
                continue
            resolved.append(mw)

        resolved.extend(service_mws)
        return resolved

    def _apply_middlewares(
        self,
        dispatch_call: Any,
        middlewares: Sequence[Middleware],
    ) -> Any:
        """Apply a middleware chain around *dispatch_call*.

        Middlewares are applied in reverse order so that the first
        element in *middlewares* runs first (outermost).  ``ToolMiddleware``
        instances are skipped here because they operate at the method
        level (handled in ``_build_dispatch_table``).

        Middlewares are expected to raise exceptions for intentional
        blocking (e.g. authentication failures). Those exceptions
        propagate to the adapter/framework as-is.
        """
        for mw in reversed(middlewares):
            if isinstance(mw, ToolMiddleware):
                continue
            original = dispatch_call

            async def _wrapped(*args: Any, _mw: Middleware = mw, _fn: Any = original, **kw: Any) -> Any:
                return await _mw.dispatch(_fn, *args, **kw)

            dispatch_call = _wrapped
        return dispatch_call

    def _build_dispatch_table(
        self, service: Service, instance: Any
    ) -> tuple[dict[str, Any], list[OperationSpec]]:
        methods = discover_methods(
            service.service,
            visibility=service.visibility,
            include=service.include,
            exclude=service.exclude,
            expose_properties=service.expose_properties,
        )
        if not methods:
            raise ValueError(
                f"Service '{service.name}' ({service.service.__name__}) exposes "
                "zero operations with the current visibility/include/exclude "
                "configuration. Nothing would be registered as a tool."
            )

        dispatch: dict[str, Any] = {}
        operations: list[OperationSpec] = []

        tool_mws = [mw for mw in getattr(service, "middlewares", ()) if isinstance(mw, ToolMiddleware)]

        for method_info in methods:
            if method_info.is_property:

                def property_getter(_instance=instance, _name=method_info.name):
                    return getattr(_instance, _name)

                safe_call = make_safe_caller(
                    property_getter,
                    error_map=service.error_map,
                    error_rules=service.error_rules,
                    sanitize_system_errors=service.sanitize_system_errors,
                )
            else:
                bound_method = getattr(instance, method_info.name)
                safe_call = make_safe_caller(
                    bound_method,
                    error_map=service.error_map,
                    error_rules=service.error_rules,
                    sanitize_system_errors=service.sanitize_system_errors,
                )

            for tmw in tool_mws:
                if not tmw.is_allowed(method_info.name):
                    continue
                original = safe_call
                tmw_ref = tmw

                async def _tool_mw_call(
                    *args: Any,
                    _fn: Any = original,
                    _mw: ToolMiddleware = tmw_ref,
                    **kw: Any,
                ) -> Any:
                    return await _mw.dispatch(_fn, *args, **kw)

                safe_call = _tool_mw_call

            dispatch[method_info.name] = safe_call
            operations.append(
                OperationSpec(
                    name=method_info.name,
                    description=method_info.doc_summary,
                    parameters=method_info.parameters,
                )
            )
        return dispatch, operations

    def _build_spec_for_service(self, service: Service) -> ToolSpec:
        instance = service.get_instance()
        dispatch_table, operations = self._build_dispatch_table(service, instance)

        async def dispatch_call(operations: Any = None, **_ignored) -> ToolResponse:
            if not isinstance(operations, list) or not operations:
                return ToolResponse(
                    error=ToolError(
                        category=frozenset("validation_error"),
                        message=(
                            "`operations` must be a non-empty list of "
                            '{"method": ..., "args": {...}} objects.'
                        ),
                        exception_type="ValueError",
                        retryable=True,
                    )
                )

            results: list[dict[str, Any]] = []
            # Tracks each op's outcome by position ("op0", "op1", ...) AND
            # by its custom "id" if given, so a later operation's "when"
            # clause can reference either.
            resolved_by_ref: dict[str, dict[str, Any]] = {}

            for index, raw_op in enumerate(operations):
                position_ref = f"op{index}"

                if not isinstance(raw_op, dict):
                    entry = {
                        "method": None,
                        "success": False,
                        "error": {
                            "category": "validation_error",
                            "message": "Each operation must be an object with 'method' and 'args'.",
                        },
                    }
                    results.append(entry)
                    resolved_by_ref[position_ref] = entry
                    continue

                method_name = raw_op.get("method")
                op_args = raw_op.get("args", {}) or {}
                custom_ref = raw_op.get("id")
                custom_ref = custom_ref if isinstance(custom_ref, str) else None
                when = raw_op.get("when")

                if not isinstance(op_args, dict):
                    entry = {
                        "method": method_name,
                        "success": False,
                        "error": {"category": "validation_error", "message": "'args' must be an object."},
                    }
                    results.append(entry)
                    resolved_by_ref[position_ref] = entry
                    if custom_ref:
                        resolved_by_ref[custom_ref] = entry
                    continue

                if when is not None:
                    skip_entry = _evaluate_when(when, resolved_by_ref)
                    if skip_entry is not None:
                        entry = {"method": method_name, "skipped": True, "reason": skip_entry}
                        results.append(entry)
                        resolved_by_ref[position_ref] = {**entry, "success": False}
                        if custom_ref:
                            resolved_by_ref[custom_ref] = resolved_by_ref[position_ref]
                        continue

                if not isinstance(method_name, str) or method_name not in dispatch_table:
                    available = ", ".join(sorted(dispatch_table))
                    entry = {
                        "method": method_name,
                        "success": False,
                        "error": {
                            "category": "unknown_operation",
                            "message": f"Unknown operation '{method_name}'. Available: {available}.",
                        },
                    }
                    results.append(entry)
                    resolved_by_ref[position_ref] = entry
                    if custom_ref:
                        resolved_by_ref[custom_ref] = entry
                    continue

                safe_call = dispatch_table[method_name]

                try:
                    response = await safe_call(**op_args)
                except TypeError as exc:
                    # e.g. malformed `args` (wrong/extra keys) slipping past
                    # the dict check above at the Python call boundary.
                    response = ToolResponse(
                        error=ToolError(
                            category=frozenset("validation_error"),
                            message=str(exc),
                            exception_type="TypeError",
                            retryable=True,
                        )
                    )

                if response.error is None:
                    entry = {"method": method_name, "id": custom_ref, "success": True, "result": response.content}
                else:
                    cats = response.error.category
                    entry = {
                        "method": method_name,
                        "id": custom_ref,
                        "success": False,
                        "error": {
                            "category": sorted(cats) if cats else None,
                            "message": response.error.message,
                        },
                    }
                results.append(entry)
                resolved_by_ref[position_ref] = entry
                if custom_ref:
                    resolved_by_ref[custom_ref] = entry

            return ToolResponse(content=results)

        resolved = self._resolve_middlewares(service)
        dispatch_call = self._apply_middlewares(dispatch_call, resolved)

        cls_summary = class_summary(service.service)
        contract = _build_operations_contract(operations)
        return ToolSpec(
            name=service.name,
            description=_build_tool_description(
                service, operations, class_description=cls_summary, contract=contract
            ),
            parameters=(
                ParamSpec(
                    name="operations",
                    annotation=list[dict],
                    required=True,
                    description=contract,
                ),
            ),
            call=dispatch_call,
            operations=tuple(operations),
            class_description=cls_summary or None,
            service_name=service.name,
        )

    @property
    def tool_specs(self) -> list[ToolSpec]:
        """Builds (and caches) the full, framework-agnostic tool list —
        exactly ONE ToolSpec per registered Service or Module."""
        if self._specs is None:
            self._specs = [self._build_spec_for_service(s) for s in self.__services.values()]
            for module in self.__modules.values():
                spec = module.build_tool_spec(parent_middlewares=self.__middlewares)
                self._specs.append(spec)
        return self._specs

    def refresh(self) -> None:
        """Invalidate the cached tool_specs, forcing a rebuild on next access."""
        self._specs = None

    def with_planner(
        self,
        dependency_graph: ServiceDependencyGraph | None = None,
    ) -> Planner:
        """Create a Planner that wraps this manager.

        The planner adds a cross-service planning layer on top of the
        existing batching system. Steps reference operations across
        services, and execution order is validated against an optional
        dependency graph.

        Parameters
        ----------
        dependency_graph:
            Optional graph of inter-service dependencies. When provided,
            the planner validates that step execution respects these
            constraints. When absent, the agent decides freely.

        Returns
        -------
        Planner
            A planner instance bound to this manager.
        """
        from to_tool_manager.core.planner import Planner, ServiceDependencyGraph

        # Allow passing a raw list of ServiceDependency or a full graph
        graph: ServiceDependencyGraph | None = None
        if dependency_graph is not None:
            if isinstance(dependency_graph, ServiceDependencyGraph):
                graph = dependency_graph
            else:
                graph = ServiceDependencyGraph(dependencies=dependency_graph)

        return Planner(self, dependency_graph=graph)

    def register_middleware(self, middlewares: Sequence[Middleware] | Middleware) -> None:
        """Register middleware at runtime (appends to global list)."""
        if isinstance(middlewares, Middleware):
            middlewares = [middlewares]
        if self.__middlewares is None:
            self.__middlewares = list(middlewares)
        else:
            self.__middlewares = list(self.__middlewares) + list(middlewares)
        self.refresh()