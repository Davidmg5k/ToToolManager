"""
Error Handling Skill -- Patterns for error handling.

Influences HOW the agent reacts to errors.
Contains no specific recovery logic, only general strategies.
"""
try:
    from pydantic_ai_skills import Skill
except ImportError:
    Skill = None  # type: ignore[assignment,misc]


ERROR_HANDLING_CONTENT = """
## Error Handling Patterns

### 1. Retry Strategy
When an error is retryable:
- Analyze the cause before retrying
- Limit retries to 3 maximum
- Change strategy if the second attempt fails
- Never retry validation errors

### 2. Error Communication
When reporting errors to the user:
- Be specific: what failed and why
- Offer concrete action: what the user can do
- Use categories so the user understands the problem type
- Avoid unnecessary technical jargon

### 3. Graceful Degradation
When one operation in a batch fails:
- Continue with the remaining operations
- Report success/failure separately
- Never abort the entire batch for a single error
- Offer a consolidated summary at the end
"""

error_handling_skill = Skill(
    name="error-handling",
    description="Strategies for reacting to errors effectively",
    content=ERROR_HANDLING_CONTENT,
) if Skill is not None else None
