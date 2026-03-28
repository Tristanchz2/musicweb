from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class TrackCreate(BaseModel):
    title: str
    artist: Optional[str] = None
    album: Optional[str] = None
    file_path: str
    format: Optional[str] = None
    duration_seconds: Optional[int] = None
    file_size: Optional[int] = None


class TrackResponse(BaseModel):
    id: int
    title: str
    artist: Optional[str] = None
    album: Optional[str] = None
    file_path: str
    format: Optional[str] = None
    duration_seconds: Optional[int] = None
    file_size: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True