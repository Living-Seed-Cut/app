"""Request models for the Livingseed Media Cut API."""

from typing import Optional
from urllib.parse import urlparse
from pydantic import BaseModel, validator, Field, root_validator


class ExtractionRequest(BaseModel):
    """Request model for audio extraction."""
    
    url: str = Field(..., description="YouTube video URL")
    start_time: Optional[str] = Field(None, description="Start time (HH:MM:SS, MM:SS, or seconds)")
    end_time: Optional[str] = Field(None, description="End time (HH:MM:SS, MM:SS, or seconds)")
    output_format: str = Field(default="mp3", description="Output audio format")
    filename: Optional[str] = Field(None, description="Custom filename (optional)")
    topic: Optional[str] = Field(None, description="Topic/sermon title (for MP3 metadata)")
    preacher: Optional[str] = Field(None, description="Preacher/speaker name (for MP3 metadata)")
    extract_full: bool = Field(default=False, description="Extract full audio; ignores start/end times when true")
    
    @validator('output_format')
    def validate_format(cls, v):
        allowed_formats = {'mp3', 'wav', 'mp4'}
        if v.lower() not in allowed_formats:
            raise ValueError(f'Format must be one of: {", ".join(allowed_formats)}')
        return v.lower()
    
    @validator('url')
    def validate_url(cls, v):
        try:
            parsed = urlparse(v)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError("Invalid URL format")
            return v
        except Exception:
            raise ValueError("Invalid URL")
    
    @validator('start_time', 'end_time', pre=True, always=False)
    def strip_whitespace(cls, v):
        if isinstance(v, str):
            return v.strip()
        return v

    @root_validator(pre=True)
    def validate_full_or_range(cls, values):
        # Normalize keys and default start_time
        extract_full = values.get('extract_full', False)
        start_time = values.get('start_time')
        end_time = values.get('end_time')

        if extract_full:
            # For full extraction, ignore times
            return values

        # Not full extraction -> require end_time; default start_time to 0:00 if missing/empty
        if end_time in (None, ""):
            raise ValueError("end_time is required unless extract_full is true")

        if start_time in (None, ""):
            values['start_time'] = '0:00'

        return values


class VideoInfoRequest(BaseModel):
    """Request model for video info endpoint."""
    
    url: str = Field(..., description="YouTube video URL")
    
    @validator('url')
    def validate_url(cls, v):
        try:
            parsed = urlparse(v)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError("Invalid URL format")
            return v
        except Exception:
            raise ValueError("Invalid URL")
