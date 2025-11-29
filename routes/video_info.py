"""
API endpoints for video information.
"""

import logging
from fastapi import APIRouter, HTTPException

from models.requests import VideoInfoRequest
from models.responses import VideoInfoResponse
from services.extractor import extractor

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/video-info", response_model=VideoInfoResponse)
async def get_video_info_endpoint(request: VideoInfoRequest):
    """Get video information without starting extraction."""
    try:
        # Get video info
        video_info = await extractor.get_video_info(request.url)
        
        return VideoInfoResponse(
            title=video_info.get('title', 'Unknown'),
            duration=video_info.get('duration', 0),
            uploader=video_info.get('uploader', 'Unknown'),
            upload_date=video_info.get('upload_date', 'Unknown'),
            thumbnail=video_info.get('thumbnail')
        )
    except Exception as e:
        logger.error(f"Error getting video info: {e}")
        raise HTTPException(status_code=500, detail=str(e))
