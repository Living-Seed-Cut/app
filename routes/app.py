"""
API endpoints for application management and statistics.
"""

import os
import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

import config
from services.extractor import extractor, job_storage, file_storage, cache_storage

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=dict)
async def root():
    """Root endpoint with API information."""
    return {
        "message": "YouTube Audio Snippet Extractor API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "health": "/health"
    }





@router.get("/stats")
async def get_stats():
    """Get API statistics."""
    total_jobs = len(job_storage)
    completed_jobs = sum(1 for job in job_storage.values() if job['status'] == 'completed')
    failed_jobs = sum(1 for job in job_storage.values() if job['status'] == 'failed')
    processing_jobs = sum(1 for job in job_storage.values() if job['status'] == 'processing')
    
    return {
        "total_jobs": total_jobs,
        "completed_jobs": completed_jobs,
        "failed_jobs": failed_jobs,
        "processing_jobs": processing_jobs,
        "stored_files": len(file_storage),
        "cached_files": len(cache_storage),
        "concurrent_jobs_limit": config.MAX_CONCURRENT_JOBS,
        "cache_enabled": config.CACHE_ENABLED,
        "ffmpeg_threads": config.FFMPEG_THREADS,
        "ytdl_concurrent_fragments": config.YTDL_CONCURRENT_FRAGMENTS,
        "uptime": datetime.now().isoformat()
    }


@router.post("/cleanup")
async def trigger_cleanup():
    """Manually trigger cleanup of old files and jobs."""
    try:
        extractor._perform_cleanup()
        return {
            "message": "Cleanup completed successfully",
            "files_remaining": len(file_storage),
            "jobs_remaining": len(job_storage)
        }
    except Exception as e:
        logger.error(f"Manual cleanup failed: {e}")
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")
