"""Global exception handlers that map domain exceptions to HTTP responses."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from aerisun.domain.exceptions import (
    AuthenticationFailed,
    DomainError,
    PayloadTooLarge,
    PermissionDenied,
    ResourceNotFound,
    StateConflict,
    ValidationError,
)

_STATUS_MAP: dict[type[DomainError], int] = {
    ResourceNotFound: 404,
    AuthenticationFailed: 401,
    PermissionDenied: 403,
    ValidationError: 422,
    StateConflict: 409,
    PayloadTooLarge: 413,
}


async def _domain_exception_handler(_request: Request, exc: DomainError) -> JSONResponse:
    status_code = _STATUS_MAP.get(type(exc), 400)
    return JSONResponse(status_code=status_code, content={"detail": exc.detail})


def register_exception_handlers(app: FastAPI) -> None:
    """Register the domain-exception → HTTP-response handler on *app*."""
    app.add_exception_handler(DomainError, _domain_exception_handler)
