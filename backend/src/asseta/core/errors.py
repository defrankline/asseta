"""Structured error envelope and domain exception hierarchy."""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from asseta.core.correlation import get_correlation_id


class ErrorDetail(BaseModel):
    field: str | None = None
    issue: str


class ErrorBody(BaseModel):
    code: str
    message: str
    correlation_id: str
    details: list[ErrorDetail] = []


class ErrorEnvelope(BaseModel):
    error: ErrorBody


class AppError(Exception):
    status_code = 400
    code = "BAD_REQUEST"

    def __init__(self, message: str, details: list[ErrorDetail] | None = None, code: str | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or []
        if code:
            self.code = code


class NotAuthenticated(AppError):
    status_code = 401
    code = "NOT_AUTHENTICATED"


class PermissionDenied(AppError):
    status_code = 403
    code = "PERMISSION_DENIED"


class NotFound(AppError):
    status_code = 404
    code = "NOT_FOUND"


class Conflict(AppError):
    status_code = 409
    code = "CONFLICT"


class BusinessRuleViolation(AppError):
    status_code = 422
    code = "BUSINESS_RULE_VIOLATION"


class DependencyUnavailable(AppError):
    status_code = 503
    code = "DEPENDENCY_UNAVAILABLE"


def _envelope(status: int, code: str, message: str, details: list[ErrorDetail]) -> JSONResponse:
    body = ErrorEnvelope(
        error=ErrorBody(code=code, message=message, correlation_id=get_correlation_id(), details=details)
    )
    return JSONResponse(status_code=status, content=body.model_dump())


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return _envelope(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            ErrorDetail(
                field=".".join(str(p) for p in err.get("loc", ()) if p != "body") or None,
                issue=str(err.get("msg", "invalid")),
            )
            for err in exc.errors()
        ]
        return _envelope(422, "VALIDATION_FAILED", "Request validation failed", details)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        import structlog

        structlog.get_logger().exception("unhandled_error", error_type=type(exc).__name__)
        return _envelope(500, "INTERNAL_ERROR", "An unexpected error occurred", [])


ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    code: {"model": ErrorEnvelope} for code in (400, 401, 403, 404, 409, 422, 503)
}
