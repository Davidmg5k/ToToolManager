import pytest
from dataclasses import dataclass
from typing import Optional
from pydantic import BaseModel

from to_tool_manager.core.coercion import (
    coerce_value,
    coerce_kwargs,
    CoercionError,
    _is_plain_class,
)


class MyPydanticModel(BaseModel):
    name: str
    count: int = 0


@dataclass
class MyDataclass:
    name: str
    value: int


class MyPlainClass:
    def __init__(self, name: str, value: int):
        self.name = name
        self.value = value


class TestCoerceValue:
    def test_none_annotation(self):
        assert coerce_value(None, "anything") == "anything"

    def test_none_value(self):
        assert coerce_value(str, None) is None

    def test_str_to_str(self):
        assert coerce_value(str, "hello") == "hello"

    def test_int_to_int(self):
        assert coerce_value(int, 42) == 42

    def test_str_to_int(self):
        assert coerce_value(int, "42") == 42

    def test_int_to_str(self):
        with pytest.raises(CoercionError):
            coerce_value(str, 42)

    def test_bool_coercion(self):
        assert coerce_value(bool, 1) is True
        assert coerce_value(bool, 0) is False

    def test_list_coercion(self):
        result = coerce_value(list[int], [1, 2, 3])
        assert result == [1, 2, 3]

    def test_pydantic_model(self):
        result = coerce_value(MyPydanticModel, {"name": "test", "count": 5})
        assert isinstance(result, MyPydanticModel)
        assert result.name == "test"
        assert result.count == 5

    def test_pydantic_model_validation_error(self):
        with pytest.raises(CoercionError):
            coerce_value(MyPydanticModel, {"name": "test", "count": "not_a_number"})

    def test_dataclass(self):
        result = coerce_value(MyDataclass, {"name": "test", "value": 42})
        assert isinstance(result, MyDataclass)
        assert result.name == "test"
        assert result.value == 42

    def test_plain_class(self):
        result = coerce_value(MyPlainClass, {"name": "test", "value": 42})
        assert isinstance(result, MyPlainClass)
        assert result.name == "test"
        assert result.value == 42

    def test_plain_class_missing_required_field(self):
        with pytest.raises(CoercionError, match="missing required field"):
            coerce_value(MyPlainClass, {"name": "test"})

    def test_optional_type(self):
        result = coerce_value(Optional[str], None)
        assert result is None

    def test_optional_type_with_value(self):
        result = coerce_value(Optional[str], "hello")
        assert result == "hello"


class TestIsPlainClass:
    def test_plain_class(self):
        assert _is_plain_class(MyPlainClass) is True

    def test_pydantic_model(self):
        assert _is_plain_class(MyPydanticModel) is False

    def test_dataclass(self):
        assert _is_plain_class(MyDataclass) is False

    def test_not_a_class(self):
        assert _is_plain_class("string") is False

    def test_builtin_type(self):
        assert _is_plain_class(int) is True


class TestCoerceKwargs:
    def test_coerces_matching_args(self):
        def func(name: str, count: int):
            pass

        result = coerce_kwargs(func, {"name": "test", "count": "42"})
        assert result["name"] == "test"
        assert result["count"] == 42

    def test_skips_missing_args(self):
        def func(name: str, count: int = 10):
            pass

        result = coerce_kwargs(func, {"name": "test"})
        assert result["name"] == "test"
        assert "count" not in result

    def test_coercion_error_propagates(self):
        def func(model: MyPydanticModel):
            pass

        with pytest.raises(CoercionError):
            coerce_kwargs(func, {"model": {"name": "test", "count": "invalid"}})

    def test_ignores_self_parameter(self):
        def func(self, name: str):
            pass

        result = coerce_kwargs(func, {"name": "test"})
        assert result["name"] == "test"
