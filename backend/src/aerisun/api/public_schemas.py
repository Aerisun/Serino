from __future__ import annotations

from pydantic import BaseModel, Field


class CommentImageUploadData(BaseModel):
    url: str = Field(description="Public URL of the uploaded image")


class CommentImageUploadResponse(BaseModel):
    errno: int = Field(default=0, description="Error number, 0 for success")
    data: CommentImageUploadData = Field(description="Upload result data containing the image URL")


class VisitBeaconIn(BaseModel):
    url: str = Field(min_length=1, max_length=2048, description="In-app URL (path + query) being viewed")
    referer: str | None = Field(default=None, max_length=2048, description="Document referrer, if any")
    screen: str | None = Field(default=None, max_length=16, description="Screen size as WIDTHxHEIGHT")
    language: str | None = Field(default=None, max_length=35, description="Navigator language")
    # Client-measured page load / route-transition time in ms (Performance API).
    # Kept permissive so an oversized value never rejects an otherwise-valid
    # beacon; the value is clamped to a sane range server-side.
    load_ms: int | None = Field(default=None, description="Client-measured page load time in milliseconds")


class VisitBeaconResponse(BaseModel):
    accepted: bool = Field(default=True, description="Whether the visit was queued for recording")
