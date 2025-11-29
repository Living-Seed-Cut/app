"""Response models for the Livingseed Media Cut API."""

from typing import Optional, Dict
from pydantic import BaseModel


class JobStatus(BaseModel):
    """Job status response model."""
    
    job_id: str
    status: str
    progress: str
    created_at: str
    completed_at: Optional[str] = None
    cancelled_at: Optional[str] = None
    error: Optional[str] = None
    file_id: Optional[str] = None
    file_size: Optional[int] = None
    duration: Optional[float] = None
    percent: Optional[float] = None


class HealthResponse(BaseModel):
    """Health check response."""
    
    status: str
    timestamp: str
    dependencies: Dict[str, bool]


class VideoInfoResponse(BaseModel):
    """Video information response."""
    
    title: str
    duration: int
    uploader: str
    upload_date: str
    thumbnail: Optional[str] = None
