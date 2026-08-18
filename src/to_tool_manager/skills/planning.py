"""
Planning Skill — Cross-service planning patterns.

Influences HOW the agent plans and organizes multi-service operations.
Contains no business logic, only orchestration guidance.
"""
try:
    from pydantic_ai_skills import Skill
except ImportError:
    Skill = None  # type: ignore[assignment,misc]


PLANNING_CONTENT = """
## Cross-Service Planning Patterns

### 0. Guiding Principle
Before executing anything, analyze the most appropriate order to apply the requested changes, ensuring their propagation does not introduce inconsistencies or break the correct functioning of the rest of the system. This principle applies generically to any request — regardless of scope, number of services, or type of operation — and must always be weighed against two factors:
- **The user's actual intent**: what outcome they need, not just the literal sequence of actions they described.
- **Tool execution constraints**: what each available tool can and cannot guarantee (atomicity, side effects, rollback support, etc.).

Use this principle to decide *whether* to plan (section 1) and *how* to order and batch steps (sections 3–4).

### 1. When to Plan
Create a plan when the request involves:
- Multiple services (e.g., User + Order + Product)
- Dependent operations (e.g., create user before creating their order)
- Complex sequences that benefit from explicit step tracking

For simple, single-service requests, skip planning and use tools directly.

### 2. Plan Structure
Each step should include:
- `description`: Clear explanation of what this step does
- `operations`: List of {service, method, args, id?} objects to execute.
  Give an operation an explicit `id` whenever ANOTHER step will need to
  reference its result specifically (see `$from` below), or whenever this
  step calls more than one operation on the same service.
- `depends_on`: IDs of steps that must complete first (empty if independent)
- `condition`: Optional — skip this step entirely unless an earlier step's
  outcome matches (see below). If set, its referenced step is auto-added
  to `depends_on` — no need to list it twice.

### 3. Cross-step references ($from)
Instead of reading a previous step's result and writing the literal value
into a new step, reference it directly in `args`:

```json
{"service": "Order", "method": "create", "args": {
    "user_id": {"$from": "step1", "path": "User.result.id"},
    "item": "Widget"
}}
```

- `path` starts with the service name called in that step, then `.result`
  (or `.error`) and however deep into the returned value you need to go
  (e.g. `User.result.id`, `Order.result.items[0].sku`).
- If the referenced step called more than one operation on that service,
  insert the operation's explicit `id` right after the service name:
  `"User.<op_id>.result.id"` — otherwise the reference is ambiguous and
  gets rejected with the list of valid ids.
- Referencing an unknown step, or a step that hasn't completed
  successfully, is rejected with a clear error — either upfront (unknown
  step id) or when that step turns out to have failed/not run.

### 4. Step-level conditions (branching)
`when` (inside a single service call) only sequences operations within
ONE call. To make an entire step's execution depend on whether an EARLIER
STEP (any service) succeeded or failed, use `condition` on the step
itself — same shape as `when`:

```json
{"condition": {"op": "step2", "outcome": "error", "category"?: "not_found"}}
```

If the condition isn't met, the step is marked `skipped` (not `failed`)
and never runs — nothing else needs to be done to "cancel" it.

### 5. Smart Batching
- Steps without dependencies → execute in parallel (separate tool calls)
- Steps with dependencies → execute in sequence
- Group operations from the SAME service into a single step when possible
- Independent operations across DIFFERENT services can be parallel steps

### 6. Dependency Rules
When a service dependency graph was configured for this planner:
- `depends_on` is auto-derived for any step that wasn't explicit about it
  — you don't have to declare `depends_on` yourself for known
  service-level dependencies, just call the operations; the planner fills
  it in.
- An explicit `depends_on`/`condition`/`$from` that contradicts the graph
  (would create a circular wait) is rejected upfront, before anything runs
  — fix the plan and resubmit rather than guessing why it's stuck.

When no graph exists:
- The agent decides order based on logical reasoning
- Read operations before write operations when they reference the same data
- Verify preconditions before creating dependent resources

### 7. Validation happens upfront
`create_plan` checks step references (`depends_on`, `condition.op`,
`$from`), service/method existence, and dependency-graph consistency
BEFORE executing anything. If it returns an error, fix the plan
description and call `create_plan` again — nothing was run yet, there's
nothing to undo.

### 8. Error Handling in Plans
- If a step fails, it's marked `failed`
- Steps that depend on a failed step are marked `skipped`
- A step whose `condition` wasn't met is also `skipped` — check `result`
  on a skipped step for the reason
- Report what failed, what was skipped and why, and what succeeded
- Never silently ignore failures in a plan

### 9. State Tracking
- Emit events when step status changes
- Use snapshots for full plan state
- Use deltas for incremental updates
- Keep the user informed of progress
"""

planning_skill = Skill(
    name="planning",
    description="Cross-service planning patterns for complex multi-service operations",
    content=PLANNING_CONTENT,
) if Skill is not None else None
