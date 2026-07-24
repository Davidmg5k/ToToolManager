"""
Planning Skill — Cross-service planning patterns.

Influences HOW the agent plans and organizes multi-service operations.
Contains no business logic, only orchestration guidance.
"""
from pydantic_ai_skills import Skill


PLANNING_CONTENT = """
## Cross-Service Planning Patterns

### 1. When to Plan
Create a plan when the request involves:
- Multiple services (e.g., User + Order + Product)
- Dependent operations (e.g., create user before creating their order)
- Complex sequences that benefit from explicit step tracking

For simple, single-service requests, skip planning and use tools directly.

### 2. Plan Structure
Each step should include:
- `description`: Clear explanation of what this step does
- `operations`: List of {service, method, args} objects to execute
- `depends_on`: IDs of steps that must complete first (empty if independent)

### 3. Smart Batching
- Steps without dependencies → execute in parallel (separate tool calls)
- Steps with dependencies → execute in sequence
- Group operations from the SAME service into a single step when possible
- Independent operations across DIFFERENT services can be parallel steps

### 4. Dependency Rules
When a dependency graph exists:
- The planner validates execution order automatically
- Steps are reordered if needed
- Violations are reported before execution

When no graph exists:
- The agent decides order based on logical reasoning
- Read operations before write operations when they reference the same data
- Verify preconditions before creating dependent resources

### 5. Error Handling in Plans
- If a step fails, mark it as `failed`
- Steps that depend on a failed step are marked as `skipped`
- Report what failed, why, and what succeeded
- Never silently ignore failures in a plan

### 6. State Tracking
- Emit events when step status changes
- Use snapshots for full plan state
- Use deltas for incremental updates
- Keep the user informed of progress
"""

planning_skill = Skill(
    name="planning",
    description="Cross-service planning patterns for complex multi-service operations",
    content=PLANNING_CONTENT,
)
