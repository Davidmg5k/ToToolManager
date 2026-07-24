"""
Reasoning Skill — Patterns for reasoning and strategy.

Influences HOW the agent thinks and plans before executing.
Contains no business logic, only behavioral guidelines.
"""
from pydantic_ai_skills import Skill


REASONING_CONTENT = """
## Reasoning Patterns

### 1. Pre-Analysis
Before executing any operation:
- Identify the user's final goal
- List dependencies between operations
- Detect potential conflicts or anticipated errors

### 2. Execution Strategy
For multiple operations:
- Group operations that don't depend on each other
- Execute read operations before write operations
- If dependencies exist, respect the causal order

### 3. Uncertainty Handling
When information is missing:
- Ask for clarification before assuming
- Offer alternatives when possible
- Prefer "I don't know" over executing with incorrect assumptions

### 4. Call Optimization
To reduce round-trips:
- Combine independent operations into a single call
- Use batch operations when available
- Minimize redundant read-only calls
"""

reasoning_skill = Skill(
    name="reasoning",
    description="Patterns for reasoning and strategy to execute tasks optimally",
    content=REASONING_CONTENT,
)
