from __future__ import annotations

from urllib.parse import urlparse

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from aerisun.core.settings import Settings


def _build_source_list(*sources: str) -> str:
    return " ".join(source for source in dict.fromkeys(sources) if source)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, settings: Settings) -> None:
        super().__init__(app)
        waline_url = settings.waline_server_url.strip()
        parsed_waline_url = urlparse(waline_url)
        waline_origin = waline_url if parsed_waline_url.scheme and parsed_waline_url.netloc else ""
        script_sources = _build_source_list("'self'", waline_origin)
        connect_sources = _build_source_list("'self'", waline_origin)
        frame_sources = _build_source_list("'self'", waline_origin)
        self.is_production = settings.environment == "production"
        # style-src 保留 'unsafe-inline'：motion (framer-motion) 和 Waline 通过 JS
        # 动态创建 <style> 标签，CSP nonce 对此无效，移除会导致动画和评论样式全部失效。
        self.csp = "; ".join(
            [
                "default-src 'self'",
                f"script-src {script_sources}",
                "style-src 'self' 'unsafe-inline'",
                "img-src 'self' data: https: blob:",
                "font-src 'self' data:",
                f"connect-src {connect_sources}",
                f"frame-src {frame_sources}",
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
