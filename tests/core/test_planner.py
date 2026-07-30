import pytest
from to_tool_manager.core.planner import (
    Planner,
    Plan,
    Step,
    StepOperation,
    StepStatus,
    ServiceDependency,
    ServiceDependencyGraph,
    DependencyValidator,
    PlanEvent,
    PlanEventType,
    PlanRefError,
)
from to_tool_manager.core.manager import ToToolManager
from to_tool_manager.core.service import Service


class OrderService:
    def create(self, name: str) -> str:
        return f"Created {name}"

    def list_all(self) -> list:
        return ["order1", "order2"]


class UserService:
    def get(self, user_id: int) -> str:
        return f"User {user_id}"


@pytest.fixture
def manager():
    svc1 = Service(name="Order", service=OrderService)
    svc2 = Service(name="User", service=UserService)
    return ToToolManager([svc1, svc2])


@pytest.fixture
def planner(manager):
    return Planner(manager)


class TestStepStatus:
    def test_values(self):
        assert StepStatus.PENDING == "pending"
        assert StepStatus.IN_PROGRESS == "in_progress"
        assert StepStatus.COMPLETED == "completed"
        assert StepStatus.FAILED == "failed"
        assert StepStatus.SKIPPED == "skipped"


class TestStepOperation:
    def test_creation(self):
        op = StepOperation(service="Order", method="create", args={"name": "test"})
        assert op.service == "Order"
        assert op.method == "create"
        assert op.args == {"name": "test"}

    def test_optional_id(self):
        op = StepOperation(service="Order", method="create", id="op1")
        assert op.id == "op1"


class TestStep:
    def test_creation(self):
        step = Step(description="Create order")
        assert step.description == "Create order"
        assert step.status == StepStatus.PENDING
        assert step.depends_on == []

    def test_custom_id(self):
        step = Step(id="step1", description="Test")
        assert step.id == "step1"


class TestPlan:
    def test_creation(self):
        plan = Plan()
        assert plan.steps == []
        assert plan.id is not None
        assert plan.created_at is not None


class TestDependencyValidator:
    def test_no_graph(self):
        validator = DependencyValidator(None)
        assert validator.validate_order([]) is None

    def test_valid_order(self):
        graph = ServiceDependencyGraph(
            dependencies=[ServiceDependency(source="Order", target="User")]
        )
        validator = DependencyValidator(graph)
        steps = [
            Step(id="s1", description="User step", operations=[StepOperation(service="User", method="get")]),
            Step(id="s2", description="Order step", operations=[StepOperation(service="Order", method="create")]),
        ]
        assert validator.validate_order(steps) is None

    def test_invalid_order(self):
        graph = ServiceDependencyGraph(
            dependencies=[ServiceDependency(source="Order", target="User")]
        )
        validator = DependencyValidator(graph)
        steps = [
            Step(id="s1", description="Order step", operations=[StepOperation(service="Order", method="create")]),
            Step(id="s2", description="User step", operations=[StepOperation(service="User", method="get")]),
        ]
        errors = validator.validate_order(steps)
        assert errors is not None
        assert len(errors) > 0

    def test_get_next_executable_no_deps(self):
        validator = DependencyValidator(None)
        steps = [
            Step(id="s1", description="Step 1", depends_on=[]),
            Step(id="s2", description="Step 2", depends_on=["s1"]),
        ]
        next_steps = validator.get_next_executable(steps, set())
        assert len(next_steps) == 1
        assert next_steps[0].id == "s1"

    def test_get_next_executable_with_deps_satisfied(self):
        validator = DependencyValidator(None)
        steps = [
            Step(id="s1", description="Step 1", depends_on=[]),
            Step(id="s2", description="Step 2", depends_on=["s1"]),
        ]
        steps[0].status = StepStatus.COMPLETED
        next_steps = validator.get_next_executable(steps, {"s1"})
        assert len(next_steps) == 1
        assert next_steps[0].id == "s2"

    def test_get_next_executable_all_independent(self):
        validator = DependencyValidator(None)
        steps = [
            Step(id="s1", description="Step 1", depends_on=[]),
            Step(id="s2", description="Step 2", depends_on=[]),
        ]
        next_steps = validator.get_next_executable(steps, set())
        assert len(next_steps) == 2


class TestPlanner:
    @pytest.mark.anyio
    async def test_create_plan(self, planner):
        steps = [
            Step(
                description="Create order",
                operations=[StepOperation(service="Order", method="create", args={"name": "test"})],
            )
        ]
        plan = await planner.create_plan(steps)
        assert plan is not None
        assert len(plan.steps) == 1

    @pytest.mark.anyio
    async def test_get_plan(self, planner):
        steps = [Step(description="Test", operations=[])]
        plan = await planner.create_plan(steps)
        retrieved = planner.get_plan(plan.id)
        assert retrieved is plan

    @pytest.mark.anyio
    async def test_get_plan_not_found(self, planner):
        assert planner.get_plan("nonexistent") is None

    @pytest.mark.anyio
    async def test_execute_plan(self, planner):
        steps = [
            Step(
                id="step1",
                description="Create order",
                operations=[StepOperation(service="Order", method="create", args={"name": "test"})],
            )
        ]
        plan = await planner.create_plan(steps)
        result = await planner.execute_plan(plan.id)
        assert result.steps[0].status == StepStatus.COMPLETED

    @pytest.mark.anyio
    async def test_execute_plan_not_found(self, planner):
        with pytest.raises(ValueError, match="not found"):
            await planner.execute_plan("nonexistent")

    @pytest.mark.anyio
    async def test_update_step(self, planner):
        steps = [Step(id="s1", description="Test", operations=[])]
        plan = await planner.create_plan(steps)
        step = await planner.update_step(plan.id, "s1", status=StepStatus.COMPLETED, result={"done": True})
        assert step is not None
        assert step.status == StepStatus.COMPLETED

    @pytest.mark.anyio
    async def test_update_step_not_found(self, planner):
        steps = [Step(id="s1", description="Test", operations=[])]
        plan = await planner.create_plan(steps)
        result = await planner.update_step(plan.id, "nonexistent")
        assert result is None

    @pytest.mark.anyio
    async def test_condition_auto_depends_on(self, planner):
        steps = [
            Step(id="s1", description="Step 1", operations=[]),
            Step(
                id="s2",
                description="Step 2",
                operations=[],
                condition={"op": "s1", "outcome": "success"},
            ),
        ]
        plan = await planner.create_plan(steps)
        assert "s1" in plan.steps[1].depends_on

    @pytest.mark.anyio
    async def test_condition_invalid_op_raises(self, planner):
        steps = [
            Step(
                id="s1",
                description="Step 1",
                operations=[],
                condition={"op": "nonexistent", "outcome": "success"},
            )
        ]
        with pytest.raises(ValueError, match="unknown step"):
            await planner.create_plan(steps)

    def test_build_tools(self, planner):
        tools = planner.build_tools()
        assert len(tools) == 4
        names = [t["name"] for t in tools]
        assert "create_plan" in names
        assert "execute_plan" in names
        assert "update_plan_step" in names
        assert "get_plan" in names
