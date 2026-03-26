from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from aerisun.core.base import Base, TimestampMixin, uuid_str


class Asset(Base, TimestampMixin):
    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    resource_key: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    visibility: Mapped[str] = mapped_column(String(32), nullable=False, default="internal")
    scope: Mapped[str] = mapped_column(String(32), nullable=False, default="user")
    category: Mapped[str] = mapped_column(String(80), nullable=False, default="general")
    note: Mapped[str | None] = mapped_column(String(500))
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(120))
    byte_size: Mapped[int | None] = mapped_column(Integer)
    sha256: Mapped[str | None] = mapped_column(String(128))
