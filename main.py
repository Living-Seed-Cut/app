"""
Main FastAPI application entry point.
"""

import os
import time
import logging
import tempfile
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

import config
from services.extractor import extractor, file_storage
from routes import extract_router, video_info_router, health_router, app_router

# Configure logging
# Configure logging
handlers = [logging.StreamHandler()]
if config.LOG_TO_FILE:
    try:
        handlers.append(logging.FileHandler(config.LOG_FILE_NAME))
    except IOError as e:
        print(f"⚠️  Could not create log file: {e}")

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper()),
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=handlers
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting YouTube Audio Snippet Extractor API")
    
    # Create temp directory if it doesn't exist
    os.makedirs(config.TEMP_DIR, exist_ok=True)
    
    # Start automatic cleanup thread
    extractor.start_cleanup_thread()
    
    yield
    
    # Shutdown
    logger.info("Shutting down API")
    
    # Stop cleanup thread
    extractor.stop_cleanup_thread()
    
    # Clean up all remaining files (with timeout)
    cleanup_start = time.time()
    for file_info in list(file_storage.values()):  # Create a copy to avoid modification during iteration
        try:
            if os.path.exists(file_info['path']):
                os.remove(file_info['path'])
                logger.info(f"Cleaned up file on shutdown: {file_info['path']}")
        except Exception as e:
            logger.error(f"Failed to cleanup file: {e}")
        
        # Timeout after 3 seconds to prevent hanging
        if time.time() - cleanup_start > 3:
            logger.warning("File cleanup timeout, continuing shutdown...")
            break


app = FastAPI(
    title="YouTube Audio Snippet Extractor API",
    description="Extract audio snippets from YouTube videos with professional-grade reliability",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(app_router)
app.include_router(extract_router)
app.include_router(video_info_router)
app.include_router(health_router)


# Error handlers
@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """General exception handler."""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


if __name__ == "__main__":
    import argparse
    import uvicorn
    import sys
    
    parser = argparse.ArgumentParser(description='Living Seed Media YouTube Audio Snippet Extractor API')
    parser.add_argument('--host', default=config.HOST, help='Host to bind to')
    parser.add_argument('--port', type=int, default=config.PORT, help='Port to bind to')
    parser.add_argument('--reload', action='store_true', help='Enable auto-reload')
    parser.add_argument('--log-level', default=config.LOG_LEVEL, choices=['debug', 'info', 'warning', 'error'], help='Log level')
    
    args = parser.parse_args()
    
    # Update config from args
    config.HOST = args.host
    config.PORT = args.port
    config.RELOAD = args.reload or config.RELOAD
    config.LOG_LEVEL = args.log_level
    
    print(f"🚀 Starting YouTube Audio Snippet Extractor API")
    print(f"📍 Host: {config.HOST}")
    print(f"🔌 Port: {config.PORT}")
    print(f"🔄 Reload: {config.RELOAD}")
    print(f"📝 Log Level: {config.LOG_LEVEL}")
    print(f"🌐 API Documentation: http://{config.HOST}:{config.PORT}/docs")
    print(f"❤️  Health Check: http://{config.HOST}:{config.PORT}/health")
    
    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.RELOAD,
        log_level=config.LOG_LEVEL
    )
