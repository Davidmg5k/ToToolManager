import pytest

from to_tool_manager.core.manager import ToToolManager
from to_tool_manager.core.module import Module
from to_tool_manager.core.service import Service
from to_tool_manager.operations import check_manager_health


class HealthyService:
    def ping(self) -> str:
        """Returns pong."""
        return "pong"


class BrokenService:
    def __init__(self):
        raise RuntimeError("could not connect to downstream dependency")

    def ping(self) -> str:
        """Returns pong."""
        return "pong"


class TestCheckManagerHealthAllHealthy:
    @pytest.mark.anyio
    async def test_single_healthy_service(self):
        manager = ToToolManager([Service(name="Healthy", service=HealthyService)])

        report = await check_manager_health(manager)

        assert report.healthy is True
        assert len(report.services) == 1
        assert report.services[0].name == "Healthy"
        assert report.services[0].healthy is True
        assert report.services[0].error is None

    @pytest.mark.anyio
    async def test_module_with_healthy_services(self):
        module = Module(
            name="Ops",
            services=[Service(name="Healthy", service=HealthyService)],
        )
        manager = ToToolManager([module])

        report = await check_manager_health(manager)

        assert report.healthy is True
        assert len(report.services) == 1
        assert report.services[0].name == "Ops"


class TestCheckManagerHealthWithBrokenService:
    @pytest.mark.anyio
    async def test_broken_service_reported_unhealthy_without_raising(self):
        manager = ToToolManager([Service(name="Broken", service=BrokenService)])

        report = await check_manager_health(manager)

        assert report.healthy is False
        assert len(report.services) == 1
        assert report.services[0].name == "Broken"
        assert report.services[0].healthy is False
        assert "could not connect" in report.services[0].error

    @pytest.mark.anyio
    async def test_one_broken_service_does_not_obscure_a_healthy_sibling(self):
        """Core design point: services are checked independently, so a
        broken service's failure doesn't prevent reporting on its
        healthy siblings."""
        manager = ToToolManager([
            Service(name="Healthy", service=HealthyService),
            Service(name="Broken", service=BrokenService),
        ])

        report = await check_manager_health(manager)

        assert report.healthy is False
        by_name = {s.name: s for s in report.services}
        assert by_name["Healthy"].healthy is True
        assert by_name["Broken"].healthy is False


class TestCheckManagerHealthReadinessProbes:
    @pytest.mark.anyio
    async def test_sync_probe_success(self):
        manager = ToToolManager([Service(name="Healthy", service=HealthyService)])

        report = await check_manager_health(manager, readiness_probes={"db": lambda: True})

        assert report.healthy is True
        assert report.probes[0].name == "db"
        assert report.probes[0].healthy is True

    @pytest.mark.anyio
    async def test_async_probe_success(self):
        async def db_probe() -> bool:
            return True

        manager = ToToolManager([Service(name="Healthy", service=HealthyService)])

        report = await check_manager_health(manager, readiness_probes={"db": db_probe})

        assert report.healthy is True
        assert report.probes[0].healthy is True

    @pytest.mark.anyio
    async def test_failing_probe_marks_overall_unhealthy_even_with_healthy_services(self):
        manager = ToToolManager([Service(name="Healthy", service=HealthyService)])

        report = await check_manager_health(manager, readiness_probes={"db": lambda: False})

        assert report.healthy is False
        assert all(s.healthy for s in report.services)  # services themselves are fine
        assert report.probes[0].healthy is False

    @pytest.mark.anyio
    async def test_raising_probe_reported_unhealthy_without_propagating(self):
        def broken_probe() -> bool:
            raise ConnectionError("db unreachable")

        manager = ToToolManager([Service(name="Healthy", service=HealthyService)])

        report = await check_manager_health(manager, readiness_probes={"db": broken_probe})

        assert report.healthy is False
        assert report.probes[0].healthy is False
        assert "db unreachable" in report.probes[0].error

    @pytest.mark.anyio
    async def test_no_probes_given_is_fine(self):
        manager = ToToolManager([Service(name="Healthy", service=HealthyService)])

        report = await check_manager_health(manager)

        assert report.probes == ()
