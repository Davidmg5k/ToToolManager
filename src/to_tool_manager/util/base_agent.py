"""BaseAgent: declarative agent lifecycle built on top of TTMBuilder."""

from abc import ABC, abstractmethod
from typing import Any, List, Sequence

from pydantic_ai import (
    Agent,
    AgentModelSettings,
    AgentRetries,
    AnyConcurrencyLimit,
    EndStrategy,
)
from pydantic_ai.models import KnownModelName, Model

from to_tool_manager.core.builder.ttm_builder import TTMBuilder
from to_tool_manager.core.main.shared.dinamic_depend import DinamicDepend


class BaseAgent(ABC):
    """Abstract base class for the platform's agents.

    `BaseAgent` wraps the declarative assembly performed by `TTMBuilder`
    behind a two-step lifecycle:

    1. The subclass is constructed with the *exact* keyword arguments
       accepted by `TTMBuilder.__init__` (same names, order, types and
       defaults). Every value is captured verbatim and never mutated.
    2. `init_agent()` opens a `TTMBuilder` context configured with those
       values, delegates registration of services, modules, middlewares
       and skills to the abstract `_composer()` hook, and lets the
       context manager close the builder, which triggers
       `TTMBuilder.build()`.

    Once `init_agent()` returns, the built `pydantic_ai.Agent` is readable
    through the `agent` property and the populated dependency container
    through `dependency`. Both raise `RuntimeError` before that point.

    Subclass contract:
        Implement `_composer(ttm_builder)` and register the agent's
        components there. Do **not** call `TTMBuilder.build()` yourself;
        the context manager owns the build step.

    Example:
        ```python
        class Greeter:
            def greet(self, name: str) -> str:
                return f"Hello {name}"

        class GreeterAgent(BaseAgent):
            def _composer(self, ttm_builder: TTMBuilder) -> None:
                ttm_builder.add_service(
                    name="greeter",
                    service=Greeter,
                    instructions="Use this service to greet users.",
                )

        wrapper = GreeterAgent(name="greeter", model="test")
        wrapper.init_agent()
        wrapper.agent       # -> pydantic_ai.Agent
        wrapper.dependency  # -> DinamicDepend with the "greeter" service
        ```

    Precondition: `name` is a valid string; the subclass implements
    `_composer`.
    Postcondition: after `init_agent()`, `agent` and `dependency` are
    readable; before it, both raise `RuntimeError`.
    """

    def __init__(
        self,
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
        """Captures the `TTMBuilder` configuration without building anything.

        The signature mirrors `TTMBuilder.__init__` exactly -- same
        parameter names, order, annotations and defaults -- so any
        configuration valid for the builder is valid here and can be
        compared one-to-one against the builder's reference.

        No `Agent` is created at construction time: the deferred build
        happens in `init_agent()`, after `_composer()` has registered
        the components.

        Precondition: `name` is a valid string; `model`, if given,
        resolves to a model known to pydantic-ai (checked at build time
        unless `defer_model_check` is `True`).
        Postcondition: configuration stored on private attributes;
        `agent` and `dependency` still raise `RuntimeError`.

        Args:
            name: Agent name; also used as the fallback `instructions`
                by `TTMBuilder.build()`.
            capabilities: Extra capabilities merged with the generated
                ones. Defaults to `None`.
            toolsets: Extra toolsets; skills and modules are prepended
                to them. Defaults to `None`.
            model: LLM model -- a `Model` instance, a `KnownModelName`,
                or a `"provider:model"` string. Defaults to `None`
                (resolved by pydantic-ai at build time).
            instructions: Agent instructions. When falsy, `name` is used
                instead. Defaults to `None`.
            system_prompt: System prompt, either a single string or a
                sequence of strings. Defaults to `()`.
            model_settings: pydantic-ai `AgentModelSettings` forwarded
                verbatim to `Agent`. Defaults to `None`.
            retries: Retry budget, as an `int` or an `AgentRetries`
                instance. Defaults to `None`.
            validation_context: Validation context forwarded verbatim
                to `Agent`. Defaults to `None`.
            tools: Extra hand-written tools exposed by the agent.
                Defaults to `()`.
            defer_model_check: Skip model validation at construction so
                the agent can be built offline (e.g. with
                `model="test"`). Defaults to `False`.
            end_strategy: Strategy applied when the run's end condition
                is reached; forwarded verbatim to `Agent`. Defaults to
                `'graceful'`.
            metadata: Arbitrary metadata forwarded verbatim to `Agent`.
                Defaults to `None`.
            tool_timeout: Per-tool timeout in seconds; `None` disables
                it. Defaults to `None`.
            max_concurrency: Maximum number of concurrent tool calls;
                `None` uses the pydantic-ai default. Defaults to `None`.
            output_type: Result type of an agent run. Defaults to `str`.
            description: Human-readable agent description. Defaults to
                `None`.

        Note:
            The `Any` annotations on `instructions`, `validation_context`,
            `metadata` and `output_type` are not a local shortcut: they
            mirror `TTMBuilder.__init__`'s public contract, where
            pydantic-ai deliberately accepts heterogeneous values.
        """
        self.__agent: Agent | None = None
        self.__dependency: DinamicDepend | None = None

        self.__name: str = name
        self.__capabilities: List | None = capabilities
        self.__toolsets: List | None = toolsets
        self.__model: Model | KnownModelName | str | None = model
        self.__instructions: Any = instructions
        self.__system_prompt: str | Sequence[str] = system_prompt
        self.__model_settings: AgentModelSettings | None = model_settings
        self.__retries: int | AgentRetries | None = retries
        self.__validation_context: Any = validation_context
        self.__tools: Sequence[Any] = tools
        self.__defer_model_check: bool = defer_model_check
        self.__end_strategy: EndStrategy = end_strategy
        self.__metadata: Any = metadata
        self.__tool_timeout: float | None = tool_timeout
        self.__max_concurrency: AnyConcurrencyLimit = max_concurrency
        self.__output_type: Any = output_type
        self.__description: str | None = description

    # ===============================================================
    # Lifecycle
    # ===============================================================

    def init_agent(self) -> None:
        """Builds the underlying `pydantic_ai.Agent` from the stored configuration.

        Opens a `TTMBuilder` context configured with the values captured
        in `__init__`, hands the builder to `_composer()` so the subclass
        can register its services, modules, middlewares and skills, and
        lets the context manager run `TTMBuilder.build()` on exit.

        Calling this method a second time rebuilds from scratch on a
        fresh builder, replacing the instances subsequently returned by
        the `agent` and `dependency` properties (references already
        obtained keep pointing to the previous objects).

        Precondition: `_composer` is implemented and registers at least
        one service, module or skill; otherwise the agent is built with
        no tools.
        Postcondition: `self.__agent` and `self.__dependency` hold the
        results of the last build and both properties are readable.

        Raises:
            Propagates any exception raised by `_composer()` or by
            `TTMBuilder.build()`. In that case the postcondition does
            not hold and `agent` / `dependency` keep raising
            `RuntimeError`.
        """
        with TTMBuilder(
            name=self.__name,
            capabilities=self.__capabilities,
            toolsets=self.__toolsets,
            model=self.__model,
            instructions=self.__instructions,
            system_prompt=self.__system_prompt,
            model_settings=self.__model_settings,
            retries=self.__retries,
            validation_context=self.__validation_context,
            tools=self.__tools,
            defer_model_check=self.__defer_model_check,
            end_strategy=self.__end_strategy,
            metadata=self.__metadata,
            tool_timeout=self.__tool_timeout,
            max_concurrency=self.__max_concurrency,
            output_type=self.__output_type,
            description=self.__description,
        ) as ttmb:
            self._composer(ttmb)
        self.__agent = ttmb.agent
        self.__dependency = ttmb.dependency

    # ===============================================================
    # Properties
    # ===============================================================

    @property
    def agent(self) -> Agent:
        """Returns the agent built by the last `init_agent()` call.

        Precondition: `init_agent()` completed successfully.
        Postcondition: returns the `pydantic_ai.Agent` instance created
        by `TTMBuilder.build()`; the instance is stable until the next
        `init_agent()` call.

        Raises:
            RuntimeError: if `init_agent()` has not been called yet, or
                if the last call failed before the postcondition held.

        Returns:
            The built `pydantic_ai.Agent`, ready to run.
        """
        if self.__agent is None:
            raise RuntimeError(
                f"Agent {self.__name!r} is not initialized: call init_agent() first."
            )
        return self.__agent

    @property
    def dependency(self) -> DinamicDepend:
        """Returns the dependency container populated by the last `init_agent()` call.

        The container holds one instance per service registered through
        `_composer()`, and is the `deps` object passed to every tool run
        by pydantic-ai.

        Precondition: `init_agent()` completed successfully.
        Postcondition: returns the `DinamicDepend` instance filled during
        the last build; the instance is stable until the next
        `init_agent()` call.

        Raises:
            RuntimeError: if `init_agent()` has not been called yet, or
                if the last call failed before the postcondition held.

        Returns:
            The populated `DinamicDepend` container.
        """
        if self.__dependency is None:
            raise RuntimeError(
                f"Dependencies of {self.__name!r} are not initialized: "
                "call init_agent() first."
            )
        return self.__dependency

    # ===============================================================
    # Template method
    # ===============================================================

    @abstractmethod
    def _composer(self, ttm_builder: TTMBuilder) -> None:
        """Registers the agent's components on the open builder.

        Template method of the class: `init_agent()` calls it while the
        `TTMBuilder` context is still open, before the implicit
        `build()`. Register services (`add_service`), modules
        (`add_module`), sub-agents (`add_sub_agent`), middlewares
        (`add_middleware`) and skills (`add_skill`) here.

        Do not call `TTMBuilder.build()` inside this method: the context
        manager owns the build step and the builder is still unbuilt
        when the hook runs.

        Precondition: `ttm_builder` is an open, unbuilt builder already
        configured with the constructor values.
        Postcondition: every component registered here is included in the
        subsequent `TTMBuilder.build()`.

        Args:
            ttm_builder: The builder opened by `init_agent()`, ready to
                receive components.

        Returns:
            None. The effect is entirely on `ttm_builder`.
        """
        ...
