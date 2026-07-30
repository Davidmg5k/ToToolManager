"""
Shared `when`/`condition` evaluation.

Framework- and layer-agnostic: no imports from manager.py, module.py,
or planner.py. This is the single source of truth for the declarative
"run only if X" vocabulary used at the operation level (`when`, inside
one service call) and at the step level (`condition`, across a plan) —
same shape, same semantics, evaluated against whatever
`resolved_by_ref`-style dict the caller builds for its own layer.
"""
from __future__ import annotations

from typing import Any


def _evaluate_when(when: Any, resolved_by_ref: dict[str, dict[str, Any]]) -> str | None:
    """
    Evaluates a declarative `when`/`condition` clause against entries
    already resolved by the caller. Returns None if the operation/step
    should run, or a human-readable reason (str) if it should be
    skipped instead.

    Intentionally not Turing-complete: a single {"op", "outcome",
    optional "category"} condition, no boolean combinators, no loops.
    This is enough to express "run B only if A failed/succeeded" without
    introducing arbitrary code execution.
    """
    if not isinstance(when, dict):
        return "malformed 'when' clause (must be an object); operation skipped."

    op_ref = when.get("op")
    outcome = when.get("outcome")
    if not isinstance(op_ref, str) or outcome not in ("success", "error"):
        return "malformed 'when' clause (need 'op': str and 'outcome': 'success'|'error'); operation skipped."

    referenced = resolved_by_ref.get(op_ref)
    if referenced is None:
        return f"referenced operation '{op_ref}' has not run (yet) or does not exist; operation skipped."
    if referenced.get("skipped"):
        return f"referenced operation '{op_ref}' was itself skipped; operation skipped."

    ref_success = bool(referenced.get("success"))
    outcome_match = (ref_success and outcome == "success") or (not ref_success and outcome == "error")
    if not outcome_match:
        actual = "success" if ref_success else "error"
        return f"condition not met ('{op_ref}' outcome was '{actual}', expected '{outcome}')."

    category = when.get("category")
    if category is not None:
        ref_error = referenced.get("error") or {}
        ref_cats = ref_error.get("category")
        # Normalize ref_cats to a set for matching
        if isinstance(ref_cats, str):
            ref_cats = {ref_cats}
        elif isinstance(ref_cats, (list, tuple, set, frozenset)):
            ref_cats = set(ref_cats)
        else:
            ref_cats = set()
        # Normalize the target category to a set
        if isinstance(category, str):
            target_cats = {category}
        elif isinstance(category, (list, tuple, set, frozenset)):
            target_cats = set(category)
        else:
            target_cats = set()
        if not target_cats & ref_cats:
            return (
                f"condition not met (expected error category "
                f"'{category}', got '{ref_cats or None}')."
            )

    return None  # condition met — the operation/step should run
