"""
FFmpeg utility module for hybrid FFmpeg path resolution.

This module provides a hybrid approach to locating FFmpeg:
1. First tries to use bundled FFmpeg from imageio-ffmpeg package
2. Falls back to system FFmpeg if available
3. Raises an error if neither is available

This eliminates the need for manual FFmpeg installation while maintaining
backward compatibility with existing system installations.
"""

import subprocess
import logging
from typing import Optional
from functools import lru_cache

logger = logging.getLogger(__name__)

# Cache the FFmpeg path for performance
_ffmpeg_path_cache: Optional[str] = None


@lru_cache(maxsize=1)
def get_ffmpeg_path() -> str:
    """
    Get the path to FFmpeg executable.
    
    Tries multiple sources in order:
    1. Bundled FFmpeg from imageio-ffmpeg package
    2. System FFmpeg from PATH
    
    Returns:
        str: Path to FFmpeg executable
        
    Raises:
        RuntimeError: If FFmpeg is not available from any source
    """
    global _ffmpeg_path_cache
    
    if _ffmpeg_path_cache:
        return _ffmpeg_path_cache
    
    # Try 1: Use bundled FFmpeg from imageio-ffmpeg
    try:
        import imageio_ffmpeg
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        
        # Verify the bundled FFmpeg works
        result = subprocess.run(
            [ffmpeg_path, '-version'],
            capture_output=True,
            timeout=5
        )
        
        if result.returncode == 0:
            logger.info(f"✅ Using bundled FFmpeg from imageio-ffmpeg: {ffmpeg_path}")
            _ffmpeg_path_cache = ffmpeg_path
            return ffmpeg_path
    except ImportError:
        logger.warning("imageio-ffmpeg not installed, trying system FFmpeg...")
    except Exception as e:
        logger.warning(f"Failed to use bundled FFmpeg: {e}, trying system FFmpeg...")
    
    # Try 2: Use system FFmpeg
    try:
        result = subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True,
            timeout=5
        )
        
        if result.returncode == 0:
            logger.info("✅ Using system FFmpeg from PATH")
            _ffmpeg_path_cache = 'ffmpeg'
            return 'ffmpeg'
    except FileNotFoundError:
        logger.error("System FFmpeg not found in PATH")
    except Exception as e:
        logger.error(f"Failed to use system FFmpeg: {e}")
    
    # No FFmpeg available
    raise RuntimeError(
        "FFmpeg is not available. Please install imageio-ffmpeg (pip install imageio-ffmpeg) "
        "or install FFmpeg manually from https://ffmpeg.org/download.html"
    )


def check_ffmpeg_available() -> bool:
    """
    Check if FFmpeg is available without raising an error.
    
    Returns:
        bool: True if FFmpeg is available, False otherwise
    """
    try:
        get_ffmpeg_path()
        return True
    except RuntimeError:
        return False


def get_ffmpeg_version() -> Optional[str]:
    """
    Get the version of the available FFmpeg.
    
    Returns:
        str: FFmpeg version string, or None if not available
    """
    try:
        ffmpeg_path = get_ffmpeg_path()
        result = subprocess.run(
            [ffmpeg_path, '-version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            # Extract version from first line
            first_line = result.stdout.split('\n')[0]
            return first_line
        
        return None
    except Exception as e:
        logger.error(f"Failed to get FFmpeg version: {e}")
        return None
