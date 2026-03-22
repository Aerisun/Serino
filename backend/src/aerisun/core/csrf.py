from __future__ import annotations

from typing import ClassVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class OriginCheckMiddleware(BaseHTTPMiddleware):
    UNSAFE_METHODS: ClassVar[set[str]] = {"POST", "PUT", "DELETE", "PATCH"}

    def __init__(self, app, allowed_origins: list[str]) -> None:
        super().__init__(app)
        self.allowed_origins = set(allowed_origins)

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method in self.UNSAFE_METHODS:
            origin = request.headers.get("origin")
            if origin is not None and origin not in self.allowed_origins:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Origin not allowed"},
                )
        return await call_next(request)
