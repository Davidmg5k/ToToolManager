"""
Task Planning Skill — boundary guidance between the built-in Planner and
pydantic-ai-harness's ``Planning`` capability.

Influences HOW the agent chooses between two mechanisms that solve
different problems and are never meant to replace each other:

- ``Planner`` (``core.planner``): cross-service execution. "How do I run
  this?" -- typed ``StepOperation(service, method, args)``, ``$from``
  references, ``condition`` branching, dependency graphs.
- ``Planning`` (pydantic-ai-harness): the model's own task list. "What do
  I need to do?" -- flat ``PlanItem`` entries with a status, optionally
  persisted across runs/sessions.

This skill is only injected by ``build_agent`` when a ``Planning``
capability instance is actually present in ``capabilities`` -- it is
never added blindly, since the guidance would be actionable noise for
agents that were not given the harness planning tools.
"""
from pydantic_ai_skills import Skill


TASK_PLANNING_CONTENT = """
## Task Planning vs. Cross-Service Planning

You have access to two different planning mechanisms in this
conversation. They are complementary, not interchangeable -- picking the
wrong one for the job wastes a turn.

### 1. Which one answers which question

- **`write_plan` / `read_plan` / `add_task` / `update_task_status` /
  `remove_task`** (task tracking): answers "what do I still need to do?"
  Use these to keep track of your OWN multi-step work across a
  conversation -- a flat checklist of intent, not of service calls. A
  task item never contains a `service`, `method`, or `args` -- if you
  find yourself putting those in a task's `content`, you actually need
  `create_plan` instead.
- **`create_plan` / `execute_plan` / `get_plan` / `update_plan_step`**
  (cross-service planning): answers "how do I actually run this?" Use
  these the moment a task requires calling one or more registered
  services -- they are the only mechanism that validates
  `depends_on`/`condition`/`$from` references and executes real
  operations. A task on your checklist becomes one or more steps here
  when it's time to execute it.

### 2. Typical flow when both are available

1. Break the user's request into tasks with `write_plan`/`add_task` --
   this is your own working memory, not something that touches any
   service.
2. For each task that requires calling a service, build a `create_plan`
   with the corresponding `StepOperation`s and call `execute_plan`.
3. Mark the task `completed` via `update_task_status` once its
   `execute_plan` step(s) resolved successfully -- or `failed` if they
   didn't, citing what went wrong.
4. Move to the next pending task.

### 3. Do not duplicate state between the two

- Never mirror a `Plan`'s steps as separate task items -- one task can
  map to an entire `Plan`, not to each of its `Step`s.
- If the task list and a `Plan`'s step statuses disagree (e.g. a task
  says `completed` but its `execute_plan` step `failed`), the `Plan` is
  the source of truth for execution outcome; correct the task status to
  match it, not the other way around.
- Persistence, if configured, applies to the task list across
  runs/sessions -- it does NOT persist `Plan` state. A resumed
  conversation may find a task marked `in_progress` whose `Plan` no
  longer exists; in that case, re-`create_plan` before resuming
  execution rather than assuming the old plan is still valid.
"""

task_planning_skill = Skill(
    name="task_planning",
    description="Boundary guidance between task-tracking (Planning) and cross-service execution (Planner)",
    content=TASK_PLANNING_CONTENT,
)
