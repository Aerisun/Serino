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
from aerisun.domain.ops.user_agent import parse_user_agent
from aerisun.domain.ops.visit_tracking import classify_visit_path, compute_visitor_id, parse_referer, parse_utm

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
)


def _is_public_visit_candidate(request: Request) -> bool:
    if request.method != "GET":
        return False
    path = request.url.path or "/"
    if any(path.startswith(prefix) for prefix in _VISITOR_SKIP_PREFIXES):
        return False
    return classify_visit_path(path) == "page"


def get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        first = forwarded_for.split(",", 1)[0].strip()
        if first:
            return first
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "unknown"


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
        path = request.url.path or "/"
        visit_path_kind = classify_visit_path(path)
        should_track_visit = _is_public_visit_candidate(request)
        visited_at = shanghai_now()
        client_ip = get_client_ip(request) if should_track_visit else ""
        user_agent = request.headers.get("user-agent") if should_track_visit else None
        referer = request.headers.get("referer") if should_track_visit else None
        language = request.headers.get("accept-language") if should_track_visit else None
        query_string = request.url.query or None if should_track_visit else None
        ua_info = parse_user_agent(user_agent) if should_track_visit else None
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = rid
            duration_ms = round((time.perf_counter() - start) * 1000, 1)
            log = structlog.get_logger("aerisun.http")
            log.info(
                "request_completed",
                method=request.method,
                path=path,
                status=response.status_code,
                duration_ms=duration_ms,
            )
            if request.method == "GET" and visit_path_kind != "page":
                log.info(
                    "non_page_visit_recorded",
                    method=request.method,
                    path=path,
                    visit_path_kind=visit_path_kind,
                    status=response.status_code,
                    duration_ms=duration_ms,
                )
            if should_track_visit and ua_info is not None:
                try:
                    utm = parse_utm(query_string)
                    language_value = language.split(",", 1)[0].strip()[:35] if language else None
                    payload = VisitRecordPayload(
                        visited_at=visited_at,
                        path=request.url.path,
                        query=query_string[:512] if query_string else None,
                        ip_address=client_ip,
                        visitor_id=compute_visitor_id(client_ip, user_agent),
                        user_agent=user_agent,
                        referer=referer[:500] if referer else None,
                        referer_domain=parse_referer(referer, current_host=request.url.hostname),
                        status_code=response.status_code,
                        duration_ms=int(duration_ms),
                        is_bot=ua_info.is_bot,
                        browser=ua_info.browser,
                        browser_version=ua_info.browser_version,
                        os=ua_info.os,
                        os_version=ua_info.os_version,
                        device_type=ua_info.device_type,
                        language=language_value,
                        utm_source=utm.source,
                        utm_medium=utm.medium,
                        utm_campaign=utm.campaign,
                        utm_term=utm.term,
                        utm_content=utm.content,
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
