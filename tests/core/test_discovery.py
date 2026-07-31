import pytest
from to_tool_manager.core.discovery import (
    classify_visibility,
    discover_methods,
    parse_docstring,
    class_summary,
)


class SampleClass:
    """A sample class for testing discovery."""

    def public_method(self) -> str:
        """Public method."""
        return "public"

    def _protected_method(self) -> str:
        """Protected method."""
        return "protected"

    def __private_method(self) -> str:
        """Private method."""
        return "private"

    @property
    def version(self) -> str:
        """Version property."""
        return "1.0"

    def __dunder_method__(self):
        """Dunder method - should be excluded."""
        pass


class TestClassifyVisibility:
    def test_public(self):
        assert classify_visibility("public_method", "SampleClass") == "public"

    def test_protected(self):
        assert classify_visibility("_protected_method", "SampleClass") == "protected"

    def test_private(self):
        assert classify_visibility("__private_method", "SampleClass") == "private"

    def test_dunder_excluded(self):
        assert classify_visibility("__dunder_method__", "SampleClass") is None

    def test_name_mangled(self):
        assert classify_visibility("_SampleClass__private_method", "SampleClass") == "private"


class TestParseDocstring:
    def test_empty_docstring(self):
        summary, params = parse_docstring(None)
        assert summary == ""
        assert params == {}

    def test_summary_only(self):
        summary, params = parse_docstring("This is a summary.")
        assert summary == "This is a summary."
        assert params == {}

    def test_google_style_args(self):
        summary, params = parse_docstring(
            "Process data.\n\n"
            "Args:\n"
            "  name: The name of the item.\n"
            "  count: Number of items.\n"
        )
        assert summary == "Process data."
        assert "name" in params
        assert "count" in params

    def test_numpy_style_args(self):
        summary, params = parse_docstring(
            "Process data.\n\n"
            "Parameters\n"
            "----------\n"
            "name : str\n"
            "    The name of the item.\n"
            "count : int\n"
            "    Number of items.\n"
        )
        assert summary == "Process data."
        assert "name" in params
        assert "count" in params


class TestDiscoverMethods:
    def test_public_only(self):
        methods = discover_methods(SampleClass, visibility=frozenset({"public"}))
        names = [m.name for m in methods]
        assert "public_method" in names
        assert "_protected_method" not in names
        assert "__dunder_method__" not in names

    def test_public_and_protected(self):
        methods = discover_methods(
            SampleClass, visibility=frozenset({"public", "protected"})
        )
        names = [m.name for m in methods]
        assert "public_method" in names
        assert "_protected_method" in names

    def test_include_overrides_visibility(self):
        methods = discover_methods(
            SampleClass,
            visibility=frozenset({"public"}),
            include=frozenset({"_protected_method"}),
        )
        names = [m.name for m in methods]
        assert "_protected_method" in names
        assert "public_method" not in names

    def test_exclude(self):
        methods = discover_methods(
            SampleClass,
            visibility=frozenset({"public"}),
            exclude=frozenset({"public_method"}),
        )
        names = [m.name for m in methods]
        assert "public_method" not in names

    def test_properties_not_exposed_by_default(self):
        methods = discover_methods(SampleClass, visibility=frozenset({"public"}))
        names = [m.name for m in methods]
        assert "version" not in names

    def test_properties_exposed(self):
        methods = discover_methods(
            SampleClass,
            visibility=frozenset({"public"}),
            expose_properties=True,
        )
        names = [m.name for m in methods]
        assert "version" in names

    def test_method_info_fields(self):
        methods = discover_methods(SampleClass, visibility=frozenset({"public"}))
        public = next(m for m in methods if m.name == "public_method")
        assert public.visibility == "public"
        assert public.is_property is False
        assert public.doc_summary == "Public method."

    def test_unknown_visibility_raises(self):
        with pytest.raises(ValueError, match="Unknown visibility"):
            discover_methods(SampleClass, visibility=frozenset({"invalid"}))


class TestClassSummary:
    def test_with_docstring(self):
        summary = class_summary(SampleClass)
        assert summary == "A sample class for testing discovery."

    def test_without_docstring(self):
        class NoDoc:
            pass

        summary = class_summary(NoDoc)
        assert summary == ""
