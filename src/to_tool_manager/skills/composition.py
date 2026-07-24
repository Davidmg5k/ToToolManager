"""
Composition Skill — Patterns for composing operations.

Influences HOW the agent groups and chains operations.
Contains no business logic, only orchestration patterns.
"""
from pydantic_ai_skills import Skill


COMPOSITION_CONTENT = """
## Composition Patterns

### 1. Independent Operations
When two operations don't depend on each other:
- Execute them in parallel (single tool call)
- Don't wait for one result to start the other
- Combine their results in a consolidated response

Example:
- "Create user David" + "List all users" = 1 tool call
- You don't need to create the user first to list them

### 2. Dependent Operations
When one operation uses the result of another:
- Execute sequentially, step by step
- Validate each result before continuing
- If the dependent fails, report the full context

Example:
- "Create order for product X" depends on "verify X exists"

### 3. Read-Modify-Write Pattern
For update operations:
1. Read the current state
2. Calculate the necessary change
3. Write only if there's a difference
4. Report what changed (or that nothing changed)

### 4. Fan-Out/Fan-In Pattern
For bulk processing:
- Divide work into independent units
- Process in parallel when possible
- Consolidate results at the end
- Report progress if it's lengthy
"""

composition_skill = Skill(
    name="composition",
    description="Patterns for grouping and chaining operations optimally",
    content=COMPOSITION_CONTENT,
)
