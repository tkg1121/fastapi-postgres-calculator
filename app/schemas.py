"""Validated user and calculation data, with separate public responses."""

from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel, ConfigDict, EmailStr, Field, FiniteFloat, SecretStr,
    field_validator, model_validator,
)


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


CalculationType = Literal["add", "subtract", "multiply", "divide"]


class CalculationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    a: FiniteFloat
    b: FiniteFloat
    type: CalculationType

    @field_validator("a", "b", mode="before")
    @classmethod
    def validate_numbers(cls, value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Operands must be numbers.")
        return value

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, value):
        if isinstance(value, str):
            normalized = value.strip().lower()
            return "subtract" if normalized == "sub" else normalized
        return value

    @model_validator(mode="after")
    def validate_divisor(self):
        if self.type == "divide" and self.b == 0:
            raise ValueError("Cannot divide by zero!")
        return self


class CalculationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    a: FiniteFloat
    b: FiniteFloat
    type: CalculationType
    result: FiniteFloat
    created_at: datetime
