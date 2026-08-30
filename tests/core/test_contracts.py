"""
Tests for centralized contracts and constants.

Validates that the contracts are consistent and properly formatted.
"""
import pytest
from to_tool_manager.core.contracts import (
    OPERATIONS_CONTRACT,
    EMPTY_OPERATIONS_ERROR,
    INVALID_OPERATION_ERROR,
    INVALID_ARGS_ERROR,
)


class TestOperationsContract:
    """Tests for the operations contract constant."""

    def test_contract_contains_method_placeholder(self):
        """Contract must mention the method placeholder."""
        assert "<name>" in OPERATIONS_CONTRACT

    def test_contract_contains_args_placeholder(self):
        """Contract must mention the args structure."""
        assert "<param_name>" in OPERATIONS_CONTRACT
        assert "<value>" in OPERATIONS_CONTRACT

    def test_contract_mentions_must_match(self):
        """Contract must explicitly state that args keys MUST match parameters."""
        assert "MUST match" in OPERATIONS_CONTRACT





    def test_contract_mentions_optional_id_and_when(self):
        """Contract must mention optional id and when fields."""
        assert '"id"' in OPERATIONS_CONTRACT
        assert '"when"' in OPERATIONS_CONTRACT


class TestErrorMessages:
    """Tests for error message constants."""

    def test_empty_operations_error_mentions_operations(self):
        """Error must mention 'operations'."""
        assert "operations" in EMPTY_OPERATIONS_ERROR.lower()

    def test_empty_operations_error_mentions_method_and_args(self):
        """Error must mention the expected structure."""
        assert "method" in EMPTY_OPERATIONS_ERROR
        assert "args" in EMPTY_OPERATIONS_ERROR

    def test_invalid_operation_error_mentions_method_and_args(self):
        """Error must mention required fields."""
        assert "method" in INVALID_OPERATION_ERROR
        assert "args" in INVALID_OPERATION_ERROR

    def test_invalid_args_error_mentions_args(self):
        """Error must mention 'args'."""
        assert "args" in INVALID_ARGS_ERROR


class TestContractConsistency:
    """Tests to ensure contract consistency across the codebase."""

    def test_manager_uses_shared_contract(self):
        """manager.py should import and use OPERATIONS_CONTRACT."""
        from to_tool_manager.core import manager
        import inspect

        source = inspect.getsource(manager)
        assert "OPERATIONS_CONTRACT" in source
        assert "_OPERATIONS_CONTRACT_REF" not in source

    def test_module_uses_shared_contract(self):
        """module.py should import and use OPERATIONS_CONTRACT."""
        from to_tool_manager.core import module
        import inspect

        source = inspect.getsource(module)
        assert "OPERATIONS_CONTRACT" in source
        assert "_MODULE_OPERATIONS_CONTRACT_REF" not in source

    def test_prompts_uses_shared_contract(self):
        """prompts.py should import and use OPERATIONS_CONTRACT."""
        from to_tool_manager.core import prompts
        import inspect

        source = inspect.getsource(prompts)
        assert "OPERATIONS_CONTRACT" in source
