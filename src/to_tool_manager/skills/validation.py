"""
Validation Skill — Patterns for validation before execution.

Influences HOW the agent validates data and preconditions.
Contains no specific business rules, only general patterns.
"""
try:
    from pydantic_ai_skills import Skill
except ImportError:
    Skill = None  # type: ignore[assignment,misc]


VALIDATION_CONTENT = """
## Validation Patterns

### 1. Input Validation
Always validate before executing:
- Required parameters present
- Correct data types
- Values within acceptable ranges
- Non-empty strings when content is expected

### 2. State Validation
Before modifying data:
- Verify resources exist (for creation: must not exist; for modification: must exist)
- Detect concurrent state conflicts
- Respect system invariants

### 3. Dependency Validation
When one operation depends on another:
- Execute the dependent operation first
- Verify the result is valid before continuing
- If it fails, report dependency_not_satisfied error

### 4. Security Validation
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
