"""Check persisted calculations and database constraints using PostgreSQL."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError

from app.calculations import CalculationFactory, create_calculation
from app.models import Calculation
from app.schemas import CalculationCreate, CalculationRead


pytestmark = [pytest.mark.integration, pytest.mark.database]


def test_migration_created_calculation_columns_and_primary_key(postgres_engine):
    database = inspect(postgres_engine)

    assert database.has_table("calculations", schema="calculator")
    columns = {column["name"]: column for column in database.get_columns("calculations", schema="calculator")}
    assert set(columns) == {"id", "type", "a", "b", "result", "created_at"}
    assert all(not column["nullable"] for column in columns.values())
    assert columns["created_at"]["default"] is not None
    assert database.get_pk_constraint("calculations", schema="calculator")["constrained_columns"] == ["id"]


@pytest.mark.parametrize("operation,a,b,expected", [
    ("add", 2, 3, 5),
    ("subtract", 10, 4, 6),
    ("multiply", -4, 5, -20),
    ("divide", 9, 2, 4.5),
])
def test_calculation_is_persisted_and_reloaded_with_result_and_timestamp(db_session, operation, a, b, expected):
    record = create_calculation(db_session, CalculationCreate(type=operation, a=a, b=b))
    record_id = record.id
    db_session.commit()
    db_session.expunge_all()

    loaded = db_session.get(Calculation, record_id)

    assert loaded is not record
    assert loaded.id > 0
    assert loaded.type == operation
    assert loaded.a == a
    assert loaded.b == b
    assert loaded.result == pytest.approx(expected)
    assert loaded.created_at.tzinfo is not None
    assert abs((datetime.now(timezone.utc) - loaded.created_at).total_seconds()) < 60
    serialized = CalculationRead.model_validate(loaded).model_dump(mode="json")
    assert serialized["id"] == record_id
    assert serialized["result"] == pytest.approx(expected)


def test_factory_object_can_be_saved_with_a_normal_sqlalchemy_session(db_session):
    record = CalculationFactory.create(" ADD ", 0.5, 0.25)
    db_session.add(record)
    db_session.flush()
    db_session.refresh(record)

    assert record.id > 0
    assert record.type == "add"
    assert record.result == pytest.approx(0.75)
    assert record.created_at.tzinfo is not None


def test_sub_alias_is_persisted_and_serialized_as_subtract(db_session):
    record = create_calculation(db_session, CalculationCreate(type="Sub", a=8, b=2))
    record_id = record.id
    db_session.commit()
    db_session.expunge_all()

    loaded = db_session.get(Calculation, record_id)
    payload = CalculationRead.model_validate(loaded).model_dump(mode="json")

    assert payload["type"] == "subtract"
    assert payload["result"] == 6


def test_creation_leaves_transaction_control_to_the_caller(db_session):
    before = db_session.scalar(select(func.count()).select_from(Calculation))
    record = create_calculation(db_session, CalculationCreate(type="multiply", a=3, b=7))
    record_id = record.id
    assert db_session.get(Calculation, record_id) is not None

    db_session.rollback()

    assert db_session.get(Calculation, record_id) is None
    assert db_session.scalar(select(func.count()).select_from(Calculation)) == before
    recovered = create_calculation(db_session, CalculationCreate(type="add", a=3, b=7))
    db_session.commit()
    assert recovered.result == 10


@pytest.mark.parametrize("field,value,constraint", [
    ("type", "power", "ck_calculations_type"),
    ("type", "ADD", "ck_calculations_type"),
    ("a", float("nan"), "ck_calculations_a_finite"),
    ("a", float("inf"), "ck_calculations_a_finite"),
    ("a", float("-inf"), "ck_calculations_a_finite"),
    ("b", float("nan"), "ck_calculations_b_finite"),
    ("b", float("inf"), "ck_calculations_b_finite"),
    ("b", float("-inf"), "ck_calculations_b_finite"),
    ("result", float("nan"), "ck_calculations_result_finite"),
    ("result", float("inf"), "ck_calculations_result_finite"),
    ("result", float("-inf"), "ck_calculations_result_finite"),
])
def test_postgres_rejects_invalid_values_even_without_pydantic(db_session, field, value, constraint):
    values = {"type": "add", "a": 2.0, "b": 3.0, "result": 5.0, field: value}
    db_session.add(Calculation(**values))

    with pytest.raises(IntegrityError) as failure:
        db_session.flush()

    assert failure.value.orig.sqlstate == "23514"
    assert failure.value.orig.diag.constraint_name == constraint
    db_session.rollback()


@pytest.mark.parametrize("divisor", [0.0, -0.0])
def test_postgres_rejects_division_by_zero(db_session, divisor):
    db_session.add(Calculation(type="divide", a=2.0, b=divisor, result=0.0))

    with pytest.raises(IntegrityError) as failure:
        db_session.flush()

    assert failure.value.orig.sqlstate == "23514"
    assert failure.value.orig.diag.constraint_name == "ck_calculations_divisor"
    db_session.rollback()


@pytest.mark.parametrize("field", ["type", "a", "b", "result"])
def test_postgres_rejects_missing_calculation_values(db_session, field):
    values = {"type": "add", "a": 2.0, "b": 3.0, "result": 5.0, field: None}
    db_session.add(Calculation(**values))

    with pytest.raises(IntegrityError) as failure:
        db_session.flush()

    assert failure.value.orig.sqlstate == "23502"
    db_session.rollback()
