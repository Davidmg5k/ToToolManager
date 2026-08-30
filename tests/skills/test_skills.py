from to_tool_manager.skills import (
    strategy_skill,
    reasoning_skill,
    composition_skill,
    dependencies_skill,
    validation_skill,
    error_handling_skill,
    planning_skill,
    default_skills,
    build_skills_toolset,
)
from pydantic_ai_skills import Skill, SkillsToolset


class TestSkills:
    def test_strategy_skill(self):
        assert strategy_skill.name == "strategy"
        assert "Pre-Analysis" in strategy_skill.content

    def test_reasoning_skill_alias(self):
        # Backward compat: reasoning_skill is the same object as strategy_skill
        assert reasoning_skill is strategy_skill

    def test_composition_skill_alias(self):
        # Backward compat: composition_skill is the same object as strategy_skill
        assert composition_skill is strategy_skill

    def test_dependencies_skill(self):
        assert dependencies_skill.name == "dependencies"
        assert "Propagation" in dependencies_skill.content

    def test_validation_skill(self):
        assert validation_skill.name == "validation"
        assert "Input & State Validation" in validation_skill.content

    def test_error_handling_skill(self):
        assert error_handling_skill.name == "error-handling"
        assert error_handling_skill.content is not None
        # Verify "Error Classification" section was removed (duplicated from instructions)
        assert "Error Classification" not in error_handling_skill.content

    def test_planning_skill(self):
        assert planning_skill.name == "planning"
        assert planning_skill.content is not None


class TestDefaultSkills:
    def test_count(self):
        # 3 ALWAYS_ON (strategy, validation, error_handling) + 2 CONDITIONAL = 5
        assert len(default_skills) == 5

    def test_all_are_skills(self):
        for skill in default_skills:
            assert isinstance(skill, Skill)


class TestBuildSkillsToolset:
    def test_default(self):
        toolset = build_skills_toolset()
        assert isinstance(toolset, SkillsToolset)

    def test_custom_skills(self):
        custom = [strategy_skill, validation_skill]
        toolset = build_skills_toolset(skills=custom)
        assert isinstance(toolset, SkillsToolset)

    def test_with_directories(self):
        toolset = build_skills_toolset(directories=["/some/path"])
        assert isinstance(toolset, SkillsToolset)
