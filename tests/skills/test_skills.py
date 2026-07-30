import pytest
from to_tool_manager.skills import (
    reasoning_skill,
    dependencies_skill,
    validation_skill,
    error_handling_skill,
    composition_skill,
    planning_skill,
    default_skills,
    build_skills_toolset,
)
from pydantic_ai_skills import Skill, SkillsToolset


class TestSkills:
    def test_reasoning_skill(self):
        assert reasoning_skill.name == "reasoning"
        assert "Pre-Analysis" in reasoning_skill.content

    def test_dependencies_skill(self):
        assert dependencies_skill.name == "dependencies"
        assert "Propagation" in dependencies_skill.content

    def test_validation_skill(self):
        assert validation_skill.name == "validation"
        assert "Input Validation" in validation_skill.content

    def test_error_handling_skill(self):
        assert error_handling_skill.name == "error-handling"
        assert error_handling_skill.content is not None

    def test_composition_skill(self):
        assert composition_skill.name == "composition"
        assert composition_skill.content is not None

    def test_planning_skill(self):
        assert planning_skill.name == "planning"
        assert planning_skill.content is not None


class TestDefaultSkills:
    def test_count(self):
        assert len(default_skills) == 6

    def test_all_are_skills(self):
        for skill in default_skills:
            assert isinstance(skill, Skill)


class TestBuildSkillsToolset:
    def test_default(self):
        toolset = build_skills_toolset()
        assert isinstance(toolset, SkillsToolset)

    def test_custom_skills(self):
        custom = [reasoning_skill, validation_skill]
        toolset = build_skills_toolset(skills=custom)
        assert isinstance(toolset, SkillsToolset)

    def test_with_directories(self):
        toolset = build_skills_toolset(directories=["/some/path"])
        assert isinstance(toolset, SkillsToolset)
