"""
Agnostic Skills — Behavioral patterns for agents.

These skills contain no business logic.
They are guidelines that influence HOW the agent thinks and executes.
"""
from pydantic_ai_skills import SkillsToolset

from to_tool_manager.skills.composition import composition_skill
from to_tool_manager.skills.error_handling import error_handling_skill
from to_tool_manager.skills.planning import planning_skill
from to_tool_manager.skills.reasoning import reasoning_skill
from to_tool_manager.skills.validation import validation_skill

__all__ = [
    "reasoning_skill",
    "validation_skill",
    "error_handling_skill",
    "composition_skill",
    "planning_skill",
    "default_skills",
    "build_skills_toolset",
]

default_skills = [
    reasoning_skill,
    validation_skill,
    error_handling_skill,
    composition_skill,
    planning_skill,
]


def build_skills_toolset(
    skills=None,
    directories=None,
):
    """
    Build a SkillsToolset with default or custom skills.

    Args:
        skills: List of programmatic Skills. If None, uses default_skills.
        directories: Directories to discover SKILL.md skills.

    Returns:
        Configured SkillsToolset.
    """
    return SkillsToolset(
        skills=skills or default_skills,
        directories=directories or [],
    )
