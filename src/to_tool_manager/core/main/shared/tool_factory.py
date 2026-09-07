import inspect
from typing import Any, Callable

from pydantic_ai.tools import RunContext

from to_tool_manager.core.main.shared.discover import MethodMeta
from to_tool_manager.core.main.shared.dinamic_depend import DinamicDepend


def make_tool(service_name: str, method_meta: MethodMeta) -> Callable[..., Any]:
    """Creates an automatic tool wrapper for a service method.

    Precondition: service_name is valid, method_meta contains the method
    Postcondition: returns wrapper function compatible with pydantic_ai Tool

    The wrapper:
    - Receives RunContext as first arg
    - Gets instance from ctx.deps via service_name
    - Invokes the method with correct args
    - Preserves signature for pydantic_ai schema
    """
    method_func = method_meta.func
    method_name = method_meta.name

    is_effectively_async = inspect.iscoroutinefunction(method_func)

    if is_effectively_async:
        async def async_wrapper(ctx: RunContext[DinamicDepend], **kwargs: Any) -> Any:
            instance = getattr(ctx.deps, service_name)
            bound = method_func.__get__(instance, type(instance))
            try:
                return await bound(**kwargs)
            except Exception as e:
                return f"Error in {service_name}.{method_name}: {type(e).__name__}: {e}"
        wrapper = async_wrapper
    else:
        def sync_wrapper(ctx: RunContext[DinamicDepend], **kwargs: Any) -> Any:
            instance = getattr(ctx.deps, service_name)
            bound = method_func.__get__(instance, type(instance))
            try:
                return bound(**kwargs)
            except Exception as e:
                return f"Error in {service_name}.{method_name}: {type(e).__name__}: {e}"
        wrapper = sync_wrapper

    # Preserve original method metadata
    wrapper.__name__ = method_name
    wrapper.__qualname__ = f"{service_name}.{method_name}"
    wrapper.__module__ = method_func.__module__

    if method_meta.docstring:
        wrapper.__doc__ = method_meta.docstring

    # Preserve type annotations (excluding 'self')
    # IMPORTANT: do not overwrite the ctx: RunContext[DinamicDepend] annotation
    # because pydantic-ai uses it to detect that the tool receives RunContext
    if hasattr(method_func, '__annotations__'):
        annotations = {
            k: v for k, v in method_func.__annotations__.items()
            if k != 'self'
        }
        wrapper.__annotations__.update(annotations)

    # Build explicit signature so pydantic_ai generates the correct JSON schema.
    # Without this, inspect.signature() sees **kwargs and the LLM doesn't see the real parameters.
    sig_params = [
        inspect.Parameter('ctx', inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=RunContext[DinamicDepend])
    ]
    for pname, param in method_meta.parameters.items():
        sig_params.append(param.replace(kind=inspect.Parameter.KEYWORD_ONLY))
    return_annotation = method_func.__annotations__.get('return', type(None))
    wrapper.__signature__ = inspect.Signature(sig_params, return_annotation=return_annotation)

    return wrapper
