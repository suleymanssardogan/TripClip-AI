"""Additive pagination contract; list keys remain client-compatible."""
from pydantic import BaseModel, Field


class PageResponse(BaseModel):
    total: int = Field(ge=0)
    limit: int = Field(default=20, ge=1, le=50)
    offset: int = Field(default=0, ge=0)
    has_more: bool = False
