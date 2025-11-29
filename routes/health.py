"""
API endpoints for health checks.
"""

from datetime import datetime
from fastapi import APIRouter

from models.responses import HealthResponse
from services.extractor import extractor

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    deps = extractor.check_dependencies()
    
    return HealthResponse(
        status="healthy" if all(deps.values()) else "unhealthy",
        timestamp=datetime.now().isoformat(),
        dependencies=deps
    )
