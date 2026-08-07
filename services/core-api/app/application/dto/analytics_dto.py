"""
Analytics DTO'ları — API request/response şemaları.
"""
from pydantic import BaseModel
from typing import Any, Dict, Optional


class TrackEventRequest(BaseModel):
    event: str
    trip_id: int
    platform: str
    source: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
