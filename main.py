"""FastAPI routes and error handling for the calculator."""

import logging
import math
from pathlib import Path

import psycopg
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, FiniteFloat, field_validator
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.database import get_database_name
from app.operations import add, divide, multiply, subtract


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)
app = FastAPI(title="FastAPI Calculator")
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))
OPERATIONS = {"add": add, "subtract": subtract, "multiply": multiply, "divide": divide}


class OperationRequest(BaseModel):
    """Two finite JSON numbers supplied to an arithmetic endpoint."""

    a: FiniteFloat = Field(description="The first number")
    b: FiniteFloat = Field(description="The second number")

    @field_validator("a", "b", mode="before")
    @classmethod
    def validate_numbers(cls, value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Both a and b must be numbers.")
        return value


class OperationResponse(BaseModel):
    result: FiniteFloat


class ErrorResponse(BaseModel):
    error: str


@app.middleware("http")
async def log_request(request: Request, call_next):
    """Record the method, path, and status without logging request bodies."""
    response = await call_next(request)
    logger.info("method=%s path=%s status=%s", request.method, request.url.path, response.status_code)
    return response


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    logger.warning("HTTP error path=%s status=%s error=%s", request.url.path, exc.status_code, exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail}, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    messages = "; ".join(f"{error['loc'][-1]}: {error['msg']}" for error in exc.errors())
    logger.warning("Validation error path=%s error=%s", request.url.path, messages)
    return JSONResponse(status_code=400, content={"error": messages})


@app.get("/")
async def read_root(request: Request):
    """Serve the calculator page."""
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/health/db", responses={503: {"model": ErrorResponse}})
def database_health():
    """Check the Compose database without creating or changing any records."""
    try:
        return {"status": "ok", "database": get_database_name()}
    except psycopg.Error as error:
        logger.warning("Database health check failed")
        raise HTTPException(status_code=503, detail="Database unavailable.") from error


def calculate(name: str, operation: OperationRequest) -> OperationResponse:
    """Share result validation and exception handling across the routes."""
    try:
        result = OPERATIONS[name](operation.a, operation.b)
        if not math.isfinite(result):
            raise ValueError("Result is too large for a finite number.")
        return OperationResponse(result=result)
    except ValueError as error:
        logger.warning("operation=%s error=%s", name, error)
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        logger.exception("Unexpected calculation failure operation=%s", name)
        raise HTTPException(status_code=500, detail="Internal Server Error") from error


@app.post("/add", response_model=OperationResponse, responses={400: {"model": ErrorResponse}})
async def add_route(operation: OperationRequest):
    return calculate("add", operation)


@app.post("/subtract", response_model=OperationResponse, responses={400: {"model": ErrorResponse}})
async def subtract_route(operation: OperationRequest):
    return calculate("subtract", operation)


@app.post("/multiply", response_model=OperationResponse, responses={400: {"model": ErrorResponse}})
async def multiply_route(operation: OperationRequest):
    return calculate("multiply", operation)


@app.post("/divide", response_model=OperationResponse, responses={400: {"model": ErrorResponse}})
async def divide_route(operation: OperationRequest):
    return calculate("divide", operation)
