from __future__ import annotations

from datetime import UTC, datetime

from aerisun.core.schemas import ModelBase


class _SchemaProbe(ModelBase):
    name: str
    count: int
    created_at: datetime


def test_model_base_preserves_field_types_in_serialization_schema() -> None:
    properties = _SchemaProbe.model_json_schema(mode="serialization")["properties"]

    assert properties["name"]["type"] == "string"
    assert properties["count"]["type"] == "integer"
    assert properties["created_at"] == {
        "format": "date-time",
        "title": "Created At",
        "type": "string",
    }


def test_model_base_keeps_beijing_datetime_serialization() -> None:
    probe = _SchemaProbe(
        name="typed",
        count=1,
        created_at=datetime(2026, 8, 9, 5, 30, tzinfo=UTC),
    )

    assert probe.model_dump(mode="json")["created_at"] == "2026-08-09T13:30:00+08:00"
