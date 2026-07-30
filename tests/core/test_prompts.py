import pytest
from to_tool_manager.core.prompts import (
    build_system_prompt,
    build_instructions,
    build_service_description,
    _services_overview,
    _merge,
)
from to_tool_manager.core.service import Service
from to_tool_manager.core.module import Module


class DummyService:
    pass


class TestMerge:
    def test_none_custom(self):
        result = _merge("default", None, "extend")
        assert result == "default"

    def test_extend_mode(self):
        result = _merge("default", "custom text", "extend")
        assert "default" in result
        assert "custom text" in result

    def test_override_mode(self):
        result = _merge("default", "custom text", "override")
        assert result == "custom text"
        assert "default" not in result

    def test_custom_stripped(self):
        result = _merge("default", "  custom  ", "extend")
        assert "custom" in result


class TestServicesOverview:
    def test_services_only(self):
        svc = Service(name="Order", service=DummyService, description="Order service")
        overview = _services_overview([svc])
        assert "Order" in overview
        assert "Order service" in overview

    def test_modules(self):
        svc = Service(name="Item", service=DummyService)
        module = Module(name="Inventory", services=[svc], description="Inventory module")
        overview = _services_overview([module])
        assert "Inventory" in overview
        assert "Module" in overview

    def test_empty(self):
        overview = _services_overview([])
        assert "no services" in overview

    def test_no_description(self):
        svc = Service(name="Test", service=DummyService)
        overview = _services_overview([svc])
        assert "Test" in overview


class TestBuildSystemPrompt:
    def test_default(self):
        svc = Service(name="Order", service=DummyService, description="Order service")
        prompt = build_system_prompt([svc])
        assert "Order" in prompt
        assert "DEFAULT:BEGIN" in prompt

    def test_extend_mode(self):
        svc = Service(name="Order", service=DummyService)
        prompt = build_system_prompt([svc], custom="Custom instructions", mode="extend")
        assert "DEFAULT:BEGIN" in prompt
        assert "Custom instructions" in prompt

    def test_override_mode(self):
        svc = Service(name="Order", service=DummyService)
        prompt = build_system_prompt([svc], custom="Custom prompt", mode="override")
        assert "Custom prompt" in prompt
        assert "DEFAULT:BEGIN" not in prompt


class TestBuildInstructions:
    def test_default(self):
        instructions = build_instructions()
        assert "DEFAULT:BEGIN" in instructions

    def test_extend(self):
        instructions = build_instructions(custom="Extra rules", mode="extend")
        assert "DEFAULT:BEGIN" in instructions
        assert "Extra rules" in instructions

    def test_override(self):
        instructions = build_instructions(custom="My rules", mode="override")
        assert instructions == "My rules"


class TestBuildServiceDescription:
    def test_default(self):
        svc = Service(name="Order", service=DummyService)
        desc = build_service_description(svc)
        assert "Order" in desc

    def test_with_custom_description(self):
        svc = Service(name="Order", service=DummyService, description="Custom desc")
        desc = build_service_description(svc)
        assert "Custom desc" in desc

    def test_extend(self):
        svc = Service(name="Order", service=DummyService)
        desc = build_service_description(svc, custom="Extra", mode="extend")
        assert "Order" in desc
        assert "Extra" in desc

    def test_override(self):
        svc = Service(name="Order", service=DummyService)
        desc = build_service_description(svc, custom="My desc", mode="override")
        assert desc == "My desc"
