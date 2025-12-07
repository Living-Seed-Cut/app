"""
Configuration module for Livingseed Media Cut application.
Centralizes all environment variables and application constants.
"""

import os
import tempfile
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# =============================================================================
# Server Configuration
# =============================================================================

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "5000"))
RELOAD = os.getenv("RELOAD", "false").lower() == "true"

LOG_LEVEL = os.getenv("LOG_LEVEL", "info")
LOG_TO_FILE = os.getenv("LOG_TO_FILE", "false").lower() == "true"
LOG_FILE_NAME = os.getenv("LOG_FILE_NAME", "audio_snippet_api.log")

# =============================================================================
# Cleanup Configuration
# =============================================================================

# Cleanup interval in seconds (default: 1 hour)
CLEANUP_INTERVAL = int(os.getenv("CLEANUP_INTERVAL", "3600"))

# File retention time in hours (default: 24 hours)
FILE_RETENTION_HOURS = int(os.getenv("FILE_RETENTION_HOURS", "24"))

# Maximum number of files to keep
MAX_FILES = int(os.getenv("MAX_FILES", "100"))

# =============================================================================
# Performance Optimization Configuration
# =============================================================================

# Maximum concurrent extraction jobs
MAX_CONCURRENT_JOBS = int(os.getenv("MAX_CONCURRENT_JOBS", "3"))

# Enable caching of downloaded audio files
CACHE_ENABLED = os.getenv("CACHE_ENABLED", "true").lower() == "true"

# Cache retention time in hours
CACHE_RETENTION_HOURS = int(os.getenv("CACHE_RETENTION_HOURS", "6"))

# FFmpeg thread count for processing
FFMPEG_THREADS = int(os.getenv("FFMPEG_THREADS", "4"))

# yt-dlp concurrent fragment downloads
YTDL_CONCURRENT_FRAGMENTS = int(os.getenv("YTDL_CONCURRENT_FRAGMENTS", "8"))

# =============================================================================
# Duration Limits (in seconds)
# =============================================================================

# Maximum video duration: 4 hours
MAX_VIDEO_DURATION = int(os.getenv("MAX_VIDEO_DURATION", "14400"))

# Maximum snippet duration: 4 hours
MAX_SNIPPET_DURATION = int(os.getenv("MAX_SNIPPET_DURATION", "14400"))

# =============================================================================
# Paths
# =============================================================================

# Temporary directory for file processing
TEMP_DIR = os.getenv("TEMP_DIR", tempfile.gettempdir())

# =============================================================================
# YouTube Configuration
# =============================================================================

# Optional proxy URL for YouTube requests
YOUTUBE_PROXY_URL = os.getenv("YOUTUBE_PROXY_URL")

# Path to YouTube cookies file (Netscape format)
YOUTUBE_COOKIES_PATH = os.getenv("YOUTUBE_COOKIES_PATH")

# Content of YouTube cookies file (Base64 encoded, optional)
YOUTUBE_COOKIES_CONTENT = os.getenv("YOUTUBE_COOKIES_CONTENT")

# Path to YouTube API OAuth credentials (pickle file)
YOUTUBE_API_TOKEN_FILE = os.getenv("YOUTUBE_API_TOKEN_FILE", "youtube_api_creds.pickle")

# Google OAuth Credentials (Base64 encoded content)
GOOGLE_CLIENT_SECRETS = os.getenv("GOOGLE_CLIENT_SECRETS")
GOOGLE_API_TOKEN = os.getenv("GOOGLE_API_TOKEN")

# YouTube Proof of Origin (PO) Token
# This is a cookie-less way to bypass bot detection.
# See: https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide
YOUTUBE_PO_TOKEN = os.getenv("YOUTUBE_PO_TOKEN")
YOUTUBE_VISITOR_DATA = os.getenv("YOUTUBE_VISITOR_DATA")

# =============================================================================
# Processing Configuration
# =============================================================================

# Default timeout for processing operations (in seconds)
PROCESSING_TIMEOUT = int(os.getenv("PROCESSING_TIMEOUT", "300"))

# Maximum output audio file size in MB (0 = no limit)
# Audio will be compressed to fit within this limit
MAX_OUTPUT_SIZE_MB = float(os.getenv("MAX_OUTPUT_SIZE_MB", "16"))
