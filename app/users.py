"""User registration, credential verification, and public user lookup."""

import logging
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import UserCreate, UserLogin, UserRead
from app.security import hash_password, verify_password


router = APIRouter(prefix="/users", tags=["users"])
logger = logging.getLogger(__name__)
DatabaseSession = Annotated[Session, Depends(get_db)]
DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(32))


def _rollback_safely(db: Session):
    """Keep the original generic error even if the connection cannot roll back."""
    try:
        db.rollback()
    except SQLAlchemyError:
        logger.warning("User database rollback failed")


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
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
        _rollback_safely(db)
        if getattr(error.orig, "sqlstate", None) == "23505":
            logger.warning("User registration rejected: duplicate identity")
            raise HTTPException(
                status_code=409, detail="Username or email already registered."
            ) from error
        logger.warning("User registration database failure")
        raise HTTPException(status_code=503, detail="Database unavailable.") from error
    except SQLAlchemyError as error:
        _rollback_safely(db)
        logger.warning("User registration database failure")
        raise HTTPException(status_code=503, detail="Database unavailable.") from error
    logger.info("User registered id=%s", response.id)
    return response


@router.post("/login", response_model=UserRead)
def login_user(credentials: UserLogin, db: DatabaseSession):
    """Verify credentials and return public identity fields without a session token."""
    identity = (
        User.username == credentials.username
        if credentials.username is not None
        else User.email == str(credentials.email)
    )
    try:
        record = db.scalar(select(User).where(identity))
    except SQLAlchemyError as error:
        _rollback_safely(db)
        logger.warning("User login database failure")
        raise HTTPException(status_code=503, detail="Database unavailable.") from error

    # Unknown identities still incur a password verification to reduce timing differences.
    stored_hash = record.password_hash if record is not None else DUMMY_PASSWORD_HASH
    valid_password = verify_password(credentials.password.get_secret_value(), stored_hash)
    if record is None or not valid_password:
        logger.warning("User login rejected")
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    logger.info("User login succeeded id=%s", record.id)
    return UserRead.model_validate(record)


@router.get("/{user_id}", response_model=UserRead)
def read_user(user_id: Annotated[int, Path(gt=0)], db: DatabaseSession):
    """Return public user fields, never the stored password hash."""
    try:
        record = db.get(User, user_id)
    except SQLAlchemyError as error:
        _rollback_safely(db)
        logger.warning("User lookup database failure")
        raise HTTPException(status_code=503, detail="Database unavailable.") from error
    if record is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return record
