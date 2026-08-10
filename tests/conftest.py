import pytest
from to_tool_manager.core.types import ErrorMap, ErrorEntry, ParamSpec, ToolSpec, ToolResponse, ToolError
from to_tool_manager.core.service import Service
from to_tool_manager.orchestrator import ToToolManager
from to_tool_manager.core.discovery import discover_methods


# ---------------------------------------------------------------------------
# Sample service classes for testing
# ---------------------------------------------------------------------------

class DummyService:
    """A simple service for testing."""
    
    def greet(self, name: str) -> str:
        """Greet a user by name."""
        return f"Hello, {name}!"
    
    def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        return a + b
    
    def divide(self, a: float, b: float) -> float:
        """Divide a by b."""
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b


class AsyncDummyService:
    """An async service for testing."""
    
    async def fetch(self, url: str) -> str:
        """Fetch content from URL."""
        return f"Content from {url}"
    
    async def process(self, data: list[int]) -> int:
        """Process a list of numbers."""
        return sum(data)


class PrivateMethodsService:
    """Service with mixed visibility."""
    
    def public_method(self) -> str:
        """A public method."""
        return "public"
    
    def _protected_method(self) -> str:
        """A protected method."""
        return "protected"
    
    def __private_method(self) -> str:
        """A private method."""
        return "private"


class PropertiesService:
    """Service with properties."""
    
    @property
    def version(self) -> str:
        """Service version."""
        return "1.0.0"
    
    def get_name(self) -> str:
        """Get service name."""
        return "PropertiesService"


class FailingService:
    """Service that raises various errors."""
    
    def not_found(self, id: int) -> str:
        """Raise not found error."""
        raise FileNotFoundError(f"Item {id} not found")
    
    def permission_error(self) -> str:
        """Raise permission error."""
        raise PermissionError("Access denied")
    
    def timeout_error(self) -> str:
        """Raise timeout error."""
        raise TimeoutError("Request timed out")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def dummy_service_class():
    return DummyService


@pytest.fixture
def async_service_class():
    return AsyncDummyService


@pytest.fixture
def dummy_service():
    return DummyService()


@pytest.fixture
def service_config():
    return Service(
        name="Dummy",
        service=DummyService,
        description="A dummy service for testing",
    )


@pytest.fixture
def async_service_config():
    return Service(
        name="AsyncDummy",
        service=AsyncDummyService,
        description="An async dummy service",
    )


@pytest.fixture
def error_map():
    return (
        ErrorMap()
        .map(FileNotFoundError, category="not_found")
        .map(PermissionError, category="permission_denied", retryable=False)
        .map(TimeoutError, category="timeout", retryable=True)
    )


@pytest.fixture
def failing_service_config(error_map):
    return Service(
        name="Failing",
        service=FailingService,
        error_map=error_map,
    )


@pytest.fixture
def simple_manager(service_config):
    return ToToolManager([service_config])


@pytest.fixture
def multi_service_manager(service_config, async_service_config):
    return ToToolManager([service_config, async_service_config])
