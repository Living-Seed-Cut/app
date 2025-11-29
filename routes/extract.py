"""
API endpoints for audio extraction jobs.
"""

import os
import uuid
import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from fastapi.responses import FileResponse

from models.requests import ExtractionRequest
from models.responses import JobStatus
from services.extractor import extractor, job_storage, file_storage

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/extract", response_model=dict)
async def create_extraction_job(request: ExtractionRequest, background_tasks: BackgroundTasks):
    """Create a new audio extraction job."""
    job_id = str(uuid.uuid4())
    
    # Initialize job
    job_storage[job_id] = {
        'job_id': job_id,
        'status': 'created',
        'progress': 'Job created',
        'percent': 0.0,
        'created_at': datetime.now().isoformat(),
        'request': request.dict()
    }
    
    # Add background task
    background_tasks.add_task(extractor.extract_snippet_async, job_id, request)
    
    logger.info(f"Created extraction job: {job_id}")
    
    return {
        "job_id": job_id,
        "status": "created",
        "message": "Extraction job created successfully",
        "status_url": f"/jobs/{job_id}",
        "download_url": f"/download/{job_id}"  # Will be available after completion
    }


@router.get("/jobs/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    """Get job status by ID."""
    if job_id not in job_storage:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = job_storage[job_id]
    return JobStatus(**job)


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    """Cancel a running job."""
    if job_id not in job_storage:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = job_storage[job_id]
    
    # Only allow cancellation of running jobs
    if job['status'] not in ['created', 'processing']:
        raise HTTPException(status_code=400, detail="Job cannot be cancelled in its current state")
    
    # Mark job as cancelled
    job['status'] = 'cancelled'
    job['progress'] = 'Cancelled by user'
    job['percent'] = 0.0
    job['cancelled_at'] = datetime.now().isoformat()
    
    logger.info(f"Job {job_id} cancelled by user")
    
    return {
        "job_id": job_id,
        "status": "cancelled",
        "message": "Job cancelled successfully"
    }


@router.get("/jobs", response_model=List[JobStatus])
async def list_jobs(limit: int = Query(10, ge=1, le=100)):
    """List recent jobs."""
    jobs = list(job_storage.values())
    # Sort by created_at descending
    jobs.sort(key=lambda x: x['created_at'], reverse=True)
    return [JobStatus(**job) for job in jobs[:limit]]


@router.get("/download/{job_id}")
async def download_file(job_id: str):
    """Download the extracted audio file."""
    if job_id not in job_storage:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = job_storage[job_id]
    
    if job['status'] != 'completed':
        raise HTTPException(status_code=400, detail=f"Job status: {job['status']}")
    
    file_id = job.get('file_id')
    if not file_id or file_id not in file_storage:
        raise HTTPException(status_code=404, detail="File not found")
    
    file_info = file_storage[file_id]
    
    if not os.path.exists(file_info['path']):
        raise HTTPException(status_code=410, detail="File no longer available")
    
    return FileResponse(
        path=file_info['path'],
        filename=file_info['filename'],
        media_type=file_info['mime_type']
    )


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete a job and its associated file."""
    if job_id not in job_storage:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = job_storage[job_id]
    
    # Delete associated file if exists
    file_id = job.get('file_id')
    if file_id and file_id in file_storage:
        file_info = file_storage[file_id]
        try:
            if os.path.exists(file_info['path']):
                os.remove(file_info['path'])
            del file_storage[file_id]
        except Exception as e:
            logger.error(f"Failed to delete file: {e}")
    
    # Delete job
    del job_storage[job_id]
    
    return {"message": "Job deleted successfully"}
