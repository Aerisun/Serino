"""Legacy compatibility import for the early api.v1 router path."""

from __future__ import annotations

from aerisun.api.router import api_router as api_v1_router

__all__ = ["api_v1_router"]
