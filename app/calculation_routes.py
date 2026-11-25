"""Browse, read, edit, add, and delete persisted calculation records."""

from contextlib import contextmanager
import logging
from typing import Annotated, Iterator

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.calculations import CalculationFactory
from app.database import get_db
from app.models import Calculation
from app.schemas import CalculationCreate, CalculationRead


router = APIRouter(prefix="/calculations", tags=["calculations"])
logger = logging.getLogger(__name__)
DatabaseSession = Annotated[Session, Depends(get_db)]
CalculationId = Annotated[int, Path(gt=0)]


@contextmanager
def _database_operation(db: Session, operation: str) -> Iterator[None]:
    """Roll back failed database work without exposing connection details."""
    try:
        yield
    except SQLAlchemyError as error:
        try:
            db.rollback()
        except SQLAlchemyError:
            logger.warning("Calculation database rollback failed")
        logger.warning("Calculation %s database failure", operation)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable.",
        ) from error


def _get_calculation(db: Session, calculation_id: int) -> Calculation:
    """Resolve a record consistently for read, edit, and delete requests."""
    record = db.get(Calculation, calculation_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calculation not found.",
        )
    return record


def _build_calculation(calculation: CalculationCreate) -> Calculation:
    """Calculate through the shared factory and reject arithmetic overflow."""
    try:
        return CalculationFactory.create(
            calculation.type, calculation.a, calculation.b,
        )
    except ValueError as error:
        logger.warning("Calculation rejected: result is not finite")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Result is too large for a finite number.",
        ) from error


@router.get("", response_model=list[CalculationRead])
def browse_calculations(db: DatabaseSession):
    """Return saved calculations in stable primary-key order."""
    with _database_operation(db, "browse"):
        records = db.scalars(select(Calculation).order_by(Calculation.id)).all()
        return [CalculationRead.model_validate(record) for record in records]


@router.get("/{calculation_id}", response_model=CalculationRead)
def read_calculation(calculation_id: CalculationId, db: DatabaseSession):
    """Return one saved calculation, or report that its ID is missing."""
    with _database_operation(db, "read"):
        return CalculationRead.model_validate(_get_calculation(db, calculation_id))


@router.post("", response_model=CalculationRead, status_code=status.HTTP_201_CREATED)
def add_calculation(calculation: CalculationCreate, db: DatabaseSession):
    """Compute and persist a new calculation before returning its fields."""
    record = _build_calculation(calculation)
    with _database_operation(db, "create"):
        db.add(record)
        db.flush()
        response = CalculationRead.model_validate(record)
        db.commit()
    logger.info("Calculation created id=%s", response.id)
    return response


@router.put("/{calculation_id}", response_model=CalculationRead)
def edit_calculation(
    calculation_id: CalculationId, calculation: CalculationCreate, db: DatabaseSession,
):
    """Replace the inputs and result while retaining the ID and creation time."""
    with _database_operation(db, "edit"):
        record = _get_calculation(db, calculation_id)
        replacement = _build_calculation(calculation)
        record.a = replacement.a
        record.b = replacement.b
        record.type = replacement.type
        record.result = replacement.result
        db.flush()
        response = CalculationRead.model_validate(record)
        db.commit()
    logger.info("Calculation edited id=%s", response.id)
    return response


@router.delete("/{calculation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_calculation(calculation_id: CalculationId, db: DatabaseSession):
    """Delete one saved calculation and return an empty successful response."""
    with _database_operation(db, "delete"):
        record = _get_calculation(db, calculation_id)
        db.delete(record)
        db.commit()
    logger.info("Calculation deleted id=%s", calculation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
