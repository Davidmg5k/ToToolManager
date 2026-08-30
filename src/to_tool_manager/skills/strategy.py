"""
Strategy Skill -- Combined reasoning, analysis, and composition patterns.

Merged from reasoning + composition to reduce token overhead while
preserving all behavioral guidance for how the agent thinks, plans,
and groups operations.
"""
try:
    from pydantic_ai_skills import Skill
except ImportError:
    Skill = None  # type: ignore[assignment,misc]


STRATEGY_CONTENT = """
## Strategy Patterns

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

### 3. Independent Operations
When two operations don't depend on each other:
- Execute them in parallel (single tool call)
- Don't wait for one result to start the other
- Combine their results in a consolidated response

### 4. Dependent Operations
When one operation uses the result of another:
- Execute sequentially, step by step
- Validate each result before continuing
- If the dependent fails, report the full context

### 5. Read-Modify-Write Pattern
For update operations:
1. Read the current state
2. Calculate the necessary change
3. Write only if there's a difference
4. Report what changed (or that nothing changed)

### 6. Fan-Out/Fan-In Pattern
For bulk processing:
- Divide work into independent units
- Process in parallel when possible
- Consolidate results at the end

### 7. Uncertainty Handling
When information is missing:
- Ask for clarification before assuming
- Offer alternatives when possible
- Prefer "I don't know" over executing with incorrect assumptions
"""

strategy_skill = Skill(
    name="strategy",
    description="Reasoning, analysis, and composition patterns for optimal execution",
    content=STRATEGY_CONTENT,
) if Skill is not None else None
