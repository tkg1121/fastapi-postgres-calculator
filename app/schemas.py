"""Request validation and public user responses."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    email: EmailStr = Field(max_length=254)
    password: SecretStr = Field(min_length=12, max_length=128)

    @field_validator("username", "email", mode="before")
    @classmethod
    def normalize_identity(cls, value):
        if isinstance(value, str):
            return value.strip().lower()
        return value


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    created_at: datetime
