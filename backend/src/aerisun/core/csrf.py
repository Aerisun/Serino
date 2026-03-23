from __future__ import annotations

import re
from typing import ClassVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class OriginCheckMiddleware(BaseHTTPMiddleware):
    UNSAFE_METHODS: ClassVar[set[str]] = {"POST", "PUT", "DELETE", "PATCH"}
    _LOCALHOST_RE = re.compile(r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$")

    def __init__(self, app, allowed_origins: list[str], *, allow_any_localhost: bool = False) -> None:
        super().__init__(app)
        self.allowed_origins = set(allowed_origins)
        self.allow_any_localhost = allow_any_localhost

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method in self.UNSAFE_METHODS:
            origin = request.headers.get("origin")
            if origin is not None:
                if self.allow_any_localhost and self._LOCALHOST_RE.match(origin):
                    pass
                elif origin not in self.allowed_origins:
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "Origin not allowed"},
                    )
        return await call_next(request)
