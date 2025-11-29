"""Routes package."""

from .extract import router as extract_router
from .video_info import router as video_info_router
from .health import router as health_router
from .app import router as app_router

__all__ = [
    'extract_router',
    'video_info_router',
    'health_router',
    'app_router',
]
