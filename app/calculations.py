"""Build and persist calculations while reusing the arithmetic operations."""

import math

from sqlalchemy.orm import Session

from app.models import Calculation
from app.operations import add, divide, multiply, subtract
from app.schemas import CalculationCreate


class CalculationFactory:
    """Select the operation and construct a validated calculation record."""

    _operations = {
        "add": add,
        "subtract": subtract,
        "multiply": multiply,
        "divide": divide,
    }

    @classmethod
    def create(cls, calculation_type: str, a: float, b: float) -> Calculation:
        values = CalculationCreate(type=calculation_type, a=a, b=b)
        result = cls._operations[values.type](values.a, values.b)
        if not math.isfinite(result):
            raise ValueError("Result is too large for a finite number.")
        return Calculation(a=values.a, b=values.b, type=values.type, result=result)


def create_calculation(session: Session, calculation: CalculationCreate) -> Calculation:
    """Flush a new record; the caller decides whether to commit or roll back."""
    record = CalculationFactory.create(calculation.type, calculation.a, calculation.b)
    session.add(record)
    session.flush()
    return record
