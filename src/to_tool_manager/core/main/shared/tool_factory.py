import inspect
from typing import Any, Callable

from pydantic_ai.tools import RunContext

from to_tool_manager.core.main.shared.discover import MethodMeta
from to_tool_manager.core.main.shared.dinamic_depend import DinamicDepend


def make_tool(service_name: str, method_meta: MethodMeta) -> Callable[..., Any]:
    """Crea una tool wrapper automática para un método de servicio.

    Precondición: service_name es válido, method_meta contiene el método
    Postcondición: retorna función wrapper compatible con pydantic_ai Tool

    La wrapper:
    - Recibe RunContext como primer arg
    - Obtiene instancia de ctx.deps vía service_name
    - Invoca el método con los args correctos
    - Preserva firma para schema de pydantic_ai
    """
    method_func = method_meta.func
    method_name = method_meta.name

    is_effectively_async = inspect.iscoroutinefunction(method_func)

    if is_effectively_async:
        async def wrapper(ctx: RunContext[DinamicDepend], **kwargs: Any) -> Any:
            instance = getattr(ctx.deps, service_name)
            instance_method = getattr(instance, method_name)
            bound = method_func.__get__(instance, type(instance))
            return await bound(**kwargs)
    else:
        def wrapper(ctx: RunContext[DinamicDepend], **kwargs: Any) -> Any:
            instance = getattr(ctx.deps, service_name)
            instance_method = getattr(instance, method_name)
            bound = method_func.__get__(instance, type(instance))
            return bound(**kwargs)

    # Preservar metadata del método original
    wrapper.__name__ = method_name
    wrapper.__qualname__ = f"{service_name}.{method_name}"
    wrapper.__module__ = method_func.__module__

    if method_meta.docstring:
        wrapper.__doc__ = method_meta.docstring

    # Preservar anotaciones de tipo (excluyendo 'self')
    # IMPORTANTE: no sobrescribir la anotación de ctx: RunContext[DinamicDepend]
    # porque pydantic-ai la usa para detectar que la tool recibe RunContext
    if hasattr(method_func, '__annotations__'):
        annotations = {
            k: v for k, v in method_func.__annotations__.items()
            if k != 'self'
        }
        wrapper.__annotations__.update(annotations)

    # Construir firma explícita para que pydantic_ai genere el JSON schema correcto.
    # Sin esto, inspect.signature() ve **kwargs y el LLM no ve los parámetros reales.
    sig_params = [
        inspect.Parameter('ctx', inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=RunContext[DinamicDepend])
    ]
    for pname, param in method_meta.parameters.items():
        sig_params.append(param.replace(kind=inspect.Parameter.KEYWORD_ONLY))
    return_annotation = method_func.__annotations__.get('return', type(None))
    wrapper.__signature__ = inspect.Signature(sig_params, return_annotation=return_annotation)

    return wrapper
