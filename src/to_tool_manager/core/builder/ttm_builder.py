from typing import Any, List, Sequence, Tuple, cast

from fastmcp import FastMCP
from pydantic_ai import (
    Agent,
    AgentModelSettings,
    AgentRetries,
    AgentToolset,
    AnyConcurrencyLimit,
    EndStrategy,
)
from pydantic_ai.models import Model, KnownModelName
from pydantic_ai_skills import Skill

from to_tool_manager.core.main.module import Module
from to_tool_manager.core.main.service import Service
from to_tool_manager.core.builder.manager import Manager
from to_tool_manager.core.main.shared.dinamic_depend import DinamicDepend
from to_tool_manager.core.main.to_tool_manager import ToToolManager
from to_tool_manager.core.middleware.middleware import Middleware
from to_tool_manager.exception.agent import AgentAlreadyBuiltError
from to_tool_manager.infra.types.main.service import Include, Exclude
from to_tool_manager.infra.types.main.signature import MethodsType
from to_tool_manager.exception import AgentNotBuiltError


class TTMBuilder:
    """Builder for creating agents declaratively.

    Precondition: name is a valid str
    Postcondition: Agent configured via fluent API

    Reference: REQ-004
    """

    def __init__(self,
        name: str,
        capabilities: List | None = None,
        toolsets: List | None = None,
        model: Model | KnownModelName | str | None = None,
        instructions: Any = None,
        system_prompt: str | Sequence[str] = (),
        model_settings: AgentModelSettings | None = None,
        retries: int | AgentRetries | None = None,
        validation_context: Any = None,
        tools: Sequence[Any] = (),
        defer_model_check: bool = False,
        end_strategy: EndStrategy = 'graceful',
        metadata: Any = None,
        tool_timeout: float | None = None,
        max_concurrency: AnyConcurrencyLimit = None,
        output_type: Any = str,
        description: str | None = None,
    ) -> None:
        """
        Precondition: name is a valid str
        Postcondition: Manager and DinamicDepend initialized
        """
        self.__manager = Manager()
        self.__agent: Agent | None = None
        self.__dep = DinamicDepend()

        self.__name = name
        self.__capabilities = capabilities
        self.__toolsets = toolsets
        self.__middlewares: List[Middleware] = []

        # Store Agent parameters for build()
        self.__model = model
        self.__instructions = instructions
        self.__system_prompt = system_prompt
        self.__model_settings = model_settings
        self.__retries = retries
        self.__validation_context = validation_context
        self.__tools = tools
        self.__defer_model_check = defer_model_check
        self.__end_strategy = end_strategy
        self.__metadata = metadata
        self.__tool_timeout = tool_timeout
        self.__max_concurrency = max_concurrency
        self.__output_type = output_type
        self.__description = description

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.build()

    @property
    def agent(self) -> Agent:
        """Returns the built agent.

        Precondition: build() has been called
        Postcondition: returns a valid Agent
        """
        if self.__agent is None:
            raise AgentNotBuiltError("TTMBuilder")
        return self.__agent

    @agent.setter
    def agent(self, agent: Agent) -> None:
        if self.__agent:
            raise AgentAlreadyBuiltError("TTMBuilder")
        self.__agent = agent

    @property
    def dependency(self) -> DinamicDepend:
        """Returns the dependency instance with registered services.

        Precondition: add_service() has been called at least once
        Postcondition: returns DinamicDepend with registered services
        """
        return self.__dep

    def build(self,
        model: Model | KnownModelName | str | None = None,
        instructions: Any = None,
        system_prompt: str | Sequence[str] | None = None,
        model_settings: AgentModelSettings | None = None,
        retries: int | AgentRetries | None = None,
        validation_context: Any = None,
        tools: Sequence[Any] | None = None,
        defer_model_check: bool | None = None,
        end_strategy: EndStrategy | None = None,
        metadata: Any = None,
        tool_timeout: float | None = None,
        max_concurrency: AnyConcurrencyLimit = None,
        output_type: Any = None,
        description: str | None = None,
    ) -> None:
        """Builds the final agent with the added components.

        Precondition: at least one service or module added
        Postcondition: __agent created

        build() parameters take priority over constructor parameters.
        If a parameter is None, the constructor value is used.

        Reference: REQ-004
        """
        toolsets = self.__manager.toolsets(self.__toolsets)
        capabilities = self.__manager.capabilities(self.__capabilities)

        # build() parameters take priority over __init__ ones
        effective_model = model if model is not None else self.__model
        effective_instructions = instructions if instructions is not None else self.__instructions
        effective_system_prompt = system_prompt if system_prompt is not None else self.__system_prompt
        effective_model_settings = model_settings if model_settings is not None else self.__model_settings
        effective_retries = retries if retries is not None else self.__retries
        effective_validation_context = validation_context if validation_context is not None else self.__validation_context
        effective_tools = tools if tools is not None else self.__tools
        effective_defer_model_check = defer_model_check if defer_model_check is not None else self.__defer_model_check
        effective_end_strategy = cast(EndStrategy, end_strategy if end_strategy is not None else self.__end_strategy)
        effective_metadata = metadata if metadata is not None else self.__metadata
        effective_tool_timeout = tool_timeout if tool_timeout is not None else self.__tool_timeout
        effective_max_concurrency = max_concurrency if max_concurrency is not None else self.__max_concurrency
        effective_output_type = output_type if output_type is not None else self.__output_type
        effective_description = description if description is not None else self.__description

        self.__agent = Agent(
            model=effective_model,
            name=self.__name,
            toolsets=toolsets,  # type: ignore
            capabilities=capabilities,
            instructions=effective_instructions or self.__name,
            deps_type=DinamicDepend,
            system_prompt=effective_system_prompt,
            model_settings=effective_model_settings,
            retries=effective_retries,
            validation_context=effective_validation_context,
            tools=effective_tools,
            defer_model_check=effective_defer_model_check,
            end_strategy=effective_end_strategy,
            metadata=effective_metadata,
            tool_timeout=effective_tool_timeout,
            max_concurrency=effective_max_concurrency,
            output_type=effective_output_type,
            description=effective_description,
        )

        # Apply general middlewares to registered services
        if self.__middlewares:
            self.__apply_middlewares_to_services()

    def add_service(self,
        name: str,
        service: type,
        instructions: str,
        middleware: List | None = None,
        disable_middlewares: Tuple[str, ...] = (),
        include: MethodsType | Include | None = None,
        exclude: MethodsType | Exclude | None = None,
        args: tuple = (),
        kwargs: dict | None = None,
    ) -> 'TTMBuilder':
        """Adds a service to the builder.

        Precondition: name is unique, service is a valid class
        Postcondition: service added to manager, returns self

        Reference: REQ-001
        """
        self.__manager.add_service(Service(
            name=name,
            service=service,
            instructions=instructions,
            middleware=middleware or [],
            disable_middlewares=disable_middlewares,
            include=include,
            exclude=exclude,
            args=args,
            kwargs=kwargs or {},
        ), self.__dep)
        return self

    def add_module(self,
        name: str,
        services: Sequence[Service],
        description: str,
        middleware: List | None = None,
        disable_middlewares: Tuple[str, ...] = (),
        capabilities: List | None = None,
        model: Model | KnownModelName | str | None = None,
        instructions: Any = None,
        system_prompt: str | Sequence[str] = (),
        model_settings: AgentModelSettings | None = None,
        retries: int | AgentRetries | None = None,
        validation_context: Any = None,
        tools: Sequence[Any] = (),
        toolsets: Sequence[AgentToolset] | None = None,
        defer_model_check: bool = False,
        end_strategy: EndStrategy = 'graceful',
        metadata: Any = None,
        tool_timeout: float | None = None,
        max_concurrency: AnyConcurrencyLimit = None,
        output_type: Any = str,
    ) -> 'TTMBuilder':
        """Adds a module to the builder.

        Precondition: name is unique, services is not empty
        Postcondition: module added to manager, returns self

        Reference: REQ-002
        """
        module = Module(
            name=name,
            services=services,
            description=description,
            middleware=middleware,
            disable_middlewares=disable_middlewares,
            capabilities=capabilities,
            model=model,
            instructions=instructions,
            system_prompt=system_prompt,
            model_settings=model_settings,
            retries=retries,
            validation_context=validation_context,
            tools=tools,
            toolsets=toolsets,
            defer_model_check=defer_model_check,
            end_strategy=end_strategy,
            metadata=metadata,
            tool_timeout=tool_timeout,
            max_concurrency=max_concurrency,
            output_type=output_type,
        )
        self.__manager.add_module(module)
        for svc in services:
            svc.service_to_dependency(self.__dep)
        return self

    def add_middleware(self, middleware: Middleware) -> 'TTMBuilder':
        """Adds a general middleware to the builder.

        Precondition: middleware is a valid Middleware
        Postcondition: middleware registered, returns self

        Reference: REQ-005
        """
        self.__middlewares.append(middleware)
        return self

    def remove_middleware_to_service(self, service_name: str, middleware_type: type) -> 'TTMBuilder':
        """Removes a middleware from a service by type.

        Precondition: service_name exists in registered services
        Postcondition: middleware removed from service, returns self

        Reference: REQ-005
        """
        self.__manager.remove_middleware_from_services(service_name, middleware_type)
        return self

    def add_skill(self, skill: Skill) -> 'TTMBuilder':
        """Adds a skill to the builder.

        Precondition: skill is a valid Skill
        Postcondition: skill registered, returns self
        """
        self.__manager.add_skill(skill)
        return self

    def add_ttm(self, manager: ToToolManager) -> 'TTMBuilder':
        """Adds an existing ToToolManager to the builder.

        Precondition: manager is a valid ToToolManager
        Postcondition: manager registered, returns self
        """
        self.__manager.add_ttm(manager)
        return self

    def to_mcp_tool(self, 
        name: str, 
        instructions: str
    ) -> FastMCP:
        """Converts the builder into an MCP server.

        Precondition: name and instructions are valid strings
        Postcondition: returns FastMCP with registered tools
        
        Reference: REQ-008
        """
        if self.__agent is None:
            self.build()

        mcp_tools = self.__build_mcp_tools()

        app = FastMCP(
            name=name,
            instructions=instructions,
            tools=mcp_tools
        )

        return app

    def __build_mcp_tools(self) -> list:
        """Builds FastMCP-compatible functions from capabilities.

        Precondition: build() has been called (services instantiated in DinamicDepend)
        Postcondition: list of flat functions for FastMCP
        """
        import inspect

        mcp_tools = []
        service_objects = self.__manager.service_objects

        capabilities = self.__get_capabilities()
        for capability in capabilities:
            # SubAgents (modules) — manage their tools internally via the framework
            from pydantic_ai_harness.subagents import SubAgents
            if isinstance(capability, SubAgents):
                continue

            # Capability (service) — create flat wrappers
            from pydantic_ai.tools import Tool
            for tool in capability.tools:
                if not isinstance(tool, Tool):
                    continue
                func = self.__make_mcp_wrapper(tool.function, service_objects)
                if func is not None:
                    mcp_tools.append(func)

        return mcp_tools

    def __make_mcp_wrapper(self, pydantic_ai_func, service_objects: dict):
        """Creates a flat FastMCP-compatible function from a pydantic-ai wrapper.

        Precondition: pydantic_ai_func is a make_tool wrapper
        Postcondition: returns function without RunContext, or None if not convertible
        """
        import inspect
        from pydantic_ai.tools import RunContext

        sig = inspect.signature(pydantic_ai_func)
        params = list(sig.parameters.values())

        # Find the ctx: RunContext[DinamicDepend] parameter
        ctx_param = None
        other_params = []
        for p in params:
            if p.name == 'ctx':
                ctx_param = p
            else:
                other_params.append(p)

        if ctx_param is None:
            # Not a pydantic-ai wrapper, return as-is
            return pydantic_ai_func

        # Get service_name from qualname: "ServiceName.method_name"
        qualname = pydantic_ai_func.__qualname__
        parts = qualname.rsplit('.', 1)
        if len(parts) != 2:
            return pydantic_ai_func
        service_name = parts[0]

        # Verify that the service is registered
        if service_name not in service_objects:
            return pydantic_ai_func

        service_obj = service_objects[service_name]
        service_cls = service_obj.service
        instance = getattr(self.__dep, service_name, None)
        if instance is None:
            return pydantic_ai_func

        # Get the original method from the class
        method_name = parts[1]
        original_method = getattr(service_cls, method_name, None)
        if original_method is None:
            return pydantic_ai_func

        # Create flat function with original signature (without ctx)
        if inspect.iscoroutinefunction(original_method):
            async def mcp_async_wrapper(**kwargs):
                bound = original_method.__get__(instance, service_cls)
                return await bound(**kwargs)
            wrapper = mcp_async_wrapper
            wrapper.__name__ = f"{service_name}__{method_name}"
            wrapper.__qualname__ = f"{service_name}__{method_name}"
        else:
            def mcp_sync_wrapper(**kwargs):
                bound = original_method.__get__(instance, service_cls)
                return bound(**kwargs)
            wrapper = mcp_sync_wrapper
            wrapper.__name__ = f"{service_name}__{method_name}"
            wrapper.__qualname__ = f"{service_name}__{method_name}"

        wrapper.__module__ = original_method.__module__
        if hasattr(original_method, '__doc__'):
            wrapper.__doc__ = original_method.__doc__

        # Preserve type annotations (without self)
        if hasattr(original_method, '__annotations__'):
            annotations = {
                k: v for k, v in original_method.__annotations__.items()
                if k != 'self'
            }
            wrapper.__annotations__ = annotations

        # Build signature without ctx
        mcp_params = []
        for p in other_params:
            mcp_params.append(p.replace(kind=inspect.Parameter.KEYWORD_ONLY))
        ret = sig.return_annotation
        return_annotation = ret if ret is not inspect.Parameter.empty else None
        wrapper.__signature__ = inspect.Signature(mcp_params, return_annotation=return_annotation)

        return wrapper

    def __get_capabilities(self):
        """Returns combined capabilities: manager (services + modules) + external.

        Precondition: manager initialized
        Postcondition: unified list of capabilities
        """
        return self.__manager.capabilities(self.__capabilities)

    def __apply_middlewares_to_services(self) -> None:
        """Applies general middlewares to all registered services.

        Precondition: __middlewares is not empty
        Postcondition: middlewares added to each service and Capabilities rebuilt
        """
        self.__manager.apply_middlewares_to_services(self.__middlewares)
        self.__manager.rebuild_capabilities()
