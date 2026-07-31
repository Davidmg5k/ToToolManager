from to_tool_manager.core.conditions import _evaluate_when


class TestEvaluateWhen:
    def test_malformed_not_dict(self):
        result = _evaluate_when("not a dict", {})
        assert result is not None
        assert "malformed" in result

    def test_malformed_missing_op(self):
        result = _evaluate_when({"outcome": "success"}, {})
        assert result is not None
        assert "malformed" in result

    def test_malformed_invalid_outcome(self):
        result = _evaluate_when({"op": "step1", "outcome": "invalid"}, {})
        assert result is not None
        assert "malformed" in result

    def test_referenced_op_not_found(self):
        result = _evaluate_when({"op": "nonexistent", "outcome": "success"}, {})
        assert result is not None
        assert "not run" in result

    def test_referenced_op_skipped(self):
        resolved = {"step1": {"skipped": True}}
        result = _evaluate_when({"op": "step1", "outcome": "success"}, resolved)
        assert result is not None
        assert "skipped" in result

    def test_success_condition_met(self):
        resolved = {"step1": {"success": True}}
        result = _evaluate_when({"op": "step1", "outcome": "success"}, resolved)
        assert result is None

    def test_success_condition_not_met(self):
        resolved = {"step1": {"success": False}}
        result = _evaluate_when({"op": "step1", "outcome": "success"}, resolved)
        assert result is not None
        assert "condition not met" in result

    def test_error_condition_met(self):
        resolved = {"step1": {"success": False}}
        result = _evaluate_when({"op": "step1", "outcome": "error"}, resolved)
        assert result is None

    def test_error_condition_not_met(self):
        resolved = {"step1": {"success": True}}
        result = _evaluate_when({"op": "step1", "outcome": "error"}, resolved)
        assert result is not None
        assert "condition not met" in result

    def test_category_match(self):
        resolved = {
            "step1": {
                "success": False,
                "error": {"category": ["not_found"], "message": "Item not found"},
            }
        }
        result = _evaluate_when(
            {"op": "step1", "outcome": "error", "category": "not_found"}, resolved
        )
        assert result is None

    def test_category_no_match(self):
        resolved = {
            "step1": {
                "success": False,
                "error": {"category": ["timeout"], "message": "Timed out"},
            }
        }
        result = _evaluate_when(
            {"op": "step1", "outcome": "error", "category": "not_found"}, resolved
        )
        assert result is not None
        assert "category" in result

    def test_category_list_match(self):
        resolved = {
            "step1": {
                "success": False,
                "error": {"category": ["not_found", "missing"], "message": "err"},
            }
        }
        result = _evaluate_when(
            {"op": "step1", "outcome": "error", "category": ["not_found"]}, resolved
        )
        assert result is None

    def test_category_string_in_ref(self):
        resolved = {
            "step1": {
                "success": False,
                "error": {"category": "timeout", "message": "err"},
            }
        }
        result = _evaluate_when(
            {"op": "step1", "outcome": "error", "category": "timeout"}, resolved
        )
        assert result is None

    def test_positional_reference(self):
        resolved = {"op0": {"success": True}}
        result = _evaluate_when({"op": "op0", "outcome": "success"}, resolved)
        assert result is None
