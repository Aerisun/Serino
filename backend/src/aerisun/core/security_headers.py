from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from aerisun.core.settings import Settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, settings: Settings) -> None:
        super().__init__(app)
        waline_url = settings.waline_server_url
        self.is_production = settings.environment == "production"
        self.csp = "; ".join(
            [
                "default-src 'self'",
                f"script-src 'self' 'unsafe-inline' {waline_url}",
                "style-src 'self' 'unsafe-inline'",
                "img-src 'self' data: https: blob:",
                "font-src 'self' data:",
                f"connect-src 'self' {waline_url}",
                f"frame-src 'self' {waline_url}",
                "object-src 'none'",
                "base-uri 'self'",
                "form-action 'self'",
            ]
        )

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
        response.headers["Content-Security-Policy"] = self.csp
        if self.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        return response
