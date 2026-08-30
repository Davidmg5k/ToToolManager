"""Diagnostic: what does the LLM see?"""
import asyncio, sys, os, dataclasses
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "example"))

# --- Stub types matching the example app ---
@dataclasses.dataclass
class CreateUser:
    user_name: str
    email: str
    password: str

@dataclasses.dataclass
class GetUser:
    user_id: str

class StubUserService:
    async def create_user(self, data: CreateUser):
        return {"created": True, "user_name": data.user_name}

    async def get_user(self, data: GetUser):
        return {"user_id": data.user_id}

    async def list_users(self):
        return []


def _build_manager():
    from to_tool_manager.core.manager import ToToolManager
    from to_tool_manager.core.service import Service
    svc = Service(name="user_service", service=StubUserService, description="User mgmt.")
    return ToToolManager([svc])


def _spec(mgr):
    for s in mgr.tool_specs:
        if s.name == "user_service": return s
    raise KeyError


class TestToolSchema:
    def test_one_param_operations(self):
        spec = _spec(_build_manager())
        print("\n=== TOOL SPEC ===")
        print("  Name:", spec.name)
        print("  Params:", [p.name for p in spec.parameters])
        print("  Desc:\n", spec.description)
        assert len(spec.parameters) == 1
        assert spec.parameters[0].name == "operations"

    def test_description_lists_data_param(self):
        spec = _spec(_build_manager())
        assert "create_user" in spec.description
        assert "data" in spec.description

    def test_pydantic_ai_callable_signature(self):
        from to_tool_manager.adapters.pydantic_ai import _build_callable
        fn = _build_callable(_spec(_build_manager()))
        print("\n=== PYDANTIC-AI TOOL ===")
        print("  Sig:", fn.__signature__)
        assert fn.__signature__.parameters["operations"].annotation == list[dict]


class TestLLMArgPatterns:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.spec = _spec(_build_manager())

    async def _d(self, ops):
        return await self.spec.call(operations=ops)

    def test_wrapped_args_success(self):
        ops = [{"method": "create_user", "args": {"data": {"user_name": "u", "email": "u@e.com", "password": "p"}}}]
        r = asyncio.run(self._d(ops))
        print("\n=== WRAPPED ===", r.content or r.error)
        assert r.error is None

    def test_flat_args_auto_wrapped(self):
        """Flat args are auto-wrapped under the param name when they
        match the complex type's field names."""
        ops = [{"method": "create_user", "args": {"user_name": "u", "email": "u@e.com", "password": "p"}}]
        r = asyncio.run(self._d(ops))
        print("\n=== FLAT (auto-wrapped) ===", r.content)
        assert r.error is None
        entry = r.content[0]
        assert entry["success"] is True

    def test_empty_args_fails(self):
        r = asyncio.run(self._d([{"method": "create_user", "args": {}}]))
        print("\n=== EMPTY ===", r.content)
        # Error is in content (nested operations), not top-level
        assert r.error is None
        entry = r.content[0]
        assert entry["success"] is False
        assert "validation_error" in entry["error"]["category"]
        assert "missing" in entry["error"]["message"]

    def test_list_users_no_args(self):
        r = asyncio.run(self._d([{"method": "list_users", "args": {}}]))
        print("\n=== LIST ===", r.content or r.error)
        assert r.error is None


class TestAdapterE2E:
    def test_wrapped_args_through_adapter(self):
        from to_tool_manager.adapters.pydantic_ai import to_pydantic_ai_tools
        fn = next(t for t in to_pydantic_ai_tools(_build_manager().service_specs) if t.__name__ == "user_service")
        async def run():
            return await fn(operations=[{"method": "create_user", "args": {"data": {"user_name": "a", "email": "a@b.com", "password": "x"}}}])
        r = asyncio.run(run())
        print("\n=== ADAPTER WRAPPED ===", r)
        assert isinstance(r, str)

    def test_flat_args_through_adapter(self):
        from to_tool_manager.adapters.pydantic_ai import to_pydantic_ai_tools
        fn = next(t for t in to_pydantic_ai_tools(_build_manager().service_specs) if t.__name__ == "user_service")
        async def run():
            return await fn(operations=[{"method": "create_user", "args": {"user_name": "a", "email": "a@b.com", "password": "x"}}])
        r = asyncio.run(run())
        print("\n=== ADAPTER FLAT ===", r)
        assert isinstance(r, str)


class TestCoercion:
    def test_dict_to_model(self):
        from to_tool_manager.core.coercion import coerce_kwargs
        def fn(self, data):
            return data
        fn.__annotations__ = {"data": CreateUser}
        c = coerce_kwargs(fn, {"data": {"user_name": "t", "email": "t@t.com", "password": "p"}})
        print("\n=== COERCION ===", type(c["data"]))
        assert isinstance(c["data"], CreateUser)


class TestPromptConsistency:
    def test_example_has_data_wrapper(self):
        from to_tool_manager.core.prompts import DEFAULT_SYSTEM_PROMPT_TEMPLATE
        from to_tool_manager.core.contracts import OPERATIONS_CONTRACT
        p = DEFAULT_SYSTEM_PROMPT_TEMPLATE.format(DEFAULT_BEGIN="", DEFAULT_END="", operations_contract=OPERATIONS_CONTRACT, services_overview="")
        print("\n=== PROMPT ===")
        for l in p.split("\n"):
            if any(k in l for k in ["Example", "create_user", "args"]):
                print(" ", l)
        q = chr(34)
        assert q+"data"+q in p
        assert q+"user_name"+q in p


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--tb=short"])
