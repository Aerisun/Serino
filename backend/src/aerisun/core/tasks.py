from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import delete

from aerisun.core.db import get_session_factory
from aerisun.domain.iam.models import AdminSession

logger = logging.getLogger(__name__)


async def cleanup_expired_sessions(interval_seconds: int = 3600) -> None:
    """Periodically delete expired admin sessions."""
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            session_factory = get_session_factory()
            with session_factory() as session:
                result = session.execute(
                    delete(AdminSession).where(
                        AdminSession.expires_at < datetime.now(UTC)
                    )
                )
                session.commit()
                if result.rowcount:
                    logger.info("Cleaned up %d expired sessions", result.rowcount)
        except Exception:
            logger.exception("Error cleaning expired sessions")
