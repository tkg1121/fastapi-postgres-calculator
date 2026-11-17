"""Validate calculation input, factory behavior, and public serialization."""

from datetime import datetime, timezone
from types import SimpleNamespace

from pydantic import ValidationError
import pytest
from sqlalchemy import inspect

from app.calculations import CalculationFactory
from app.models import Calculation
from app.schemas import CalculationCreate, CalculationRead


pytestmark = pytest.mark.unit


@pytest.mark.parametrize("operation,a,b,expected", [
    ("add", 2, 3, 5),
    ("add", -4, 1, -3),
    ("add", 0.1, 0.2, 0.3),
    ("subtract", 9, 4, 5),
    ("subtract", -4, -1, -3),
    ("subtract", 0.5, 0.25, 0.25),
    ("multiply", 4, 5, 20),
    ("multiply", -4, 5, -20),
    ("multiply", 0, 12, 0),
    ("divide", 10, 2, 5),
    ("divide", -9, 2, -4.5),
    ("divide", 0, 2, 0),
])
def test_factory_builds_correct_unpersisted_calculation(operation, a, b, expected):
    calculation = CalculationFactory.create(operation, a, b)

    assert isinstance(calculation, Calculation)
    assert inspect(calculation).transient
    assert calculation.id is None
    assert calculation.type == operation
    assert calculation.a == a
    assert calculation.b == b
    assert calculation.result == pytest.approx(expected)


@pytest.mark.parametrize("operation", ["add", "subtract", "multiply", "divide"])
def test_schema_and_factory_normalize_operation_name(operation):
    supplied_type = f"  {operation.upper()}  "
    payload = CalculationCreate(type=supplied_type, a=8, b=2)

    assert payload.type == operation
    assert CalculationFactory.create(supplied_type, 8, 2).type == operation


@pytest.mark.parametrize("supplied_type", ["Sub", "sub", " SUB "])
def test_sub_alias_is_normalized_to_subtract(supplied_type):
    payload = CalculationCreate(type=supplied_type, a=8, b=2)
    record = CalculationFactory.create(supplied_type, 8, 2)

    assert payload.type == "subtract"
    assert record.type == "subtract"
    assert record.result == 6


@pytest.mark.parametrize("operation", ["", "power", "root", "sum", None, True, 7])
def test_unsupported_operation_is_rejected(operation):
    with pytest.raises(ValidationError):
        CalculationCreate(type=operation, a=1, b=2)
    with pytest.raises(ValueError):
        CalculationFactory.create(operation, 1, 2)


@pytest.mark.parametrize("field", ["a", "b"])
@pytest.mark.parametrize("invalid", [
    float("nan"), float("inf"), float("-inf"),
    True, False, "12", "NaN", None, [], {},
])
def test_operands_must_be_finite_json_numbers(field, invalid):
    values = {"type": "add", "a": 1, "b": 2, field: invalid}
    with pytest.raises(ValidationError):
        CalculationCreate(**values)
    with pytest.raises(ValueError):
        CalculationFactory.create(values["type"], values["a"], values["b"])


@pytest.mark.parametrize("divisor", [0, 0.0, -0.0])
def test_division_by_zero_is_rejected_before_execution(divisor):
    with pytest.raises(ValidationError):
        CalculationCreate(type="divide", a=10, b=divisor)
    with pytest.raises(ValueError):
        CalculationFactory.create("divide", 10, divisor)


@pytest.mark.parametrize("operation", ["add", "subtract", "multiply"])
def test_zero_second_operand_is_valid_for_other_operations(operation):
    payload = CalculationCreate(type=operation, a=10, b=0)
    assert payload.b == 0


@pytest.mark.parametrize("operation,a,b", [
    ("add", 1e308, 1e308),
    ("subtract", 1e308, -1e308),
    ("multiply", 1e308, 2),
    ("divide", 1e308, 1e-308),
])
def test_factory_rejects_nonfinite_arithmetic_results(operation, a, b):
    with pytest.raises(ValueError, match="finite"):
        CalculationFactory.create(operation, a, b)


@pytest.mark.parametrize("missing", ["type", "a", "b"])
def test_input_requires_operation_and_both_operands(missing):
    values = {"type": "add", "a": 1, "b": 2}
    values.pop(missing)
    with pytest.raises(ValidationError):
        CalculationCreate(**values)


@pytest.mark.parametrize("field,value", [
    ("id", 10), ("result", 999), ("created_at", "2026-01-01T00:00:00Z"),
])
def test_input_rejects_server_computed_fields(field, value):
    with pytest.raises(ValidationError):
        CalculationCreate(type="add", a=1, b=2, **{field: value})


def test_read_schema_serializes_orm_attributes_as_json():
    created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    stored = SimpleNamespace(id=11, type="divide", a=9.0, b=2.0, result=4.5, created_at=created_at)

    response = CalculationRead.model_validate(stored)
    payload = response.model_dump(mode="json")

    assert set(payload) == {"id", "type", "a", "b", "result", "created_at"}
    assert payload["id"] == 11
    assert payload["type"] == "divide"
    assert payload["a"] == 9.0
    assert payload["b"] == 2.0
    assert payload["result"] == 4.5
    assert datetime.fromisoformat(payload["created_at"].replace("Z", "+00:00")) == created_at
