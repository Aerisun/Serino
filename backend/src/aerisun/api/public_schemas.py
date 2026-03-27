from __future__ import annotations

from pydantic import BaseModel, Field


class CommentImageUploadData(BaseModel):
    url: str = Field(description="Public URL of the uploaded image")


class CommentImageUploadResponse(BaseModel):
    errno: int = Field(default=0, description="Error number, 0 for success")
    data: CommentImageUploadData = Field(description="Upload result data containing the image URL")
