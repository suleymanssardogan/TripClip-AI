"""
Trip sharing DTO'ları — API request/response şemaları.
"""
from pydantic import BaseModel
from typing import Optional, List


class CreateShareRequest(BaseModel):
    role: str  # "viewer" | "editor"
    expires_at: Optional[str] = None  # ISO 8601, örn. "2026-09-01T00:00:00Z"
    max_uses: Optional[int] = None


class ShareResponse(BaseModel):
    share_id: int
    trip_id: int
    role: str
    status: str
    created_at: Optional[str]
    responded_at: Optional[str]
    expires_at: Optional[str]
    max_uses: Optional[int]
    use_count: int
    revoked: bool
    # Yalnızca oluşturma anındaki yanıtta dolu — bir daha asla geri alınamaz.
    token: Optional[str] = None
    share_url: Optional[str] = None


class ShareListResponse(BaseModel):
    shares: List[ShareResponse]


class SharePreviewResponse(BaseModel):
    """Kimlik doğrulama gerektirmez — davet linkini açan biri kabul etmeden
    önce neyi kabul edeceğini görür."""
    trip_title: str
    stops_count: int
    role: str


class AcceptShareRequest(BaseModel):
    token: str


class AcceptShareResponse(BaseModel):
    trip_id: int


class DeclineShareRequest(BaseModel):
    token: str


class CollaboratorResponse(BaseModel):
    user_id: int
    role: str
    joined_at: Optional[str]


class CollaboratorListResponse(BaseModel):
    collaborators: List[CollaboratorResponse]
