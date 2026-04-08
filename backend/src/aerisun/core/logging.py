"""Structured logging configuration and request-ID middleware."""

from __future__ import annotations

import logging
import time
import uuid
from contextvars import ContextVar

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from aerisun.core.time import shanghai_now
from aerisun.domain.ops.service import VisitRecordPayload, enqueue_visit_record

# ---------------------------------------------------------------------------
# Context variable that holds the current request ID
# ---------------------------------------------------------------------------
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


# ---------------------------------------------------------------------------
# Logging bootstrap
# ---------------------------------------------------------------------------


def setup_logging(settings) -> None:
    """Configure *structlog* and bridge the stdlib :mod:`logging` into it.

    Parameters
    ----------
    settings:
        An instance of :class:`aerisun.core.settings.Settings`.  Only
        ``log_level``, ``log_format`` and ``environment`` are read.
    """

    is_dev = settings.log_format == "console" or (
        settings.log_format == "auto" and settings.environment == "development"
    )

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if is_dev:
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(settings.log_level.upper())


# ---------------------------------------------------------------------------
# Request-ID middleware
# ---------------------------------------------------------------------------


_VISITOR_SKIP_PREFIXES = (
    "/api",
    "/admin",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/media",
    "/health",
    "/favicon",
)
_VISITOR_SKIP_EXTENSIONS = (
    ".js",
    ".css",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".ico",
    ".webp",
    ".avif",
    ".map",
    ".json",
    ".txt",
    ".xml",
    ".woff",
    ".woff2",
    ".ttf",
)
_BOT_MARKERS = (
    "bot",
    "spider",
    "crawler",
    "curl",
    "wget",
    "headless",
    "python-requests",
    "httpx",
)


def _is_public_visit_candidate(request: Request) -> bool:
    if request.method != "GET":
        return False
    path = request.url.path or "/"
    if any(path.startswith(prefix) for prefix in _VISITOR_SKIP_PREFIXES):
        return False
    lowered = path.lower()
    return not lowered.endswith(_VISITOR_SKIP_EXTENSIONS)


def _get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        first = forwarded_for.split(",", 1)[0].strip()
        if first:
            return first
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "unknown"


def _is_bot_request(user_agent: str | None) -> bool:
    if not user_agent:
        return False
    lowered = user_agent.lower()
    return any(marker in lowered for marker in _BOT_MARKERS)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Assign a unique ID to every HTTP request.

    * Generates a UUID-4 per request.
    * Stores it in :data:`request_id_var` (a :class:`~contextvars.ContextVar`).
    * Binds it to *structlog*'s context so every log line includes ``request_id``.
    * Returns it as an ``X-Request-ID`` response header.
    * Logs request completion with duration and flags slow requests (>500ms).
    """

    SLOW_REQUEST_THRESHOLD_MS = 500

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        rid = uuid.uuid4().hex
        request_id_var.set(rid)
        structlog.contextvars.bind_contextvars(request_id=rid)
        start = time.perf_counter()
        should_track_visit = _is_public_visit_candidate(request)
        visited_at = shanghai_now()
        client_ip = _get_client_ip(request) if should_track_visit else ""
        user_agent = request.headers.get("user-agent") if should_track_visit else None
        referer = request.headers.get("referer") if should_track_visit else None
        is_bot = _is_bot_request(user_agent) if should_track_visit else False
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = rid
            duration_ms = round((time.perf_counter() - start) * 1000, 1)
            log = structlog.get_logger("aerisun.http")
            log.info(
                "request_completed",
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                duration_ms=duration_ms,
            )
            if should_track_visit:
                try:
                    payload = VisitRecordPayload(
                        visited_at=visited_at,
                        path=request.url.path,
                        ip_address=client_ip,
                        user_agent=user_agent,
                        referer=referer,
                        status_code=response.status_code,
                        duration_ms=int(duration_ms),
                        is_bot=is_bot,
                    )
                    enqueue_visit_record(payload)
                except Exception:
                    # Never fail the request due to visit tracking.
                    log.exception("visit_record_enqueue_failed", path=request.url.path)
            if duration_ms > self.SLOW_REQUEST_THRESHOLD_MS:
                log.warning(
                    "slow_request",
                    method=request.method,
                    path=request.url.path,
                    status=response.status_code,
                    duration_ms=duration_ms,
                )
            try:
                import sentry_sdk

                sentry_sdk.set_tag("request_id", rid)
            except ImportError:
                pass
            return response
        finally:
            structlog.contextvars.clear_contextvars()
