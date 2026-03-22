from __future__ import annotations

from collections.abc import Callable

from fastapi import Request, Response
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from aerisun.core.db import get_engine
from aerisun.domain.ops.models import AuditLog


class AuditLogMiddleware(BaseHTTPMiddleware):
    """Automatically logs admin write operations (POST/PUT/DELETE) to the audit log."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Only audit admin write endpoints
        path = request.url.path
        method = request.method

        if not path.startswith("/api/v1/admin/") or method in (
            "GET",
            "OPTIONS",
            "HEAD",
        ):
            return await call_next(request)

        # Skip auth endpoints to avoid logging login/logout noise
        if "/auth/login" in path or "/auth/logout" in path:
            return await call_next(request)

        response = await call_next(request)

        # Only log successful operations
        if response.status_code < 400:
            try:
                # Extract action from method + path
                action = f"{method} {path}"

                # Extract target from path
                parts = path.replace("/api/v1/admin/", "").strip("/").split("/")
                target_type = parts[0] if parts else None
                target_id = parts[1] if len(parts) > 1 else None

                # Get admin user ID from auth header (if available)
                actor_id = None
                auth = request.headers.get("authorization", "")
                if auth.lower().startswith("bearer "):
                    token = auth[7:]
                    from aerisun.domain.iam.models import AdminSession

                    engine = get_engine()
                    with Session(engine) as db:
                        admin_session = (
                            db.query(AdminSession)
                            .filter(AdminSession.session_token == token)
                            .first()
                        )
                        if admin_session:
                            actor_id = admin_session.admin_user_id

                        log = AuditLog(
                            actor_type="admin",
                            actor_id=actor_id,
                            action=action,
                            target_type=target_type,
                            target_id=target_id,
                            payload={},
                        )
                        db.add(log)
                        db.commit()
            except Exception:
                pass  # Don't let audit logging break the request

        return response
