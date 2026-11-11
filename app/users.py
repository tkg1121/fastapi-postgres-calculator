"""User registration and lookup, with passwords excluded from public output."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import UserCreate, UserRead
from app.security import hash_password


router = APIRouter(prefix="/users", tags=["users"])
logger = logging.getLogger(__name__)
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate, db: DatabaseSession):
    """Store a validated identity and a salted password hash."""
    record = User(
        username=user.username,
        email=str(user.email),
        password_hash=hash_password(user.password.get_secret_value()),
    )
    try:
        db.add(record)
        db.flush()
        response = UserRead.model_validate(record)
        db.commit()
    except IntegrityError as error:
        db.rollback()
        if getattr(error.orig, "sqlstate", None) == "23505":
            logger.warning("User registration rejected: duplicate identity")
            raise HTTPException(
                status_code=409, detail="Username or email already registered."
            ) from error
        logger.warning("User registration database failure")
        raise HTTPException(status_code=503, detail="Database unavailable.") from error
    except SQLAlchemyError as error:
        db.rollback()
        logger.warning("User registration database failure")
        raise HTTPException(status_code=503, detail="Database unavailable.") from error
    logger.info("User registered id=%s", response.id)
    return response


@router.get("/{user_id}", response_model=UserRead)
def read_user(user_id: Annotated[int, Path(gt=0)], db: DatabaseSession):
    """Return public user fields, never the stored password hash."""
    try:
        record = db.get(User, user_id)
    except SQLAlchemyError as error:
        db.rollback()
        logger.warning("User lookup database failure")
        raise HTTPException(status_code=503, detail="Database unavailable.") from error
    if record is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return record
