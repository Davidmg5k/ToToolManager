"""
Dependencies Skill — Side-effect propagation analysis.

Influences HOW the agent reasons about what a write operation might
affect BEYOND its own declared inputs/outputs. Complements (and
deliberately does not repeat) `reasoning` (causal ordering) and
`composition` (parallel vs. sequential execution): this skill owns
propagation, the other two own ordering and batching.

Contains no business logic, only a generic checklist applicable to any
domain.
"""
from pydantic_ai_skills import Skill


DEPENDENCIES_CONTENT = """
## Dependency & Propagation Analysis

Scope: this skill is about SIDE EFFECTS — what a write operation may
change beyond the value it directly returns. For causal ordering of
operations, see `reasoning`; for parallel vs. sequential execution,
see `composition`.

### 1. Before any write operation, ask
- What other data, aggregates, or related entities could this affect
  (counts, totals, derived/cached values, linked records)?
- Could this change the correctness of another operation already
  planned earlier or later in the same request?
- Does it invalidate a value read earlier in this conversation?

### 2. Propagation checklist
- Trace the operation to every entity it touches, not just the one it
  names (e.g. removing a user may orphan their orders).
- If a later operation needs a value a write produces, order them so
  that value exists first — never assume a pre-write value is still
  valid afterward.
- When unsure whether a side effect exists, re-read (call a read
  operation) instead of assuming; a read is cheap, a wrong write isn't.

### 3. Minimizing blast radius
- Prefer orderings that keep risk low: read/reversible operations
  first, destructive/irreversible ones last.
- If two operations could conflict (e.g. both mutate the same
  resource), never treat them as independent — make the second
  depend on the first.

### Example
"Delete user Ana, then list all orders" — deleting Ana may orphan her
orders. Resolve or flag her orders BEFORE deleting her, even though
the request never states that dependency explicitly.
"""

dependencies_skill = Skill(
    name="dependencies",
    description="Analyzes side-effect propagation of write operations before executing them",
    content=DEPENDENCIES_CONTENT,
)
