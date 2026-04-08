from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from aerisun.core.time import format_beijing_iso_datetime


class ModelBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @field_serializer("*", when_used="json", check_fields=False)
    def _serialize_datetime_fields(self, value: object) -> object:
        if isinstance(value, datetime):
            return format_beijing_iso_datetime(value)
        return value


class HealthRead(ModelBase):
    status: str = Field(description="Service health status")
    timestamp: datetime = Field(description="Current server timestamp")
