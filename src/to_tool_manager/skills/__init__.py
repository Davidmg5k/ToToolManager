"""
Agnostic Skills — Behavioral patterns for agents.

These skills contain no business logic.
They are guidelines that influence HOW the agent thinks and executes.
"""
from pydantic_ai_skills import SkillsToolset

from to_tool_manager.skills.composition import composition_skill
from to_tool_manager.skills.dependencies import dependencies_skill
from to_tool_manager.skills.error_handling import error_handling_skill
from to_tool_manager.skills.planning import planning_skill
from to_tool_manager.skills.reasoning import reasoning_skill
from to_tool_manager.skills.validation import validation_skill

__all__ = [
    "reasoning_skill",
    "dependencies_skill",
    "validation_skill",
    "error_handling_skill",
    "composition_skill",
    "planning_skill",
    "default_skills",
    "build_skills_toolset",
]

# Always present (same rationale as the other five): each skill is a
# small, fixed-cost block (well under the 500-token budget) and
# `build_skills_toolset()` has no visibility into a specific manager's
# service count, so conditional inclusion by "number of services"
# would require threading manager state through the adapter just to
# decide whether to load ~390 tokens of guidance. Not worth the extra
# API surface — see docs/mejoras-y-plan-de-desarrollo.md (section 2.2,
# P-1/P-2/P-3) for the full rationale.
default_skills = [
    reasoning_skill,
    dependencies_skill,
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
