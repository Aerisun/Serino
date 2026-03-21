"""Legacy compatibility import for the early api.v1 module layout.

The mounted runtime router lives in ``aerisun.api.public``. This module stays
as a thin alias so older imports keep resolving without maintaining a second
copy of the public API implementation.
"""

from __future__ import annotations

from aerisun.api.public import router

__all__ = ["router"]
