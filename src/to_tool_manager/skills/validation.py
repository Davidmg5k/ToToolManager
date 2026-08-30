"""
Validation Skill -- Patterns for validation before execution.

Influences HOW the agent validates data and preconditions.
Contains no specific business rules, only general patterns.
"""
try:
    from pydantic_ai_skills import Skill
except ImportError:
    Skill = None  # type: ignore[assignment,misc]


VALIDATION_CONTENT = """
## Validation Patterns

### 1. Input & State Validation
Before executing:
- Required parameters present, correct types, values in range
- Non-empty strings when content is expected
- Resources exist (for modification) or don't (for creation)
- Detect concurrent state conflicts and respect system invariants

### 2. Dependency Validation
When one operation depends on another:
- Execute the dependent operation first
- Verify the result is valid before continuing
- If it fails, report dependency_not_satisfied error

### 3. Security Validation
Before sensitive operations:
- Verify permissions (if applicable)
- Detect potentially destructive operations
- Confirm with the user when ambiguous
"""

validation_skill = Skill(
    name="validation",
    description="Patterns for validating data and preconditions before executing operations",
    content=VALIDATION_CONTENT,
) if Skill is not None else None
