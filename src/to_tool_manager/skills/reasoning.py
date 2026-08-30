"""
Reasoning Skill -- Backward-compatible alias for strategy_skill.

The original reasoning content has been merged into strategy.py to
reduce token overhead. This module re-exports for backward compatibility.
"""
try:
    from pydantic_ai_skills import Skill
except ImportError:
    Skill = None  # type: ignore[assignment,misc]

from to_tool_manager.skills.strategy import strategy_skill as _strategy

# Backward-compatible alias: code that imports reasoning_skill gets
# the same object as strategy_skill.
reasoning_skill = _strategy
